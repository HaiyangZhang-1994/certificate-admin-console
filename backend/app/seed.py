"""Explicit local demo fixtures. Run: python -m app.seed [--reset]."""

import argparse
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from app.database import initialize, make_engine, transaction
from app.models.schema import (
    admins,
    certificates,
    courses,
    enrollments,
    learners,
    metadata,
    tenants,
)
from app.services.auth import passwords
from app.services.certificates import write_audit


def fixed(group, index):
    return f"{group}0000000-0000-4000-8000-{index:012d}"


def stable(name):
    return str(uuid5(NAMESPACE_URL, "certificate-demo/" + name))


def seed(engine):
    with transaction(engine, write=True) as connection:
        for index, city, timezone in [
            (1, "Sydney", "Australia/Sydney"),
            (2, "Perth", "Australia/Perth"),
        ]:
            tenant, admin = fixed(2, index), fixed(1, index)
            if connection.scalar(select(tenants.c.id).where(tenants.c.id == tenant)):
                continue  # Never recreate or overwrite previously edited business data.
            connection.execute(
                tenants.insert().values(id=tenant, name=f"{city} Training", timezone=timezone)
            )
            connection.execute(
                admins.insert().values(
                    id=admin,
                    tenant_id=tenant,
                    username=f"{city.lower()}.admin",
                    name=f"{city} Admin",
                    password_hash=passwords.hash("DemoPass123!"),
                )
            )
            course_id = fixed(3, index)
            connection.execute(
                courses.insert().values(
                    id=course_id, tenant_id=tenant, title="Workplace Safety", ends_at=1790812800000
                )
            )
            for kind, end in [("Future", 4102444800000), ("Empty", 1790812800000)]:
                connection.execute(
                    courses.insert().values(
                        id=stable(f"{city}/{kind}"),
                        tenant_id=tenant,
                        title=f"{kind} Course",
                        ends_at=end,
                    )
                )
            for number in range(1, 31 if index == 1 else 5):
                learner = fixed(4, number) if index == 1 else stable(f"{city}/learner/{number}")
                enrollment = (
                    fixed(6, number) if index == 1 else stable(f"{city}/enrollment/{number}")
                )
                certificate = fixed(5, number) if index == 1 else stable(f"{city}/cert/{number}")
                name = "Alex Chen" if number == 1 else f"{city} Learner {number:02}"
                if number == 2:
                    name = '中文, "Learner"\nSecond line'
                if number == 3:
                    name = ' =HYPERLINK("https://example.test")'
                connection.execute(
                    learners.insert().values(
                        id=learner,
                        tenant_id=tenant,
                        name=name,
                        email=f"learner{number}@example.test",
                    )
                )
                completed = number != 30
                connection.execute(
                    enrollments.insert().values(
                        id=enrollment,
                        tenant_id=tenant,
                        course_id=course_id,
                        learner_id=learner,
                        status="completed" if completed else "in_progress",
                        completed_at=1790812800000 if completed else None,
                    )
                )
                if number <= (25 if index == 1 else 2):
                    at = 1792539000000  # 2026-10-20T23:30:00Z; fixed across resets.
                    revoked = number == 25
                    connection.execute(
                        certificates.insert().values(
                            id=certificate,
                            tenant_id=tenant,
                            enrollment_id=enrollment,
                            serial_number=f"CERT-{certificate}",
                            issued_at=at,
                            issued_by=admin,
                            revoked_at=at + 5400000 if revoked else None,
                            revoked_by=admin if revoked else None,
                        )
                    )
                    write_audit(
                        connection, tenant, "issued", certificate, course_id, learner, admin, at
                    )
                    if revoked:
                        write_audit(
                            connection,
                            tenant,
                            "revoked",
                            certificate,
                            course_id,
                            learner,
                            admin,
                            at + 5400000,
                        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true", help="Delete all configured database tables"
    )
    args = parser.parse_args()
    engine = make_engine()
    try:
        if args.reset:
            metadata.drop_all(engine)
        initialize(engine)
        seed(engine)
        print("Demo data ready: sydney.admin / perth.admin; password: DemoPass123!")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
