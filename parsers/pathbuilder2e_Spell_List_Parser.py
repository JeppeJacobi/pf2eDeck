from __future__ import annotations

import hashlib
import re
from typing import List, Optional, Dict, Tuple

from bs4 import BeautifulSoup, Tag
from models.SpellCard import SpellCard  # adjust import to your project


# -------- helpers --------

_WS_RE = re.compile(r"\s+")
_LEVEL_RE = re.compile(r"^(Cantrip|Spell)\s+(\d+)\s*$", re.IGNORECASE)

def norm_ws(s: str) -> str:
    return _WS_RE.sub(" ", s).strip()

def stable_int_id(*parts: str) -> int:
    """
    Deterministic int ID derived from input parts.
    Good enough for local use; replace with a real ID later if you have one.
    """
    blob = "||".join(norm_ws(p) for p in parts if p is not None)
    h = hashlib.sha1(blob.encode("utf-8")).hexdigest()
    # take first 12 hex chars -> fits in 48 bits -> safe in int
    return int(h[:12], 16)

def parse_action_from_icon_src(src: str) -> Optional[str]:
    """
    Map Pathbuilder action icons to a textual value.
    You can later change this to a richer structure (enum/count).
    """
    src = src.lower()
    if "action_single" in src:
        return "1"
    if "action_double" in src:
        return "2"
    if "action_triple" in src:
        return "3"
    if "action_range" in src:
        return "reaction"  # or "varies" depending on your conventions
    return None

def find_next_spell_block_start(tag: Tag) -> Optional[Tag]:
    """
    From a .stretcher-bearer, the spell's trait/body/source nodes follow as siblings
    until the next .stretcher-bearer or a .pagebreak.
    """
    sib = tag.next_sibling
    while sib is not None and not isinstance(sib, Tag):
        sib = sib.next_sibling
    return sib

def collect_spell_detail_nodes(stretcher_bearer: Tag) -> List[Tag]:
    """
    Collect tags belonging to this spell entry: trait divs + body div + copyright div.
    Stops before the next .stretcher-bearer or .pagebreak.
    """
    nodes: List[Tag] = []
    sib = stretcher_bearer.next_siblings
    for s in sib:
        if not isinstance(s, Tag):
            continue
        classes = set(s.get("class", []))
        if "stretcher-bearer" in classes or "pagebreak" in classes:
            break
        # Skip <hr> and <br>
        if s.name in {"hr", "br"}:
            continue
        nodes.append(s)
    return nodes

def parse_label_line_from_body(body_div: Tag) -> Tuple[Dict[str, str], str]:
    """
    In the body div, Pathbuilder uses <b>Label</b> value; ... <br> ... then prose.
    We'll parse the bold-label fields and also keep full HTML as body.
    """
    # Split label line from prose by the first double <br>. Also remove that pair from body HTML.
    contents = list(body_div.contents)

    def _is_whitespace(node) -> bool:
        return not isinstance(node, Tag) and str(node).strip() == ""

    double_br_start = None
    double_br_end = None
    for i, c in enumerate(contents):
        if not (isinstance(c, Tag) and c.name == "br"):
            continue
        # Find next non-whitespace node
        j = i + 1
        while j < len(contents) and _is_whitespace(contents[j]):
            j += 1
        if j < len(contents) and isinstance(contents[j], Tag) and contents[j].name == "br":
            double_br_start = i
            double_br_end = j
            break

    # Fallback to first <br> if no double <br> is present
    if double_br_start is None:
        br_indices = [i for i, c in enumerate(contents) if isinstance(c, Tag) and c.name == "br"]
        if br_indices:
            double_br_start = br_indices[0]
            double_br_end = br_indices[1] if len(br_indices) > 1 else br_indices[0]

    # Extract pairs from the HTML in a simple way: <b>Label</b> textUntilNextBoldOrBreak
    # Approach: walk children and capture <b> tags and the following text.
    fields: Dict[str, str] = {}

    current_label: Optional[str] = None
    current_value_parts: List[str] = []

    def flush():
        nonlocal current_label, current_value_parts
        if current_label:
            val = norm_ws("".join(current_value_parts))
            if val:
                fields[current_label] = val
        current_label = None
        current_value_parts = []

    # Determine where the label block ends: the first <br> followed by non-<b> content.
    label_break_index = None
    for i, c in enumerate(contents):
        if not (isinstance(c, Tag) and c.name == "br"):
            continue
        j = i + 1
        while j < len(contents) and _is_whitespace(contents[j]):
            j += 1
        if j >= len(contents):
            label_break_index = i
            break
        if not (isinstance(contents[j], Tag) and contents[j].name == "b"):
            label_break_index = i
            break

    # Only parse labels up to the detected label break (or fallback to first double <br>).
    if label_break_index is not None:
        label_children = contents[:label_break_index]
    else:
        label_children = contents if double_br_start is None else contents[:double_br_start]

    for child in label_children:
        if isinstance(child, Tag) and child.name == "b":
            # New label begins
            flush()
            current_label = norm_ws(child.get_text(" ", strip=True)).rstrip(":")
        else:
            # collect value-ish text, but stop at double breaks is too annoying; keep simple
            txt = ""
            if isinstance(child, Tag):
                # preserve semicolons/line breaks in text version
                txt = child.get_text(" ", strip=False)
            else:
                txt = str(child)
            current_value_parts.append(txt)

    flush()

    # Build body_html from only the prose after the label block when labels were found.
    if fields:
        if label_break_index is not None:
            body_start = label_break_index + 1
            while body_start < len(contents):
                node = contents[body_start]
                if _is_whitespace(node):
                    body_start += 1
                    continue
                if isinstance(node, Tag) and node.name == "br":
                    body_start += 1
                    continue
                break
            body_html = "".join(str(c) for c in contents[body_start:]).strip()
        elif double_br_end is not None:
            body_start = double_br_end + 1
            body_html = "".join(str(c) for c in contents[body_start:]).strip()
        else:
            body_html = "".join(str(c) for c in contents).strip()
    else:
        body_html = "".join(str(c) for c in contents).strip()

    # fields keys examples: "Range", "Targets", "Area", "Duration", "Defense", "Saving Throw", "Cast"
    # We'll map later.
    return fields, body_html


# -------- main parser --------

def parse_pathbuilder_spellbook_html(html: str) -> List[SpellCard]:
    soup = BeautifulSoup(html, "lxml")

    spells: List[SpellCard] = []

    # Each spell entry starts with this block
    for sb in soup.select("div.stretcher-bearer"):
        title_div = sb.select_one(".listview-title")
        level_div = sb.select_one(".listview-item-level")
        if not title_div or not level_div:
            continue

        # Name: remove the action-holder content from text
        # title_div text includes name + maybe whitespace; easiest: take title_div.contents[0] texty part
        title_text = norm_ws(title_div.get_text(" ", strip=True))
        # This includes the name but may include nothing else; safe to use directly
        name = title_text

        # Actions: look for icon inside title
        actions = None
        icon = title_div.select_one("img.action-icon")
        if icon and icon.get("src"):
            actions = parse_action_from_icon_src(icon["src"])

        # Level/tier: "Cantrip 1" or "Spell 2"
        level_text = norm_ws(level_div.get_text(" ", strip=True))
        m = _LEVEL_RE.match(level_text)
        if not m:
            # unexpected; skip rather than poisoning data
            continue
        kind = m.group(1).lower()   # "cantrip" or "spell"
        tier = int(m.group(2))

        # Collect the following nodes that belong to this spell
        nodes = collect_spell_detail_nodes(sb)

        traits: List[str] = []
        body_div: Optional[Tag] = None
        source: Optional[str] = None

        for n in nodes:
            classes = set(n.get("class", []))
            if "trait" in classes:
                t = norm_ws(n.get_text(" ", strip=True))
                if t:
                    traits.append(t)
            elif "copyright" in classes:
                source = norm_ws(n.get_text(" ", strip=True)) or None
            else:
                # The main body is usually a plain <div class=""> ... </div> right after traits
                # Some are class="" so check it has substantial text and contains <b> tags or Heightened blocks
                if body_div is None:
                    txt = norm_ws(n.get_text(" ", strip=True))
                    if txt:
                        body_div = n

        if body_div is None:
            # no rules text found; still create minimal spell if you want; here we skip
            continue

        label_fields, body_html = parse_label_line_from_body(body_div)

        # Map label fields into your model fields
        # Many spells use: Range, Targets, Area, Duration, Defense, Saving Throw, Cast, Requirements
        range_ = label_fields.get("Range")
        targets = label_fields.get("Targets")
        area = label_fields.get("Area")
        duration = label_fields.get("Duration")
        # Some spells use Defense, others Saving Throw
        defense = label_fields.get("Defense")
        saving_throw = label_fields.get("Saving Throw") or defense

        cast_time = label_fields.get("Cast")
        requirements = label_fields.get("Requirements")

        # Heightening is embedded in body; you can optionally extract it later.
        # For now keep it None and rely on body_html for rendering.
        # If you want, you can regex out "<b>Heightened" sections later.

        spell = SpellCard(
            id=stable_int_id(name, str(tier), kind),
            name=name,
            card_type="spell",
            tier=tier,
            actions=actions,
            traits=traits or None,
            cast_time=cast_time,
            range=range_,
            targets=targets,
            area=area,
            duration=duration,
            saving_throw=saving_throw,
            requirements=requirements,
            body=body_html,
            source=source,
        )
        spells.append(spell)

    # Optional: de-duplicate by id if the HTML contains repeats
    uniq: Dict[int, SpellCard] = {s.id: s for s in spells}
    return list(uniq.values())
