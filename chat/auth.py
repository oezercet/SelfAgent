"""Simple local authentication for SelfAgent.

Optional PIN-based auth for WebSocket connections.
Set `server.auth_pin` in config.yaml to enable.
"""

import hashlib
import hmac
import logging
import secrets

from core.config import get_config

logger = logging.getLogger(__name__)

# Session tokens for authenticated clients
_valid_tokens: set[str] = set()


def is_auth_enabled() -> bool:
    """Check if PIN authentication is configured."""
    pin = get_config().server.auth_pin
    return bool(pin and pin.strip())


def verify_pin(pin: str) -> str | None:
    """Verify a PIN and return a session token if correct.

    Returns None if the PIN is wrong.
    """
    config_pin = get_config().server.auth_pin
    if not config_pin:
        return None

    # Constant-time comparison to prevent timing attacks
    if hmac.compare_digest(pin.strip(), config_pin.strip()):
        token = secrets.token_hex(16)
        _valid_tokens.add(token)
        logger.info("PIN verified, token issued")
        return token

    logger.warning("Invalid PIN attempt")
    return None


def verify_token(token: str) -> bool:
    """Check if a session token is valid."""
    return token in _valid_tokens


def revoke_token(token: str) -> None:
    """Revoke a session token."""
    _valid_tokens.discard(token)
