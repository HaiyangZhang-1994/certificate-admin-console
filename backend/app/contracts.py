"""Frozen v1 wire contract. Regenerate OpenAPI/TypeScript after coordinated edits."""

from datetime import timedelta
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field


def require_utc(value: AwareDatetime) -> AwareDatetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("API timestamps must be UTC")
    return value


UtcTimestamp = Annotated[AwareDatetime, AfterValidator(require_utc)]


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorCode(StrEnum):
    UNAUTHORIZED = "unauthorized"
    INVALID_CREDENTIALS = "invalid_credentials"
    FORBIDDEN_ORIGIN = "forbidden_origin"
    RESOURCE_NOT_FOUND = "resource_not_found"
    VALIDATION_ERROR = "validation_error"
    COURSE_NOT_FINISHED = "course_not_finished"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    DATABASE_BUSY = "database_busy"
    INTERNAL_ERROR = "internal_error"
    NOT_IMPLEMENTED = "not_implemented"


class ErrorBody(DTO):
    code: ErrorCode
    message: str


class ErrorResponse(DTO):
    error: ErrorBody


class HealthResponse(DTO):
    status: Literal["ok"]
    service: Literal["certificate-admin-api"]


class LoginRequest(DTO):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class AdminSummary(DTO):
    id: UUID
    username: str
    name: str


class TenantSummary(DTO):
    id: UUID
    name: str
    timezone: str = Field(examples=["Australia/Sydney"])


class Identity(DTO):
    admin: AdminSummary
    tenant: TenantSummary


class LearnerSummary(DTO):
    id: UUID
    name: str
    email: str


class CourseRef(DTO):
    id: UUID
    title: str


class CourseSummary(CourseRef):
    ends_at: UtcTimestamp
    is_finished: bool
    enrollment_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    eligible_count: int = Field(ge=0)
    already_issued_count: int = Field(ge=0)


class CourseList(DTO):
    items: list[CourseSummary]


class CertificateSummary(DTO):
    id: UUID
    learner: LearnerSummary
    course: CourseRef
    serial_number: str
    issued_at: UtcTimestamp
    status: Literal["valid", "revoked"]


class CertificateDetail(CertificateSummary):
    issued_by: AdminSummary
    revoked_at: UtcTimestamp | None
    revoked_by: AdminSummary | None


class CertificatePage(DTO):
    items: list[CertificateSummary]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class CertificateFilters(DTO):
    q: str = Field(default="", max_length=200)
    course_id: UUID | None = None
    status: Literal["valid", "revoked"] | None = None
    sort_by: Literal["issued_at", "learner_name", "serial_number"] = "issued_at"
    sort_order: Literal["asc", "desc"] = "desc"


class CertificateListQuery(CertificateFilters):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class IssuedOutcome(DTO):
    enrollment_id: UUID
    learner_id: UUID
    learner_name: str
    outcome: Literal["issued"]
    reason: None
    certificate_id: UUID
    serial_number: str


class SkippedOutcome(DTO):
    enrollment_id: UUID
    learner_id: UUID
    learner_name: str
    outcome: Literal["skipped"]
    reason: Literal["not_completed", "already_issued", "certificate_revoked"]
    certificate_id: UUID | None
    serial_number: str | None


class FailedOutcome(DTO):
    enrollment_id: UUID
    learner_id: UUID
    learner_name: str
    outcome: Literal["failed"]
    reason: Literal["invalid_enrollment"]
    certificate_id: None
    serial_number: None


LearnerOutcome = Annotated[
    IssuedOutcome | SkippedOutcome | FailedOutcome, Field(discriminator="outcome")
]


class BulkIssueResult(DTO):
    issued_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    results: list[LearnerOutcome]
