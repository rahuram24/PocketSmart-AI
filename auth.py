import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from jose import jwt

ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return salt.hex() + ":" + digest.hex()

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), 120_000
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False

def create_token(user_id: int, secret_key: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=12)).timestamp()),
    }
    return jwt.encode(payload, secret_key, algorithm=ALGORITHM)

def decode_token(token: str, secret_key: str):
    return jwt.decode(token, secret_key, algorithms=[ALGORITHM])
