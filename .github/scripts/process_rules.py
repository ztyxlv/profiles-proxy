# download remote rules --> source_dir
# generate inline rules --> source_dir
#         |
#         v
# extract_text_rules() --> list[str]
# extract_yaml_rules() --> list[str]
# extract_json_rules() +--> normalize_json_rules() --> list[dict[str, Any]
#         |
#         v
# excldue_text_rules() --> list[str]
# normalize_json_rules(excludes) +--> exclude_json_rules() --> list[dict[str, Any]
#         |
#         v
# incldue_text_rules() --> list[str]
# normalize_json_rules(includes) +--> include_json_rules() --> list[dict[str, Any]
#         |
#         v
# merge_text_rules() +--> deduplicate & sort --> list[str]
# merge_json_rules() +--> deduplicate & sort --> list[dict[str, Any]
#         |
#         v
# write_text_rules() --> merged_dir
# write_yaml_rules() --> merged_dir
# weire_json_rules() --> merged_dir

import sys
from pathlib import Path
import yaml
import json
from typing import Any
from typing import TextIO
from datetime import datetime, timezone, timedelta

FIELD_GROUPS = {
  "domain": "dst-net",
  "domain_suffix": "dst-net",
  "domain_keyword": "dst-net",
  "domain_regex": "dst-net",
  "geosite": "dst-net",
  "geoip": "dst-net",
  "ip_cidr": "dst-net",
  "ip_is_private": "dst-net",

  "port": "dst-port",
  "port_range": "dst-port",

  "source_geoip": "src-ip",
  "source_ip_cidr": "src-ip",
  "source_ip_is_private": "src-ip",

  "source_port": "src_port",
  "source_port_range": "src_port",

  "network": "network"
}

SCALAR_FIELDS = {
  "ip_version",
  "source_ip_is_private",
  "ip_is_private",
  "clash_mode",
  "network_is_expensive",
  "network_is_constrained",
  "invert",
  "action",
  "outbound"
}

def extract_text_rules(group_dir: Path) -> list[str]:

  text_rules = []

  for rule_f in group_dir.iterdir():

    if rule_f.suffix in [".list", ".conf", ".txt"]:
      with rule_f.open("r", encoding="utf-8") as f:

        for line in f:

          line = line.strip()

          if not line or line.startswith("#"):
            continue

          text_rules.append(line)

    elif rule_f.suffix == ".yaml":

      with rule_f.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

      for item in data.get("payload", []):
        text_rules.append(item)

  return text_rules

def merge_list(first: list[str], second: list[str]) -> list[str]:

  return first + second

def merge_dict(first: dict[str, list[str]], second: dict[str, list[str]]) -> dict[str, list[str]]:

  result = {key: list(values) for key, values in first.items()}

  for key, values in second.items():

    result.setdefault(key, [])

    result[key].extend(values)

  return result

def exclude_text_rules(text_rules: list[str], excludes: list[str]) -> list[str]:

  if not excludes:
    return text_rules

  exclude_set = set(excludes)

  return [rule for rule in text_rules if rule not in exclude_set]

def include_text_rules(text_rules: list[str], includes: list[str]) -> list[str]:

  if not includes:
    return text_rules

  return text_rules + includes

def normalize_text_rules(text_rules: list[str]) -> list[str]:

  return sorted(set(text_rules))

def extract_json_rules(group_dir: Path) -> list[dict[str, Any]]:

  json_rules = []

  for rule_f in group_dir.glob("*.json"):

    with rule_f.open("r", encoding="utf-8") as f:
      data = json.load(f)

    json_rules.extend(data.get("rules", []))

  return json_rules

def normalize_json_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:

  result = []

  for rule in rules:

    new_rule = {}

    for key, value in rule.items():

      if key in SCALAR_FIELDS:
          new_rule[key] = value
      else:
          new_rule[key] = value if isinstance(value, list) else [value]

    result.append(new_rule)

  return result

def get_rule_signature(rule: dict[str, Any]) -> tuple[str, ...]:

  return tuple(sorted({FIELD_GROUPS.get(field, field) for field in rule}))

def exclude_json_rules(rules: list[dict], excludes: list[dict]) -> list[dict]:

  if not excludes:
    return rules

  prepared_excludes = [
    (
      get_rule_signature(exclude),
      {
        key: set(values)
        for key, values in exclude.items()
      }
    )
    for exclude in excludes
  ]

  result = []

  for rule in rules:

    new_rule = {key: list(values) for key, values in rule.items()}

    rule_signature = get_rule_signature(rule)

    for exclude_signature, exclude_values in prepared_excludes:

      if rule_signature != exclude_signature:
        continue

      for key, values in exclude_values.items():

        if key not in new_rule:
          continue

        new_rule[key] = [value for value in new_rule[key] if value not in values]

        if not new_rule[key]:
          del new_rule[key]

    if new_rule:
      result.append(new_rule)

  return result

def include_json_rules(rules: list[dict], includes: list[dict]) -> list[dict]:

  if not includes:
    return rules

  return rules + includes

def merge_json_rules(json_rules: list[dict]) -> list[dict]:

  merged = {}

  for rule in json_rules:

    signature = get_rule_signature(rule)

    if signature not in merged:

      merged[signature] = {key: list(value) if isinstance(value, list) else value for key, value in rule.items()}

      continue

    target = merged[signature]

    for key, value in rule.items():

      if key not in target:

        target[key] = value

      elif isinstance(value, list):

        target[key].extend(value)

      elif target[key] != value:

        target[key] = value

  for rule in merged.values():

    for key, value in rule.items():

      if isinstance(value, list):

        rule[key] = sorted(set(value))

  return list(merged.values())

def write_rule_metadata(rule_name: str, rule_count: int, output_f: TextIO):

  now = datetime.now(timezone(timedelta(hours=8)))

  output_f.write(
    f"# Rule Name: {rule_name}\n"
    f"# Total Rules: {rule_count}\n"
    f"# Generated At: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC+08:00\n"
    "\n"
  )

def write_text_rules(rule_name: str, rules: list[str], output_f: Path):

  with output_f.open("w", encoding="utf-8") as f:

    write_rule_metadata(rule_name, len(rules), f)

    for rule in rules:

      f.write(rule + "\n")

class IndentDumper(yaml.SafeDumper):
  def increase_indent(self, flow=False, indentless=False):
    return super().increase_indent(flow=False, indentless=False)

def write_yaml_rules(rule_name: str, rules: list[str], file: Path):

  data = {
    "payload": rules
  }

  with file.open("w", encoding="utf-8") as f:

    write_rule_metadata(rule_name, len(rules), f)

    yaml.dump(
      data,
      f,
      Dumper=IndentDumper,
      allow_unicode=True,
      sort_keys=False,
      indent=2
    )

def write_json_rules(rules: list[dict[str, Any]], output_f: Path):

  data = {
    "version": 5,
    "rules": rules
  }

  with output_f.open("w", encoding="utf-8") as f:

    json.dump(
      data,
      f,
      ensure_ascii=False,
      indent=2
    )

def generate_rules(client: str, manifest_f: Path, source_dir: Path):

  with manifest_f.open("r", encoding="utf-8") as f:
    manifest_d = yaml.safe_load(f) 

  for rule in manifest_d.get("rules", []):
    rule_name = rule.get("name")
    rules = rule.get("rules")

    if not rules:
      continue

    if client in ["mihomo", "surge"]:

      output_f = source_dir / rule_name / f"{rule_name}.list"

      output_f.parent.mkdir(parents=True, exist_ok=True)

      write_text_rules(rule_name, rules, output_f)

    elif client == "sing-box":

      output_f = source_dir / rule_name / f"{rule_name}.json"

      output_f.parent.mkdir(parents=True, exist_ok=True)

      write_json_rules(rules, output_f)

def process_rules(client: str, manifest_f: Path, source_dir: Path, merged_dir: Path):

  with manifest_f.open("r", encoding="utf-8") as f:

    manifest_d = yaml.safe_load(f)

  global_data = manifest_d.get("global", {})

  for rule in manifest_d.get("rules", []):

    rule_name = rule.get("name", "")

    group_dir = (source_dir / rule_name)

    if client in ["mihomo", "surge"]:

      text_rules = extract_text_rules(group_dir)

      rule_type = rule.get("type", "")

      global_excludes = global_data.get("excludes", {})
      global_includes = global_data.get("includes", {})

      print(type(global_excludes))
      print(global_excludes)

      print(type(global_includes))
      print(global_includes)

      type_excludes = global_excludes.get(rule_type, [])
      type_includes = global_includes.get(rule_type, [])

      rule_excludes = rule.get("excludes", [])
      rule_includes = rule.get("includes", [])

      excludes = merge_list(type_excludes, rule_excludes)
      includes = merge_list(type_includes, rule_includes)

      text_rules = exclude_text_rules(text_rules, excludes)
      text_rules = include_text_rules(text_rules, includes)

      text_rules = normalize_text_rules(text_rules)

      output_f = merged_dir / f"{rule_name}.list"

      write_text_rules(rule_name, text_rules, output_f)

    elif client == "sing-box":

      json_rules = extract_json_rules(group_dir)

      json_rules = normalize_json_rules(json_rules)

      global_excludes = global_data.get("excludes", [])
      global_includes = global_data.get("includes", [])

      rule_excludes = rule.get("excludes", [])
      rule_includes = rule.get("includes", [])

      excludes = global_excludes + rule_excludes
      includes = global_includes + rule_includes

      excludes = normalize_json_rules(excludes)
      includes = normalize_json_rules(includes)

      json_rules = exclude_json_rules(json_rules, excludes)
      json_rules = include_json_rules(json_rules, includes)

      json_rules = merge_json_rules(json_rules)

      output_f = merged_dir / f"{rule_name}.json"

      write_json_rules(json_rules, output_f)

def main():

  client = sys.argv[1]

  manifest_f = Path(sys.argv[2])
  source_dir = Path(sys.argv[3])
  merged_dir = Path(sys.argv[4])

  generate_rules(client, manifest_f, source_dir)
  process_rules(client, manifest_f, source_dir, merged_dir)

if __name__ == "__main__":
  main()
