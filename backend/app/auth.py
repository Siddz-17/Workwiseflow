"""Authentication (Supabase JWT or local dev tokens) and workspace role checks."""

import uuid
from functools import lru_cache

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import ROLES, Invite, Membership, User

RANK = {r: i for i, r in enumerate(ROLES)}


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{url.rstrip('/')}/auth/v1/.well-known/jwks.json", cache_keys=True)


def _claims_from_supabase(token: str) -> dict:
    s = get_settings()
    try:
        if s.supabase_jwt_secret:
            return jwt.decode(token, s.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
        if not s.supabase_url:
            raise HTTPException(500, "Server misconfigured: set SUPABASE_URL or SUPABASE_JWT_SECRET")
        key = _jwks_client(s.supabase_url).get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["RS256", "ES256"], audience="authenticated")
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from e


def dev_user_id(email: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"workflowwise-dev:{email.lower()}"))


def get_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    s = get_settings()

    if s.auth_mode == "dev":
        if s.app_env == "production":
            raise HTTPException(500, "AUTH_MODE=dev is not allowed in production")
        if not token.startswith("dev:") or "@" not in token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Dev tokens look like 'dev:you@example.com'")
        email = token[4:].strip().lower()
        uid, name = dev_user_id(email), email.split("@")[0].replace(".", " ").title()
    else:
        claims = _claims_from_supabase(token)
        uid = claims["sub"]
        email = (claims.get("email") or "").lower()
        meta = claims.get("user_metadata") or {}
        name = meta.get("full_name") or meta.get("name") or (email.split("@")[0] if email else None)
        if not email:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has no email claim")

    user = db.get(User, uid)
    if user is None:
        user = User(id=uid, email=email, name=name)
        db.add(user)
        db.flush()
    elif user.email != email:
        user.email = email
    _claim_invites(db, user)
    db.commit()
    return user


def _claim_invites(db: Session, user: User) -> None:
    for inv in db.scalars(select(Invite).where(Invite.email == user.email)):
        exists = db.scalar(
            select(Membership).where(Membership.workspace_id == inv.workspace_id, Membership.user_id == user.id)
        )
        if not exists:
            db.add(Membership(workspace_id=inv.workspace_id, user_id=user.id, role=inv.role))
        db.delete(inv)


def require_role(db: Session, user: User, workspace_id: str, minimum: str = "viewer") -> Membership:
    m = db.scalar(select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == user.id))
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    if RANK[m.role] < RANK[minimum]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires {minimum} role or higher (you are {m.role})")
    return m
