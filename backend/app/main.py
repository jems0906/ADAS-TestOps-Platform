from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from .config import APP_NAME, FRONTEND_DIST_DIR, UPLOAD_DIR
from .database import Base, SessionLocal, engine, get_db
from .models import CapturedFile, Issue, TestCase, TestCaseResult, TestPlan, TestRun, VehicleConfig
from .schemas import (
    DashboardMetric,
    DashboardResponse,
    HealthResponse,
    IssueCreate,
    IssueUpdate,
    PlanCreate,
    RunCreate,
    SimpleMessage,
    TestCaseCreate,
    TestCaseResultCreate,
    TrendPoint,
    VehicleCreate,
)


app = FastAPI(title=APP_NAME, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.astimezone(UTC).isoformat() if value else None


def _safe_name(file_name: str) -> str:
    return Path(file_name).name.replace(" ", "_")


def _serialize_plan(plan: TestPlan, db: Session) -> dict:
    run_count = db.scalar(select(func.count(TestRun.id)).where(TestRun.plan_id == plan.id)) or 0
    return {
        "id": plan.id,
        "title": plan.title,
        "vehicle_platform": plan.vehicle_platform,
        "objective": plan.objective,
        "owner": plan.owner,
        "priority": plan.priority,
        "status": plan.status,
        "route": plan.route,
        "scheduled_at": _iso(plan.scheduled_at),
        "created_at": _iso(plan.created_at),
        "updated_at": _iso(plan.updated_at),
        "run_count": run_count,
    }


def _serialize_vehicle(vehicle: VehicleConfig, db: Session) -> dict:
    active_runs = db.scalar(select(func.count(TestRun.id)).where(TestRun.vehicle_id == vehicle.id)) or 0
    return {
        "id": vehicle.id,
        "vehicle_label": vehicle.vehicle_label,
        "vin": vehicle.vin,
        "platform": vehicle.platform,
        "logger_model": vehicle.logger_model,
        "logger_health": vehicle.logger_health,
        "flash_version": vehicle.flash_version,
        "sensor_stack": vehicle.sensor_stack,
        "instrumentation": vehicle.instrumentation,
        "notes": vehicle.notes,
        "last_checked_at": _iso(vehicle.last_checked_at),
        "created_at": _iso(vehicle.created_at),
        "active_runs": active_runs,
    }


def _serialize_run(run: TestRun) -> dict:
    return {
        "id": run.id,
        "plan_id": run.plan_id,
        "plan_title": run.plan.title if run.plan else None,
        "vehicle_id": run.vehicle_id,
        "vehicle_label": run.vehicle.vehicle_label if run.vehicle else None,
        "title": run.title,
        "route": run.route,
        "status": run.status,
        "logger_health": run.logger_health,
        "flash_version": run.flash_version,
        "pass_count": run.pass_count,
        "fail_count": run.fail_count,
        "anomaly_count": run.anomaly_count,
        "missing_data_count": run.missing_data_count,
        "coverage_pct": run.coverage_pct,
        "notes": run.notes,
        "started_at": _iso(run.started_at),
        "ended_at": _iso(run.ended_at),
        "created_at": _iso(run.created_at),
    }


def _serialize_issue(issue: Issue) -> dict:
    return {
        "id": issue.id,
        "run_id": issue.run_id,
        "run_title": issue.run.title if issue.run else None,
        "severity": issue.severity,
        "category": issue.category,
        "title": issue.title,
        "detail": issue.detail,
        "status": issue.status,
        "created_at": _iso(issue.created_at),
    }


def _serialize_file(file_record: CapturedFile) -> dict:
    return {
        "id": file_record.id,
        "run_id": file_record.run_id,
        "run_title": file_record.run.title if file_record.run else None,
        "file_name": file_record.file_name,
        "storage_key": file_record.storage_key,
        "file_type": file_record.file_type,
        "size_bytes": file_record.size_bytes,
        "checksum": file_record.checksum,
        "tags": file_record.tags,
        "indexed_at": _iso(file_record.indexed_at),
        "status": file_record.status,
        "missing_segments": file_record.missing_segments,
        "created_at": _iso(file_record.created_at),
    }


def _serialize_test_case(test_case: TestCase) -> dict:
    return {
        "id": test_case.id,
        "plan_id": test_case.plan_id,
        "plan_title": test_case.plan.title if test_case.plan else None,
        "case_id": test_case.case_id,
        "title": test_case.title,
        "objective": test_case.objective,
        "subsystem": test_case.subsystem,
        "severity": test_case.severity,
        "expected_result": test_case.expected_result,
        "status": test_case.status,
        "tags": test_case.tags,
        "created_at": _iso(test_case.created_at),
    }


def _serialize_case_result(case_result: TestCaseResult) -> dict:
    return {
        "id": case_result.id,
        "run_id": case_result.run_id,
        "run_title": case_result.run.title if case_result.run else None,
        "test_case_id": case_result.test_case_id,
        "case_id": case_result.test_case.case_id if case_result.test_case else None,
        "test_case_title": case_result.test_case.title if case_result.test_case else None,
        "verdict": case_result.verdict,
        "anomaly": case_result.anomaly,
        "missing_data": case_result.missing_data,
        "notes": case_result.notes,
        "executed_at": _iso(case_result.executed_at),
    }


def _recompute_run_stats(db: Session, run: TestRun) -> None:
    results = db.scalars(select(TestCaseResult).where(TestCaseResult.run_id == run.id)).all()
    run.pass_count = sum(1 for item in results if item.verdict == "Passed")
    run.fail_count = sum(1 for item in results if item.verdict == "Failed")
    run.anomaly_count = sum(1 for item in results if item.anomaly.strip())
    run.missing_data_count = sum(1 for item in results if item.missing_data.strip())

    if run.plan_id is not None:
        total_cases = db.scalar(select(func.count(TestCase.id)).where(TestCase.plan_id == run.plan_id)) or 0
    else:
        total_cases = db.scalar(select(func.count(TestCase.id))) or 0

    if total_cases > 0:
        run.coverage_pct = round((len(results) / total_cases) * 100, 1)
    else:
        run.coverage_pct = 0.0


def _seed_demo_data(db: Session) -> None:
    if db.scalar(select(func.count(TestPlan.id))) or 0:
        return

    now = datetime.now(UTC)
    plans = [
        TestPlan(
            title="Autopilot lane keeping validation",
            vehicle_platform="R1T Prototype",
            objective="Confirm lateral control stability across mixed surface segments.",
            owner="Validation Team Alpha",
            priority="High",
            status="Planned",
            route="Desert Loop",
            scheduled_at=now + timedelta(days=1),
        ),
        TestPlan(
            title="Night vision regression sweep",
            vehicle_platform="R1S Launch",
            objective="Compare low-light sensor confidence and event latency.",
            owner="ADAS Reliability",
            priority="Critical",
            status="In Progress",
            route="Night Highway",
            scheduled_at=now,
        ),
    ]
    vehicles = [
        VehicleConfig(
            vehicle_label="Vehicle 12 - Canyon",
            vin="7FAR0012TESTOPS",
            platform="R1T Prototype",
            logger_model="Motive 8-Track",
            logger_health="Healthy",
            flash_version="ADAS-2.8.14",
            sensor_stack=["Front camera", "Radar", "IMU", "GNSS"],
            instrumentation=["CAN tap", "12V monitor", "Thermal probe"],
            notes="Baseline vehicle for desert loop.",
            last_checked_at=now - timedelta(hours=4),
        ),
        VehicleConfig(
            vehicle_label="Vehicle 21 - Falcon",
            vin="7FAR0021TESTOPS",
            platform="R1S Launch",
            logger_model="Motive 8-Track",
            logger_health="Needs Review",
            flash_version="ADAS-2.8.16",
            sensor_stack=["Front camera", "Rear camera", "Ultrasonic"],
            instrumentation=["CAN tap", "High speed Ethernet"],
            notes="Logger temp spike observed during last session.",
            last_checked_at=now - timedelta(hours=12),
        ),
    ]
    db.add_all(plans + vehicles)
    db.flush()

    runs = [
        TestRun(
            plan_id=plans[0].id,
            vehicle_id=vehicles[0].id,
            title="Morning route proving run",
            route="Desert Loop",
            status="Passed",
            logger_health="Healthy",
            flash_version="ADAS-2.8.14",
            pass_count=18,
            fail_count=0,
            anomaly_count=1,
            missing_data_count=0,
            coverage_pct=94.0,
            notes="Clean capture with one minor GNSS jitter warning.",
            started_at=now - timedelta(hours=6),
            ended_at=now - timedelta(hours=5, minutes=10),
        ),
        TestRun(
            plan_id=plans[1].id,
            vehicle_id=vehicles[1].id,
            title="Night glare regression",
            route="Night Highway",
            status="Failed",
            logger_health="Needs Review",
            flash_version="ADAS-2.8.16",
            pass_count=9,
            fail_count=3,
            anomaly_count=2,
            missing_data_count=1,
            coverage_pct=81.0,
            notes="Front camera sync drift and a missing 14-second segment.",
            started_at=now - timedelta(hours=2),
            ended_at=now - timedelta(hours=1, minutes=10),
        ),
        TestRun(
            plan_id=plans[1].id,
            vehicle_id=vehicles[1].id,
            title="Sensor heat soak follow-up",
            route="Service Loop",
            status="Running",
            logger_health="Degraded",
            flash_version="ADAS-2.8.16",
            pass_count=7,
            fail_count=1,
            anomaly_count=3,
            missing_data_count=2,
            coverage_pct=76.0,
            notes="Ongoing capture under thermal stress.",
            started_at=now - timedelta(minutes=35),
        ),
    ]
    db.add_all(runs)
    db.flush()

    test_cases = [
        TestCase(
            plan_id=plans[0].id,
            case_id="LK-001",
            title="Lane centering steady-state tracking",
            objective="Validate lane center error remains within tolerance at steady speed.",
            subsystem="Perception",
            severity="High",
            expected_result="Center offset remains below 0.25 m for the full segment.",
            status="Ready",
            tags=["lane-keeping", "daylight", "baseline"],
        ),
        TestCase(
            plan_id=plans[1].id,
            case_id="NV-014",
            title="Night glare object classification",
            objective="Check pedestrian and vehicle classification confidence under high-beam glare.",
            subsystem="Vision",
            severity="Critical",
            expected_result="Classification confidence stays above 0.78 with no false negatives.",
            status="Ready",
            tags=["night", "glare", "classification"],
        ),
        TestCase(
            plan_id=plans[1].id,
            case_id="NV-021",
            title="Camera and CAN timestamp sync",
            objective="Ensure camera frames and CAN events stay synchronized during maneuvers.",
            subsystem="Sensor fusion",
            severity="High",
            expected_result="Timestamp skew remains below 15 ms.",
            status="Ready",
            tags=["sync", "timing", "night"],
        ),
    ]
    db.add_all(test_cases)
    db.flush()

    db.add_all(
        [
            TestCaseResult(
                run_id=runs[0].id,
                test_case_id=test_cases[0].id,
                verdict="Passed",
                notes="Stable lane centering observed for full route.",
                anomaly="",
                missing_data="",
                executed_at=now - timedelta(hours=5, minutes=15),
            ),
            TestCaseResult(
                run_id=runs[1].id,
                test_case_id=test_cases[1].id,
                verdict="Failed",
                notes="Glare reduced confidence below threshold near marker 2.8.",
                anomaly="classification dip",
                missing_data="",
                executed_at=now - timedelta(hours=1, minutes=20),
            ),
            TestCaseResult(
                run_id=runs[1].id,
                test_case_id=test_cases[2].id,
                verdict="Failed",
                notes="Timestamp skew exceeded allowed band after acceleration event.",
                anomaly="sync drift",
                missing_data="14-second CAN segment missing",
                executed_at=now - timedelta(hours=1, minutes=12),
            ),
        ]
    )

    for run in runs:
        _recompute_run_stats(db, run)

    demo_file_path = UPLOAD_DIR / "night_glare_session_001.log"
    demo_file_path.write_text("CAN=stable\nRADAR=jitter\nGPS=missing 14s\n", encoding="utf-8")
    file_bytes = demo_file_path.read_bytes()
    db.add_all(
        [
            CapturedFile(
                run_id=runs[0].id,
                file_name="morning_route_proving.bin",
                storage_key=str(demo_file_path.name),
                file_type="bin",
                size_bytes=len(file_bytes),
                checksum=sha256(file_bytes).hexdigest(),
                tags=["baseline", "route-a", "can"],
                status="indexed",
                missing_segments="",
                indexed_at=now - timedelta(hours=5),
            ),
            CapturedFile(
                run_id=runs[1].id,
                file_name="night_glare_session_001.log",
                storage_key=str(demo_file_path.name),
                file_type="log",
                size_bytes=len(file_bytes),
                checksum=sha256(file_bytes).hexdigest(),
                tags=["night", "glare", "missing-data"],
                status="indexed",
                missing_segments="GPS stream missing between 00:14 and 00:28",
                indexed_at=now - timedelta(hours=1, minutes=5),
            ),
        ]
    )

    db.add_all(
        [
            Issue(
                run_id=runs[1].id,
                severity="Critical",
                category="Sensor timing",
                title="Front camera frame sync drift",
                detail="Camera and CAN timestamps diverged after the first acceleration event.",
                status="Open",
            ),
            Issue(
                run_id=runs[2].id,
                severity="High",
                category="Logger health",
                title="Logger thermal warning",
                detail="Logger temperature exceeded the preferred operating band during the soak segment.",
                status="Investigating",
            ),
            Issue(
                run_id=None,
                severity="Medium",
                category="Data completeness",
                title="Upload coverage gap",
                detail="Captured file for one braking sweep is missing from the latest transfer batch.",
                status="Open",
            ),
        ]
    )
    db.commit()


@app.on_event("startup")
def startup() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        _seed_demo_data(db)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=APP_NAME)


@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardResponse:
    plans = db.scalars(select(TestPlan).order_by(TestPlan.created_at.desc())).all()
    runs = db.scalars(
        select(TestRun)
        .options(joinedload(TestRun.plan), joinedload(TestRun.vehicle))
        .order_by(TestRun.started_at.desc().nullslast(), TestRun.created_at.desc())
    ).all()
    issues = db.scalars(select(Issue).options(joinedload(Issue.run)).order_by(Issue.created_at.desc())).all()
    files = db.scalars(select(CapturedFile).options(joinedload(CapturedFile.run)).order_by(CapturedFile.created_at.desc())).all()
    test_cases = db.scalars(select(TestCase).options(joinedload(TestCase.plan)).order_by(TestCase.created_at.desc())).all()
    case_results = db.scalars(
        select(TestCaseResult)
        .options(joinedload(TestCaseResult.run), joinedload(TestCaseResult.test_case))
        .order_by(TestCaseResult.executed_at.desc())
    ).all()

    total_runs = len(runs)
    passing_runs = sum(1 for run in runs if run.status.lower() == "passed")
    pass_rate = round((passing_runs / total_runs * 100) if total_runs else 0.0)
    avg_coverage = round(sum(run.coverage_pct for run in runs) / total_runs) if total_runs else 0
    healthy_loggers = sum(1 for run in runs if run.logger_health.lower() == "healthy")
    open_issues = sum(1 for issue in issues if issue.status.lower() not in {"closed", "resolved"})
    critical_issues = sum(1 for issue in issues if issue.severity == "Critical" and issue.status.lower() not in {"closed", "resolved"})
    indexed_files = len(files)
    total_missing = sum(run.missing_data_count for run in runs)
    active_plans = sum(1 for plan in plans if plan.status.lower() in {"planned", "in progress", "running"})
    total_case_results = len(case_results)
    passed_case_results = sum(1 for item in case_results if item.verdict == "Passed")
    case_pass_rate = round((passed_case_results / total_case_results * 100) if total_case_results else 0.0)
    covered_case_ids = {item.test_case_id for item in case_results}
    test_case_coverage = round((len(covered_case_ids) / len(test_cases) * 100) if test_cases else 0.0)

    issue_breakdown = Counter(issue.category for issue in issues if issue.status.lower() not in {"closed", "resolved"})
    status_breakdown = Counter(run.status for run in runs)
    coverage_breakdown = Counter(
        "90%+" if run.coverage_pct >= 90 else "80-89%" if run.coverage_pct >= 80 else "Below 80%"
        for run in runs
    )

    metrics = [
        DashboardMetric(label="Pass rate", value=f"{pass_rate}%", detail=f"{passing_runs} of {total_runs} test runs passed"),
        DashboardMetric(label="Coverage", value=f"{avg_coverage}%", detail="Average captured data coverage across recent runs"),
        DashboardMetric(label="Open issues", value=str(open_issues), detail=f"{critical_issues} critical or blocking findings"),
        DashboardMetric(label="Logger health", value=f"{healthy_loggers}/{total_runs}", detail="Runs reported healthy logger status"),
        DashboardMetric(label="Missing segments", value=str(total_missing), detail="Detected gaps across current runs"),
        DashboardMetric(label="Active plans", value=str(active_plans), detail="Planned or in-flight validation sessions"),
        DashboardMetric(label="Case pass rate", value=f"{case_pass_rate}%", detail=f"{passed_case_results} of {total_case_results} executed test cases passed"),
        DashboardMetric(label="Test case coverage", value=f"{test_case_coverage}%", detail=f"{len(covered_case_ids)} of {len(test_cases)} defined test cases executed"),
    ]

    recent_runs = [_serialize_run(run) for run in runs[:6]]
    open_issue_rows = [_serialize_issue(issue) for issue in issues if issue.status.lower() not in {"closed", "resolved"}][:6]
    recent_file_rows = [_serialize_file(file_record) for file_record in files[:6]]
    recent_test_cases = [_serialize_test_case(test_case) for test_case in test_cases[:6]]
    recent_case_results = [_serialize_case_result(case_result) for case_result in case_results[:6]]

    return DashboardResponse(
        metrics=metrics,
        status_breakdown=[TrendPoint(label=label, value=count) for label, count in status_breakdown.items()],
        issue_breakdown=[TrendPoint(label=label, value=count) for label, count in issue_breakdown.items()],
        coverage_breakdown=[TrendPoint(label=label, value=count) for label, count in coverage_breakdown.items()],
        recent_runs=recent_runs,
        open_issues=open_issue_rows,
        recent_files=recent_file_rows,
        recent_test_cases=recent_test_cases,
        recent_case_results=recent_case_results,
    )


@app.get("/api/plans")
def list_plans(db: Session = Depends(get_db)) -> list[dict]:
    plans = db.scalars(select(TestPlan).order_by(TestPlan.created_at.desc())).all()
    return [_serialize_plan(plan, db) for plan in plans]


@app.post("/api/plans")
def create_plan(payload: PlanCreate, db: Session = Depends(get_db)) -> dict:
    plan = TestPlan(**payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _serialize_plan(plan, db)


@app.get("/api/vehicles")
def list_vehicles(db: Session = Depends(get_db)) -> list[dict]:
    vehicles = db.scalars(select(VehicleConfig).order_by(VehicleConfig.created_at.desc())).all()
    return [_serialize_vehicle(vehicle, db) for vehicle in vehicles]


@app.post("/api/vehicles")
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)) -> dict:
    vehicle = VehicleConfig(**payload.model_dump(), last_checked_at=datetime.now(UTC))
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return _serialize_vehicle(vehicle, db)


@app.get("/api/runs")
def list_runs(db: Session = Depends(get_db)) -> list[dict]:
    runs = db.scalars(
        select(TestRun)
        .options(joinedload(TestRun.plan), joinedload(TestRun.vehicle))
        .order_by(TestRun.started_at.desc().nullslast(), TestRun.created_at.desc())
    ).all()
    return [_serialize_run(run) for run in runs]


@app.post("/api/runs")
def create_run(payload: RunCreate, db: Session = Depends(get_db)) -> dict:
    if payload.plan_id is not None and not db.get(TestPlan, payload.plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")
    if payload.vehicle_id is not None and not db.get(VehicleConfig, payload.vehicle_id):
        raise HTTPException(status_code=404, detail="Vehicle not found")
    run = TestRun(**payload.model_dump())
    db.add(run)
    db.commit()
    db.refresh(run)
    run = db.scalars(
        select(TestRun)
        .options(joinedload(TestRun.plan), joinedload(TestRun.vehicle))
        .where(TestRun.id == run.id)
    ).one()
    return _serialize_run(run)


@app.get("/api/test-cases")
def list_test_cases(db: Session = Depends(get_db)) -> list[dict]:
    test_cases = db.scalars(select(TestCase).options(joinedload(TestCase.plan)).order_by(TestCase.created_at.desc())).all()
    return [_serialize_test_case(test_case) for test_case in test_cases]


@app.post("/api/test-cases")
def create_test_case(payload: TestCaseCreate, db: Session = Depends(get_db)) -> dict:
    if payload.plan_id is not None and not db.get(TestPlan, payload.plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")
    exists = db.scalar(select(func.count(TestCase.id)).where(TestCase.case_id == payload.case_id)) or 0
    if exists:
        raise HTTPException(status_code=409, detail="case_id already exists")
    test_case = TestCase(**payload.model_dump())
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    test_case = db.scalars(select(TestCase).options(joinedload(TestCase.plan)).where(TestCase.id == test_case.id)).one()
    return _serialize_test_case(test_case)


@app.get("/api/test-case-results")
def list_test_case_results(db: Session = Depends(get_db)) -> list[dict]:
    case_results = db.scalars(
        select(TestCaseResult)
        .options(joinedload(TestCaseResult.run), joinedload(TestCaseResult.test_case))
        .order_by(TestCaseResult.executed_at.desc())
    ).all()
    return [_serialize_case_result(case_result) for case_result in case_results]


@app.post("/api/test-case-results")
def create_test_case_result(payload: TestCaseResultCreate, db: Session = Depends(get_db)) -> dict:
    run = db.get(TestRun, payload.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    test_case = db.get(TestCase, payload.test_case_id)
    if test_case is None:
        raise HTTPException(status_code=404, detail="Test case not found")

    result = TestCaseResult(**payload.model_dump())
    db.add(result)
    db.flush()
    _recompute_run_stats(db, run)
    db.commit()
    db.refresh(result)

    result = db.scalars(
        select(TestCaseResult)
        .options(joinedload(TestCaseResult.run), joinedload(TestCaseResult.test_case))
        .where(TestCaseResult.id == result.id)
    ).one()
    return _serialize_case_result(result)


@app.get("/api/issues")
def list_issues(db: Session = Depends(get_db)) -> list[dict]:
    issues = db.scalars(select(Issue).options(joinedload(Issue.run)).order_by(Issue.created_at.desc())).all()
    return [_serialize_issue(issue) for issue in issues]


@app.post("/api/issues")
def create_issue(payload: IssueCreate, db: Session = Depends(get_db)) -> dict:
    if payload.run_id is not None and not db.get(TestRun, payload.run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    issue = Issue(**payload.model_dump())
    db.add(issue)
    db.commit()
    db.refresh(issue)
    issue = db.scalars(select(Issue).options(joinedload(Issue.run)).where(Issue.id == issue.id)).one()
    return _serialize_issue(issue)


@app.patch("/api/issues/{issue_id}")
def update_issue(issue_id: int, payload: IssueUpdate, db: Session = Depends(get_db)) -> dict:
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    issue.status = payload.status
    db.commit()
    db.refresh(issue)
    issue = db.scalars(select(Issue).options(joinedload(Issue.run)).where(Issue.id == issue.id)).one()
    return _serialize_issue(issue)


@app.get("/api/files")
def list_files(db: Session = Depends(get_db)) -> list[dict]:
    files = db.scalars(select(CapturedFile).options(joinedload(CapturedFile.run)).order_by(CapturedFile.created_at.desc())).all()
    return [_serialize_file(file_record) for file_record in files]


@app.post("/api/files/upload")
async def upload_file(run_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    run = db.get(TestRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_name(file.filename or "capture.bin")
    storage_key = f"{uuid4().hex}_{safe_name}"
    destination = UPLOAD_DIR / storage_key

    hasher = sha256()
    size_bytes = 0
    with destination.open("wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            size_bytes += len(chunk)
            hasher.update(chunk)
            buffer.write(chunk)

    file_type = destination.suffix.lstrip(".").lower() or "unknown"
    tag_tokens = [token for token in safe_name.replace(".", "_").split("_") if token]
    tags = sorted({token.lower() for token in tag_tokens[:6]})
    missing_segments = ""
    if "gap" in safe_name.lower() or "missing" in safe_name.lower():
        missing_segments = "Potential gap detected from filename heuristic"

    record = CapturedFile(
        run_id=run_id,
        file_name=safe_name,
        storage_key=storage_key,
        file_type=file_type,
        size_bytes=size_bytes,
        checksum=hasher.hexdigest(),
        tags=tags,
        status="indexed",
        missing_segments=missing_segments,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    record = db.scalars(select(CapturedFile).options(joinedload(CapturedFile.run)).where(CapturedFile.id == record.id)).one()
    return _serialize_file(record)


@app.get("/api/summary", response_model=SimpleMessage)
def summary() -> SimpleMessage:
    return SimpleMessage(message="ADAS TestOps Platform is ready for validation planning, execution, and review.")


if FRONTEND_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True), name="frontend")