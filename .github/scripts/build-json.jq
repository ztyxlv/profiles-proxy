def exclude_rules(exc):
  reduce exc[] as $e (.;
    reduce ($e | to_entries[]) as $i (.;
      if has($i.key) then
        if ($i.value | type) == "array" then
          .[$i.key] -= $i.value
          | if (.[$i.key] | length) == 0 then del(.[$i.key]) else . end
        else
          if .[$i.key] == $i.value then del(.[$i.key]) else . end
        end
      else . end
    )
  );

def aggregate_rules:
  reduce .[] as $r ({};
    reduce ($r | to_entries[]) as $e (.;
      if ($e.value | type) == "array" then
        .[$e.key] = ((.[$e.key] // []) + $e.value)
      else
        .[$e.key] = $e.value
      end
    )
  )
  | with_entries(
      if (.value | type) == "array" then
        .value |= (unique | sort)
      else . end
    );

($ruleset[0] | map(exclude_rules($exclude))) as $filtered
| ($filtered + $include) as $all
| {
    version: 5,
    rules: (if ($all | length) == 0 then [] else [$all | aggregate_rules] end)
  }
