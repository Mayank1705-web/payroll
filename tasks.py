import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from model import PayrollJob, PayrollResult, PayrollRowError


CENT = Decimal("0.01")

REQUIRED_COLUMNS = {
    "employee_id",
    "name",
    "monthly_salary",
    "working_days",
    "present_days",
    "bonus",
}


def process_payroll(job_id: int):
    db = SessionLocal()

    try:
        job = db.get(PayrollJob, job_id)

        if not job or job.status != "PENDING":
            return

        job.status = "PROCESSING"
        db.commit()

        with open(
            job.file_path, newline="", encoding="utf-8-sig"
        ) as file:
            reader = csv.DictReader(file)

            if (
                not reader.fieldnames
                or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames))
            ):
                job.status = "FAILED"
                job.error_summary = "Required CSV columns are missing"
                db.commit()
                return

            for row_number, row in enumerate(reader, start=2):
                employee_id = (row.get("employee_id") or "").strip()

                try:
                    if None in row:
                        raise ValueError("Unexpected extra CSV columns")

                    if any(row.get(c) is None for c in REQUIRED_COLUMNS):
                        raise ValueError("Missing CSV field")

                    name = (row.get("name") or "").strip()

                    if not employee_id or not name:
                        raise ValueError(
                            "employee_id and name are required"
                        )

                    salary = Decimal(row["monthly_salary"].strip())
                    bonus = Decimal(row["bonus"].strip())
                    working_days = int(row["working_days"].strip())
                    present_days = int(row["present_days"].strip())

                    if not salary.is_finite() or not bonus.is_finite():
                        raise ValueError(
                            "Salary and bonus must be finite numbers"
                        )

                    if salary < 0 or bonus < 0:
                        raise ValueError(
                            "Salary and bonus cannot be negative"
                        )

                    if working_days <= 0:
                        raise ValueError(
                            "working_days must be greater than zero"
                        )

                    if present_days < 0 or present_days > working_days:
                        raise ValueError(
                            "present_days must be between 0 and working_days"
                        )

                    # Calculate salary using decimal-safe arithmetic.
                    net_salary = (
                        salary * Decimal(present_days)
                        / Decimal(working_days) + bonus
                    ).quantize(CENT, rounding=ROUND_HALF_UP)

                    result = PayrollResult(
                        job_id=job_id,
                        employee_id=employee_id,
                        name=name,
                        payroll_month=job.payroll_month,
                        monthly_salary=salary,
                        working_days=working_days,
                        present_days=present_days,
                        bonus=bonus,
                        net_salary=net_salary,
                    )

                    db.add(result)
                    db.flush()

                    job.success_count += 1
                    db.commit()

                except (
                    ValueError,
                    TypeError,
                    KeyError,
                    InvalidOperation,
                    ArithmeticError,
                ) as exc:
                    db.rollback()

                    db.add(
                        PayrollRowError(
                            job_id=job_id,
                            row_number=row_number,
                            employee_id=employee_id or None,
                            error_message=str(exc) or "Invalid row",
                        )
                    )
                    db.commit()

                    job = db.get(PayrollJob, job_id)
                    job.failed_count += 1
                    db.commit()

                except IntegrityError:
                    # Duplicate employee/month is rejected by MySQL.
                    db.rollback()

                    db.add(
                        PayrollRowError(
                            job_id=job_id,
                            row_number=row_number,
                            employee_id=employee_id or None,
                            error_message=(
                                "Payroll result already exists for this "
                                "employee and month"
                            ),
                        )
                    )
                    db.commit()

                    job = db.get(PayrollJob, job_id)
                    job.failed_count += 1
                    db.commit()

                finally:
                    # Update progress even when a row fails.
                    job = db.get(PayrollJob, job_id)
                    job.processed_rows += 1
                    db.commit()

        # Set final job status.
        job = db.get(PayrollJob, job_id)

        if job.failed_count == 0:
            job.status = "COMPLETED"
        elif job.success_count > 0:
            job.status = "PARTIAL"
        else:
            job.status = "FAILED"

        job.error_summary = (
            f"{job.failed_count} row(s) failed"
            if job.failed_count
            else None
        )

        db.commit()

    except Exception as exc:
        db.rollback()

        job = db.get(PayrollJob, job_id)

        if job:
            job.status = "FAILED"
            job.error_summary = f"Processing failed: {str(exc)[:500]}"
            db.commit()

    finally:
        db.close()