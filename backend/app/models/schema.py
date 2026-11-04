"""SQLite schema: every relationship carries its tenant boundary."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Index,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()


def entity(name, *columns, refs=(), constraints=()):
    return Table(
        name,
        metadata,
        Column("id", String, primary_key=True),
        Column("tenant_id", String, nullable=False),
        *columns,
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        *(
            ForeignKeyConstraint(["tenant_id", col], [f"{table}.tenant_id", f"{table}.id"])
            for col, table in refs
        ),
        *constraints,
    )


def required(name, type_=String):
    return Column(name, type_, nullable=False)


tenants = Table(
    "tenants",
    metadata,
    Column("id", String, primary_key=True),
    required("name"),
    required("timezone"),
)
admins = entity(
    "admins",
    required("username"),
    required("name"),
    required("password_hash"),
    constraints=(UniqueConstraint("username"),),
)
courses = entity("courses", required("title"), required("ends_at", BigInteger))
learners = entity("learners", required("name"), required("email"))
enrollments = entity(
    "enrollments",
    required("course_id"),
    required("learner_id"),
    required("status"),
    Column("completed_at", BigInteger),
    refs=(("course_id", "courses"), ("learner_id", "learners")),
    constraints=(
        UniqueConstraint("tenant_id", "course_id", "learner_id"),
        CheckConstraint("status IN ('in_progress', 'completed')"),
        CheckConstraint("status != 'completed' OR completed_at IS NOT NULL"),
    ),
)
certificates = entity(
    "certificates",
    required("enrollment_id"),
    required("serial_number"),
    required("issued_at", BigInteger),
    required("issued_by"),
    Column("revoked_at", BigInteger),
    Column("revoked_by", String),
    refs=(("enrollment_id", "enrollments"), ("issued_by", "admins"), ("revoked_by", "admins")),
    constraints=(
        UniqueConstraint("tenant_id", "enrollment_id"),
        UniqueConstraint("serial_number"),
        CheckConstraint("(revoked_at IS NULL) = (revoked_by IS NULL)"),
    ),
)
audit_logs = entity(
    "audit_logs",
    required("action"),
    required("certificate_id"),
    required("course_id"),
    required("learner_id"),
    required("actor_id"),
    required("occurred_at", BigInteger),
    refs=(
        ("certificate_id", "certificates"),
        ("course_id", "courses"),
        ("learner_id", "learners"),
        ("actor_id", "admins"),
    ),
    constraints=(
        CheckConstraint("action IN ('issued', 'revoked')"),
        UniqueConstraint("tenant_id", "certificate_id", "action"),
    ),
)
issuance_requests = entity(
    "issuance_requests",
    required("idempotency_key"),
    required("request_hash"),
    required("response_json", Text),
    required("created_at", BigInteger),
    constraints=(UniqueConstraint("tenant_id", "idempotency_key"),),
)
Index(
    "ix_certificates_tenant_issued_id",
    certificates.c.tenant_id,
    certificates.c.issued_at,
    certificates.c.id,
)
Index(
    "ix_enrollments_tenant_course_status",
    enrollments.c.tenant_id,
    enrollments.c.course_id,
    enrollments.c.status,
)
