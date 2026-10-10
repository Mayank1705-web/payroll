import csv
import io
import re
import shutil
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

from database import engine, Base, SessionLocal
from model import PayrollJob, PayrollResult, PayrollRowError
from tasks import REQUIRED_COLUMNS, process_payroll

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Automated Payroll Processing System")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/payroll/upload", status_code=202)
def upload_payroll(
    background_tasks: BackgroundTasks,
    payroll_month: str = Form(...),
    file: UploadFile = File(...),
):
    # Validate payroll month.
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", payroll_month):
        raise HTTPException(
            status_code=400,
            detail="payroll_month must be in YYYY-MM format",
        )

    # Validate file extension.
    if not file.filename or Path(file.filename).suffix.lower() != ".csv":
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are allowed",
        )

    file_path = UPLOAD_DIR / (
        f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}.csv"
    )

    try:
        with file_path.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)

        # Validate CSV headers and count records.
        try:
            with file_path.open(
                newline="", encoding="utf-8-sig"
            ) as source:
                reader = csv.DictReader(source)

                if not reader.fieldnames:
                    raise HTTPException(
                        status_code=400,
                        detail="CSV file has no header",
                    )

                if len(reader.fieldnames) != len(set(reader.fieldnames)):
                    raise HTTPException(
                        status_code=400,
                        detail="CSV contains duplicate column names",
                    )

                missing = REQUIRED_COLUMNS - set(reader.fieldnames)

                if missing:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "message": "Missing required CSV columns",
                            "missing_columns": sorted(missing),
                        },
                    )

                total_rows = sum(1 for _ in reader)

        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="CSV must use UTF-8 encoding",
            )

        if total_rows == 0:
            raise HTTPException(
                status_code=400,
                detail="CSV contains no employee records",
            )

        # Create the payroll job in MySQL.
        db = SessionLocal()

        try:
            job = PayrollJob(
                payroll_month=payroll_month,
                file_path=str(file_path.resolve()),
                status="PENDING",
                total_rows=total_rows,
                processed_rows=0,
                success_count=0,
                failed_count=0,
            )

            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = job.id

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()

        # Process the file after returning the HTTP response.
        background_tasks.add_task(process_payroll, job_id)

        return {
            "message": "Payroll file accepted for processing",
            "job_id": job_id,
            "status": "PENDING",
            "total_rows": total_rows,
        }

    except HTTPException:
        file_path.unlink(missing_ok=True)
        raise

    except Exception as exc:
        file_path.unlink(missing_ok=True)
        print("PAYROLL UPLOAD ERROR:", repr(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Could not create payroll job: {str(exc)}",
        )

    finally:
        file.file.close()


@app.get("/payroll/jobs/{job_id}")
def get_job_status(job_id: int):
    db = SessionLocal()

    try:
        job = db.get(PayrollJob, job_id)

        if not job:
            raise HTTPException(
                status_code=404,
                detail="Payroll job not found",
            )

        return {
            "job_id": job.id,
            "payroll_month": job.payroll_month,
            "status": job.status,
            "total_rows": job.total_rows,
            "processed_rows": job.processed_rows,
            "success_count": job.success_count,
            "failed_count": job.failed_count,
            "error_summary": job.error_summary,
        }

    finally:
        db.close()


@app.get("/payroll/jobs/{job_id}/results")
def get_job_results(job_id: int):
    db = SessionLocal()

    try:
        job = db.get(PayrollJob, job_id)

        if not job:
            raise HTTPException(
                status_code=404,
                detail="Payroll job not found",
            )

        results = (
            db.query(PayrollResult)
            .filter(PayrollResult.job_id == job_id)
            .order_by(PayrollResult.id)
            .all()
        )

        errors = (
            db.query(PayrollRowError)
            .filter(PayrollRowError.job_id == job_id)
            .order_by(PayrollRowError.row_number)
            .all()
        )

        return {
            "job_id": job.id,
            "status": job.status,
            "total_rows": job.total_rows,
            "processed_rows": job.processed_rows,
            "success_count": job.success_count,
            "failed_count": job.failed_count,
            "results": [
                {
                    "employee_id": r.employee_id,
                    "name": r.name,
                    "payroll_month": r.payroll_month,
                    "monthly_salary": str(r.monthly_salary),
                    "working_days": r.working_days,
                    "present_days": r.present_days,
                    "bonus": str(r.bonus),
                    "net_salary": str(r.net_salary),
                }
                for r in results
            ],
            "errors": [
                {
                    "row_number": e.row_number,
                    "employee_id": e.employee_id,
                    "error_message": e.error_message,
                }
                for e in errors
            ],
        }

    finally:
        db.close()


@app.get("/payroll/jobs/{job_id}/download")
def download_payroll(job_id: int):
    db = SessionLocal()

    try:
        job = db.get(PayrollJob, job_id)

        if not job:
            raise HTTPException(
                status_code=404,
                detail="Payroll job not found",
            )

        if job.status not in ("COMPLETED", "PARTIAL"):
            raise HTTPException(
                status_code=409,
                detail="Payroll download is not ready",
            )

        results = (
            db.query(PayrollResult)
            .filter(PayrollResult.job_id == job_id)
            .order_by(PayrollResult.id)
            .all()
        )

        if not results:
            raise HTTPException(
                status_code=404,
                detail="No successful payroll results available",
            )

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "employee_id",
            "name",
            "payroll_month",
            "monthly_salary",
            "working_days",
            "present_days",
            "bonus",
            "net_salary",
        ])

        for r in results:
            writer.writerow([
                r.employee_id,
                r.name,
                r.payroll_month,
                r.monthly_salary,
                r.working_days,
                r.present_days,
                r.bonus,
                r.net_salary,
            ])

        csv_content = output.getvalue()

        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition":
                    f'attachment; filename="payroll_{job_id}.csv"'
            },
        )

    finally:
        db.close()