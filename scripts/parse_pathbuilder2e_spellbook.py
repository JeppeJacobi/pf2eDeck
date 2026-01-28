from pathlib import Path
import sys

# Allow running this script directly from the scripts/ folder.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from parsers.pathbuilder2e_Spell_List_Parser import parse_pathbuilder_spellbook_html

html_path = Path("data/card_sources/pathbuilder2e_spell_lists/goff_spell_list.html")
html = html_path.read_text(encoding="utf-8")

spells = parse_pathbuilder_spellbook_html(html)

print(f"Parsed {len(spells)} spells")
print(spells[0].model_dump())
