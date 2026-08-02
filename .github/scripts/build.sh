#!/usr/bin/env bash

set -euo pipefail

install_jq() {
  command -v jq &>/dev/null && return

  sudo curl -fsSL https://github.com/jqlang/jq/releases/latest/download/jq-linux-amd64 -o /usr/local/bin/jq
  sudo chmod +x /usr/local/bin/jq
}

install_yq() {
  command -v yq &>/dev/null && return

  sudo curl -fsSL https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -o /usr/local/bin/yq
  sudo chmod +x /usr/local/bin/yq
}

install_resvg() {
  command -v resvg &>/dev/null && return

  local url

  url=$(curl -fsSL https://api.github.com/repos/linebender/resvg/releases/latest \
    | jq -r '.assets[] | select(.name | test("resvg-linux-x86_64.tar.gz")) | .browser_download_url')

  curl -fsSL "$url" \
    | sudo tar -xz -C /usr/local/bin
}

install_mihomo() {
  command -v mihomo &>/dev/null && return

  local url

  url=$(curl -fsSL https://api.github.com/repos/MetaCubeX/mihomo/releases \
    | jq -r '.[] | select(.prerelease == true) | .assets[] | select(.name | test("mihomo-linux-amd64-v3-alpha-.*\\.gz")) | .browser_download_url' \
    | head -n1)

  curl -fsSL "$url" \
    | gunzip -c \
    | sudo install -m 755 /dev/stdin /usr/local/bin/mihomo
}

install_sing-box() {
  command -v sing-box &>/dev/null && return

  local url

  url=$(curl -fsSL https://api.github.com/repos/SagerNet/sing-box/releases \
    | jq -r '.[] | select(.prerelease == true) | .assets[] | select(.name | test("sing-box-.*-alpha.*-linux-amd64\\.tar\\.gz")) | .browser_download_url' \
    | head -n1)

  curl -fsSL "$url" \
    | sudo tar -xz -C /usr/local/bin --strip-components=1 --wildcards "*/sing-box"
}

install_tools() {
  local target="$1"
  local client="${2:-}"

  install_jq
  install_yq

  case "$target" in
    icons)
      install_resvg
      ;;
    rules)
      case "$client" in
        mihomo)
          install_mihomo
          ;;
        sing-box)
          install_sing-box
          ;;
        surge)
          ;;
      esac
      ;;
  esac
}

reset_icons_dir() {
  rm -rf icons/{svg,png}
  mkdir -p icons/{svg,png}/{services,policies,flags}
}

reset_rules_dir() {
  local client="$1"

  rm -rf rules/"$client"/{source,merged,compiled}

  case "$client" in
    mihomo|sing-box)
      mkdir -p rules/"$client"/{source,merged,compiled}
      ;;
    surge)
      mkdir -p rules/"$client"/{source,merged}
      ;;
  esac  
}

download_icons() {
  local manifest_f="$1"
  local svg_dir="$2"

  # shellcheck disable=SC2016
  yq -r '.icons[] | select(.url) | [.name, .category, .url] | @tsv' "$manifest_f" \
    | xargs -n3 -P10 sh -c 'curl -fsSL "$3" --create-dirs -o "'"$svg_dir"'/$2/$1.svg"' _
}

download_rules() {
  local manifest_f="$1"
  local source_dir="$2"

  # shellcheck disable=SC2016
  yq -r '.rules[] | select(.rulesets) | .name as $group | .rulesets[] | [$group, .name, .url] | @tsv' "$manifest_f" \
    | xargs -n3 -P10 sh -c 'curl -fsSL "$3" --create-dirs -o "'"$source_dir"'/$1/$2.${3##*.}"' _
}

convert_icons() {
  local manifest_f="$1"
  local svg_dir="$2"
  local png_dir="$3"

  # shellcheck disable=SC2016
  yq -r '.icons[] | select(.url) | [.name, .category] | @tsv' "$manifest_f" \
    | xargs -n2 -P10 sh -c 'resvg -w 64 "'"$svg_dir"'/$2/$1.svg" "'"$png_dir"'/$2/$1.png"' _
}

compile_mihomo_rules() {
  local manifest_f="$1"
  local merged_dir="$2"
  local compiled_dir="$3"

  while IFS=$'\t' read -r name type; do
    local merged_f="$merged_dir/$name.yaml"
    local compiled_f="$compiled_dir/$name.mrs"

    case "$type" in
      domain|ipcidr)
        [[ -f "$merged_f" ]] || continue
        mihomo convert-ruleset "$type" yaml "$merged_f" "$compiled_f"
        ;;
      classical)
        ;;
    esac
  done < <(yq -r '.rules[] | [.name, .type] | @tsv' "$manifest_f")
}

compile_singbox_rules() {
  local manifest_f="$1"
  local merged_dir="$2"
  local compiled_dir="$3"

  while IFS=$'\t' read -r name; do
    local merged_f="$merged_dir/$name.json"
    local compiled_f="$compiled_dir/$name.srs"

    [[ -f "$merged_f" ]] || continue
    sing-box rule-set compile "$merged_f" -o "$compiled_f"
  done < <(yq -r '.rules[].name' "$manifest_f")
}

compile_rules() {
  local client="$1"
  local manifest_f="$2"
  local merged_dir="$3"
  local compiled_dir="$4"

  case "$client" in
    mihomo)
      compile_mihomo_rules "$manifest_f" "$merged_dir" "$compiled_dir"
      ;;
    sing-box)
      compile_singbox_rules "$manifest_f" "$merged_dir" "$compiled_dir"
      ;;
    surge)
      ;;
  esac
}

build_icons() {
  local manifest_f="icons/manifest.yaml"
  local svg_dir="icons/svg"
  local png_dir="icons/png"

  install_tools icons
  reset_icons_dir
  download_icons "$manifest_f" "$svg_dir"
  convert_icons "$manifest_f" "$svg_dir" "$png_dir"
}

build_rules() {
  local client="$1"
  local manifest_f="rules/$client/manifest.yaml"
  local source_dir="rules/$client/source"
  local merged_dir="rules/$client/merged"
  local compiled_dir="rules/$client/compiled"

  install_tools rules "$client"
  reset_rules_dir "$client"
  download_rules "$manifest_f" "$source_dir"
  python3 .github/scripts/process_rules.py "$client" "$manifest_f" "$source_dir" "$merged_dir"
  compile_rules "$client" "$manifest_f" "$merged_dir" "$compiled_dir"
}

sync_changes() {
  local path="$1"

  git config user.name "github-actions[bot]"
  git config user.email "github-actions[bot]@users.noreply.github.com"

  git add "$path"

  if ! git diff --cached --quiet; then
    git commit -m "Updated on $(TZ=Asia/Shanghai date '+%F at %T')"
    git pull --rebase
    git push
  fi
}

main() {
  local target="$1"
  local client="${2:-}"

  case "$target" in
    icons)
      build_icons
      ;;
    rules)
      build_rules "$client"
      ;;
  esac
}

main "$@"
