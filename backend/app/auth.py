import hashlib
import hmac
import secrets
from datetime import timedelta, timezone

from sqlalchemy.orm import Session

from .models import AuthSession, Operator, now


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_hex, expected_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=16384, r=8, p=1)
        return hmac.compare_digest(actual, bytes.fromhex(expected_hex))
    except (ValueError, TypeError):
        return False


def issue_session(db: Session, operator: Operator) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), operator_id=operator.id, expires_at=now() + timedelta(hours=8)))
    db.commit()
    return token


def operator_for_token(db: Session, token: str) -> Operator | None:
    stored = db.get(AuthSession, hashlib.sha256(token.encode()).hexdigest())
    if not stored or stored.revoked_at is not None:
        return None
    expiry = stored.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= now():
        return None
    return db.get(Operator, stored.operator_id)


def revoke_session(db: Session, token: str) -> None:
    stored = db.get(AuthSession, hashlib.sha256(token.encode()).hexdigest())
    if stored:
        stored.revoked_at = now()
        db.commit()
