"""Tests for Cascade Lite. Run with: make test"""
import os, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")  # isolated DB per run

from fastapi.testclient import TestClient   # noqa: E402
import main                                  # noqa: E402

client = TestClient(main.app)


def test_health_and_ready():
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/readyz").json() == {"ready": True}


def test_paint_then_read_back():
    r = client.post("/api/paint", json={"x": 3, "y": 4, "color": "#4fd1c5"})
    assert r.status_code == 200 and r.json()["ok"] is True
    canvas = client.get("/api/canvas").json()
    assert {"x": 3, "y": 4, "color": "#4fd1c5"} in canvas["pixels"]


def test_out_of_bounds_is_rejected():
    r = client.post("/api/paint", json={"x": 999, "y": 0, "color": "#ffffff"})
    assert r.status_code == 400 and r.json()["ok"] is False


def test_bad_color_is_rejected():
    r = client.post("/api/paint", json={"x": 1, "y": 1, "color": "notacolor"})
    assert r.status_code == 400


def test_metrics_exposed():
    body = client.get("/metrics").text
    assert "cascade_paints_total" in body
    assert "cascade_paint_errors_total" in body
