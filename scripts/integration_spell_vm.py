from pathlib import Path
import sys

# Allow running this script directly from the scripts/ folder.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from parsers.pathbuilder2e_Spell_List_Parser import parse_pathbuilder_spellbook_html
from render.view_models.spell_card_vm import build_spell_card_vm

html_path = Path("data/card_sources/pathbuilder2e_spell_lists/goff_spell_list.html")
html = html_path.read_text(encoding="utf-8")

spells = parse_pathbuilder_spellbook_html(html)
if not spells:
    raise SystemExit("No spells parsed from HTML")

vms = [build_spell_card_vm(s) for s in spells]

# Basic integration checks
required_keys = {
    "id",
    "name",
    "type",
    "tier",
    "actions",
    "traits",
    "traits_text",
    "meta",
    "body_html",
    "has_body",
    "source",
    "debug",
}

first = vms[0]
missing = required_keys.difference(first.keys())
if missing:
    raise SystemExit(f"VM missing keys: {sorted(missing)}")

print(f"Parsed {len(spells)} spells")
print(f"Built {len(vms)} view models")
print("First VM sample:")
print(first)
