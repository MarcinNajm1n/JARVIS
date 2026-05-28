from types import SimpleNamespace

from fastapi.testclient import TestClient

from src import web_app


class FakeAsyncClient:
    response = SimpleNamespace(
        status_code=200,
        headers={"content-type": "image/png", "content-length": "4"},
        content=b"png!",
    )

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        return self.response


def test_image_proxy_rejects_localhost():
    assert not web_app._is_safe_remote_image_url("http://localhost/image.png")
    assert not web_app._is_safe_remote_image_url("http://127.0.0.1/image.png")
    assert not web_app._is_safe_remote_image_url("file:///tmp/image.png")


def test_image_proxy_accepts_safe_http_url(monkeypatch):
    monkeypatch.setattr(web_app.socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))])

    assert web_app._is_safe_remote_image_url("https://example.com/image.png")


def test_image_proxy_returns_image(monkeypatch):
    monkeypatch.setattr(web_app, "_is_safe_remote_image_url", lambda url: True)
    monkeypatch.setattr(web_app.httpx, "AsyncClient", FakeAsyncClient)

    response = TestClient(web_app.app).get("/api/image-proxy", params={"url": "https://example.com/image.png"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"png!"


def test_image_proxy_rejects_non_image(monkeypatch):
    class FakeTextClient(FakeAsyncClient):
        response = SimpleNamespace(
            status_code=200,
            headers={"content-type": "text/html", "content-length": "5"},
            content=b"hello",
        )

    monkeypatch.setattr(web_app, "_is_safe_remote_image_url", lambda url: True)
    monkeypatch.setattr(web_app.httpx, "AsyncClient", FakeTextClient)

    response = TestClient(web_app.app).get("/api/image-proxy", params={"url": "https://example.com/page"})

    assert response.status_code == 502


def test_image_proxy_rejects_redirect(monkeypatch):
    class FakeRedirectClient(FakeAsyncClient):
        response = SimpleNamespace(
            status_code=302,
            headers={"location": "http://127.0.0.1/private.png"},
            content=b"",
        )

    monkeypatch.setattr(web_app, "_is_safe_remote_image_url", lambda url: True)
    monkeypatch.setattr(web_app.httpx, "AsyncClient", FakeRedirectClient)

    response = TestClient(web_app.app).get(
        "/api/image-proxy",
        params={"url": "https://example.com/image.png"},
    )

    assert response.status_code == 502
