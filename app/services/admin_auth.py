import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from app.core.config import settings


SESSION_COOKIE = "gibdd_admin_session"
SESSION_TTL_SECONDS = 8 * 60 * 60


@dataclass(frozen=True)
class AdminSession:
    username: str
    csrf_token: str


def verify_password(password: str) -> bool:
    stored = settings.ADMIN_PASSWORD_HASH
    if not stored:
        return False
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(actual.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def make_password_hash(password: str, iterations: int = 390_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def create_session(username: str) -> str:
    payload = {
        "u": username,
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
        "csrf": secrets.token_urlsafe(24),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    signature = hmac.new(_session_secret(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def read_session(value: str | None) -> AdminSession | None:
    if not value:
        return None
    try:
        encoded, signature = value.rsplit(".", 1)
        expected = hmac.new(
            _session_secret(), encoded.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        if payload["u"] != settings.ADMIN_USERNAME or payload["exp"] < time.time():
            return None
        return AdminSession(username=payload["u"], csrf_token=payload["csrf"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def _session_secret() -> bytes:
    value = settings.ADMIN_SESSION_SECRET or settings.SECRET_KEY
    return value.encode()
