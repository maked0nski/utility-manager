import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.config import settings


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_token(
    subject: str,
    role: str,
    ttl_seconds: int = 60 * 60 * 24,
    token_type: str = "access",
    session_version: int | None = None,
) -> str:
    payload = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl_seconds,
    }
    if session_version is not None:
        payload["session_version"] = int(session_version)
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    sig = hmac.new(settings.app_secret_key.encode("utf-8"), raw, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw).decode("utf-8") + "." + base64.urlsafe_b64encode(sig).decode("utf-8")


def parse_token(token: str) -> dict:
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        raw = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
        sig = base64.urlsafe_b64decode(sig_b64.encode("utf-8"))
    except Exception as exc:
        raise ValueError("Invalid token format.") from exc

    expected = hmac.new(settings.app_secret_key.encode("utf-8"), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid token signature.")

    payload = json.loads(raw.decode("utf-8"))
    if payload.get("exp", 0) < int(time.time()):
        raise ValueError("Token expired.")
    return payload
