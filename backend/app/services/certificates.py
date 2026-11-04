import csv
import hashlib
import io
import json
import time
from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from starlette.responses import StreamingResponse

from app.contracts import BulkIssueResult, ErrorCode
from app.database import transaction
from app.errors import ApiError
from app.models.schema import (
    admins,
    audit_logs,
    courses,
    learners,
)
from app.models.schema import (
    certificates as certs,
)
from app.models.schema import (
    enrollments as ens,
)
from app.models.schema import (
    issuance_requests as requests,
)


def now_ms():
    return time.time_ns() // 1_000_000


def timestamp(ms):
    return datetime.fromtimestamp(ms / 1000, UTC)


def missing():
    raise ApiError(404, ErrorCode.RESOURCE_NOT_FOUND, "Resource not found.")


def course(connection, tenant, course_id):
    row = (
        connection.execute(
            select(courses).where(courses.c.tenant_id == tenant, courses.c.id == str(course_id))
        )
        .mappings()
        .first()
    )
    if row is None:
        missing()
    return row


def list_courses(engine, tenant):
    joined = courses.outerjoin(
        ens, and_(ens.c.tenant_id == courses.c.tenant_id, ens.c.course_id == courses.c.id)
    ).outerjoin(
        certs, and_(certs.c.tenant_id == ens.c.tenant_id, certs.c.enrollment_id == ens.c.id)
    )
    statement = (
        select(
            courses,
            func.count(ens.c.id).label("enrollment_count"),
            func.count(case((ens.c.status == "completed", ens.c.id))).label("completed_count"),
            func.count(certs.c.id).label("already_issued_count"),
            func.count(
                case((and_(ens.c.status == "completed", certs.c.id.is_(None)), ens.c.id))
            ).label("eligible_count"),
        )
        .select_from(joined)
        .where(courses.c.tenant_id == tenant)
        .group_by(courses.c.id)
        .order_by(courses.c.id)
    )
    with transaction(engine) as connection:
        rows = connection.execute(statement).mappings().all()
    instant = now_ms()
    return {
        "items": [
            dict(
                id=r["id"],
                title=r["title"],
                ends_at=timestamp(r["ends_at"]),
                is_finished=r["ends_at"] <= instant,
                enrollment_count=r["enrollment_count"],
                completed_count=r["completed_count"],
                already_issued_count=r["already_issued_count"],
                eligible_count=r["eligible_count"] if r["ends_at"] <= instant else 0,
            )
            for r in rows
        ]
    }


def certificate_query(tenant):
    return (
        select(
            certs,
            learners.c.id.label("learner_id"),
            learners.c.name.label("learner_name"),
            learners.c.email.label("learner_email"),
            courses.c.id.label("course_id"),
            courses.c.title.label("course_title"),
        )
        .select_from(
            certs.join(
                ens, and_(ens.c.tenant_id == certs.c.tenant_id, ens.c.id == certs.c.enrollment_id)
            )
            .join(
                learners,
                and_(learners.c.tenant_id == ens.c.tenant_id, learners.c.id == ens.c.learner_id),
            )
            .join(
                courses,
                and_(courses.c.tenant_id == ens.c.tenant_id, courses.c.id == ens.c.course_id),
            )
        )
        .where(certs.c.tenant_id == tenant)
    )


def filtered(connection, tenant, query):
    if query.course_id:
        course(connection, tenant, query.course_id)
    statement = certificate_query(tenant)
    if query.course_id:
        statement = statement.where(courses.c.id == str(query.course_id))
    if query.status:
        statement = statement.where(
            certs.c.revoked_at.is_(None)
            if query.status == "valid"
            else certs.c.revoked_at.is_not(None)
        )
    text = query.q.strip()
    if text:
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(
            or_(
                learners.c.name.like(f"%{escaped}%", escape="\\"),
                certs.c.serial_number.like(f"%{escaped}%", escape="\\"),
            )
        )
    column = {
        "issued_at": certs.c.issued_at,
        "learner_name": learners.c.name,
        "serial_number": certs.c.serial_number,
    }[query.sort_by]
    ordering = (column, certs.c.id)
    return statement.order_by(
        *(c.asc() if query.sort_order == "asc" else c.desc() for c in ordering)
    )


def summary(row):
    return dict(
        id=row["id"],
        learner=dict(id=row["learner_id"], name=row["learner_name"], email=row["learner_email"]),
        course=dict(id=row["course_id"], title=row["course_title"]),
        serial_number=row["serial_number"],
        issued_at=timestamp(row["issued_at"]),
        status="revoked" if row["revoked_at"] is not None else "valid",
    )


def list_certificates(engine, tenant, query):
    with transaction(engine) as connection:
        statement = filtered(connection, tenant, query)
        total = connection.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        rows = (
            connection.execute(
                statement.limit(query.page_size).offset((query.page - 1) * query.page_size)
            )
            .mappings()
            .all()
        )
        return dict(
            items=[summary(row) for row in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )


def detail(connection, tenant, certificate_id):
    row = (
        connection.execute(certificate_query(tenant).where(certs.c.id == str(certificate_id)))
        .mappings()
        .first()
    )
    if row is None:
        missing()

    def actor(admin_id):
        return dict(
            connection.execute(
                select(admins.c.id, admins.c.username, admins.c.name).where(
                    admins.c.tenant_id == tenant, admins.c.id == admin_id
                )
            )
            .mappings()
            .one()
        )

    return dict(
        **summary(row),
        issued_by=actor(row["issued_by"]),
        revoked_at=timestamp(row["revoked_at"]) if row["revoked_at"] is not None else None,
        revoked_by=actor(row["revoked_by"]) if row["revoked_by"] else None,
    )


def write_audit(connection, tenant, action, certificate_id, course_id, learner_id, actor_id, at):
    connection.execute(
        audit_logs.insert().values(
            id=str(uuid4()),
            tenant_id=tenant,
            action=action,
            certificate_id=certificate_id,
            course_id=course_id,
            learner_id=learner_id,
            actor_id=actor_id,
            occurred_at=at,
        )
    )


def revoke(engine, identity, certificate_id):
    tenant, actor = identity["tenant"]["id"], identity["admin"]["id"]
    with transaction(engine, write=True) as connection:
        result = detail(connection, tenant, certificate_id)
        if result["revoked_at"] is None:
            at = now_ms()
            connection.execute(
                certs.update()
                .where(certs.c.tenant_id == tenant, certs.c.id == str(certificate_id))
                .values(revoked_at=at, revoked_by=actor)
            )
            write_audit(
                connection,
                tenant,
                "revoked",
                str(certificate_id),
                result["course"]["id"],
                result["learner"]["id"],
                actor,
                at,
            )
            result = detail(connection, tenant, certificate_id)
    return result


class InvalidEnrollment(Exception):
    """Known recoverable domain error; unknown DB errors must abort the batch."""


def validate_enrollment(row, instant):
    if row["completed_at"] is None or row["completed_at"] > instant:
        raise InvalidEnrollment()


def existing_certificate(connection, tenant, enrollment_id):
    return (
        connection.execute(
            select(certs).where(certs.c.tenant_id == tenant, certs.c.enrollment_id == enrollment_id)
        )
        .mappings()
        .first()
    )


def skipped(result, existing):
    return dict(
        **result,
        outcome="skipped",
        reason="certificate_revoked" if existing["revoked_at"] is not None else "already_issued",
        certificate_id=existing["id"],
        serial_number=existing["serial_number"],
    )


def issue(engine, identity, course_id, key):
    tenant, actor = identity["tenant"]["id"], identity["admin"]["id"]
    course_id, key = str(course_id), str(key)
    digest = hashlib.sha256(
        json.dumps(
            {"operation": "issue:v1", "course_id": course_id, "admin_id": actor, "body": None},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    with transaction(engine, write=True) as connection:
        previous = (
            connection.execute(
                select(requests).where(
                    requests.c.tenant_id == tenant, requests.c.idempotency_key == key
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if previous["request_hash"] != digest:
                raise ApiError(409, ErrorCode.IDEMPOTENCY_CONFLICT, "Idempotency key conflict.")
            return json.loads(previous["response_json"])
        selected = course(connection, tenant, course_id)
        instant = now_ms()
        if selected["ends_at"] > instant:
            raise ApiError(409, ErrorCode.COURSE_NOT_FINISHED, "Course has not finished.")
        rows = (
            connection.execute(
                select(ens, learners.c.name.label("learner_name"))
                .join(
                    learners,
                    and_(
                        learners.c.tenant_id == ens.c.tenant_id, learners.c.id == ens.c.learner_id
                    ),
                )
                .where(ens.c.tenant_id == tenant, ens.c.course_id == course_id)
                .order_by(ens.c.id)
            )
            .mappings()
            .all()
        )
        results = []
        for row in rows:
            base = dict(
                enrollment_id=row["id"],
                learner_id=row["learner_id"],
                learner_name=row["learner_name"],
            )
            existing = existing_certificate(connection, tenant, row["id"])
            if existing:
                results.append(skipped(base, existing))
                continue
            if row["status"] != "completed":
                results.append(
                    dict(
                        **base,
                        outcome="skipped",
                        reason="not_completed",
                        certificate_id=None,
                        serial_number=None,
                    )
                )
                continue
            try:
                with connection.begin_nested():
                    validate_enrollment(row, instant)
                    certificate_id = str(uuid4())
                    serial = f"CERT-{certificate_id}"
                    connection.execute(
                        certs.insert().values(
                            id=certificate_id,
                            tenant_id=tenant,
                            enrollment_id=row["id"],
                            serial_number=serial,
                            issued_at=instant,
                            issued_by=actor,
                        )
                    )
                    write_audit(
                        connection,
                        tenant,
                        "issued",
                        certificate_id,
                        course_id,
                        row["learner_id"],
                        actor,
                        instant,
                    )
                results.append(
                    dict(
                        **base,
                        outcome="issued",
                        reason=None,
                        certificate_id=certificate_id,
                        serial_number=serial,
                    )
                )
            except InvalidEnrollment:
                results.append(
                    dict(
                        **base,
                        outcome="failed",
                        reason="invalid_enrollment",
                        certificate_id=None,
                        serial_number=None,
                    )
                )
            except IntegrityError as exc:
                # Only the precise enrollment certificate uniqueness conflict is recoverable.
                if (
                    "UNIQUE constraint failed: certificates.tenant_id, certificates.enrollment_id"
                    not in str(exc.orig)
                ):
                    raise
                existing = existing_certificate(connection, tenant, row["id"])
                if existing is None:
                    raise
                results.append(skipped(base, existing))
        result = dict(
            results=results,
            **{
                f"{kind}_count": sum(r["outcome"] == kind for r in results)
                for kind in ("issued", "skipped", "failed")
            },
        )
        # Validate before committing so serialization errors cannot commit a false success.
        result = BulkIssueResult.model_validate(result).model_dump(mode="json")
        connection.execute(
            requests.insert().values(
                id=str(uuid4()),
                tenant_id=tenant,
                idempotency_key=key,
                request_hash=digest,
                response_json=json.dumps(result, separators=(",", ":")),
                created_at=instant,
            )
        )
    return result


def safe_cell(value):
    # Include whitespace/control prefixes which spreadsheet importers may strip.
    probe = value.lstrip(
        "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d"
        "\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a"
        "\x1b\x1c\x1d\x1e\x1f \x7f\ufeff"
    )
    if value and (ord(value[0]) < 32 or probe.startswith(("=", "+", "-", "@"))):
        return "'" + value
    return value


def local_time(ms, timezone):
    return timestamp(ms).astimezone(ZoneInfo(timezone)).isoformat()


class CSVSnapshot:
    """Own the real read transaction before headers, and close even if never iterated."""

    def __init__(self, engine, tenant, query):
        self.connection = engine.connect()
        self.result = None
        try:
            self.connection.exec_driver_sql("BEGIN")
            self.result = self.connection.execute(
                filtered(self.connection, tenant, query)
            ).mappings()
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.result is not None:
            self.result.close()
        self.connection.close()

    def chunks(self, timezone):
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        try:
            writer.writerow(["learner_name", "course_title", "serial_number", "issue_date"])
            yield ("\ufeff" + buffer.getvalue()).encode("utf-8")
            while rows := self.result.fetchmany(100):
                buffer.seek(0)
                buffer.truncate()
                for row in rows:
                    writer.writerow(
                        [
                            safe_cell(row["learner_name"]),
                            safe_cell(row["course_title"]),
                            safe_cell(row["serial_number"]),
                            local_time(row["issued_at"], timezone),
                        ]
                    )
                yield buffer.getvalue().encode("utf-8")
        finally:
            buffer.close()
            self.close()


class CSVResponse(StreamingResponse):
    def __init__(self, snapshot, timezone):
        self.snapshot = snapshot
        super().__init__(
            snapshot.chunks(timezone),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="certificates.csv"',
                "Cache-Control": "no-store",
            },
        )

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.snapshot.close()


def export(engine, identity, query):
    snapshot = CSVSnapshot(engine, identity["tenant"]["id"], query)
    return CSVResponse(snapshot, identity["tenant"]["timezone"])
