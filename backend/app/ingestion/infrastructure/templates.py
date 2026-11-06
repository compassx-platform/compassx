"""Path, query, and body placeholders for one param value."""
from __future__ import annotations

from typing import Any, Dict, Optional


def _render_template(template: str, param_value: str, cursor: Optional[str]) -> str:
    return (
        template
        .replace("{param_value}", param_value)
        .replace("{asset_id}", param_value)
        .replace("{cursor}", cursor or "")
    )


def _render_dict_template(
    template: Dict[str, Any], param_value: str, cursor: Optional[str]
) -> Dict[str, Any]:
    rendered = {}
    for k, v in template.items():
        if isinstance(v, str):
            rendered[k] = _render_template(v, param_value, cursor)
        else:
            rendered[k] = v
    return rendered
