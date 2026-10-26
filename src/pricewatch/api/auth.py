from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from pricewatch.api.config import ApiSettings, get_api_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


class User(BaseModel):
    username: str
    role: str


def _users(settings: ApiSettings) -> dict[str, tuple[str, str]]:
    return {
        "analyst": (settings.api_analyst_password_hash, "analyst"),
        "admin": (settings.api_admin_password_hash, "admin"),
    }


def authenticate(username: str, password: str, settings: ApiSettings) -> User | None:
    record = _users(settings).get(username)
    if not record or not record[0]:
        return None
    password_hash, role = record
    if not bcrypt.checkpw(password.encode(), password_hash.encode()):
        return None
    return User(username=username, role=role)


def create_token(user: User, settings: ApiSettings) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    settings: Annotated[ApiSettings, Depends(get_api_settings)],
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise unauthorized from exc
    if claims.get("role") not in ("analyst", "admin"):
        raise unauthorized
    return User(username=claims["sub"], role=claims["role"])


def require_role(*roles: str):

    def checker(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=f"requires role: {', '.join(roles)}"
            )
        return user

    return checker
