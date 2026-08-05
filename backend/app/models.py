from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from .database import Base


json_type = JSON().with_variant(JSONB(), "postgresql")


class TestPlan(Base):
    __tablename__ = "test_plans"

    id = Column(Integer, primary_key=True)
    title = Column(String(180), nullable=False)
    vehicle_platform = Column(String(120), nullable=False)
    objective = Column(Text, nullable=False)
    owner = Column(String(120), nullable=False)
    priority = Column(String(32), nullable=False, default="High")
    status = Column(String(32), nullable=False, default="Planned")
    route = Column(String(120), nullable=False, default="Proving Grounds")
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    runs = relationship("TestRun", back_populates="plan", cascade="all, delete-orphan")
    test_cases = relationship("TestCase", back_populates="plan", cascade="all, delete-orphan")


class VehicleConfig(Base):
    __tablename__ = "vehicle_configs"

    id = Column(Integer, primary_key=True)
    vehicle_label = Column(String(120), nullable=False)
    vin = Column(String(32), nullable=False)
    platform = Column(String(120), nullable=False)
    logger_model = Column(String(120), nullable=False)
    logger_health = Column(String(32), nullable=False)
    flash_version = Column(String(64), nullable=False)
    sensor_stack = Column(json_type, nullable=False, default=list)
    instrumentation = Column(json_type, nullable=False, default=list)
    notes = Column(Text, nullable=False, default="")
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    runs = relationship("TestRun", back_populates="vehicle")


class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("test_plans.id"), nullable=True)
    vehicle_id = Column(Integer, ForeignKey("vehicle_configs.id"), nullable=True)
    title = Column(String(180), nullable=False)
    route = Column(String(120), nullable=False)
    status = Column(String(32), nullable=False)
    logger_health = Column(String(32), nullable=False)
    flash_version = Column(String(64), nullable=False)
    pass_count = Column(Integer, nullable=False, default=0)
    fail_count = Column(Integer, nullable=False, default=0)
    anomaly_count = Column(Integer, nullable=False, default=0)
    missing_data_count = Column(Integer, nullable=False, default=0)
    coverage_pct = Column(Float, nullable=False, default=0.0)
    notes = Column(Text, nullable=False, default="")
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    plan = relationship("TestPlan", back_populates="runs")
    vehicle = relationship("VehicleConfig", back_populates="runs")
    files = relationship("CapturedFile", back_populates="run", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="run", cascade="all, delete-orphan")
    case_results = relationship("TestCaseResult", back_populates="run", cascade="all, delete-orphan")


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("test_plans.id"), nullable=True)
    case_id = Column(String(64), nullable=False, unique=True)
    title = Column(String(220), nullable=False)
    objective = Column(Text, nullable=False)
    subsystem = Column(String(80), nullable=False)
    severity = Column(String(32), nullable=False, default="Medium")
    expected_result = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="Ready")
    tags = Column(json_type, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    plan = relationship("TestPlan", back_populates="test_cases")
    results = relationship("TestCaseResult", back_populates="test_case", cascade="all, delete-orphan")


class TestCaseResult(Base):
    __tablename__ = "test_case_results"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=False)
    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False)
    verdict = Column(String(32), nullable=False)
    anomaly = Column(String(220), nullable=False, default="")
    missing_data = Column(String(220), nullable=False, default="")
    notes = Column(Text, nullable=False, default="")
    executed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    run = relationship("TestRun", back_populates="case_results")
    test_case = relationship("TestCase", back_populates="results")


class CapturedFile(Base):
    __tablename__ = "captured_files"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    storage_key = Column(String(255), nullable=False)
    file_type = Column(String(64), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    checksum = Column(String(128), nullable=False)
    tags = Column(json_type, nullable=False, default=list)
    indexed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    status = Column(String(32), nullable=False, default="indexed")
    missing_segments = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    run = relationship("TestRun", back_populates="files")


class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=True)
    severity = Column(String(32), nullable=False)
    category = Column(String(64), nullable=False)
    title = Column(String(200), nullable=False)
    detail = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="Open")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    run = relationship("TestRun", back_populates="issues")
