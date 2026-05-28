"""Client for the standalone DocFusion server task API."""

from __future__ import annotations

import json
import mimetypes
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_SERVER_TASK_URL = "http://127.0.0.1:8010"


class ServerTaskError(RuntimeError):
    pass


@dataclass(frozen=True)
class ServerTaskConfig:
    base_url: str = DEFAULT_SERVER_TASK_URL
    token: str = ""


def load_server_task_config(path: str | Path, defaults_path: str | Path | None = None) -> ServerTaskConfig:
    payload: dict[str, Any] = {}
    if defaults_path:
        payload.update(_read_config_payload(defaults_path))
    payload.update(_read_config_payload(path))
    return ServerTaskConfig(
        base_url=str(payload.get("base_url") or DEFAULT_SERVER_TASK_URL),
        token=str(payload.get("token") or ""),
    )


def save_server_task_config(config: ServerTaskConfig, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")


def _read_config_payload(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


class ServerTaskClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30):
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        url = self._absolute_url("/healthz")
        request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
        return self._open_json(request)

    def tools(self) -> dict[str, Any]:
        request = urllib.request.Request(
            self._absolute_url("/api/server-tools"),
            headers=self._headers(),
            method="GET",
        )
        return self._open_json(request)

    def submit_instruction(
        self,
        instruction: str,
        files: list[str | Path],
        *,
        priority: str = "normal",
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        fields: dict[str, str] = {"instruction": instruction, "priority": priority}
        if timeout_seconds:
            fields["timeout"] = str(timeout_seconds)
        request = self._multipart_request("/api/server-tasks", fields, files)
        return self._open_json(request, timeout=max(self.timeout, 90))

    def task_status(self, task_id: str) -> dict[str, Any]:
        request = urllib.request.Request(
            self._absolute_url(f"/api/server-tasks/{task_id}"),
            headers=self._headers(),
            method="GET",
        )
        return self._open_json(request)

    def task_logs(self, task_id: str) -> dict[str, Any]:
        request = urllib.request.Request(
            self._absolute_url(f"/api/server-tasks/{task_id}/logs"),
            headers=self._headers(),
            method="GET",
        )
        return self._open_json(request)

    def download_result(self, task_id: str, destination: str | Path) -> Path:
        request = urllib.request.Request(
            self._absolute_url(f"/api/server-tasks/{task_id}/download"),
            headers=self._headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=max(self.timeout, 120)) as response:
                payload = response.read()
                filename = _filename_from_disposition(response.headers.get("Content-Disposition")) or f"{task_id}.bin"
        except urllib.error.HTTPError as exc:
            raise ServerTaskError(_format_http_error(exc)) from exc
        except urllib.error.URLError as exc:
            raise ServerTaskError(f"Cannot connect to server task API: {exc.reason}") from exc

        target = Path(destination)
        if target.is_dir():
            target = target / filename
        target.write_bytes(payload)
        return target

    def _multipart_request(self, path: str, fields: dict[str, str], files: list[str | Path]) -> urllib.request.Request:
        boundary = "----DocFusionServerTaskBoundary7MA4YWxk"
        parts: list[bytes] = []
        for name, value in fields.items():
            parts.extend(
                [
                    f"--{boundary}\r\n".encode("utf-8"),
                    f'Content-Disposition: form-data; name="{_quote_multipart_value(name)}"\r\n\r\n'.encode("utf-8"),
                    str(value).encode("utf-8"),
                    b"\r\n",
                ]
            )
        for file_path in files:
            source = Path(file_path)
            if not source.is_file():
                raise ServerTaskError(f"File not found: {source}")
            content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
            parts.extend(
                [
                    f"--{boundary}\r\n".encode("utf-8"),
                    f"{_multipart_content_disposition('files', source.name)}\r\n".encode("utf-8"),
                    f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                    source.read_bytes(),
                    b"\r\n",
                ]
            )
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)
        headers = self._headers()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        headers["Content-Length"] = str(len(body))
        return urllib.request.Request(self._absolute_url(path), data=body, headers=headers, method="POST")

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise ServerTaskError("Server task token is required")
        return {"Accept": "application/json", "Authorization": f"Bearer {self.token}"}

    def _absolute_url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _open_json(self, request: urllib.request.Request, timeout: float | None = None) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            raise ServerTaskError(_format_http_error(exc)) from exc
        except urllib.error.URLError as exc:
            raise ServerTaskError(f"Cannot connect to server task API: {exc.reason}") from exc
        if not payload:
            return {}
        return json.loads(payload.decode("utf-8"))


def _filename_from_disposition(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r'filename="?([^";]+)"?', value)
    return match.group(1) if match else None


def _quote_multipart_value(value: str) -> str:
    return urllib.parse.quote(str(value), safe="")


def _multipart_content_disposition(field_name: str, filename: str) -> str:
    safe_field = _quote_multipart_value(field_name)
    safe_filename = urllib.parse.quote(Path(str(filename)).name, safe="")
    return (
        f'Content-Disposition: form-data; name="{safe_field}"; '
        f'filename="{safe_filename}"; filename*=UTF-8\'\'{safe_filename}'
    )


def _format_http_error(exc: urllib.error.HTTPError) -> str:
    detail = exc.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(detail)
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            detail = error.get("message") or detail
        elif isinstance(payload, dict) and "detail" in payload:
            detail = str(payload["detail"])
    except json.JSONDecodeError:
        pass
    return f"Server task API failed HTTP {exc.code}: {detail}"
