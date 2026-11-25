"""End-user messages for validation error codes, for form errors.

Never show raw codes to end users; unknown codes fall back to a generic
message. English only: translate them with your own i18n (e.g. gettext).
"""

from __future__ import annotations

from typing import Dict, Optional

GENERIC = "CAPTCHA verification did not pass. Please try again."
_REFRESH = "CAPTCHA expired or was already used. Please refresh and try again."
_CONFIG = "CAPTCHA configuration error. Please contact the site owner."
_SLOW = "Too many CAPTCHA attempts. Please wait a moment."

MESSAGES: Dict[str, str] = {
    "token_expired": _REFRESH,
    "token_already_used": _REFRESH,
    "token_not_found": _REFRESH,
    "action_mismatch": "CAPTCHA was solved for a different action. Please refresh and try again.",
    "hostname_mismatch": "CAPTCHA was solved on a different site. Please refresh and try again.",
    "request_failed": "CAPTCHA service is temporarily unavailable. Please try again shortly.",
    "rate_limited": _SLOW,
    "rate_limit_exceeded": _SLOW,
    "invalid_app_key": _CONFIG,
    "invalid_app_secret": _CONFIG,
    "missing_app_key": _CONFIG,
    "test_always_fail": GENERIC,
}


def user_message(code: Optional[str]) -> str:
    """A short, user-safe message for a ``ValidateResult.error`` code."""
    return MESSAGES.get(code or "", GENERIC)
