from __future__ import annotations

from copy import deepcopy
from typing import Any


def sanitize_wizard_progress(
    wizard_progress: dict[str, Any] | None,
    *,
    created_bot_exists: bool | None,
) -> dict[str, Any] | None:
    if wizard_progress is None:
        return None

    sanitized = deepcopy(wizard_progress)
    created_bot_uuid = sanitized.get('created_bot_uuid')
    if created_bot_uuid and created_bot_exists is False:
        sanitized['created_bot_uuid'] = None
        sanitized['bot_saved'] = False

    return sanitized
