"""
YouTube OAuth 2.0 authentication flow.
"""
import base64
import hashlib
import hmac
import secrets
import time
from typing import Optional, Tuple
from app.core.config import settings


class YouTubeAuth:
    """Handles YouTube OAuth 2.0 flow for channel authorization."""
    STATE_TTL_SECONDS = 900

    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube",
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
    ]

    def __init__(self):
        self.client_id = settings.YOUTUBE_CLIENT_ID
        self.client_secret = settings.YOUTUBE_CLIENT_SECRET
        self.redirect_uri = settings.YOUTUBE_REDIRECT_URI

    def _state_secret(self) -> bytes:
        """
        Secret used to sign OAuth state.
        Prefer ENCRYPTION_KEY; fallback to OAuth client secret.
        """
        secret = settings.ENCRYPTION_KEY or self.client_secret
        if not secret:
            raise ValueError("ENCRYPTION_KEY (or YOUTUBE_CLIENT_SECRET) must be set for OAuth state validation")
        return secret.encode() if isinstance(secret, str) else secret

    def _sign_state_payload(self, payload: str) -> str:
        signature = hmac.new(self._state_secret(), payload.encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(signature).decode().rstrip("=")

    def generate_state(self) -> str:
        """Generate signed OAuth state with timestamp and random nonce."""
        issued_at = int(time.time())
        nonce = secrets.token_urlsafe(24)
        payload = f"{issued_at}.{nonce}"
        signature = self._sign_state_payload(payload)
        return f"{payload}.{signature}"

    def validate_state(self, state: str) -> bool:
        """Validate OAuth state signature and expiry window."""
        parts = (state or "").split(".")
        if len(parts) != 3:
            return False

        issued_at_raw, nonce, signature = parts
        if not issued_at_raw.isdigit() or not nonce or not signature:
            return False

        issued_at = int(issued_at_raw)
        now = int(time.time())

        # Basic clock skew tolerance and max age check.
        if issued_at > now + 60:
            return False
        if now - issued_at > self.STATE_TTL_SECONDS:
            return False

        payload = f"{issued_at_raw}.{nonce}"
        expected_signature = self._sign_state_payload(payload)
        return hmac.compare_digest(signature, expected_signature)

    def get_auth_url(self) -> str:
        """Generate OAuth consent URL for the user."""
        if not self.client_id or not self.client_secret:
            raise ValueError("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set")
        if not settings.ENCRYPTION_KEY:
            raise ValueError("ENCRYPTION_KEY must be set before connecting a YouTube channel")

        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=self.SCOPES,
        )
        flow.redirect_uri = self.redirect_uri

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=self.generate_state(),
        )
        return auth_url

    def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for tokens."""
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=self.SCOPES,
        )
        flow.redirect_uri = self.redirect_uri
        flow.fetch_token(code=code)

        credentials = flow.credentials
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }

    def refresh_access_token(self, refresh_token: str) -> Tuple[str, Optional[str]]:
        """Refresh an expired access token."""
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_uri="https://oauth2.googleapis.com/token",
        )
        creds.refresh(Request())
        expiry = creds.expiry.isoformat() if creds.expiry else None
        return creds.token, expiry

    def get_channel_info(self, access_token: str) -> dict:
        """Fetch channel info using access token."""
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials

        creds = Credentials(token=access_token)
        youtube = build("youtube", "v3", credentials=creds)
        response = youtube.channels().list(part="snippet,statistics", mine=True).execute()

        items = response.get("items", [])
        if not items:
            raise ValueError("No YouTube channel found for this account")

        channel = items[0]
        return {
            "channel_id": channel["id"],
            "channel_title": channel["snippet"]["title"],
            "subscriber_count": channel["statistics"].get("subscriberCount", "0"),
            "video_count": channel["statistics"].get("videoCount", "0"),
        }

    @staticmethod
    def encrypt_token(token: str) -> str:
        """Encrypt a token for storage."""
        key = settings.ENCRYPTION_KEY
        if not key:
            raise ValueError("ENCRYPTION_KEY must be set to store YouTube tokens securely")
        from cryptography.fernet import Fernet
        f = Fernet(key.encode() if isinstance(key, str) else key)
        return f.encrypt(token.encode()).decode()

    @staticmethod
    def decrypt_token(encrypted_token: str) -> str:
        """Decrypt a stored token."""
        key = settings.ENCRYPTION_KEY
        if not key:
            raise ValueError("ENCRYPTION_KEY must be set to decrypt YouTube tokens securely")
        from cryptography.fernet import Fernet
        f = Fernet(key.encode() if isinstance(key, str) else key)
        return f.decrypt(encrypted_token.encode()).decode()
