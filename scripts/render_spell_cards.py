from pathlib import Path
import sys

# Allow running this script directly from the scripts/ folder.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from jinja2 import Environment, FileSystemLoader, select_autoescape

from parsers.pathbuilder2e_Spell_List_Parser import parse_pathbuilder_spellbook_html
from render.view_models.spell_card_vm import build_spell_card_vm


def main() -> None:
    html_path = Path("data/card_sources/pathbuilder2e_spell_lists/goff_spell_list.html")
    html = html_path.read_text(encoding="utf-8")

    spells = parse_pathbuilder_spellbook_html(html)
    vms = [build_spell_card_vm(s) for s in spells]

    env = Environment(
        loader=FileSystemLoader(PROJECT_ROOT / "render" / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("spell_cards.html")

    output_html = template.render(cards=vms)

    out_dir = PROJECT_ROOT / "render" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "spell_cards.html"
    out_file.write_text(output_html, encoding="utf-8")

    print(f"Wrote {out_file}")


if __name__ == "__main__":
    main()
