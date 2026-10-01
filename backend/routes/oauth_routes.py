"""
OAuth2 routes for Google and GitHub social login.

Flow:
  1. Frontend redirects browser to  GET /api/auth/{provider}
  2. Backend redirects to provider consent screen
  3. Provider redirects to  GET /api/auth/{provider}/callback
  4. Backend exchanges code for token, fetches user info,
     finds-or-creates local user, issues JWT,
     redirects to frontend /auth/callback?token=...
"""
from __future__ import annotations

import secrets
import urllib.parse
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import create_access_token, hash_password
from ..config import (
    BACKEND_URL,
    FRONTEND_URL,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    SECRET_KEY,
)
from ..database import SessionLocal
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["oauth"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATE_COOKIE = "archvision_oauth_state"


def _generate_state() -> str:
    """Generate a random state parameter for CSRF protection."""
    return secrets.token_urlsafe(32)


def _get_db() -> Session:
    return SessionLocal()


def _find_or_create_user(db: Session, email: str, full_name: str) -> User:
    """Return existing user by email, or create a new one for OAuth login."""
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user

    # Create new user with a random un-guessable password (OAuth-only)
    random_pw = secrets.token_urlsafe(32)
    user = User(
        email=email,
        hashed_password=hash_password(random_pw),
        full_name=full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _issue_jwt_and_redirect(user: User) -> RedirectResponse:
    """Issue a JWT and redirect the browser to the frontend callback page."""
    token = create_access_token({"sub": str(user.id)})
    redirect_url = f"{FRONTEND_URL}/auth/callback?token={urllib.parse.quote(token)}"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


def _fail_redirect(message: str) -> RedirectResponse:
    """Redirect to frontend callback with an error message."""
    redirect_url = f"{FRONTEND_URL}/auth/callback?error={urllib.parse.quote(message)}"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


GOOGLE_CALLBACK_PATH = "/api/auth/google/callback"


@router.get("/google")
def google_login(request: Request):
    """Redirect user to Google OAuth consent screen."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )

    state = _generate_state()
    callback_url = f"{BACKEND_URL}{GOOGLE_CALLBACK_PATH}"

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        _STATE_COOKIE, state, httponly=True, max_age=600, samesite="lax"
    )
    return response


@router.get("/google/callback", name="google_callback")
async def google_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Handle Google OAuth callback."""
    if error:
        return _fail_redirect(f"Google login denied: {error}")

    if not code:
        return _fail_redirect("No authorization code received from Google.")

    # Verify state
    cookie_state = request.cookies.get(_STATE_COOKIE)
    if not cookie_state or cookie_state != state:
        return _fail_redirect("Invalid OAuth state. Please try again.")

    callback_url = f"{BACKEND_URL}{GOOGLE_CALLBACK_PATH}"

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": callback_url,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )

    if token_resp.status_code != 200:
        return _fail_redirect("Failed to exchange Google authorization code.")

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        return _fail_redirect("No access token received from Google.")

    # Fetch user info
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if user_resp.status_code != 200:
        return _fail_redirect("Failed to fetch user info from Google.")

    user_info = user_resp.json()
    email = user_info.get("email")
    name = user_info.get("name", email.split("@")[0] if email else "User")

    if not email:
        return _fail_redirect("No email returned from Google account.")

    # Find or create user, issue JWT, redirect
    db = _get_db()
    try:
        user = _find_or_create_user(db, email, name)
        response = _issue_jwt_and_redirect(user)
        response.delete_cookie(_STATE_COOKIE)
        return response
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GitHub OAuth
# ---------------------------------------------------------------------------

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


GITHUB_CALLBACK_PATH = "/api/auth/github/callback"


@router.get("/github")
def github_login(request: Request):
    """Redirect user to GitHub OAuth consent screen."""
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub OAuth is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET.",
        )

    state = _generate_state()
    callback_url = f"{BACKEND_URL}{GITHUB_CALLBACK_PATH}"

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": callback_url,
        "scope": "read:user user:email",
        "state": state,
    }
    auth_url = f"{GITHUB_AUTH_URL}?{urllib.parse.urlencode(params)}"

    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        _STATE_COOKIE, state, httponly=True, max_age=600, samesite="lax"
    )
    return response


@router.get("/github/callback", name="github_callback")
async def github_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Handle GitHub OAuth callback."""
    if error:
        return _fail_redirect(f"GitHub login denied: {error}")

    if not code:
        return _fail_redirect("No authorization code received from GitHub.")

    # Verify state
    cookie_state = request.cookies.get(_STATE_COOKIE)
    if not cookie_state or cookie_state != state:
        return _fail_redirect("Invalid OAuth state. Please try again.")

    callback_url = f"{BACKEND_URL}{GITHUB_CALLBACK_PATH}"

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": callback_url,
            },
            headers={"Accept": "application/json"},
        )

    if token_resp.status_code != 200:
        return _fail_redirect("Failed to exchange GitHub authorization code.")

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        error_desc = token_data.get("error_description", "Unknown error")
        return _fail_redirect(f"GitHub token error: {error_desc}")

    # Fetch user profile
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(GITHUB_USER_URL, headers=headers)

    if user_resp.status_code != 200:
        return _fail_redirect("Failed to fetch user info from GitHub.")

    user_info = user_resp.json()
    email = user_info.get("email")
    name = user_info.get("name") or user_info.get("login", "User")

    # If email is private, fetch from /user/emails
    if not email:
        async with httpx.AsyncClient() as client:
            emails_resp = await client.get(GITHUB_EMAILS_URL, headers=headers)
        if emails_resp.status_code == 200:
            emails = emails_resp.json()
            # Pick primary verified email
            for em in emails:
                if em.get("primary") and em.get("verified"):
                    email = em["email"]
                    break
            # Fallback: any verified email
            if not email:
                for em in emails:
                    if em.get("verified"):
                        email = em["email"]
                        break

    if not email:
        return _fail_redirect("No email found on your GitHub account. Please make your email public or add a verified email.")

    # Find or create user, issue JWT, redirect
    db = _get_db()
    try:
        user = _find_or_create_user(db, email, name)
        response = _issue_jwt_and_redirect(user)
        response.delete_cookie(_STATE_COOKIE)
        return response
    finally:
        db.close()
