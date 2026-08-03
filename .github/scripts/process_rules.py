import sys
from pathlib import Path
import yaml
import json
from typing import TextIO
from datetime import datetime, timezone, timedelta

def generate_text_rules(rule: dict, group_dir: Path):

  rules = rule.get("rules")

  if not rules:
    return

  group_dir.mkdir(parents=True, exist_ok=True)

  write_text_rules(rule["name"], rules, group_dir / f"{rule['name']}.list")

def generate_json_rules(rule: dict, group_dir: Path):

  rules = rule.get("rules")

  if not rules:
    return

  group_dir.mkdir(parents=True, exist_ok=True)

  write_json_rules(rules, group_dir / f"{rule['name']}.json")

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

def extract_json_rules(group_dir: Path) -> dict[str, list[str]]:

  json_rules = {}

  for json_f in group_dir.iterdir():

    if json_f.suffix == ".json":

      with json_f.open("r", encoding="utf-8") as f:

        data = json.load(f)

      for item in data.get("rules", []):

        for key, values in item.items():

          if key not in json_rules:

            json_rules[key] = []

          json_rules[key].extend(values)

  return json_rules

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

def exclude_json_rules(json_rules: dict[str, list[str]], excludes: dict[str, list[str]]) -> dict[str, list[str]]:

  if not excludes:
    return json_rules

  result = {}

  exclude_sets = {key: set(values) for key, values in excludes.items()}

  for key, values in json_rules.items():

    if key not in exclude_sets:
      result[key] = values
      continue

    remaining = [value for value in values if value not in exclude_sets[key]]

    if remaining:
      result[key] = remaining

  return result

def include_json_rules(json_rules: dict[str, list[str]], includes: dict[str, list[str]]) -> dict[str, list[str]]:

  if not includes:
    return json_rules

  for key, values in includes.items():

    if key not in json_rules:

      json_rules[key] = []

    json_rules[key].extend(values)

  return json_rules

def normalize_text_rules(text_rules: list[str]) -> list[str]:

  return sorted(set(text_rules))

def normalize_json_rules(json_rules: dict[str, list[str]]) -> dict[str, list[str]]:

  for key, values in json_rules.items():

    json_rules[key] = sorted(set(values))

  return json_rules

def write_rule_metadata(rule_name: str, rule_count: int, file: TextIO):

  now = datetime.now(timezone(timedelta(hours=8)))

  file.write(
    f"# Rule Name: {rule_name}\n"
    f"# Total Rules: {rule_count}\n"
    f"# Generated At: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC+08:00\n"
    "\n"
  )

def write_text_rules(rule_name: str, rules: list[str], file: Path):

  with file.open("w", encoding="utf-8") as f:

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

def write_json_rules(rules: dict[str, list[str]], file: Path):

  data = {
    "version": 5,
    "rules": [
      rules
    ]
  }

  with file.open("w", encoding="utf-8") as f:

    json.dump(
      data,
      f,
      ensure_ascii=False,
      indent=2
    )

def process_rules(client: str, manifest_f: Path, source_dir: Path, merged_dir: Path):

  with manifest_f.open("r", encoding="utf-8") as f:

    manifest_data = yaml.safe_load(f)

  global_data = manifest_data.get("global", {})

  global_excludes = global_data.get("excludes", {})
  global_includes = global_data.get("includes", {})

  for rule in manifest_data.get("rules", []):

    rule_name = rule.get("name", "")

    group_dir = (source_dir / rule_name)

    if client in ["mihomo", "surge"]:

      generate_text_rules(rule, group_dir)

      text_rules = extract_text_rules(group_dir)

      rule_type = rule.get("type", "")

      type_excludes = global_excludes.get(rule_type, [])
      type_includes = global_includes.get(rule_type, [])

      rule_excludes = rule.get("excludes", [])
      rule_includes = rule.get("includes", [])

      excludes = merge_list(type_excludes, rule_excludes)
      includes = merge_list(type_includes, rule_includes)

      text_rules = exclude_text_rules(text_rules, excludes)
      text_rules = include_text_rules(text_rules, includes)

      text_rules = normalize_text_rules(text_rules)

      write_text_rules(rule_name, text_rules, merged_dir / f"{rule_name}.list")

    elif client == "sing-box":

      generate_json_rules(rule, group_dir)

      json_rules = extract_json_rules(group_dir)

      rule_excludes = rule.get("excludes", {})
      rule_includes = rule.get("includes", {})

      excludes = merge_dict(global_excludes, rule_excludes)
      includes = merge_dict(global_includes, rule_includes)

      json_rules = exclude_json_rules(json_rules, excludes)
      json_rules = include_json_rules(json_rules, includes)

      json_rules = normalize_json_rules(json_rules)

      write_json_rules(json_rules, merged_dir / f"{rule_name}.json")

def main():

  client = sys.argv[1]

  manifest_f = Path(sys.argv[2])
  source_dir = Path(sys.argv[3])
  merged_dir = Path(sys.argv[4])

  process_rules(client, manifest_f, source_dir, merged_dir)

if __name__ == "__main__":
  main()
