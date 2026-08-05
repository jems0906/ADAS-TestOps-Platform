from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class PlanCreate(BaseModel):
    title: str
    vehicle_platform: str
    objective: str
    owner: str
    priority: str = "High"
    status: str = "Planned"
    route: str = "Proving Grounds"
    scheduled_at: Optional[datetime] = None


class VehicleCreate(BaseModel):
    vehicle_label: str
    vin: str
    platform: str
    logger_model: str
    logger_health: str = "Healthy"
    flash_version: str
    sensor_stack: list[str] = Field(default_factory=list)
    instrumentation: list[str] = Field(default_factory=list)
    notes: str = ""


class RunCreate(BaseModel):
    plan_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    title: str
    route: str
    status: str = "Queued"
    logger_health: str = "Healthy"
    flash_version: str
    pass_count: int = 0
    fail_count: int = 0
    anomaly_count: int = 0
    missing_data_count: int = 0
    coverage_pct: float = 0.0
    notes: str = ""
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class IssueCreate(BaseModel):
    run_id: Optional[int] = None
    severity: Literal["Critical", "High", "Medium", "Low"] = "Medium"
    category: str
    title: str
    detail: str
    status: str = "Open"


class IssueUpdate(BaseModel):
    status: str


class TestCaseCreate(BaseModel):
    plan_id: Optional[int] = None
    case_id: str
    title: str
    objective: str
    subsystem: str
    severity: Literal["Critical", "High", "Medium", "Low"] = "Medium"
    expected_result: str
    status: str = "Ready"
    tags: list[str] = Field(default_factory=list)


class TestCaseResultCreate(BaseModel):
    run_id: int
    test_case_id: int
    verdict: Literal["Passed", "Failed", "Blocked"]
    anomaly: str = ""
    missing_data: str = ""
    notes: str = ""


class DashboardMetric(BaseModel):
    label: str
    value: str
    detail: str


class TrendPoint(BaseModel):
    label: str
    value: int


class DashboardResponse(BaseModel):
    metrics: list[DashboardMetric]
    status_breakdown: list[TrendPoint]
    issue_breakdown: list[TrendPoint]
    coverage_breakdown: list[TrendPoint]
    recent_runs: list[dict]
    open_issues: list[dict]
    recent_files: list[dict]
    recent_test_cases: list[dict]
    recent_case_results: list[dict]


class SimpleMessage(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str
    app: str


class RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
