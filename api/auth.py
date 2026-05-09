"""Local API authentication helpers."""
import hmac
import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import DATA_DIR

TOKEN_ENV_VAR = "DOCFUSION_API_TOKEN"
TOKEN_FILE = DATA_DIR / "api_token.txt"
LOCAL_CLIENTS = {"127.0.0.1", "::1", "localhost", "testclient"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
TRUSTED_ORIGIN_HOSTS = {"127.0.0.1", "localhost"}

bearer_scheme = HTTPBearer(auto_error=False)


def get_api_token(token_file: Path = TOKEN_FILE) -> str:
    """Return the configured local API bearer token, creating one if needed."""
    env_token = os.getenv(TOKEN_ENV_VAR, "").strip()
    if env_token:
        return env_token

    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()

    token_file.parent.mkdir(exist_ok=True)
    token = secrets.token_urlsafe(32)
    token_file.write_text(token, encoding="utf-8")
    try:
        os.chmod(token_file, 0o600)
    except OSError:
        pass
    return token


def _is_local_client(request: Request) -> bool:
    client = request.client
    return bool(client and client.host in LOCAL_CLIENTS)


def _is_trusted_origin(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and parsed.hostname in TRUSTED_ORIGIN_HOSTS


def _validate_browser_origin(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return

    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if origin and not _is_trusted_origin(origin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Untrusted request origin")
    if not origin and referer and not _is_trusted_origin(referer):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Untrusted request referer")


async def require_local_bearer_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    """Require loopback access and the local bearer token for API endpoints."""
    if not _is_local_client(request):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API access is limited to localhost")
    _validate_browser_origin(request)

    expected = get_api_token()
    supplied = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else ""
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API token")
