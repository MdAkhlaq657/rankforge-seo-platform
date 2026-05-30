from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.schemas import UserRegister, UserLogin, TokenResponse, MeResponse, UserOut, OrgOut
from app.services.auth import register_user, authenticate_user, create_access_token, create_refresh_token
from app.middleware.auth import get_current_user, get_current_org
from app.models import User, Organization, OrgMembership

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check email not taken
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user, org = await register_user(
        db, data.email, data.password, data.full_name, data.org_name
    )

    return TokenResponse(
        access_token=create_access_token(str(user.id), str(org.id)),
        refresh_token=create_refresh_token(str(user.id), str(org.id)),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await authenticate_user(db, data.email, data.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user, org = result
    return TokenResponse(
        access_token=create_access_token(str(user.id), str(org.id)),
        refresh_token=create_refresh_token(str(user.id), str(org.id)),
    )


@router.get("/me", response_model=MeResponse)
async def me(
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrgMembership, Organization)
        .join(Organization, OrgMembership.organization_id == Organization.id)
        .where(OrgMembership.user_id == user.id)
    )
    rows = result.all()
    orgs = [OrgOut.model_validate(row.Organization) for row in rows]

    return MeResponse(
        user=UserOut.model_validate(user),
        organizations=orgs,
        current_org=OrgOut.model_validate(org),
    )
