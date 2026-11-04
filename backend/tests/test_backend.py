import asyncio
import csv
import io
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from conftest import ORIGIN, log_in
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.requests import ClientDisconnect

from app.contracts import CertificateFilters
from app.database import make_engine, transaction
from app.errors import ApiError
from app.main import create_app
from app.models.schema import (
    admins,
    audit_logs,
    courses,
    enrollments,
    issuance_requests,
    learners,
    metadata,
)
from app.models.schema import (
    certificates as certs,
)
from app.seed import fixed, seed, stable
from app.services import auth
from app.services import certificates as service

COURSE = fixed(3, 1)
CERT = fixed(5, 1)
TENANT = fixed(2, 1)


def issue(client, key=None, course_id=COURSE):
    return client.post(
        f"/api/courses/{course_id}/issue-certificates",
        headers={"Origin": ORIGIN, "Idempotency-Key": key or str(uuid4())},
    )


def revoke(client, certificate_id=CERT):
    return client.post(f"/api/certificates/{certificate_id}/revoke", headers={"Origin": ORIGIN})


def count(client, table, *criteria):
    with transaction(client.app.state.engine) as connection:
        return connection.scalar(select(func.count()).select_from(table).where(*criteria))


def test_auth_cookie_expiry_logout(client):
    assert client.get("/api/me").status_code == 401
    bad = client.post(
        "/api/auth/login",
        headers={"Origin": ORIGIN},
        json={"username": "sydney.admin", "password": "wrong"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"
    identity = log_in(client)
    assert client.get("/api/me").json() == identity
    assert client.get("/api/me").headers.get("access-control-allow-origin") is None
    client.app.state.sessions.ttl = -1
    response = client.post(
        "/api/auth/login",
        headers={"Origin": ORIGIN},
        json={"username": "sydney.admin", "password": "DemoPass123!"},
    )
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    assert client.get("/api/me").status_code == 401
    for _ in range(2):
        response = client.post("/api/auth/logout", headers={"Origin": ORIGIN})
        assert response.status_code == 204 and response.content == b""


@pytest.mark.parametrize("origin", [None, "null", "https://evil.test"])
@pytest.mark.parametrize(
    "path",
    [
        "/auth/login",
        "/auth/logout",
        f"/certificates/{CERT}/revoke",
        f"/courses/{COURSE}/issue-certificates",
    ],
)
def test_write_origins(client, origin, path):
    response = client.post("/api" + path, headers={"Origin": origin} if origin else {})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_origin"


@pytest.mark.parametrize(
    "path",
    [
        "/certificates?page_size=101",
        "/certificates?page=0",
        "/certificates?tenant_id=forged",
        "/certificates?sort_by=name",
        "/certificates?status=bad",
        "/certificates?course_id=bad",
        "/certificates/export.csv?page=1",
        "/certificates/bad",
        "/certificates?q=" + "a" * 201,
    ],
)
def test_invalid_parameters(authenticated, path):
    response = authenticated.get("/api" + path)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_invalid_write_parameters(authenticated):
    response = authenticated.post(
        f"/api/courses/{COURSE}/issue-certificates",
        headers={"Origin": ORIGIN, "Idempotency-Key": "bad"},
    )
    assert response.status_code == 422
    response = authenticated.post(
        "/api/auth/login",
        headers={"Origin": ORIGIN},
        json={"username": "sydney.admin", "password": "DemoPass123!", "tenant_id": fixed(2, 2)},
    )
    assert response.status_code == 422


def test_tenant_isolation_every_endpoint(authenticated):
    client = authenticated
    foreign_course = fixed(3, 2)
    foreign_cert = stable("Perth/cert/1")
    assert {x["id"] for x in client.get("/api/courses").json()["items"]} == {
        COURSE,
        stable("Sydney/Future"),
        stable("Sydney/Empty"),
    }
    assert client.get("/api/certificates").json()["total"] == 25
    assert all(
        "Sydney" in row["learner"]["name"] or row["learner"]["id"].startswith("400")
        for row in client.get("/api/certificates").json()["items"]
    )
    for target in [foreign_cert, str(uuid4())]:
        assert client.get(f"/api/certificates/{target}").status_code == 404
        assert revoke(client, target).status_code == 404
    for target in [foreign_course, str(uuid4())]:
        assert issue(client, course_id=target).status_code == 404
        for path in ["/certificates", "/certificates/export.csv"]:
            assert client.get("/api" + path, params={"course_id": target}).status_code == 404
    assert b"Perth" not in client.get("/api/certificates/export.csv").content
    key = str(uuid4())
    sydney = issue(client, key).json()
    log_in(client, "perth")
    assert client.get(f"/api/certificates/{CERT}").status_code == 404
    perth = issue(client, key, foreign_course)
    assert perth.status_code == 200 and perth.json() != sydney
    assert count(client, issuance_requests) == 2


def test_issue_replay_new_key_revoke_and_no_reissue(authenticated):
    client = authenticated
    key = str(uuid4())
    first = issue(client, key)
    assert first.status_code == 200, first.text
    body = first.json()
    assert (body["issued_count"], body["skipped_count"], body["failed_count"]) == (4, 26, 0)
    assert [x["enrollment_id"] for x in body["results"]] == sorted(
        x["enrollment_id"] for x in body["results"]
    )
    assert {x["reason"] for x in body["results"]} == {
        None,
        "not_completed",
        "already_issued",
        "certificate_revoked",
    }
    assert issue(client, key).content == first.content
    next_batch = issue(client).json()
    assert next_batch["issued_count"] == 0 and next_batch["skipped_count"] == 30
    result = revoke(client)
    assert result.status_code == 200 and result.json()["status"] == "revoked"
    assert revoke(client).json() == result.json()
    assert client.get(f"/api/certificates/{CERT}").json() == result.json()
    assert (
        count(
            client,
            audit_logs,
            audit_logs.c.certificate_id == CERT,
            audit_logs.c.action == "revoked",
        )
        == 1
    )
    after = issue(client).json()
    assert after["results"][0]["reason"] == "certificate_revoked"
    assert count(client, certs, certs.c.tenant_id == TENANT) == 29
    assert (
        count(client, audit_logs, audit_logs.c.tenant_id == TENANT, audit_logs.c.action == "issued")
        == 29
    )
    # Historical replay survives subsequent revocation and course state changes.
    with transaction(client.app.state.engine, write=True) as connection:
        connection.execute(
            courses.update().where(courses.c.id == COURSE).values(ends_at=4102444800000)
        )
    assert issue(client, key).content == first.content


def test_conflict_course_and_actor(authenticated):
    client = authenticated
    key = str(uuid4())
    assert issue(client, key).status_code == 200
    assert (
        issue(client, key, stable("Sydney/Empty")).json()["error"]["code"] == "idempotency_conflict"
    )
    with transaction(client.app.state.engine, write=True) as connection:
        admin_id = str(uuid4())
        connection.execute(
            admins.insert().values(
                id=admin_id,
                tenant_id=TENANT,
                username="other",
                name="Other admin",
                password_hash=auth.passwords.hash("OtherPass123!"),
            )
        )
    client.cookies.set(auth.COOKIE, client.app.state.sessions.create(admin_id))
    response = issue(client, key)
    assert response.status_code == 409


def test_empty_future_and_course_counts(authenticated):
    client = authenticated
    rows = {x["id"]: x for x in client.get("/api/courses").json()["items"]}
    assert rows[COURSE]["completed_count"] == 29
    assert rows[COURSE]["eligible_count"] == 4
    assert rows[COURSE]["already_issued_count"] == 25
    assert rows[stable("Sydney/Future")]["eligible_count"] == 0
    assert issue(client, course_id=stable("Sydney/Future")).status_code == 409
    assert issue(client, course_id=stable("Sydney/Empty")).json() == {
        "issued_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
        "results": [],
    }


@pytest.mark.parametrize("same_key", [True, False])
def test_independent_connection_concurrency(authenticated, same_key):
    client = authenticated
    identity = client.get("/api/me").json()
    barrier = Barrier(2)
    key = str(uuid4())
    engine = make_engine(str(client.app.state.engine.url), busy_timeout=3000)

    def run(chosen_engine):
        barrier.wait(timeout=5)
        return service.issue(chosen_engine, identity, COURSE, key if same_key else str(uuid4()))

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(run, engine)
            b = pool.submit(run, client.app.state.engine)
            results = [a.result(timeout=10), b.result(timeout=10)]
        assert (
            results[0] == results[1]
            if same_key
            else sorted(r["issued_count"] for r in results) == [0, 4]
        )
        assert count(client, certs, certs.c.tenant_id == TENANT) == 29
        assert (
            count(
                client,
                audit_logs,
                audit_logs.c.tenant_id == TENANT,
                audit_logs.c.action == "issued",
            )
            == 29
        )
    finally:
        engine.dispose()


def test_audit_failure_rolls_back_entire_batch(authenticated, monkeypatch):
    client = authenticated
    original = service.write_audit
    calls = 0

    def failing(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("private database details")
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "write_audit", failing)
    key = str(uuid4())
    response = issue(client, key)
    assert response.status_code == 500 and "private" not in response.text
    assert count(client, certs, certs.c.tenant_id == TENANT) == 25
    assert count(client, issuance_requests) == 0
    assert (
        count(client, audit_logs, audit_logs.c.tenant_id == TENANT, audit_logs.c.action == "issued")
        == 25
    )
    monkeypatch.setattr(service, "write_audit", original)
    assert issue(client, key).json()["issued_count"] == 4


def test_known_invalid_enrollment_partial_failure_and_replay(authenticated, monkeypatch):
    original = service.validate_enrollment

    def invalid(row, instant):
        if row["id"] == fixed(6, 26):
            raise service.InvalidEnrollment()
        return original(row, instant)

    monkeypatch.setattr(service, "validate_enrollment", invalid)
    key = str(uuid4())
    first = issue(authenticated, key)
    assert first.status_code == 200
    assert first.json()["failed_count"] == 1 and first.json()["issued_count"] == 3
    monkeypatch.setattr(service, "validate_enrollment", original)
    assert issue(authenticated, key).content == first.content
    assert issue(authenticated).json()["issued_count"] == 1


def test_revoke_audit_failure_rolls_back(authenticated, monkeypatch):
    def failing(*args):
        raise RuntimeError("private")

    monkeypatch.setattr(service, "write_audit", failing)
    assert revoke(authenticated).status_code == 500
    assert authenticated.get(f"/api/certificates/{CERT}").json()["status"] == "valid"
    assert (
        count(
            authenticated,
            audit_logs,
            audit_logs.c.certificate_id == CERT,
            audit_logs.c.action == "revoked",
        )
        == 0
    )


def test_commit_failure_rolls_back(authenticated):
    engine = authenticated.app.state.engine

    def fail_commit(connection):
        raise RuntimeError("commit failed")

    event.listen(engine, "commit", fail_commit)
    try:
        assert issue(authenticated).status_code == 500
    finally:
        event.remove(engine, "commit", fail_commit)
    assert count(authenticated, certs, certs.c.tenant_id == TENANT) == 25
    assert count(authenticated, issuance_requests) == 0


def test_lock_timeout_retry_same_key(authenticated):
    key = str(uuid4())
    with transaction(authenticated.app.state.engine, write=True):
        response = issue(authenticated, key)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "database_busy"
    assert issue(authenticated, key).json()["issued_count"] == 4


def test_replay_after_restart_and_seed_is_not_reset(client, database_url):
    log_in(client)
    key = str(uuid4())
    first = issue(client, key)
    with TestClient(create_app(database_url, seed_demo=True)) as restarted:
        assert restarted.get("/api/me").status_code == 401
        log_in(restarted)
        assert issue(restarted, key).content == first.content
        assert restarted.get("/api/certificates").json()["total"] == 29


def test_schema_constraints_and_sqlite_settings(client):
    engine = client.app.state.engine
    assert len(metadata.tables) == 8
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 100
    bad_rows = [
        (
            enrollments,
            dict(
                id=str(uuid4()),
                tenant_id=TENANT,
                course_id=fixed(3, 2),
                learner_id=fixed(4, 1),
                status="completed",
                completed_at=1,
            ),
        ),
        (
            enrollments,
            dict(
                id=str(uuid4()),
                tenant_id=TENANT,
                course_id=COURSE,
                learner_id=fixed(4, 1),
                status="completed",
                completed_at=None,
            ),
        ),
        (
            certs,
            dict(
                id=str(uuid4()),
                tenant_id=TENANT,
                enrollment_id=fixed(6, 26),
                serial_number="CERT-test",
                issued_at=1,
                issued_by=fixed(1, 2),
            ),
        ),
        (
            certs,
            dict(
                id=str(uuid4()),
                tenant_id=TENANT,
                enrollment_id=fixed(6, 1),
                serial_number="CERT-test",
                issued_at=1,
                issued_by=fixed(1, 1),
            ),
        ),
        (
            audit_logs,
            dict(
                id=str(uuid4()),
                tenant_id=TENANT,
                certificate_id=CERT,
                course_id=COURSE,
                learner_id=fixed(4, 1),
                actor_id=fixed(1, 2),
                action="revoked",
                occurred_at=1,
            ),
        ),
    ]
    for table, row in bad_rows:
        with pytest.raises(IntegrityError), transaction(engine, write=True) as connection:
            connection.execute(table.insert().values(**row))
    before = count(client, certs)
    seed(engine)
    assert count(client, certs) == before


def test_search_paging_sort_and_export_filters(authenticated):
    client = authenticated
    assert client.get("/api/certificates", params={"q": " Alex "}).json()["total"] == 1
    assert client.get("/api/certificates", params={"q": "CERT-" + CERT}).json()["total"] == 1
    assert client.get("/api/certificates", params={"q": "%"}).json()["total"] == 0
    assert client.get("/api/certificates", params={"q": "_"}).json()["total"] == 0
    assert client.get("/api/certificates?page=500").json()["items"] == []
    for field in ["issued_at", "learner_name", "serial_number"]:
        for order in ["asc", "desc"]:
            params = {"sort_by": field, "sort_order": order, "page_size": 100}
            rows = client.get("/api/certificates", params=params).json()["items"]

            def key(r):
                return (r["learner"]["name"] if field == "learner_name" else r[field], r["id"])

            assert rows == sorted(rows, key=key, reverse=order == "desc")
    for params in [
        {},
        {"q": "Sydney", "status": "valid", "course_id": COURSE},
        {"status": "revoked"},
        {"q": "absent"},
    ]:
        page = client.get("/api/certificates", params={**params, "page_size": 100}).json()
        response = client.get("/api/certificates/export.csv", params=params)
        rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        assert len(rows) == page["total"]
        assert [r["serial_number"] for r in rows] == [r["serial_number"] for r in page["items"]]
    assert len(client.get("/api/certificates").json()["items"]) == 20


def test_csv_bom_quoting_formula_and_time(authenticated):
    response = authenticated.get("/api/certificates/export.csv")
    assert response.status_code == 200 and response.content.startswith(b"\xef\xbb\xbf")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 25
    assert any(r["learner_name"] == '中文, "Learner"\nSecond line' for r in rows)
    assert any(r["learner_name"].startswith("' =HYPERLINK") for r in rows)
    assert all(r["issue_date"] == "2026-10-21T10:30:00+11:00" for r in rows)
    log_in(authenticated, "perth")
    rows = list(
        csv.DictReader(
            io.StringIO(
                authenticated.get("/api/certificates/export.csv").content.decode("utf-8-sig")
            )
        )
    )
    assert all(r["issue_date"] == "2026-10-21T07:30:00+08:00" for r in rows)


@pytest.mark.parametrize("text", ["=1", " +1", "-1", "@foo", "\tvalue", "\r=1", "\x00=1"])
def test_csv_formula_safety(text):
    assert service.safe_cell(text) == "'" + text


@pytest.mark.parametrize(
    ("utc_ms", "timezone", "expected"),
    [
        (1792539000000, "Australia/Sydney", "2026-10-21T10:30:00+11:00"),
        (1792539000000, "Australia/Perth", "2026-10-21T07:30:00+08:00"),
        (1782862200000, "Australia/Sydney", "2026-07-01T09:30:00+10:00"),
        (1782862200000, "Australia/Perth", "2026-07-01T07:30:00+08:00"),
    ],
)
def test_local_time(utc_ms, timezone, expected):
    assert service.local_time(utc_ms, timezone) == expected


def test_csv_real_snapshot_batches_and_early_close(authenticated):
    engine = authenticated.app.state.engine
    snapshot = service.CSVSnapshot(engine, TENANT, CertificateFilters(sort_order="asc"))
    assert snapshot.connection.connection.driver_connection.in_transaction
    with transaction(engine, write=True) as connection:
        connection.execute(
            learners.update()
            .where(learners.c.id == fixed(4, 1))
            .values(name="Changed after snapshot")
        )
    content = b"".join(snapshot.chunks("Australia/Sydney"))
    assert b"Alex Chen" in content and b"Changed after snapshot" not in content
    assert snapshot.connection.closed
    snapshot = service.CSVSnapshot(engine, TENANT, CertificateFilters())
    chunks = snapshot.chunks("Australia/Sydney")
    next(chunks)
    chunks.close()
    assert snapshot.connection.closed
    assert engine.pool.checkedout() == 0


def test_csv_closes_when_send_fails_before_iteration(authenticated):
    identity = authenticated.get("/api/me").json()
    engine = authenticated.app.state.engine
    response = service.export(engine, identity, CertificateFilters())

    async def send(message):
        raise OSError("client disconnected")

    async def receive():
        return {"type": "http.disconnect"}

    with pytest.raises(ClientDisconnect):
        asyncio.run(response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send))
    assert engine.pool.checkedout() == 0


def test_unknown_database_error_not_partial_success(authenticated, monkeypatch):
    def fail(*args):
        raise OperationalError("SELECT", {}, RuntimeError("private connection error"))

    monkeypatch.setattr(service, "write_audit", fail)
    response = issue(authenticated)
    assert response.status_code == 500 and "private" not in response.text
    assert count(authenticated, certs, certs.c.tenant_id == TENANT) == 25


@pytest.mark.parametrize(
    "path",
    ["/me", "/courses", "/certificates", "/certificates/export.csv", f"/certificates/{CERT}"],
)
def test_business_reads_require_authentication(client, path):
    response = client.get("/api" + path)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_business_writes_require_authentication(client):
    assert issue(client).status_code == 401
    assert revoke(client).status_code == 401


def test_logout_invalidates_server_session_and_login_rotates(client):
    log_in(client)
    old_token = client.cookies.get(auth.COOKIE)
    log_in(client)
    new_token = client.cookies.get(auth.COOKIE)
    assert old_token != new_token
    with pytest.raises(ApiError) as error:
        client.app.state.sessions.resolve(old_token)
    assert error.value.status_code == 401
    assert client.post("/api/auth/logout", headers={"Origin": ORIGIN}).status_code == 204
    assert client.get("/api/me").status_code == 401
    with pytest.raises(ApiError) as error:
        client.app.state.sessions.resolve(new_token)
    assert error.value.status_code == 401


def test_https_cookie_is_secure(database_url):
    with TestClient(
        create_app(database_url, seed_demo=True), base_url="https://testserver"
    ) as client:
        response = client.post(
            "/api/auth/login",
            headers={"Origin": ORIGIN},
            json={"username": "sydney.admin", "password": "DemoPass123!"},
        )
        assert response.status_code == 200
        assert "Secure" in response.headers["set-cookie"]
        assert client.get("/api/me").status_code == 200


def test_csv_multiple_fetch_batches_and_stream_failure(authenticated):
    client = authenticated
    engine = client.app.state.engine
    with transaction(engine, write=True) as connection:
        for i in range(210):
            learner_id, enrollment_id = str(uuid4()), str(uuid4())
            connection.execute(
                learners.insert().values(
                    id=learner_id, tenant_id=TENANT, name=f"Extra {i}", email=f"{i}@example.test"
                )
            )
            connection.execute(
                enrollments.insert().values(
                    id=enrollment_id,
                    tenant_id=TENANT,
                    course_id=COURSE,
                    learner_id=learner_id,
                    status="completed",
                    completed_at=1790812800000,
                )
            )
    assert issue(client).json()["issued_count"] == 214
    snapshot = service.CSVSnapshot(engine, TENANT, CertificateFilters())
    chunks = list(snapshot.chunks("Australia/Sydney"))
    assert len(chunks) == 4  # header + 100 + 100 + 39; never load the full export.
    rows = list(csv.DictReader(io.StringIO(b"".join(chunks).decode("utf-8-sig"))))
    assert len(rows) == 239
    assert snapshot.connection.closed

    identity = client.get("/api/me").json()
    response = service.export(engine, identity, CertificateFilters())

    async def send(message):
        if message["type"] == "http.response.body":
            raise OSError("download interrupted")

    async def receive():
        return {"type": "http.disconnect"}

    with pytest.raises(ClientDisconnect):
        asyncio.run(response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send))
    assert engine.pool.checkedout() == 0


def test_unrelated_integrity_failure_is_not_skipped(authenticated, monkeypatch):
    def fail(*args):
        raise IntegrityError("INSERT", {}, RuntimeError("FOREIGN KEY constraint failed"))

    monkeypatch.setattr(service, "write_audit", fail)
    response = issue(authenticated)
    assert response.status_code == 500
    assert count(authenticated, certs, certs.c.tenant_id == TENANT) == 25
    assert count(authenticated, issuance_requests) == 0
