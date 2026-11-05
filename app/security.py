from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.config import ACCESS_TOKEN_MINUTES, REFRESH_TOKEN_DAYS, SECRET_KEY

ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("constant-invalid-password-value")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_token(user_id: int, token_type: str, lifetime: timedelta) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + lifetime
    token_id = str(uuid4())
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": token_id,
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM), token_id, expires_at


def create_token_pair(user_id: int) -> tuple[str, str, str]:
    access, _, _ = create_token(
        user_id, "access", timedelta(minutes=ACCESS_TOKEN_MINUTES)
    )
    refresh, refresh_id, expires_at = create_token(
        user_id, "refresh", timedelta(days=REFRESH_TOKEN_DAYS)
    )
    return access, refresh, refresh_id


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
