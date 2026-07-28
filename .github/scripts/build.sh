#!/usr/bin/env bash
set -euo pipefail

install_yq() {
  sudo curl -fsSL \
    https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 \
    -o /usr/local/bin/yq
  sudo chmod +x /usr/local/bin/yq
}

install_jq() {
  sudo curl -fsSL \
    https://github.com/jqlang/jq/releases/latest/download/jq-linux-amd64 \
    -o /usr/local/bin/jq
  sudo chmod +x /usr/local/bin/jq
}

install_mihomo() {
  local url

  url=$(curl -fsSL https://api.github.com/repos/MetaCubeX/mihomo/releases/latest \
    | jq -r '.assets[] | select(.name | test("mihomo-linux-amd64-v3-v.*\\.gz$")) | .browser_download_url')

  curl -fsSL "$url" \
    | gunzip -c > /tmp/mihomo

  sudo mv /tmp/mihomo /usr/local/bin/mihomo
  sudo chmod +x /usr/local/bin/mihomo
}

install_singbox() {
  local tmp url

  tmp=$(mktemp -d)

  url=$(curl -fsSL https://api.github.com/repos/SagerNet/sing-box/releases/latest \
    | jq -r '.assets[] | select(.name | test("sing-box-[0-9.]+-linux-amd64\\.tar\\.gz$")) | .browser_download_url')

  curl -fsSL "$url" \
    | tar -xz -C "$tmp"

  sudo mv "$tmp"/sing-box*/sing-box /usr/local/bin/sing-box
  sudo chmod +x /usr/local/bin/sing-box

  rm -rf "$tmp"
}

install_deps() {
  local client="$1"

  install_yq

  case "$client" in
    mihomo)
      install_jq
      install_mihomo
      ;;
    sing-box)
      install_jq
      install_singbox
      ;;
    surge)
      ;;
    *)
      exit 1
      ;;
  esac
}

init_rule_dirs() {
  local client="$1"

  case "$client" in
    mihomo|sing-box)
      rm -rf "$client/rules"/{source,merged,compiled}
      mkdir -p "$client/rules"/{source,merged,compiled}
      ;;
    surge)
      rm -rf "$client/rules"/{source,merged}
      mkdir -p "$client/rules"/{source,merged}
      ;;
    *)
      exit 1
      ;;
  esac
}

# download_rules() {
#   local manifest="$1"
#   local source_dir="$2"

#   # shellcheck disable=SC2016
#   yq -r '.rules[] | select(.ruleset) | .name + " " + (.ruleset[])' "$manifest" \
#     | xargs -n2 -P10 sh -c 'curl -fsSL "$2" --create-dirs -o "'"$source_dir"'/$1/${2##*/}"' sh
# }

download_rules() {
  local manifest="$1"
  local source_dir="$2"

  yq -r '.rules[] | select(.ruleset) | .name + "\t" + (.ruleset[])' "$manifest" |
  while IFS=$'\t' read -r name url; do

    dir="$source_dir/$name"
    mkdir -p "$dir"

    filename="${url##*/}"
    filepath="$dir/$filename"

    if [ -e "$filepath" ]; then
      base="${filename%.*}"
      ext="${filename##*.}"
      i=1

      while [ -e "$dir/${base}-${i}.${ext}" ]; do
        i=$((i + 1))
      done

      filepath="$dir/${base}_${i}.${ext}"
    fi

    curl -fsSL "$url" -o "$filepath"

  done
}

extract_rules() {
  local rule="$1"
  local file="$2"

  if compgen -G "$rule/*.list" > /dev/null; then
    grep -hvE '^[[:space:]]*(#|$)' "$rule"/*.list >> "$file"
  fi

  if compgen -G "$rule/*.conf" > /dev/null; then
    grep -hvE '^[[:space:]]*(#|$)' "$rule"/*.conf >> "$file"
  fi

  if compgen -G "$rule/*.yaml" > /dev/null; then
    yq eval-all '.payload[]' "$rule"/*.yaml >> "$file"
  fi
}

exclude_rules() {
  local manifest="$1"
  local name="$2"
  local file="$3"

  local temp
  temp=$(mktemp)

  local exclude
  exclude=$(yq -r ".rules[] | select(.name == \"$name\") | .exclude[]?" "$manifest")

  if [ -n "$exclude" ]; then
    printf '%s\n' "$exclude" | grep -vxFf - "$file" > "$temp"
    mv "$temp" "$file"
  fi
}

include_rules() {
  local manifest="$1"
  local name="$2"
  local file="$3"

  yq -r ".rules[] | select(.name == \"$name\") | .include[]?" "$manifest" >> "$file"
}

sort_rules() {
  local file="$1"

  LC_ALL=C sort -u "$file" -o "$file"
}

sync_rules() {
  local path="$1"

  git config user.name "github-actions[bot]"
  git config user.email "github-actions[bot]@users.noreply.github.com"

  git add "$path"
  git add -f "$path/source"

  if ! git diff --cached --quiet; then
    git commit -m "Updated on $(TZ=Asia/Shanghai date '+%F at %T')"
    git pull --rebase
    git push
  fi
}
