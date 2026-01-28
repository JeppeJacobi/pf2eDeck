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


def _actions_display(spell: SpellCard) -> Dict[str, Optional[str]]:
    variants = spell.action_variants
    if variants:
        numeric = []
        if variants.one is not None:
            numeric.append(1)
        if variants.two is not None:
            numeric.append(2)
        if variants.three is not None:
            numeric.append(3)
        if numeric:
            lo, hi = min(numeric), max(numeric)
            if lo == hi:
                return {"glyph": str(lo), "label": f"{lo} Action"}
            return {"glyph": f"{lo}–{hi}", "label": f"{lo}–{hi} Actions"}
        if variants.reaction is not None:
            return {"glyph": "R", "label": "Reaction"}
        if variants.free is not None:
            return {"glyph": "F", "label": "Free Action"}

    return {"glyph": _actions_glyph(spell.actions), "label": _actions_label(spell.actions)}


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
        rendered.append(f"<p>{part.strip()}</p>")
    return "".join(rendered)


def _format_degrees(spell: SpellCard) -> str:
    if not spell.degrees_of_success:
        return ""
    items: List[str] = []
    if spell.degrees_of_success.critical_success:
        items.append(f"<div class=\"degree\"><b>Critical Success</b> {spell.degrees_of_success.critical_success}</div>")
    if spell.degrees_of_success.success:
        items.append(f"<div class=\"degree\"><b>Success</b> {spell.degrees_of_success.success}</div>")
    if spell.degrees_of_success.failure:
        items.append(f"<div class=\"degree\"><b>Failure</b> {spell.degrees_of_success.failure}</div>")
    if spell.degrees_of_success.critical_failure:
        items.append(f"<div class=\"degree\"><b>Critical Failure</b> {spell.degrees_of_success.critical_failure}</div>")
    if not items:
        return ""
    return "<div class=\"degree-block\">" + "".join(items) + "</div>"


def _heightening_label(entry) -> str:
    if entry.increment is not None:
        return f"Heightened (+{entry.increment})"
    if entry.minimum_rank is not None:
        # naive ordinal formatting
        suffix = "th"
        if entry.minimum_rank % 10 == 1 and entry.minimum_rank % 100 != 11:
            suffix = "st"
        elif entry.minimum_rank % 10 == 2 and entry.minimum_rank % 100 != 12:
            suffix = "nd"
        elif entry.minimum_rank % 10 == 3 and entry.minimum_rank % 100 != 13:
            suffix = "rd"
        return f"Heightened ({entry.minimum_rank}{suffix})"
    return "Heightened"


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

    action_variants_html = ""
    if spell.action_variants:
        items = []
        order = [
            ("one", "1"),
            ("two", "2"),
            ("three", "3"),
            ("reaction", "R"),
            ("free", "F"),
        ]
        for key, glyph in order:
            detail = getattr(spell.action_variants, key)
            if detail and detail.text:
                items.append(
                    f"<div class=\"action-item\"><span class=\"action-glyph\">{glyph}</span>{detail.text}</div>"
                )
        if items:
            action_variants_html = "<div class=\"action-block\">" + "".join(items) + "</div>"

    heightening_html = ""
    if spell.heightening and spell.heightening.entries:
        items = []
        for entry in spell.heightening.entries:
            label = _heightening_label(entry)
            text = entry.text
            items.append(f"<div class=\"heightened\"><b>{label}</b> {text}</div>")
        heightening_html = "<div class=\"heightened-block\">" + "".join(items) + "</div>"

    body_html = _body_html_to_paragraphs(spell.body)
    degrees_html = _format_degrees(spell)
    body_html = body_html + action_variants_html + degrees_html + heightening_html

    return {
        "id": spell.id,
        "name": spell.name,
        "type": spell.card_type,
        "tier": spell.tier,
        "actions": {
            "raw": spell.actions,
            "label": _actions_display(spell)["label"],
            "glyph": _actions_display(spell)["glyph"],
            "badge_class": _actions_badge_class(spell.actions),
        },
        "traits": spell.traits or [],
        "traits_text": _traits_text(spell.traits),
        "meta": meta,
        "body_html": body_html,
        "has_body": bool(spell.body),
        "source": spell.source,
        "debug": {
            "missing": _missing_fields(meta),
        },
    }
