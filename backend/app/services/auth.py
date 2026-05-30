import uuid
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.models import User, Organization, OrgMembership, OrgRole

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, org_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": subject, "org_id": org_id, "exp": expire, "type": "access"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_refresh_token(subject: str, org_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": subject, "org_id": org_id, "exp": expire, "type": "refresh"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


async def get_unique_slug(db: AsyncSession, base: str) -> str:
    slug = slugify(base)
    candidate = slug
    counter = 1
    while True:
        result = await db.execute(select(Organization).where(Organization.slug == candidate))
        if not result.scalar_one_or_none():
            return candidate
        candidate = f"{slug}-{counter}"
        counter += 1


async def register_user(db: AsyncSession, email: str, password: str, full_name: Optional[str], org_name: str) -> tuple[User, Organization]:
    # Create user
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        is_verified=True,  # Skip email verification for now
    )
    db.add(user)
    await db.flush()

    # Create org
    slug = await get_unique_slug(db, org_name)
    org = Organization(name=org_name, slug=slug)
    db.add(org)
    await db.flush()

    # Create membership
    membership = OrgMembership(
        user_id=user.id,
        organization_id=org.id,
        role=OrgRole.OWNER,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(user)
    await db.refresh(org)
    return user, org


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[tuple[User, Organization]]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return None
    # Get first org membership
    result = await db.execute(
        select(OrgMembership).where(OrgMembership.user_id == user.id)
    )
    membership = result.scalar_one_or_none()
    if not membership:
        return None
    result = await db.execute(select(Organization).where(Organization.id == membership.organization_id))
    org = result.scalar_one_or_none()
    return user, org
