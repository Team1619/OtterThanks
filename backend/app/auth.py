import logging
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
import httpx
import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from backend.app.config import settings

logger = logging.getLogger("otterthanks.auth")
logging.basicConfig(level=logging.INFO)

JWT_ALGORITHM = "HS256"


class UserSession(BaseModel):
    email: str
    name: str
    picture: Optional[str] = None
    role: str = "mentor"
    exp: Optional[int] = None


def create_session_token(user_data: Dict[str, Any]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.session_expire_hours)
    to_encode = user_data.copy()
    to_encode.update({"exp": int(expire.timestamp()), "role": "mentor"})
    encoded_jwt = jwt.encode(to_encode, settings.session_secret_key, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_session_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(
            token, settings.session_secret_key, algorithms=[JWT_ALGORITHM]
        )
        return payload
    except (jwt.PyJWTError, Exception):
        return None


async def get_current_mentor(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    # Check cookie first, then Authorization header
    token = request.cookies.get(settings.session_cookie_name)
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mentor authentication required",
        )

    payload = decode_session_token(token)
    if not payload or payload.get("role") != "mentor":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    return payload


async def get_optional_mentor(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        return None

    return decode_session_token(token)


async def check_google_group_membership(
    access_token: str, user_email: str, allowed_group: str
) -> Tuple[bool, Optional[str]]:
    """
    Checks if user_email is authorized as a mentor:
    1. Checks if user_email is in ALLOWED_MENTOR_EMAILS (.env).
    2. Checks Google Directory API hasMember (with member.readonly scope).
    3. Checks Google Directory API member resource directly.
    4. Checks Google Directory API user groups list.
    5. Checks Google Cloud Identity transitive membership API.
    Returns (is_authorized, error_detail).
    """
    clean_group = allowed_group.strip().lower()
    clean_email = user_email.strip().lower()

    # 1. Direct whitelist check from ALLOWED_MENTOR_EMAILS
    if settings.allowed_mentor_emails:
        whitelist = [
            e.strip().lower()
            for e in settings.allowed_mentor_emails.split(",")
            if e.strip()
        ]
        if clean_email in whitelist:
            logger.info(
                f"User {clean_email} authorized via ALLOWED_MENTOR_EMAILS whitelist."
            )
            return True, None

    headers = {"Authorization": f"Bearer {access_token}"}
    errors = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Method A: Google Admin Directory API hasMember
        # Requires: admin.directory.group.member.readonly
        has_member_url = f"https://admin.googleapis.com/admin/directory/v1/groups/{clean_group}/hasMember/{clean_email}"
        try:
            resp = await client.get(has_member_url, headers=headers)
            logger.info(f"Google Directory hasMember status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("isMember") is True:
                    logger.info(f"User {clean_email} verified in {clean_group} via hasMember.")
                    return True, None
                else:
                    logger.info(f"User {clean_email} reported isMember=false for {clean_group}.")
            else:
                errors.append(f"hasMember ({resp.status_code}): {resp.text}")
        except Exception as e:
            errors.append(f"hasMember exception: {str(e)}")

        # Method B: Google Admin Directory API member get
        # GET https://admin.googleapis.com/admin/directory/v1/groups/{groupKey}/members/{memberKey}
        get_member_url = f"https://admin.googleapis.com/admin/directory/v1/groups/{clean_group}/members/{clean_email}"
        try:
            resp = await client.get(get_member_url, headers=headers)
            logger.info(f"Google Directory member get status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("id") or data.get("email"):
                    logger.info(f"User {clean_email} verified in {clean_group} via member get.")
                    return True, None
            else:
                errors.append(f"member get ({resp.status_code}): {resp.text}")
        except Exception as e:
            errors.append(f"member get exception: {str(e)}")

        # Method C: Google Cloud Identity transitive membership check
        # GET https://cloudidentity.googleapis.com/v1/groups/-/memberships:checkTransitiveMembership?query=...
        ci_query = f"member_key_id=='{clean_email}'&&group_key_id=='{clean_group}'"
        ci_url = f"https://cloudidentity.googleapis.com/v1/groups/-/memberships:checkTransitiveMembership?query={urllib.parse.quote(ci_query)}"
        try:
            resp = await client.get(ci_url, headers=headers)
            logger.info(f"Cloud Identity checkTransitiveMembership status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("hasMembership") is True:
                    logger.info(
                        f"User {clean_email} verified in {clean_group} via Cloud Identity."
                    )
                    return True, None
            else:
                errors.append(f"Cloud Identity ({resp.status_code}): {resp.text}")
        except Exception as e:
            errors.append(f"Cloud Identity exception: {str(e)}")

        # Method D: List groups for user
        list_groups_url = f"https://admin.googleapis.com/admin/directory/v1/groups?userKey={clean_email}"
        try:
            resp = await client.get(list_groups_url, headers=headers)
            logger.info(f"Google Directory list groups status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                groups = data.get("groups", [])
                for g in groups:
                    group_email = g.get("email", "").lower()
                    if group_email == clean_group:
                        logger.info(
                            f"User {clean_email} verified in {clean_group} via group list."
                        )
                        return True, None
            else:
                errors.append(f"list groups ({resp.status_code}): {resp.text}")
        except Exception as e:
            errors.append(f"list groups exception: {str(e)}")

    logger.warning(
        f"All Google API group checks failed for {clean_email} in {clean_group}. Details: {' | '.join(errors)}"
    )

    # Check if permission denied was the cause
    is_perm_error = any("403" in err or "Not Authorized" in err or "Insufficient" in err for err in errors)
    if is_perm_error:
        hint = (
            f"Google Workspace returned a permissions error when checking {clean_group}. "
            f"Non-admin users usually cannot call the Admin SDK Directory API with their user tokens. "
            f"Add your email ({clean_email}) to ALLOWED_MENTOR_EMAILS in .env to grant immediate mentor access."
        )
        return False, hint

    return False, f"User {clean_email} is not recognized as a member of {clean_group}."
