import json
import logging
from datetime import datetime, timezone
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models import Kudos
from backend.app.slack import (
    format_recipient_display,
    post_kudos_to_slack,
    verify_slack_signature,
)

logger = logging.getLogger("otterthanks.slack_router")

router = APIRouter(prefix="/api/slack", tags=["slack"])


@router.post("/interactions")
async def handle_slack_interactions(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handles interactive actions from Slack (such as Approve & Reject buttons).
    Configured as the Request URL under 'Interactivity & Shortcuts' in the Slack App.
    """
    raw_body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")

    # 1. Verify Slack Signature
    if not verify_slack_signature(raw_body, timestamp, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Slack request signature",
        )

    # 2. Parse payload from form-urlencoded body
    form_data = await request.form()
    payload_raw = form_data.get("payload")
    if not payload_raw:
        # Fallback: check if json was passed directly
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Slack interaction payload",
            )
    else:
        try:
            payload = json.loads(payload_raw)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in Slack interaction payload",
            )

    payload_type = payload.get("type")
    if payload_type != "block_actions":
        return Response(status_code=status.HTTP_200_OK)

    actions = payload.get("actions", [])
    if not actions:
        return Response(status_code=status.HTTP_200_OK)

    action = actions[0]
    action_id = action.get("action_id")
    kudos_id_val = action.get("value")
    user_info = payload.get("user", {})
    user_name = user_info.get("name") or user_info.get("username") or "A mentor"

    try:
        kudos_id = int(kudos_id_val)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid kudos ID in action"
        )

    result = await db.execute(select(Kudos).where(Kudos.id == kudos_id))
    kudos = result.scalar_one_or_none()
    if not kudos:
        return {
            "response_type": "ephemeral",
            "replace_original": False,
            "text": f"⚠️ Kudos #{kudos_id} was not found in the database.",
        }

    recipient_display, fallback_recipient = format_recipient_display(kudos)
    quoted_message = "\n> ".join(kudos.message.strip().splitlines())
    current_time_str = datetime.now(timezone.utc).strftime("%b %d, %Y at %I:%M %p UTC")

    # Handle Approve
    if action_id == "approve_kudos":
        if kudos.slack_status == "sent":
            status_note = f"ℹ️ Already released by @{user_name}"
        else:
            # Post to public channel
            success, error = await post_kudos_to_slack(kudos)
            if not success:
                logger.error(f"Failed to post approved kudos #{kudos_id} to Slack: {error}")
                return {
                    "response_type": "ephemeral",
                    "replace_original": False,
                    "text": f"⚠️ Failed to release to #{settings.slack_channel_id}: {error}",
                }

            kudos.slack_status = "sent"
            kudos.slack_sent_at = datetime.now(timezone.utc)
            await db.commit()
            status_note = f"✅ *Approved & Released to #{settings.slack_channel_id or 'kudos'}* by @{user_name} on {current_time_str}"

        updated_blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🦦 Kudos Approved",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*To:* {recipient_display}\n*Signed by:* *{kudos.sender_name}*",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Message:*\n> {quoted_message}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": status_note,
                    }
                ],
            },
            {"type": "divider"},
        ]

        return {
            "response_type": "in_channel",
            "replace_original": True,
            "text": f"✅ Kudos #{kudos_id} approved by @{user_name}",
            "blocks": updated_blocks,
        }

    # Handle Reject
    elif action_id == "reject_kudos":
        kudos.slack_status = "rejected"
        await db.commit()

        updated_blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🦦 Kudos Dismissed",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*To:* {recipient_display}\n*Signed by:* *{kudos.sender_name}*",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Message:*\n> {quoted_message}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"❌ *Rejected / Dismissed* by @{user_name} on {current_time_str}",
                    }
                ],
            },
            {"type": "divider"},
        ]

        return {
            "response_type": "in_channel",
            "replace_original": True,
            "text": f"❌ Kudos #{kudos_id} rejected by @{user_name}",
            "blocks": updated_blocks,
        }

    return Response(status_code=status.HTTP_200_OK)
