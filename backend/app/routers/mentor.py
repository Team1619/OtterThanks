from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import get_current_mentor
from backend.app.database import get_db
from backend.app.models import Kudos
from backend.app.schemas import KudosResponse, KudosStatusUpdate
from backend.app.slack import post_kudos_to_slack

router = APIRouter(prefix="/api/mentor", tags=["mentor"])


class MentorKudosListResponse(BaseModel):
    total: int
    pending_count: int
    sent_count: int
    failed_count: int
    items: List[KudosResponse]


@router.get("/kudos", response_model=MentorKudosListResponse)
async def list_mentor_kudos(
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_mentor: dict = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db),
):
    # Base count query
    total_res = await db.execute(select(func.count(Kudos.id)))
    total = total_res.scalar() or 0

    pending_res = await db.execute(
        select(func.count(Kudos.id)).where(Kudos.slack_status == "pending")
    )
    pending_count = pending_res.scalar() or 0

    sent_res = await db.execute(
        select(func.count(Kudos.id)).where(Kudos.slack_status == "sent")
    )
    sent_count = sent_res.scalar() or 0

    failed_res = await db.execute(
        select(func.count(Kudos.id)).where(Kudos.slack_status == "failed")
    )
    failed_count = failed_res.scalar() or 0

    # Filtered query
    query = select(Kudos).order_by(Kudos.created_at.desc())

    if status_filter and status_filter.lower() != "all":
        query = query.where(Kudos.slack_status == status_filter.lower())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Kudos.recipient_name.ilike(term),
                Kudos.message.ilike(term),
                Kudos.sender_name.ilike(term),
            )
        )

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    kudos_items = [
        KudosResponse(
            id=item.id,
            recipient_type=item.recipient_type,
            recipient_name=item.recipient_name,
            message=item.message,
            sender_name=item.sender_name,
            slack_status=item.slack_status,
            slack_sent_at=item.slack_sent_at,
            created_at=item.created_at,
        )
        for item in items
    ]

    return MentorKudosListResponse(
        total=total,
        pending_count=pending_count,
        sent_count=sent_count,
        failed_count=failed_count,
        items=kudos_items,
    )


@router.post("/kudos/{kudos_id}/release", response_model=KudosResponse)
async def release_kudos_to_slack(
    kudos_id: int,
    current_mentor: dict = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db),
):
    """
    Releases a kudos message directly to the configured Slack channel via Slack Bot API.
    """
    result = await db.execute(select(Kudos).where(Kudos.id == kudos_id))
    kudos = result.scalar_one_or_none()
    if not kudos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kudos not found"
        )

    # Post message to Slack
    success, error = await post_kudos_to_slack(kudos)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to post to Slack: {error}",
        )

    # Mark as sent
    kudos.slack_status = "sent"
    kudos.slack_sent_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(kudos)

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


@router.delete("/kudos/{kudos_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kudos(
    kudos_id: int,
    current_mentor: dict = Depends(get_current_mentor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Kudos).where(Kudos.id == kudos_id))
    kudos = result.scalar_one_or_none()
    if not kudos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kudos not found"
        )

    await db.delete(kudos)
    await db.commit()


@router.patch("/kudos/{kudos_id}/status", response_model=KudosResponse)
async def update_kudos_status_by_mentor(
    kudos_id: int,
    status_update: KudosStatusUpdate,
    current_mentor: dict = Depends(get_current_mentor),
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

    await db.commit()
    await db.refresh(kudos)

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
