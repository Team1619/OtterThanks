import hashlib
import hmac
import logging
import time
from typing import Optional, Tuple
import httpx

from backend.app.config import settings
from backend.app.models import Kudos

logger = logging.getLogger("otterthanks.slack")


def format_recipient_display(kudos: Kudos) -> Tuple[str, str]:
    if kudos.recipient_type == "team":
        return "🏆 *The Whole Team (Up-A-Creek Robotics)*", "The Whole Team"
    recipient_name = kudos.recipient_name or "Teammate"
    return f"👤 *{recipient_name}*", recipient_name


async def post_kudos_to_slack(kudos: Kudos) -> Tuple[bool, Optional[str]]:
    """
    Posts a public formatted Kudos message to the designated team Slack channel.
    Returns (success: bool, error_message: Optional[str]).
    """
    if not settings.slack_bot_token:
        return False, "SLACK_BOT_TOKEN is not configured in .env."

    if not settings.slack_channel_id:
        return False, "SLACK_CHANNEL_ID is not configured in .env."

    recipient_display, fallback_recipient = format_recipient_display(kudos)
    quoted_message = "\n> ".join(kudos.message.strip().splitlines())
    fallback_text = (
        f"🦦 Kudos for {fallback_recipient} from {kudos.sender_name}: {kudos.message}"
    )

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🦦 New Kudos Shared!",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*To:* {recipient_display}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"> {quoted_message}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"✍️ Signed by: *{kudos.sender_name}*   •   🤖 *OtterThanks*",
                }
            ],
        },
        {"type": "divider"},
    ]

    payload = {
        "channel": settings.slack_channel_id,
        "text": fallback_text,
        "blocks": blocks,
    }

    headers = {
        "Authorization": f"Bearer {settings.slack_bot_token.strip()}",
        "Content-Type": "application/json; charset=utf-8",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://slack.com/api/chat.postMessage",
                json=payload,
                headers=headers,
            )
            data = resp.json()

            if data.get("ok") is True:
                logger.info(
                    f"Successfully posted kudos #{kudos.id} to Slack channel {settings.slack_channel_id}."
                )
                return True, None

            error = data.get("error", f"HTTP {resp.status_code}")
            logger.error(f"Slack API error posting kudos #{kudos.id}: {error}")
            return False, error
    except Exception as e:
        logger.error(f"Network error posting kudos #{kudos.id} to Slack: {str(e)}")
        return False, str(e)


async def post_kudos_review_to_mentor_channel(kudos: Kudos) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Posts an interactive Kudos review card to the private mentor Slack channel with
    approve (check) and reject (x) buttons.
    Returns (success, error, channel_id, message_ts).
    """
    if not settings.slack_bot_token:
        return False, "SLACK_BOT_TOKEN is not configured in .env.", None, None

    if not settings.slack_mentor_channel_id:
        return False, "SLACK_MENTOR_CHANNEL_ID is not configured in .env.", None, None

    recipient_display, fallback_recipient = format_recipient_display(kudos)
    quoted_message = "\n> ".join(kudos.message.strip().splitlines())
    fallback_text = f"🦦 [Mentor Review Required] Kudos #{kudos.id} for {fallback_recipient} from {kudos.sender_name}"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🦦 New Kudos Awaiting Review",
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
            "type": "actions",
            "block_id": f"kudos_review_actions_{kudos.id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ Approve & Release",
                        "emoji": True,
                    },
                    "style": "primary",
                    "action_id": "approve_kudos",
                    "value": str(kudos.id),
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "❌ Reject",
                        "emoji": True,
                    },
                    "style": "danger",
                    "action_id": "reject_kudos",
                    "value": str(kudos.id),
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Kudos #{kudos.id} • Click ✅ to publish to #{settings.slack_channel_id or 'kudos'} or ❌ to dismiss.",
                }
            ],
        },
        {"type": "divider"},
    ]

    payload = {
        "channel": settings.slack_mentor_channel_id,
        "text": fallback_text,
        "blocks": blocks,
    }

    headers = {
        "Authorization": f"Bearer {settings.slack_bot_token.strip()}",
        "Content-Type": "application/json; charset=utf-8",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://slack.com/api/chat.postMessage",
                json=payload,
                headers=headers,
            )
            data = resp.json()

            if data.get("ok") is True:
                logger.info(
                    f"Successfully posted kudos #{kudos.id} to private mentor channel {settings.slack_mentor_channel_id}."
                )
                return True, None, data.get("channel"), data.get("ts")

            error = data.get("error", f"HTTP {resp.status_code}")
            logger.error(
                f"Slack API error posting review card for kudos #{kudos.id}: {error}"
            )
            return False, error, None, None
    except Exception as e:
        logger.error(
            f"Network error posting review card for kudos #{kudos.id}: {str(e)}"
        )
        return False, str(e), None, None


async def update_slack_mentor_message(kudos: Kudos, action_description: str) -> bool:
    """
    Updates the existing mentor review message in Slack to remove the buttons
    and show the current status and who performed the action.
    """
    if not settings.slack_bot_token or not kudos.slack_message_channel or not kudos.slack_message_ts:
        return False

    recipient_display, fallback_recipient = format_recipient_display(kudos)
    quoted_message = "\n> ".join(kudos.message.strip().splitlines())

    status_icon = "🦦"
    if kudos.slack_status == "sent":
        status_icon = "✅"
    elif kudos.slack_status == "rejected":
        status_icon = "❌"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{status_icon} Kudos Reviewed",
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
                    "text": action_description,
                }
            ],
        },
        {"type": "divider"},
    ]

    payload = {
        "channel": kudos.slack_message_channel,
        "ts": kudos.slack_message_ts,
        "text": f"Kudos #{kudos.id} was updated: {action_description}",
        "blocks": blocks,
    }

    headers = {
        "Authorization": f"Bearer {settings.slack_bot_token.strip()}",
        "Content-Type": "application/json; charset=utf-8",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://slack.com/api/chat.update",
                json=payload,
                headers=headers,
            )
            data = resp.json()
            if data.get("ok") is True:
                return True
            logger.error(f"Slack API error updating mentor message for kudos #{kudos.id}: {data.get('error')}")
            return False
    except Exception as e:
        logger.error(f"Network error updating mentor message for kudos #{kudos.id}: {str(e)}")
        return False


def verify_slack_signature(
    body: bytes,
    timestamp: Optional[str],
    signature: Optional[str],
) -> bool:
    """
    Verifies that a webhook request was genuinely sent from Slack using HMAC-SHA256.
    """
    if not settings.slack_signing_secret:
        # If no signing secret is configured in development, allow requests with warning
        logger.warning(
            "SLACK_SIGNING_SECRET is not set; skipping webhook signature verification."
        )
        return True

    if not timestamp or not signature:
        return False

    # Prevent replay attacks (> 5 minutes old)
    try:
        current_time = int(time.time())
        req_time = int(timestamp)
        if abs(current_time - req_time) > 60 * 5:
            logger.warning("Slack webhook timestamp out of acceptable window (> 5 min).")
            return False
    except ValueError:
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}".encode("utf-8")
    secret = settings.slack_signing_secret.strip().encode("utf-8")
    my_signature = (
        "v0=" + hmac.new(secret, sig_basestring, hashlib.sha256).hexdigest()
    )

    return hmac.compare_digest(my_signature, signature)
