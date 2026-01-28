from __future__ import annotations

from typing import Dict, List, Optional
import re

from models.SpellCard import SpellCard


def _actions_label(actions: Optional[str]) -> Optional[str]:
    if actions is None:
        return None
    if actions == "reaction":
        return "Reaction"
    if actions == "free":
        return "Free Action"
    if actions == "1":
        return "1 Action"
    if actions == "2":
        return "2 Actions"
    if actions == "3":
        return "3 Actions"
    return actions


def _actions_badge_class(actions: Optional[str]) -> Optional[str]:
    if actions is None:
        return None
    if actions == "reaction":
        return "act-reaction"
    if actions == "free":
        return "act-free"
    if actions in {"1", "2", "3"}:
        return f"act-{actions}"
    return "act-custom"


def _actions_glyph(actions: Optional[str]) -> Optional[str]:
    if actions is None:
        return None
    if actions == "reaction":
        return "R"
    if actions == "free":
        return "F"
    if actions in {"1", "2", "3"}:
        return actions
    return actions


def _traits_text(traits: Optional[List[str]]) -> str:
    if not traits:
        return ""
    return ", ".join(traits)

def _body_html_to_paragraphs(body_html: Optional[str]) -> str:
    if not body_html:
        return ""
    parts = [p for p in re.split(r"(?:<br\s*/?>\s*){2,}", body_html) if p.strip()]
    rendered: List[str] = []
    for part in parts:
        rendered.append(_render_part_with_degrees(part))
    combined = "".join(rendered)
    return _group_heightened_global(combined)


_DEGREE_LABELS = (
    "Critical Success",
    "Success",
    "Failure",
    "Critical Failure",
)

_HEIGHTENED_RE = re.compile(
    r"^\s*<b>\s*Heightened(?:\s*\([^)]*\))?\s*</b>(?:\s*\([^)]*\))?\s*",
    re.IGNORECASE,
)

def _is_degree_segment(segment: str) -> bool:
    for label in _DEGREE_LABELS:
        if re.match(rf"^\s*<b>\s*{re.escape(label)}\s*</b>", segment, re.IGNORECASE):
            return True
    return False


def _render_part_with_degrees(part_html: str) -> str:
    normalized = _normalize_degree_labels(part_html)
    # Split on <br>, but also isolate any Heightened blocks that appear inline.
    pieces = re.split(
        r"(<b>\s*Heightened(?:\s*\([^)]*\))?\s*</b>(?:\s*\([^)]*\))?\s*[^<]*)",
        normalized,
        flags=re.IGNORECASE,
    )
    segments: List[str] = []
    for piece in pieces:
        if not piece or not piece.strip():
            continue
        if _HEIGHTENED_RE.match(piece.strip()):
            segments.append(piece.strip())
        else:
            segments.extend([s.strip() for s in re.split(r"<br\s*/?>", piece) if s.strip()])
    if not segments:
        return ""

    has_degrees = any(_is_degree_segment(seg) for seg in segments)
    if not has_degrees:
        return f"<p>{normalized.strip()}</p>"

    out: List[str] = []
    degree_items: List[str] = []

    def flush_degrees() -> None:
        nonlocal degree_items
        if degree_items:
            out.append("<div class=\"degree-block\">" + "".join(degree_items) + "</div>")
            degree_items = []

    for seg in segments:
        if _is_degree_segment(seg):
            degree_items.append(f"<div class=\"degree\">{seg}</div>")
        elif _HEIGHTENED_RE.match(seg):
            flush_degrees()
            out.append(f"<p>{seg}</p>")
        else:
            if degree_items:
                degree_items[-1] = degree_items[-1].replace("</div>", f" <br>{seg}</div>")
            else:
                out.append(f"<p>{seg}</p>")

    flush_degrees()
    return "".join(out)


def _normalize_degree_labels(html: str) -> str:
    # Normalize split labels like <b>Critical</b> <b>Success</b>
    patterns = {
        r"<b>\s*Critical\s*</b>\s*<b>\s*Success\s*</b>": "<b>Critical Success</b>",
        r"<b>\s*Critical\s*</b>\s*<b>\s*Failure\s*</b>": "<b>Critical Failure</b>",
    }
    out = html
    for pattern, replacement in patterns.items():
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    return out


def _render_part_with_heightened(part_html: str) -> str:
    segments = [s.strip() for s in re.split(r"<br\s*/?>", part_html) if s.strip()]
    if not segments:
        return ""

    has_heightened = any(_HEIGHTENED_RE.match(seg) for seg in segments)
    if not has_heightened:
        return f"<p>{part_html.strip()}</p>"

    out: List[str] = []
    heightened_items: List[str] = []
    first_heightened_pos: Optional[int] = None

    i = 0
    while i < len(segments):
        seg = segments[i]
        if _HEIGHTENED_RE.match(seg):
            if first_heightened_pos is None:
                first_heightened_pos = len(out)
            item = seg
            j = i + 1
            while j < len(segments) and not _HEIGHTENED_RE.match(segments[j]):
                item = f"{item} <br>{segments[j]}"
                j += 1
            heightened_items.append(f"<div class=\"heightened\">{item}</div>")
            i = j
        else:
            if seg.strip():
                out.append(f"<p>{seg}</p>")
            i += 1

    if heightened_items:
        block_html = "<div class=\"heightened-block\">" + "".join(heightened_items) + "</div>"
        insert_at = first_heightened_pos if first_heightened_pos is not None else len(out)
        out.insert(insert_at, block_html)

    return "".join(out)


def _group_heightened_global(html: str) -> str:
    # Group any Heightened paragraphs across the whole body into a single block.
    parts = re.split(r"(<p>.*?</p>)", html, flags=re.IGNORECASE | re.DOTALL)
    out: List[str] = []
    heightened_items: List[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<p"):
            content = part[3:-4]
            if _HEIGHTENED_RE.match(content.strip()):
                chunks = [c.strip() for c in re.split(r"<br\s*/?>", content) if c.strip()]
                for chunk in chunks:
                    if _HEIGHTENED_RE.match(chunk):
                        heightened_items.append(f"<div class=\"heightened\">{chunk}</div>")
                    else:
                        if heightened_items:
                            heightened_items[-1] = heightened_items[-1].replace("</div>", f" <br>{chunk}</div>")
                        else:
                            heightened_items.append(f"<div class=\"heightened\">{chunk}</div>")
            else:
                out.append(part)
        else:
            out.append(part)

    if heightened_items:
        block = "<div class=\"heightened-block\">" + "".join(heightened_items) + "</div>"
        out.append(block)

    return "".join(out)


def _missing_fields(meta: Dict[str, Optional[str]]) -> List[str]:
    return [k for k, v in meta.items() if not v]


def build_spell_card_vm(spell: SpellCard) -> Dict[str, object]:
    meta: Dict[str, Optional[str]] = {
        "cast_time": spell.cast_time,
        "range": spell.range,
        "targets": spell.targets,
        "area": spell.area,
        "duration": spell.duration,
        "saving_throw": spell.saving_throw,
        "requirements": spell.requirements,
    }

    return {
        "id": spell.id,
        "name": spell.name,
        "type": spell.card_type,
        "tier": spell.tier,
        "actions": {
            "raw": spell.actions,
            "label": _actions_label(spell.actions),
            "glyph": _actions_glyph(spell.actions),
            "badge_class": _actions_badge_class(spell.actions),
        },
        "traits": spell.traits or [],
        "traits_text": _traits_text(spell.traits),
        "meta": meta,
        "body_html": _body_html_to_paragraphs(spell.body),
        "has_body": bool(spell.body),
        "source": spell.source,
        "debug": {
            "missing": _missing_fields(meta),
        },
    }
