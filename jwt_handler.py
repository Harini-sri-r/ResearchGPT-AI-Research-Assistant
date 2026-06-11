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

access_token_expire_minutes = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")

if not access_token_expire_minutes:
    raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be set in the environment.")

ACCESS_TOKEN_EXPIRE_MINUTES = int(access_token_expire_minutes)


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
    except JWTError as error:
        raise credentials_exception() from error

    if payload.get("sub") is None or payload.get("jti") is None:
        raise credentials_exception()

    return payload


def is_token_revoked(payload: dict, db: Session) -> bool:
    token_jti = payload.get("jti")
    if token_jti is None:
        return True

    return (
        db.query(RevokedToken)
        .filter(RevokedToken.token_jti == token_jti)
        .first()
        is not None
    )


def get_current_user(
    token: str = Depends(get_current_token),
    db: Session = Depends(get_db),
):
    payload = decode_access_token(token)

    if is_token_revoked(payload, db):
        raise credentials_exception()

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as error:
        raise credentials_exception() from error

    user = db.get(User, user_id)

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
