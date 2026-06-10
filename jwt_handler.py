

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
from models import RevokedToken, User

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY must be set in the environment.")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
)


bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    bearerFormat="JWT",
    auto_error=False,
)


def create_access_token(data: dict) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    token_data = data.copy()
    token_data.update(
        {
            "exp": expire,
            "iat": now,
            "jti": uuid4().hex,
        }
    )

    return jwt.encode(
        token_data,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise credentials_exception()

    return credentials.credentials


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
        print("✅ JWT decoded:", payload)
        return payload

    except Exception as e:
        print("❌ JWT decode failed:", type(e).__name__, str(e))
        raise credentials_exception()


def is_token_revoked(payload: dict, db: Session) -> bool:
    return (
        db.query(RevokedToken)
        .filter(RevokedToken.token_jti == payload["jti"])
        .first()
        is not None
    )
def get_current_user(
    token: str = Depends(get_current_token),
    db: Session = Depends(get_db),
):

    payload = decode_access_token(token)


    revoked = is_token_revoked(payload, db)
    print("REVOKED:", revoked)

    subject = payload.get("sub")
    print("SUBJECT:", subject)

    user = db.get(User, int(subject))
    print("USER:", user)

    if user is None:
        raise credentials_exception()

    return user

def revoke_token(
    token: str,
    db: Session,
    user_id: int,
) -> None:
    payload = decode_access_token(token)
    expires_at = datetime.fromtimestamp(
        payload["exp"],
        tz=timezone.utc,
    )

    revoked_token = RevokedToken(
        user_id=user_id,
        token_jti=payload["jti"],
        expires_at=expires_at,
    )

    db.add(revoked_token)
    db.commit()
