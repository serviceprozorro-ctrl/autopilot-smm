"""API для визуального портфолио (образы для контента)."""
import json
import logging
import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import PortfolioItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])

PORTFOLIO_DIR = Path(__file__).resolve().parents[2] / "portfolio_storage"
PORTFOLIO_DIR.mkdir(exist_ok=True)


class PortfolioItemResponse(BaseModel):
    id: int
    account_id: Optional[int]
    title: str
    image_path: str
    source: str
    description: Optional[str]
    style_tags: List[str]
    quality_score: float
    parent_id: Optional[int]
    created_at: str

    @classmethod
    def from_model(cls, item: PortfolioItem) -> "PortfolioItemResponse":
        try:
            tags = json.loads(item.style_tags) if item.style_tags else []
        except Exception:
            tags = []
        return cls(
            id=item.id, account_id=item.account_id, title=item.title,
            image_path=item.image_path, source=item.source,
            description=item.description, style_tags=tags,
            quality_score=item.quality_score, parent_id=item.parent_id,
            created_at=item.created_at.isoformat() if item.created_at else "",
        )


@router.get("/list", response_model=List[PortfolioItemResponse])
async def list_portfolio(
    account_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(PortfolioItem).order_by(PortfolioItem.created_at.desc())
    if account_id is not None:
        q = q.where(PortfolioItem.account_id == account_id)
    rows = (await db.execute(q)).scalars().all()
    return [PortfolioItemResponse.from_model(r) for r in rows]


@router.post("/upload", response_model=PortfolioItemResponse)
async def upload_portfolio(
    file: UploadFile = File(...),
    title: str = Form("Образ"),
    account_id: Optional[int] = Form(None),
    description: Optional[str] = Form(None),
    style_tags: Optional[str] = Form(None),  # comma-separated
    db: AsyncSession = Depends(get_db),
):
    suffix = Path(file.filename or "img.png").suffix.lower() or ".png"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        suffix = ".png"
    fname = f"{uuid.uuid4().hex}{suffix}"
    target = PORTFOLIO_DIR / fname
    target.write_bytes(await file.read())

    tags_json = json.dumps(
        [t.strip() for t in (style_tags or "").split(",") if t.strip()],
        ensure_ascii=False,
    )

    item = PortfolioItem(
        account_id=account_id, title=title, image_path=str(target),
        source="upload", description=description, style_tags=tags_json,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return PortfolioItemResponse.from_model(item)


class CreateFromPathRequest(BaseModel):
    image_path: str
    title: str = "Образ"
    account_id: Optional[int] = None
    source: str = "grok"
    description: Optional[str] = None
    style_tags: List[str] = []
    quality_score: float = 0.0
    parent_id: Optional[int] = None


@router.post("/create", response_model=PortfolioItemResponse)
async def create_portfolio_from_path(
    payload: CreateFromPathRequest,
    db: AsyncSession = Depends(get_db),
):
    if not os.path.exists(payload.image_path):
        raise HTTPException(404, f"Файл не найден: {payload.image_path}")
    item = PortfolioItem(
        account_id=payload.account_id, title=payload.title,
        image_path=payload.image_path, source=payload.source,
        description=payload.description,
        style_tags=json.dumps(payload.style_tags, ensure_ascii=False),
        quality_score=payload.quality_score, parent_id=payload.parent_id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return PortfolioItemResponse.from_model(item)


@router.delete("/{item_id}")
async def delete_portfolio_item(item_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(delete(PortfolioItem).where(PortfolioItem.id == item_id))
    await db.commit()
    return {"success": res.rowcount > 0}
