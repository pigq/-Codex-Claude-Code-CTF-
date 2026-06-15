from fastapi.testclient import TestClient

from codex_session_patcher import __version__
from web.backend.main import app


def test_web_version_endpoint_returns_package_version():
    client = TestClient(app)

    response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json() == {"version": __version__}
