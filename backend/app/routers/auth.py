import urllib.parse
from typing import Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from backend.app.auth import (
    check_google_group_membership,
    create_session_token,
    get_optional_mentor,
)
from backend.app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthConfigResponse(BaseModel):
    configured: bool
    allowed_group: Optional[str] = None
    dev_mode: bool


class UserProfileResponse(BaseModel):
    authenticated: bool
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    role: Optional[str] = None


@router.get("/config", response_model=AuthConfigResponse)
async def get_auth_config():
    return AuthConfigResponse(
        configured=bool(settings.google_client_id and settings.google_client_secret),
        allowed_group=settings.allowed_google_group,
        dev_mode=bool(settings.dev_mode or not settings.google_client_id),
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(user: Optional[dict] = Depends(get_optional_mentor)):
    if not user:
        return UserProfileResponse(authenticated=False)
    return UserProfileResponse(
        authenticated=True,
        email=user.get("email"),
        name=user.get("name"),
        picture=user.get("picture"),
        role=user.get("role"),
    )


@router.get("/login")
async def google_login(request: Request):
    if not settings.google_client_id or not settings.google_client_secret:
        # If in dev mode and not configured, redirect with notice
        if settings.dev_mode or not settings.google_client_id:
            return RedirectResponse(url="/mentors?dev_mode=true")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured on the server. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env",
        )

    # Determine redirect URI
    redirect_uri = settings.google_redirect_uri
    if not redirect_uri:
        # Auto-compute from request URL
        base_url = str(request.base_url).rstrip("/")
        redirect_uri = f"{base_url}/api/auth/callback"

    scopes = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/admin.directory.group.readonly",
        "https://www.googleapis.com/auth/admin.directory.group.member.readonly",
        "https://www.googleapis.com/auth/cloud-identity.groups.readonly",
    ]

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "online",
        "prompt": "select_account",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def google_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    error: Optional[str] = None,
):
    if error:
        return RedirectResponse(url=f"/mentors?error={urllib.parse.quote(error)}")

    if not code:
        return RedirectResponse(url="/mentors?error=missing_code")

    redirect_uri = settings.google_redirect_uri
    if not redirect_uri:
        base_url = str(request.base_url).rstrip("/")
        redirect_uri = f"{base_url}/api/auth/callback"

    # 1. Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(token_url, data=token_data)
        if token_resp.status_code != 200:
            return RedirectResponse(url="/mentors?error=token_exchange_failed")

        tokens = token_resp.json()
        access_token = tokens.get("access_token")

        # 2. Fetch User Profile
        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code != 200:
            return RedirectResponse(url="/mentors?error=userinfo_failed")

        user_info = userinfo_resp.json()
        user_email = user_info.get("email", "")
        user_name = user_info.get("name", user_email.split("@")[0])
        user_picture = user_info.get("picture")

    # 3. Check Google Group Authorization & Whitelist
    target_group = settings.allowed_google_group or "mentors"
    is_member, error_detail = await check_google_group_membership(
        access_token=access_token,
        user_email=user_email,
        allowed_group=target_group,
    )
    if not is_member:
        error_msg = error_detail or f"Access denied: {user_email} is not authorized for {target_group}."
        return RedirectResponse(url=f"/mentors?error={urllib.parse.quote(error_msg)}")

    # 4. Create Session Token and Set Cookie
    session_token = create_session_token(
        {
            "email": user_email,
            "name": user_name,
            "picture": user_picture,
        }
    )

    redirect_response = RedirectResponse(url="/mentors", status_code=status.HTTP_302_FOUND)
    redirect_response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=True,
        max_age=settings.session_expire_hours * 3600,
        samesite="lax",
    )
    return redirect_response


@router.post("/dev-login")
async def dev_mock_login(response: Response):
    """
    Mock login endpoint for local testing when Google credentials are not yet configured.
    """
    if not (settings.dev_mode or not settings.google_client_id):
        raise HTTPException(status_code=403, detail="Dev login is disabled in production.")

    group_hint = settings.allowed_google_group or "mentors@team1619.net"
    session_token = create_session_token(
        {
            "email": "mentor.lead@team1619.net",
            "name": "Mentor Lead (Dev)",
            "picture": None,
        }
    )

    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=True,
        max_age=settings.session_expire_hours * 3600,
        samesite="lax",
    )
    return {
        "success": True,
        "message": f"Logged in as mock mentor (Member of {group_hint})",
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=settings.session_cookie_name)
    return {"success": True, "message": "Logged out successfully"}
