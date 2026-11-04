"""Contract-first placeholders. Replace bodies only; keep the wire contract stable."""

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response, Security
from fastapi.security import APIKeyCookie

from app.contracts import (
    BulkIssueResult,
    CertificateDetail,
    CertificateFilters,
    CertificateListQuery,
    CertificatePage,
    CourseList,
    ErrorCode,
    ErrorResponse,
    Identity,
    LoginRequest,
)
from app.errors import ApiError

session_cookie = APIKeyCookie(name="certificate_admin_session", auto_error=False)
errors = {status: {"model": ErrorResponse} for status in (401, 403, 404, 409, 422, 500, 501, 503)}
router = APIRouter(prefix="/api", responses=errors)
authenticated = [Security(session_cookie)]  # OpenAPI declaration only; no auth implemented yet.


def not_implemented() -> NoReturn:
    raise ApiError(501, ErrorCode.NOT_IMPLEMENTED, "Business functionality is not implemented yet.")


@router.post("/auth/login", response_model=Identity, operation_id="login", tags=["auth"])
def login(body: LoginRequest) -> Identity:
    not_implemented()


@router.post("/auth/logout", status_code=204, operation_id="logout", tags=["auth"])
def logout() -> Response:
    not_implemented()


@router.get(
    "/me",
    response_model=Identity,
    operation_id="getIdentity",
    dependencies=authenticated,
    tags=["auth"],
)
def get_identity() -> Identity:
    not_implemented()


@router.get(
    "/courses",
    response_model=CourseList,
    operation_id="listCourses",
    dependencies=authenticated,
    tags=["courses"],
)
def list_courses() -> CourseList:
    not_implemented()


@router.get(
    "/certificates",
    response_model=CertificatePage,
    operation_id="listCertificates",
    dependencies=authenticated,
    tags=["certificates"],
)
def list_certificates(query: Annotated[CertificateListQuery, Query()]) -> CertificatePage:
    not_implemented()


@router.get(
    "/certificates/export.csv",
    response_class=Response,
    operation_id="exportCertificates",
    dependencies=authenticated,
    tags=["certificates"],
    responses={
        200: {
            "description": "All matching rows; UTF-8 BOM, tenant-local issue_date with UTC offset.",
            "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
            "headers": {
                "Content-Disposition": {"schema": {"type": "string"}},
                "Cache-Control": {"schema": {"type": "string"}},
            },
        }
    },
)
def export_certificates(query: Annotated[CertificateFilters, Query()]) -> Response:
    not_implemented()


@router.get(
    "/certificates/{id}",
    response_model=CertificateDetail,
    operation_id="getCertificate",
    dependencies=authenticated,
    tags=["certificates"],
)
def get_certificate(id: UUID) -> CertificateDetail:
    not_implemented()


@router.post(
    "/certificates/{id}/revoke",
    response_model=CertificateDetail,
    operation_id="revokeCertificate",
    dependencies=authenticated,
    tags=["certificates"],
)
def revoke_certificate(id: UUID) -> CertificateDetail:
    not_implemented()


@router.post(
    "/courses/{id}/issue-certificates",
    response_model=BulkIssueResult,
    operation_id="issueCertificates",
    dependencies=authenticated,
    tags=["courses"],
)
def issue_certificates(
    id: UUID, idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")]
) -> BulkIssueResult:
    not_implemented()
