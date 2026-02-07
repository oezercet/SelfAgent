"""Simple local authentication for SelfAgent.

Phase 1: No auth required (localhost only).
Future: Optional PIN or token-based auth.
"""

import logging

logger = logging.getLogger(__name__)


async def verify_request(headers: dict[str, str]) -> bool:
    """Verify an incoming request. Currently allows all local requests."""
    return True
