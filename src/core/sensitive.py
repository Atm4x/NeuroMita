from __future__ import annotations

import re
from typing import Any


_SENSITIVE_PARAM_RE = re.compile(r'((?:api[_-]?)?key|access_token|token)=([^&\s#"\']+)', re.IGNORECASE)
_BEARER_RE = re.compile(r'(Bearer\s+)([A-Za-z0-9._\-]+)', re.IGNORECASE)


def mask_sensitive(text: Any) -> Any:
    if not text:
        return text
    value = str(text)
    value = _SENSITIVE_PARAM_RE.sub(
        lambda match: f"{match.group(1)}=***",
        value,
    )
    return _BEARER_RE.sub(
        lambda match: f"{match.group(1)}***",
        value,
    )
