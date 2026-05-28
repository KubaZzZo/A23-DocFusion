"""Small HTTP client for the DocFusion FastAPI backend."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from project_paths import resolve_project_root


class ApiError(RuntimeError):
    pass


class DocFusionApiClient:
    def __init__(
        self,
        base_url: str = "https://docx.zhuoruan.xyz/api",
        project_root: Path | None = None,
        timeout: float = 20,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.project_root = project_root or resolve_project_root()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health", auth=False)

    def statistics(self) -> dict[str, Any]:
        return self._request("GET", "/statistics")

    def documents(self, page: int = 1, limit: int = 100) -> list[dict[str, Any]]:
        return self._request("GET", "/documents", params={"page": page, "limit": limit})

    def upload_document(self, path: str | Path) -> dict[str, Any]:
        return self._upload("/documents/upload", path)

    def parse_document(self, doc_id: int) -> dict[str, Any]:
        return self._request("POST", f"/documents/parse/{doc_id}")

    def extract_document(self, doc_id: int, force: bool = False) -> dict[str, Any]:
        return self._request("POST", f"/documents/extract/{doc_id}", params={"force": str(force).lower()})

    def command_document(self, doc_id: int, command: str) -> dict[str, Any]:
        return self._request("POST", "/documents/command", data={"doc_id": doc_id, "command": command})

    def delete_document(self, doc_id: int) -> dict[str, Any]:
        return self._request("DELETE", f"/documents/{doc_id}")

    def entities(
        self,
        doc_id: int | None = None,
        keyword: str | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"page": page, "limit": limit}
        if doc_id:
            params["doc_id"] = doc_id
        if keyword:
            params["keyword"] = keyword
        return self._request("GET", "/entities", params=params)

    def upload_template(self, path: str | Path) -> dict[str, Any]:
        return self._upload("/templates/upload", path)

    def fill_template(self, template_id: int, document_ids: list[int] | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            "/templates/fill",
            data={"template_id": template_id, "document_ids": document_ids or []},
        )

    def fill_status(self, task_id: int) -> dict[str, Any]:
        return self._request("GET", f"/templates/fill/{task_id}")

    def articles(self, page: int = 1, limit: int = 50) -> list[dict[str, Any]]:
        return self._request("GET", "/articles", params={"page": page, "limit": limit})

    def article_detail(self, article_id: int) -> dict[str, Any]:
        return self._request("GET", f"/articles/{article_id}")

    def download_document(self, doc_id: int, destination: str | Path) -> Path:
        url = self._url(f"/documents/{doc_id}/download")
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {self._token()}"}, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=max(self.timeout, 60)) as response:
                payload = response.read()
                filename = self._filename_from_disposition(response.headers.get("Content-Disposition")) or f"document-{doc_id}.docx"
        except urllib.error.HTTPError as exc:
            raise ApiError(self._format_http_error(exc)) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"Cannot connect to backend service: {exc.reason}") from exc

        target = Path(destination)
        if target.is_dir():
            target = target / filename
        target.write_bytes(payload)
        return target

    def export_entities(
        self,
        destination: str | Path,
        fmt: str = "csv",
        doc_id: int | None = None,
        keyword: str | None = None,
    ) -> Path:
        params: dict[str, Any] = {"fmt": fmt}
        if doc_id:
            params["doc_id"] = doc_id
        if keyword:
            params["keyword"] = keyword
        url = self._url("/entities/export", params=params)
        headers = {"Authorization": f"Bearer {self._token()}"}
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=max(self.timeout, 60)) as response:
                payload = response.read()
                filename = self._filename_from_disposition(response.headers.get("Content-Disposition")) or f"entities.{fmt}"
        except urllib.error.HTTPError as exc:
            raise ApiError(self._format_http_error(exc)) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"无法连接后端服务：{exc.reason}") from exc

        target = Path(destination)
        if target.is_dir():
            target = target / filename
        target.write_bytes(payload)
        return target

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> Any:
        url = self._url(path, params)
        body = None if data is None else json.dumps(data).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if auth:
            headers["Authorization"] = f"Bearer {self._token()}"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
                if not payload:
                    return {}
                return json.loads(payload.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ApiError(self._format_http_error(exc)) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"无法连接后端服务：{exc.reason}") from exc
        except TimeoutError as exc:
            raise ApiError("后端服务响应超时") from exc

    def _upload(self, path: str, file_path: str | Path) -> dict[str, Any]:
        source = Path(file_path)
        if not source.exists():
            raise ApiError(f"文件不存在：{source}")

        boundary = "----DocFusionQtBoundary7MA4YWxkTrZu0gW"
        content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        file_bytes = source.read_bytes()
        body = b"".join(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="file"; filename="{source.name}"\r\n'.encode("utf-8"),
                f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                file_bytes,
                f"\r\n--{boundary}--\r\n".encode("utf-8"),
            ]
        )
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        }
        request = urllib.request.Request(self._url(path), data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=max(self.timeout, 60)) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ApiError(self._format_http_error(exc)) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"无法连接后端服务：{exc.reason}") from exc

    def _url(self, path: str, params: dict[str, Any] | None = None) -> str:
        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if query:
                url = f"{url}?{query}"
        return url

    def _token(self) -> str:
        env_token = os.getenv("DOCFUSION_API_TOKEN", "").strip()
        if env_token:
            return env_token
        token_file = self.project_root / "data" / "api_token.txt"
        if token_file.exists():
            return token_file.read_text(encoding="utf-8").strip()
        raise ApiError("找不到 API token。请先启动主程序或运行后端服务生成本地 token。")

    @staticmethod
    def _filename_from_disposition(value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r'filename="?([^";]+)"?', value)
        return match.group(1) if match else None

    @staticmethod
    def _format_http_error(exc: urllib.error.HTTPError) -> str:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(detail)
            if isinstance(payload, dict) and "detail" in payload:
                detail = str(payload["detail"])
        except json.JSONDecodeError:
            pass
        return f"接口请求失败 HTTP {exc.code}: {detail}"
