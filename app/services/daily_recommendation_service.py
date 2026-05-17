"""
Daily recommendation service.

Loads the feature configuration and will later orchestrate the post-market
screening + analysis cron job.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Resolved once at import time; tests can monkeypatch this module attribute.
_CONFIG_PATH: Path = (
    Path(__file__).parent.parent.parent / "config" / "daily_recommendation.json"
)

_SAFE_DEFAULT: dict[str, Any] = {
    "enabled": False,
    "screening": {
        "conditions": [],
        "order_by": "market_cap",
        "order_direction": "desc",
        "limit": 5,
    },
    "analysis": {
        "research_depth": "标准",
        "market_type": "A股",
    },
}


def load_config() -> dict[str, Any]:
    """Load the daily-recommendation config from *config/daily_recommendation.json*.

    Returns the parsed dict on success.  Falls back to a safe default
    (``enabled=False``) if the file is absent or contains invalid JSON, and
    logs a warning in both cases.
    """
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.warning(
            "daily_recommendation.json not found at %s; using safe default",
            _CONFIG_PATH,
        )
    except json.JSONDecodeError as exc:
        logger.warning(
            "Failed to parse daily_recommendation.json (%s); using safe default",
            exc,
        )
    return dict(_SAFE_DEFAULT)
