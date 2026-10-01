"""API tests for auth, analysis jobs and file serving.

The ML pipeline is replaced with a fake so these run in seconds; the real
pipeline is covered by the parsing/geometry tests and by running the app.
"""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from backend import database
from backend.main import app
from backend.routes import analysis_routes, files_routes
from backend.services import pipeline_service

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

FAKE_RESULT = {
    "schema_version": "1.0.0",
    "source": {"type": "image", "file": "plan.png"},
    "pages": [{
        "page_index": 0,
        "summary": {"total_rooms": 2, "rooms_with_labels": 2, "rooms_with_dimensions": 1},
        "rooms": [
            {"id": 1, "label": "Hall", "dimensions": "15'0\" x 12'0\"",
             "area": {"value_sqft": 180.0}, "geometry": {"centroid": {"x": 10, "y": 10}}},
            {"id": 2, "label": "Bedroom", "dimensions": None,
             "area": {"value_sqft": 120.4}, "geometry": {"centroid": {"x": 30, "y": 10}}},
        ],
    }],
}


def fake_analyze_image(image_path, job_id):
    return {
        "result_json": FAKE_RESULT,
        "result_image_path": None,
        "total_rooms": 2,
        "rooms_with_labels": 2,
        "rooms_with_dimensions": 1,
    }


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client with a fresh database, temporary storage and a fake pipeline."""
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)

    uploads, results = tmp_path / "uploads", tmp_path / "results"
    uploads.mkdir()
    results.mkdir()
    monkeypatch.setattr(analysis_routes, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(files_routes, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(files_routes, "RESULTS_DIR", results)
    monkeypatch.setattr(pipeline_service, "analyze_image", fake_analyze_image)

    with TestClient(app) as c:
        yield c


def register(client, email="ada@example.com", password="secret123", name="Ada"):
    r = client.post("/api/auth/register", json={"email": email, "password": password, "full_name": name})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def upload(client, headers, filename="plan.png", content=PNG_BYTES):
    return client.post("/api/analyze", files={"file": (filename, content, "image/png")}, headers=headers)


def wait_for_job(client, headers, job_id, timeout=10.0):
    """Analysis runs in a background thread; poll until it finishes."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/analyses/{job_id}", headers=headers).json()
        if job["status"] != "processing":
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} still processing after {timeout}s")


# --- health & auth ---------------------------------------------------------

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_login_and_profile(client):
    headers = register(client)
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"
    assert me.json()["full_name"] == "Ada"

    login = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "secret123"})
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_duplicate_email_is_rejected(client):
    register(client)
    r = client.post("/api/auth/register", json={"email": "ada@example.com", "password": "other123", "full_name": "A"})
    assert r.status_code == 409


def test_wrong_password_is_rejected(client):
    register(client)
    r = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "wrong-password"})
    assert r.status_code == 401


def test_short_password_is_rejected(client):
    r = client.post("/api/auth/register", json={"email": "bob@example.com", "password": "123", "full_name": "Bob"})
    assert r.status_code == 422


@pytest.mark.parametrize("method,path", [
    ("get", "/api/auth/me"),
    ("get", "/api/analyses"),
    ("get", "/api/dashboard"),
    ("post", "/api/analyze"),
])
def test_protected_endpoints_require_a_token(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_invalid_token_is_rejected(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


# --- analysis lifecycle ----------------------------------------------------

def test_image_analysis_full_lifecycle(client):
    headers = register(client)

    r = upload(client, headers)
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]
    job = wait_for_job(client, headers, job_id)
    assert job["status"] == "completed"
    assert job["total_rooms"] == 2
    assert job["rooms_with_labels"] == 2

    listing = client.get("/api/analyses", headers=headers).json()
    assert listing["total"] == 1
    assert [a["id"] for a in listing["analyses"]] == [job_id]

    detail = client.get(f"/api/analyses/{job_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["result_json"]["pages"][0]["rooms"][0]["label"] == "Hall"

    download = client.get(f"/api/analyses/{job_id}/download", headers=headers)
    assert download.status_code == 200
    assert "plan_result.json" in download.headers["content-disposition"]
    assert download.json() == FAKE_RESULT

    summary = client.get(f"/api/analyses/{job_id}/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["total_area_sqft"] == 300  # 180.0 + 120.4, rounded

    stats = client.get("/api/dashboard", headers=headers).json()
    assert stats["total_analyses"] == 1
    assert stats["completed_analyses"] == 1
    assert stats["total_rooms_detected"] == 2

    assert client.delete(f"/api/analyses/{job_id}", headers=headers).status_code == 204
    assert client.get(f"/api/analyses/{job_id}", headers=headers).status_code == 404


def test_users_cannot_see_each_others_analyses(client):
    alice = register(client, "alice@example.com")
    bob = register(client, "bob@example.com")
    job_id = upload(client, alice).json()["id"]
    wait_for_job(client, alice, job_id)

    assert client.get(f"/api/analyses/{job_id}", headers=bob).status_code == 404
    assert client.get(f"/api/analyses/{job_id}/download", headers=bob).status_code == 404
    assert client.delete(f"/api/analyses/{job_id}", headers=bob).status_code == 404
    assert client.get("/api/analyses", headers=bob).json()["analyses"] == []
    # Alice still has it
    assert client.get(f"/api/analyses/{job_id}", headers=alice).status_code == 200


def test_unsupported_file_type_is_rejected(client):
    headers = register(client)
    r = client.post("/api/analyze", files={"file": ("notes.txt", b"hello", "text/plain")}, headers=headers)
    assert r.status_code == 400
    assert "Unsupported file type" in r.json()["detail"]


def test_pipeline_error_marks_job_failed(client, monkeypatch):
    def broken(image_path, job_id):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(pipeline_service, "analyze_image", broken)
    headers = register(client)

    job = wait_for_job(client, headers, upload(client, headers).json()["id"])
    assert job["status"] == "failed"
    assert "model exploded" in job["error_message"]
    assert client.get("/api/dashboard", headers=headers).json()["failed_analyses"] == 1


def test_upload_returns_before_analysis_finishes(client, monkeypatch):
    release = threading.Event()

    def slow(image_path, job_id):
        release.wait(timeout=10)
        return fake_analyze_image(image_path, job_id)

    monkeypatch.setattr(pipeline_service, "analyze_image", slow)
    headers = register(client)

    r = upload(client, headers)  # would hang here if analysis ran in the request
    assert r.status_code == 201
    assert r.json()["status"] == "processing"
    release.set()
    assert wait_for_job(client, headers, r.json()["id"])["status"] == "completed"


def test_progress_stream_reports_completion(client):
    r = client.post("/api/auth/register", json={"email": "sse@example.com", "password": "secret123", "full_name": "S"})
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    job_id = upload(client, headers).json()["id"]
    wait_for_job(client, headers, job_id)

    stream = client.get(f"/api/analyses/{job_id}/progress", params={"token": token})
    assert stream.status_code == 200
    assert '"step": "completed"' in stream.text


# --- file serving ----------------------------------------------------------

def test_uploaded_file_is_served(client):
    headers = register(client)
    upload(client, headers)
    # Stored under a random UUID prefix: <uuid>_plan.png
    (stored,) = list(analysis_routes.UPLOAD_DIR.iterdir())
    assert stored.name.endswith("_plan.png")
    stored_name = stored.name

    r = client.get(f"/api/files/uploads/{stored_name}")
    assert r.status_code == 200
    assert r.content == PNG_BYTES


@pytest.mark.parametrize("path", [
    "/api/files/uploads/..%2F..%2Fconfig.py",
    "/api/files/uploads/%2E%2E%2F.env",
    "/api/files/results/1/..%2F..%2F..%2F.env",
])
def test_path_traversal_is_blocked(client, path):
    r = client.get(path)
    assert r.status_code in (403, 404)
    assert b"SECRET" not in r.content
