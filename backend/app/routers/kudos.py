from datetime import datetime, timezone
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models import Kudos
from backend.app.schemas import KudosCreate, KudosResponse, KudosStatusUpdate
from backend.app.slack import post_kudos_review_to_mentor_channel

router = APIRouter(prefix="/api/kudos", tags=["kudos"])


def build_kudos_response(kudos: Kudos) -> KudosResponse:
    return KudosResponse(
        id=kudos.id,
        recipient_type=kudos.recipient_type,
        recipient_name=kudos.recipient_name,
        message=kudos.message,
        sender_name=kudos.sender_name,
        slack_status=kudos.slack_status,
        slack_sent_at=kudos.slack_sent_at,
        created_at=kudos.created_at,
    )


@router.post("", response_model=KudosResponse, status_code=status.HTTP_201_CREATED)
async def create_kudos(
    kudos_in: KudosCreate,
    db: AsyncSession = Depends(get_db),
):
    # Validate recipient_type
    clean_recipient_type = kudos_in.recipient_type.strip().lower()
    if clean_recipient_type not in ["individual", "team"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="recipient_type must be either 'individual' or 'team'",
        )

    # Validate recipient_name
    clean_recipient_name = (
        kudos_in.recipient_name.strip() if kudos_in.recipient_name else None
    )
    if clean_recipient_type == "individual":
        if not clean_recipient_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="recipient_name is required when recipient_type is 'individual'",
            )
    else:
        clean_recipient_name = None

    # Validate message
    clean_message = kudos_in.message.strip()
    if not clean_message or len(clean_message) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="message must be at least 2 characters long",
        )

    # Validate sender_name
    clean_sender_name = (
        kudos_in.sender_name.strip() if kudos_in.sender_name else ""
    )
    if not clean_sender_name:
        clean_sender_name = "Anonymous"

    # Save to database
    kudos = Kudos(
        recipient_type=clean_recipient_type,
        recipient_name=clean_recipient_name,
        message=clean_message,
        sender_name=clean_sender_name,
        slack_status="pending",
    )
    db.add(kudos)
    await db.commit()
    await db.refresh(kudos)

    # Automatically notify private mentor Slack channel if configured
    if settings.slack_mentor_channel_id and settings.slack_bot_token:
        try:
            await post_kudos_review_to_mentor_channel(kudos)
        except Exception:
            pass

    return build_kudos_response(kudos)


@router.get("", response_model=List[KudosResponse])
async def list_kudos(
    status_filter: Optional[str] = Query(
        None, alias="status", description="Filter by Slack status: pending, sent, failed"
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Kudos).order_by(Kudos.created_at.desc())
    if status_filter:
        query = query.where(Kudos.slack_status == status_filter)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    return [build_kudos_response(item) for item in items]


@router.get("/{kudos_id}", response_model=KudosResponse)
async def get_kudos(
    kudos_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Kudos).where(Kudos.id == kudos_id))
    kudos = result.scalar_one_or_none()
    if not kudos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kudos not found"
        )
    return build_kudos_response(kudos)


@router.patch("/{kudos_id}/status", response_model=KudosResponse)
async def update_kudos_status(
    kudos_id: int,
    status_update: KudosStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Kudos).where(Kudos.id == kudos_id))
    kudos = result.scalar_one_or_none()
    if not kudos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kudos not found"
        )

    kudos.slack_status = status_update.slack_status
    if status_update.slack_sent_at is not None:
        kudos.slack_sent_at = status_update.slack_sent_at
    elif status_update.slack_status == "sent" and kudos.slack_sent_at is None:
        kudos.slack_sent_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(kudos)

    return build_kudos_response(kudos)
