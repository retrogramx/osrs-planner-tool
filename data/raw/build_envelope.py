import json, importlib.util, datetime, re

spec=importlib.util.spec_from_file_location('ph','data/raw/parse_html.py')
ph=importlib.util.module_from_spec(spec); spec.loader.exec_module(ph)
mani=ph.manifest

ACCESSED=datetime.date.today().isoformat()

# Universe definition for completeness
SKILLS_23=["Attack","Strength","Defence","Ranged","Prayer","Magic","Runecraft","Construction",
 "Hitpoints","Agility","Herblore","Thieving","Crafting","Fletching","Slayer","Hunter",
 "Mining","Smithing","Fishing","Cooking","Firemaking","Woodcutting","Farming"]
# Note: Melee guides cover Attack/Strength/Defence collectively.

FAMILIES=["main","f2p","ironman"]

# cost_basis by family per domain rules
def cost_basis(fam):
    if fam=="main": return "ge"
    if fam=="ironman": return "gather/sawmill"
    if fam=="f2p": return "ge"  # f2p mains use GE
    return None

records=[]
per_guide={}
source_urls=[]
raw_files=["data/raw/rendered_manifest.json","data/raw/guides_manifest.json","data/raw/parse_html.py"]
guides_with_xp=set()

def page_url(title):
    return "https://oldschool.runescape.wiki/w/"+title.replace(" ","_")

for title,info in mani.items():
    if title=="Theoretical experience rates": continue
    recs=ph.process(info["html_file"],info["family"],info["skill"])
    per_guide[(info["family"],info["skill"],title)]=len(recs)
    if recs:
        guides_with_xp.add((info["family"],info["skill"]))
    url=page_url(info["actual_title"])
    if url not in source_urls: source_urls.append(url)
    raw_files.append(info["html_file"].replace("\\","/"))
    raw_files.append(info["file"].replace("\\","/"))
    for r in recs:
        xp=r["xp_hr"]
        rec={
            "skill": r["skill"],
            "account_family": r["account_family"],
            "level_band": r["level_band"],
            "level_band_basis": r.get("level_column"),
            "method": r["method"],
            "method_section_path": r["method_path"],
            "xp_hr": xp,
            "xp_hr_column": r["xp_hr_column"],
            "cost_basis": cost_basis(r["account_family"]),
            "value_basis": "price-volatile snapshot; xp_hr extracted verbatim from wiki training-guide rate table (computed cells reflect live GE/HA prices on access date and drift over time)",
            "audience": r["account_family"],
            "notes": None,
            "_source_title": info["actual_title"],
            "_source_url": url,
        }
        records.append(rec)

# completeness: skill x family universe (23 skills x 3 families = 69 ; minus combat-skill structural absences)
universe=len(SKILLS_23)*len(FAMILIES)
covered=len(guides_with_xp)
known_missing=[]
# enumerate which (family,skill) combos have no XP/h records and WHY (structural)
combat_collective={"Attack","Strength","Defence"}  # covered only via combined Melee/combat guides w/o level-band xp/h tables
for fam in FAMILIES:
    for sk in SKILLS_23:
        if (fam,sk) not in guides_with_xp:
            known_missing.append({"account_family":fam,"skill":sk})

provenance={
  "domain":"skills_training",
  "source_urls": source_urls,
  "source_query": None,
  "accessed": ACCESSED,
  "license":"CC BY-NC-SA 3.0",
  "license_url":"https://creativecommons.org/licenses/by-nc-sa/3.0/",
  "extraction_method":"agent: enumerated Category:Training_guides; fetched per-skill training guides for main(Pay-to-play+combined)/f2p(Free-to-play)/ironman(Ironman Guide subpages) via MediaWiki API (action=parse rendered HTML, redirects resolved); parsed every wikitable with a Level column + one or more XP/h columns into one record per (row x XP/h column). Rendered HTML used because many guides compute XP/h via parser-function/#var templates not present in raw wikitext.",
  "raw_files": sorted(set(raw_files)),
  "record_count": len(records),
  "completeness":{
    "bounded_by":"Category:Training_guides x account families {main, f2p, ironman}; per-skill XP/h-by-level-band rate tables only",
    "universe_count": universe,
    "records_count": len(records),
    "known_missing": [
      {"note":"23 skills x 3 account families = 69 (skill,family) cells; only cells whose wiki training guide contains a structured XP/h-by-level table are extractable. Combat skills (Attack/Strength/Defence) and Hitpoints have no level-band XP/h tables on the wiki (rates are given qualitatively in the Melee/combat guides), and many f2p/ironman guides give rates in prose only.",
       "missing_skill_family_cells": known_missing,
       "missing_skill_family_count": len(known_missing),
       "guides_fetched_with_zero_xp_tables":[t for (f,s,t),c in per_guide.items() if c==0],
       "not_yet_extracted_as_structured_records":[
         "Theoretical experience rates page ({{Skilling experience rate chart}} template charts) — fetched to data/raw/guide_Theoretical_experience_rates.wikitext but NOT parsed into records: the template only stores xpPerAction/ticksPerAction/actions-per-min low/high and computes XP/h client-side; rendered as an SVG chart, so the numeric XP/h is not a literal table cell.",
         "Quest XP-reward tables in Ironman guides (e.g. Ironman Guide/Mining) are quest rewards, not XP/h rates, and are intentionally excluded.",
         "Prose-only / qualitative rate statements (e.g. 'around 50,000 experience per hour') across many guides are NOT extracted as records to avoid paraphrasing facts into a false structured shape."
       ]
      }
    ]
  },
  "domain_stats":{
    "guides_fetched": len([t for t in mani if t!="Theoretical experience rates"]),
    "guides_with_xp_tables": sum(1 for c in per_guide.values() if c>0),
    "records_by_family": {f:sum(1 for r in records if r["account_family"]==f) for f in FAMILIES},
    "skills_covered_by_family": {f:sorted({r["skill"] for r in records if r["account_family"]==f}) for f in FAMILIES},
    "skill_family_cells_covered": covered,
    "skill_family_cells_universe": universe,
    "records_with_range_xp": sum(1 for r in records if "low" in r["xp_hr"]),
    "records_with_point_xp": sum(1 for r in records if "value" in r["xp_hr"]),
  }
}

envelope={"_provenance":provenance,"records":records,"_excluded":[]}
json.dump(envelope, open("data/skills_training.json","w"), indent=2, ensure_ascii=False)
print("WROTE data/skills_training.json")
print("records:",len(records))
print("universe(skill x family):",universe,"covered:",covered)
print("known_missing cells:",len(known_missing))
print("by family:",provenance["domain_stats"]["records_by_family"])
