import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api_client import DocFusionApiClient


def test_api_client_multipart_escapes_unsafe_filename(tmp_path, monkeypatch):
    unsafe = tmp_path / "quote;name.docx"
    unsafe.write_bytes(b"payload")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        captured["body"] = request.data.decode("utf-8", errors="replace")
        return FakeResponse()

    monkeypatch.setenv("DOCFUSION_API_TOKEN", "token")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    DocFusionApiClient(base_url="http://example.test/api", project_root=tmp_path)._upload("/documents", unsafe)

    assert 'filename="quote%3Bname.docx"' in captured["body"]
    assert "filename*=UTF-8''quote%3Bname.docx" in captured["body"]
    assert 'filename="quote;name.docx"' not in captured["body"]


def test_api_client_multipart_header_value_removes_crlf():
    header = DocFusionApiClient._multipart_content_disposition("file", 'bad"\r\nX-Bad: yes.docx')

    assert "%0D%0A" in header
    assert "X-Bad: yes" not in header
