"""Frozen route declarations with tenant-scoped implementations."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response, Security
from fastapi.security import APIKeyCookie

from app.contracts import (
    BulkIssueResult,
    CertificateDetail,
    CertificateFilters,
    CertificateListQuery,
    CertificatePage,
    CourseList,
    ErrorResponse,
    Identity,
    LoginRequest,
)
from app.database import transaction
from app.services import auth, certificates

session_cookie = APIKeyCookie(name="certificate_admin_session", auto_error=False)
errors = {status: {"model": ErrorResponse} for status in (401, 403, 404, 409, 422, 500, 501, 503)}
router = APIRouter(prefix="/api", responses=errors)
authenticated = [Security(session_cookie)]


@router.post("/auth/login", response_model=Identity, operation_id="login", tags=["auth"])
def login(body: LoginRequest, request: Request, response: Response) -> Identity:
    return auth.login(request, body, response)


@router.post("/auth/logout", status_code=204, operation_id="logout", tags=["auth"])
def logout(request: Request) -> Response:
    request.app.state.sessions.remove(request.cookies.get(auth.COOKIE))
    response = Response(status_code=204)
    response.delete_cookie(
        auth.COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=request.app.state.cookie_secure or request.url.scheme == "https",
    )
    return response


@router.get(
    "/me",
    response_model=Identity,
    operation_id="getIdentity",
    dependencies=authenticated,
    tags=["auth"],
)
def get_identity(request: Request) -> Identity:
    return auth.current(request)


@router.get(
    "/courses",
    response_model=CourseList,
    operation_id="listCourses",
    dependencies=authenticated,
    tags=["courses"],
)
def list_courses(request: Request) -> CourseList:
    identity = auth.current(request)
    return certificates.list_courses(request.app.state.engine, identity["tenant"]["id"])


@router.get(
    "/certificates",
    response_model=CertificatePage,
    operation_id="listCertificates",
    dependencies=authenticated,
    tags=["certificates"],
)
def list_certificates(
    query: Annotated[CertificateListQuery, Query()], request: Request
) -> CertificatePage:
    identity = auth.current(request)
    return certificates.list_certificates(request.app.state.engine, identity["tenant"]["id"], query)


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
def export_certificates(
    query: Annotated[CertificateFilters, Query()], request: Request
) -> Response:
    return certificates.export(request.app.state.engine, auth.current(request), query)


@router.get(
    "/certificates/{id}",
    response_model=CertificateDetail,
    operation_id="getCertificate",
    dependencies=authenticated,
    tags=["certificates"],
)
def get_certificate(id: UUID, request: Request) -> CertificateDetail:
    identity = auth.current(request)
    with transaction(request.app.state.engine) as connection:
        return certificates.detail(connection, identity["tenant"]["id"], id)


@router.post(
    "/certificates/{id}/revoke",
    response_model=CertificateDetail,
    operation_id="revokeCertificate",
    dependencies=authenticated,
    tags=["certificates"],
)
def revoke_certificate(id: UUID, request: Request) -> CertificateDetail:
    return certificates.revoke(request.app.state.engine, auth.current(request), id)


@router.post(
    "/courses/{id}/issue-certificates",
    response_model=BulkIssueResult,
    operation_id="issueCertificates",
    dependencies=authenticated,
    tags=["courses"],
)
def issue_certificates(
    id: UUID, idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")], request: Request
) -> BulkIssueResult:
    return certificates.issue(request.app.state.engine, auth.current(request), id, idempotency_key)
