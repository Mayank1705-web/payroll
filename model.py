from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    DateTime,
    func,
)

from database import Base


class PayrollJob(Base):
    __tablename__ = "payroll_jobs"

    id = Column(Integer, primary_key=True, index=True)
    payroll_month = Column(String(7), nullable=False)
    file_path = Column(String(500), nullable=False)
    status = Column(String(20), default="PENDING", nullable=False)
    total_rows = Column(Integer, default=0, nullable=False)
    processed_rows = Column(Integer, default=0, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    error_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class PayrollResult(Base):
    __tablename__ = "payroll_results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer, ForeignKey("payroll_jobs.id"), nullable=False
    )
    employee_id = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    payroll_month = Column(String(7), nullable=False)
    monthly_salary = Column(Numeric(12, 2), nullable=False)
    working_days = Column(Integer, nullable=False)
    present_days = Column(Integer, nullable=False)
    bonus = Column(Numeric(12, 2), nullable=False)
    net_salary = Column(Numeric(12, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "payroll_month",
            name="uq_employee_payroll_month",
        ),
    )


class PayrollRowError(Base):
    __tablename__ = "payroll_errors"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer, ForeignKey("payroll_jobs.id"), nullable=False
    )
    row_number = Column(Integer, nullable=False)
    employee_id = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=False)