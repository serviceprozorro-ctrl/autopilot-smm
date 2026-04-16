import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from core.accounts.manager import AccountManager
from db.database import get_db
from db.models import Platform, AuthType, AccountStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountCreateRequest(BaseModel):
    platform: str
    username: str
    auth_type: str = AuthType.COOKIES
    session_data: Optional[str] = None

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = [p.value for p in Platform]
        if v not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v

    @field_validator("auth_type")
    @classmethod
    def validate_auth_type(cls, v: str) -> str:
        allowed = [a.value for a in AuthType]
        if v not in allowed:
            raise ValueError(f"auth_type must be one of {allowed}")
        return v


class AccountResponse(BaseModel):
    id: int
    platform: str
    username: str
    auth_type: str
    status: str
    has_session: bool

    model_config = {"from_attributes": True}


class DeleteResponse(BaseModel):
    success: bool
    message: str


@router.post(
    "/add",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new social media account",
)
async def add_account(
    payload: AccountCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    try:
        account = await AccountManager.add_account(
            db=db,
            platform=payload.platform,
            username=payload.username,
            auth_type=payload.auth_type,
            raw_session_data=payload.session_data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to create account: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error")

    return AccountResponse(
        id=account.id,
        platform=account.platform,
        username=account.username,
        auth_type=account.auth_type,
        status=account.status,
        has_session=account.session_data is not None,
    )


@router.get(
    "/list",
    response_model=List[AccountResponse],
    summary="List all accounts",
)
async def list_accounts(db: AsyncSession = Depends(get_db)) -> List[AccountResponse]:
    accounts = await AccountManager.list_accounts(db)
    return [
        AccountResponse(
            id=acc.id,
            platform=acc.platform,
            username=acc.username,
            auth_type=acc.auth_type,
            status=acc.status,
            has_session=acc.session_data is not None,
        )
        for acc in accounts
    ]


@router.delete(
    "/{account_id}",
    response_model=DeleteResponse,
    summary="Delete an account by ID",
)
async def delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
) -> DeleteResponse:
    deleted = await AccountManager.remove_account(db, account_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with id={account_id} not found",
        )
    return DeleteResponse(success=True, message=f"Account {account_id} deleted successfully")
