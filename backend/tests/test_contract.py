import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.contracts import (
    BulkIssueResult,
    CertificateDetail,
    CertificatePage,
    CourseList,
    ErrorResponse,
    Identity,
)
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = json.loads((ROOT / "docs/api/examples.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("key", "model"),
    [
        ("identity", Identity),
        ("perth_identity", Identity),
        ("courses", CourseList),
        ("certificate_page", CertificatePage),
        ("certificate_detail", CertificateDetail),
        ("revoked_certificate_detail", CertificateDetail),
        ("bulk_issue_result", BulkIssueResult),
        ("error", ErrorResponse),
    ],
)
def test_shared_examples_match_contract(key, model):
    model.model_validate(EXAMPLES[key])


def test_wire_timestamp_rejects_naive_datetime():
    example = {**EXAMPLES["certificate_detail"], "issued_at": "2026-10-20T23:30:00"}
    with pytest.raises(ValidationError):
        CertificateDetail.model_validate(example)


def test_health(tmp_path):
    with TestClient(create_app(f"sqlite:///{(tmp_path / 'health.db').as_posix()}")) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "certificate-admin-api"}
