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
        base_url: str = "http://186.241.72.140:8000/api",
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

    def documents(self, page: int = 1, limit: int = 100, q: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"page": page, "limit": limit}
        if q:
            params["q"] = q
        return self._request("GET", "/documents", params=params)

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
        entity_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"page": page, "limit": limit}
        if doc_id:
            params["doc_id"] = doc_id
        if keyword:
            params["keyword"] = keyword
        if entity_type:
            params["entity_type"] = entity_type
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return self._request("GET", "/entities", params=params)

    def search(
        self,
        keyword: str,
        entity_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"keyword": keyword, "page": page, "limit": limit}
        if entity_type:
            params["entity_type"] = entity_type
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return self._request("GET", "/search", params=params)

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

    def document_versions(self, doc_id: int) -> list[dict[str, Any]]:
        return self._request("GET", f"/documents/{doc_id}/versions")

    def download_document_version(self, doc_id: int, version_id: int, destination: str | Path) -> Path:
        url = self._url(f"/documents/{doc_id}/versions/{version_id}/download")
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {self._token()}"}, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=max(self.timeout, 60)) as response:
                payload = response.read()
                filename = self._filename_from_disposition(response.headers.get("Content-Disposition")) or f"document-{doc_id}-v{version_id}.docx"
        except urllib.error.HTTPError as exc:
            raise ApiError(self._format_http_error(exc)) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"Cannot connect to backend service: {exc.reason}") from exc

        target = Path(destination)
        if target.is_dir():
            target = target / filename
        target.write_bytes(payload)
        return target

    def rollback_document_version(self, doc_id: int, version_id: int) -> dict[str, Any]:
        return self._request("POST", f"/documents/{doc_id}/versions/{version_id}/rollback")

    def batch_process_documents(self, paths: list[str | Path], destination: str | Path) -> dict[str, Any]:
        result = self._upload_many("/batch/process", paths)
        download_url = result.get("download_url")
        if not download_url:
            raise ApiError("Batch response did not include a report download URL")
        if isinstance(download_url, str) and download_url.startswith("/api/"):
            download_url = download_url[len("/api"):]
        report_path = self._download_path(
            str(download_url),
            destination,
            default_filename=result.get("report_filename") or "batch_report.xlsx",
        )
        result["report_path"] = str(report_path)
        return result

    def export_entities(
        self,
        destination: str | Path,
        fmt: str = "csv",
        doc_id: int | None = None,
        keyword: str | None = None,
        entity_type: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> Path:
        params: dict[str, Any] = {"fmt": fmt}
        if doc_id:
            params["doc_id"] = doc_id
        if keyword:
            params["keyword"] = keyword
        if entity_type:
            params["entity_type"] = entity_type
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
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
                f"{self._multipart_content_disposition('file', source.name)}\r\n".encode("utf-8"),
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

    def _upload_many(self, path: str, file_paths: list[str | Path]) -> dict[str, Any]:
        boundary = "----DocFusionQtBatchBoundary7MA4YWxkTrZu0gW"
        parts: list[bytes] = []
        for file_path in file_paths:
            source = Path(file_path)
            if not source.exists():
                raise ApiError(f"File does not exist: {source}")
            content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
            parts.extend(
                [
                    f"--{boundary}\r\n".encode("utf-8"),
                    f"{self._multipart_content_disposition('files', source.name)}\r\n".encode("utf-8"),
                    f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                    source.read_bytes(),
                    b"\r\n",
                ]
            )
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        }
        request = urllib.request.Request(self._url(path), data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=max(self.timeout, 120)) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ApiError(self._format_http_error(exc)) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"Cannot connect to backend service: {exc.reason}") from exc

    def _download_path(self, path: str, destination: str | Path, default_filename: str) -> Path:
        request = urllib.request.Request(self._url(path), headers={"Authorization": f"Bearer {self._token()}"}, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=max(self.timeout, 60)) as response:
                payload = response.read()
                filename = self._filename_from_disposition(response.headers.get("Content-Disposition")) or default_filename
        except urllib.error.HTTPError as exc:
            raise ApiError(self._format_http_error(exc)) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"Cannot connect to backend service: {exc.reason}") from exc

        target = Path(destination)
        if target.is_dir():
            target = target / filename
        target.write_bytes(payload)
        return target

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
            return token_file.read_text(encoding="utf-8-sig").strip()
        raise ApiError("找不到 API token。请先启动主程序或运行后端服务生成本地 token。")

    @staticmethod
    def _filename_from_disposition(value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r'filename="?([^";]+)"?', value)
        return match.group(1) if match else None

    @staticmethod
    def _multipart_content_disposition(field_name: str, filename: str) -> str:
        safe_field = urllib.parse.quote(str(field_name), safe="")
        safe_filename = urllib.parse.quote(Path(str(filename)).name, safe="")
        return (
            f'Content-Disposition: form-data; name="{safe_field}"; '
            f'filename="{safe_filename}"; filename*=UTF-8\'\'{safe_filename}'
        )

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
