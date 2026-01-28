from __future__ import annotations

import hashlib
import re
from typing import List, Optional, Dict, Tuple

from bs4 import BeautifulSoup, Tag
from models.SpellCard import SpellCard  # adjust import to your project
from models.SpellCard import DegreesOfSuccess
from models.CardBase import HeightenedBlock, HeightenedEntry, ActionsBlock, ActionDetail


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
    if "action_reaction" in src:
        return "reaction"
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
    # Work on raw HTML so nested/malformed tags (e.g., "<st br>") don't hide line breaks.
    full_html = body_div.decode_contents()

    # Extract label/value pairs from the label block using HTML slicing.
    fields: Dict[str, str] = {}

    # Label block ends at the first <br> that is NOT followed by another <b> label.
    break_match = re.search(
        r"<br\s*/?>\s*(?!<b)(?:<br\s*/?>\s*)?",
        full_html,
        flags=re.IGNORECASE,
    )

    if break_match:
        label_block_html = full_html[: break_match.start()]
        body_html = full_html[break_match.end():].strip()
    else:
        label_block_html = full_html
        body_html = full_html.strip()

    label_matches = list(re.finditer(r"<b>\s*([^<]+?)\s*</b>", label_block_html, flags=re.IGNORECASE))
    for idx, match in enumerate(label_matches):
        label = norm_ws(match.group(1)).rstrip(":")
        start = match.end()
        end = label_matches[idx + 1].start() if idx + 1 < len(label_matches) else len(label_block_html)
        value_html = label_block_html[start:end]
        value_text = BeautifulSoup(value_html, "lxml").get_text(" ", strip=True)
        value_text = norm_ws(value_text)
        if label and value_text:
            fields[label] = value_text
    # If no fields were found, keep full HTML as body.
    if not fields:
        body_html = full_html.strip()

    # fields keys examples: "Range", "Targets", "Area", "Duration", "Defense", "Saving Throw", "Cast"
    # We'll map later.
    return fields, body_html


def extract_heightened_from_html(body_html: str) -> Tuple[Optional[HeightenedBlock], str]:
    """
    Extract Heightened entries from body HTML and return the block plus cleaned HTML.
    """
    if not body_html:
        return None, body_html

    soup = BeautifulSoup(body_html, "lxml")
    text = soup.get_text("\n")

    entries: List[HeightenedEntry] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lower().startswith("heightened"):
            # Parse label forms: "Heightened (+1)" or "Heightened (2nd)"
            inc = None
            min_rank = None
            label = line
            m = re.match(r"heightened\s*\(([^)]*)\)", line, re.IGNORECASE)
            # Handle split label: "Heightened" on one line and "(4th)" on next
            if m is None and i + 1 < len(lines) and lines[i + 1].startswith("("):
                label = f"{line} {lines[i + 1]}"
                m = re.match(r"heightened\s*\(([^)]*)\)", label, re.IGNORECASE)
                i += 1
            if m:
                val = m.group(1).strip()
                if val.startswith("+") and val[1:].isdigit():
                    inc = int(val[1:])
                else:
                    # ordinal like 2nd, 4th, etc.
                    num = re.match(r"(\d+)", val)
                    if num:
                        min_rank = int(num.group(1))
            # Capture following line(s) as text until next Heightened or end
            effect_parts: List[str] = []
            j = i + 1
            while j < len(lines) and not lines[j].lower().startswith("heightened"):
                effect_parts.append(lines[j])
                j += 1
            effect_text = " ".join(effect_parts).strip()
            entries.append(HeightenedEntry(increment=inc, minimum_rank=min_rank, text=effect_text or label))
            i = j
        else:
            i += 1

    if not entries:
        return None, body_html

    # Remove Heightened paragraphs from HTML by dropping any line containing "<b>Heightened"
    cleaned = re.sub(r"<br\s*/?>\s*<b>\s*Heightened[^<]*</b>[^<]*", "", body_html, flags=re.IGNORECASE)
    return HeightenedBlock(entries=entries), cleaned


def extract_degrees_from_html(body_html: str) -> Tuple[Optional[DegreesOfSuccess], str]:
    """
    Extract Degrees of Success entries and return the block plus cleaned HTML.
    """
    if not body_html:
        return None, body_html

    soup = BeautifulSoup(body_html, "lxml")
    text = soup.get_text("\n")
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines: List[str] = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        if line.lower() == "critical" and i + 1 < len(raw_lines):
            nxt = raw_lines[i + 1]
            low = nxt.lower()
            if low.startswith("success"):
                rest = nxt[len("success"):].strip()
                merged = "Critical Success" + (f" {rest}" if rest else "")
                lines.append(merged)
                i += 2
                continue
            if low.startswith("failure"):
                rest = nxt[len("failure"):].strip()
                merged = "Critical Failure" + (f" {rest}" if rest else "")
                lines.append(merged)
                i += 2
                continue
        lines.append(line)
        i += 1

    def normalize_label(label: str) -> Optional[str]:
        label = label.strip().lower()
        if label == "critical success":
            return "critical_success"
        if label == "success":
            return "success"
        if label == "failure":
            return "failure"
        if label == "critical failure":
            return "critical_failure"
        return None

    degrees = DegreesOfSuccess()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lower().startswith("critical success"):
            key = "critical_success"
        elif line.lower().startswith("success"):
            key = "success"
        elif line.lower().startswith("failure"):
            key = "failure"
        elif line.lower().startswith("critical failure"):
            key = "critical_failure"
        else:
            i += 1
            continue

        effect_parts: List[str] = []
        j = i + 1
        while j < len(lines):
            nxt = lines[j].lower()
            if nxt.startswith("critical success") or nxt.startswith("success") or nxt.startswith("failure") or nxt.startswith("critical failure"):
                break
            if nxt.startswith("heightened"):
                break
            effect_parts.append(lines[j])
            j += 1
        effect_text = " ".join(effect_parts).strip()
        setattr(degrees, key, effect_text or line)
        i = j

    if not any([degrees.critical_success, degrees.success, degrees.failure, degrees.critical_failure]):
        return None, body_html

    # Remove degree lines from HTML (including split <b>Critical</b><b>Success</b>)
    cleaned = re.sub(
        r"<br\s*/?>\s*<b>\s*(Critical\s+Success|Critical\s+Failure|Success|Failure)\s*</b>[^<]*",
        "",
        body_html,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"<br\s*/?>\s*<b>\s*Critical\s*</b>\s*<b>\s*(Success|Failure)\s*</b>[^<]*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return degrees, cleaned


_ACTION_MARKER_RE = re.compile(
    r"\[(one-action|two-actions|three-actions|reaction|free-action)\]",
    re.IGNORECASE,
)


def extract_action_variants_from_html(body_html: str) -> Tuple[Optional[ActionsBlock], str]:
    """
    Extract action-variant blocks like [one-action] from body HTML.
    """
    if not body_html:
        return None, body_html

    matches = list(_ACTION_MARKER_RE.finditer(body_html))
    if not matches:
        return None, body_html

    def key_for_marker(marker: str) -> str:
        marker = marker.lower()
        if marker == "one-action":
            return "one"
        if marker == "two-actions":
            return "two"
        if marker == "three-actions":
            return "three"
        if marker == "reaction":
            return "reaction"
        if marker == "free-action":
            return "free"
        return marker

    actions = ActionsBlock()
    cleaned_chunks: List[str] = []
    prev = 0
    for idx, m in enumerate(matches):
        marker = m.group(1)
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body_html)

        cleaned_chunks.append(body_html[prev:m.start()])
        prev = end

        text = body_html[start:end]
        text = re.sub(r"^(?:\s*<br\s*/?>\s*)+", "", text).strip()
        text = re.sub(r"(?:\s*<br\s*/?>\s*)+$", "", text).strip()

        key = key_for_marker(marker)
        if hasattr(actions, key):
            setattr(actions, key, ActionDetail(text=text or None))

    cleaned_chunks.append(body_html[prev:])
    cleaned = "".join(cleaned_chunks).strip()
    return actions, cleaned


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
        action_variants, body_html = extract_action_variants_from_html(body_html)
        degrees_of_success, body_html = extract_degrees_from_html(body_html)
        heightening, body_html = extract_heightened_from_html(body_html)

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
            action_variants=action_variants,
            heightening=heightening,
            degrees_of_success=degrees_of_success,
            source=source,
        )
        spells.append(spell)

    # Optional: de-duplicate by id if the HTML contains repeats
    uniq: Dict[int, SpellCard] = {s.id: s for s in spells}
    return list(uniq.values())
