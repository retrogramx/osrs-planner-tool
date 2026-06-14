#!/usr/bin/env bash
# Self-host the 24 OSRS skill icons from the OSRS Wiki into ./skills/.
# Re-run any time to refresh. Source: oldschool.runescape.wiki
# (Game assets are Jagex IP — used here under fan-project terms; see app footer disclaimer.)
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p skills
UA="osrs-dashboard sprite fetch (personal project; aalvarez0295@gmail.com)"
WIKI="https://oldschool.runescape.wiki/images"

# 24 skills, incl. Sailing (the newest).
skills=(Attack Strength Defence Ranged Prayer Magic Runecraft Construction \
        Hitpoints Agility Herblore Thieving Crafting Fletching Slayer Hunter \
        Mining Smithing Fishing Cooking Firemaking Woodcutting Farming Sailing)

ok=0; fail=0
for s in "${skills[@]}"; do
  out="skills/$(echo "$s" | tr '[:upper:]' '[:lower:]').png"
  code=$(curl -sL -m 25 -A "$UA" -o "$out" -w "%{http_code}" "$WIKI/${s}_icon.png")
  sz=$(wc -c < "$out" 2>/dev/null | tr -d ' ')
  if [ "$code" = "200" ] && [ "${sz:-0}" -gt 200 ]; then
    printf "  ok   %-13s %5sb\n" "$s" "$sz"; ok=$((ok+1))
  else
    printf "  FAIL %-13s [%s, %sb]\n" "$s" "$code" "${sz:-0}"; rm -f "$out"; fail=$((fail+1))
  fi
done
echo "---- $ok ok, $fail failed ----"
