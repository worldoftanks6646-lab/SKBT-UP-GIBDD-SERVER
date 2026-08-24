from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from app.core.config import settings


bearer_scheme = HTTPBearer(auto_error=False)


def create_device_token(device_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(device_id),
            "type": "device",
            "iat": now,
            "exp": now + timedelta(days=settings.DEVICE_TOKEN_EXPIRE_DAYS),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_device_token(token: str) -> UUID:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        if payload.get("type") != "device":
            raise InvalidTokenError("Unexpected token type")
        return UUID(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


async def get_current_device_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UUID | None:
    # Tests may disable authentication; it remains enabled by default everywhere else.
    if not settings.AUTH_REQUIRED:
        return None
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_device_token(credentials.credentials)


def verify_device_id(authenticated_device_id: UUID | None, claimed_device_id: UUID) -> UUID:
    if authenticated_device_id is not None and authenticated_device_id != claimed_device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The device_id does not match the access token",
        )
    return claimed_device_id
