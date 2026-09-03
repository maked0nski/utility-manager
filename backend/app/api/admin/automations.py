# Auto-extracted from the former monolithic admin.py during the
# 2026-09 domain-router split. Behavior is unchanged from the original.

from datetime import UTC, date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import require_write_access
from app.core.security import decrypt_text, encrypt_text
from app.db.session import get_db
from app.models import Apartment, ApartmentAutomation, ApartmentServiceConnection, AutomationCyclePhaseRun, AutomationCycleRun, AutomationRunLog, AutomationTemplate, ConnectionChargeLine, Meter, MeterReading, Provider
from app.schemas import ApartmentAutomationOut, ApartmentAutomationUpsert, AutomationCyclePhaseRunOut, AutomationCyclePreviewItem, AutomationCyclePreviewOut, AutomationCycleRunDetailOut, AutomationCycleRunLogDetailOut, AutomationCycleRunOut, AutomationRowOut, AutomationRunLogOut, AutomationTemplateCreate, AutomationTemplateOut, AutomationTemplateUpdate, MeterSubmitDispatchOut, MeterSubmitDispatchRequest, MeterSubmitEvaluateOut
import re
from ._shared import _infer_cycle_log_phase, _prev_month, _preview_reason

router = APIRouter()


@router.get("/automations", response_model=list[AutomationRowOut])
def list_automations(db: Session = Depends(get_db)):
    automations = db.scalars(
        select(ApartmentAutomation).order_by(ApartmentAutomation.apartment_id, ApartmentAutomation.id)
    ).all()
    apartments = {a.id: a for a in db.scalars(select(Apartment)).all()}
    out: list[AutomationRowOut] = []
    for automation in automations:
        apartment = apartments.get(automation.apartment_id)
        if apartment is None:
            continue
        service_name = _automation_service_name(db, automation=automation)
        out.append(_automation_row_out(db, automation, apartment, service_name))
    return out

@router.get("/automation-templates", response_model=list[AutomationTemplateOut])
def list_automation_templates(db: Session = Depends(get_db)):
    rows = db.scalars(select(AutomationTemplate).order_by(AutomationTemplate.name)).all()
    out: list[AutomationTemplateOut] = []
    for row in rows:
        out.append(
            AutomationTemplateOut(
                id=row.id,
                code=row.code,
                name=row.name,
                provider_id=row.provider_id,
                provider_name=row.provider.name_full if row.provider else None,
                utility_type=row.utility_type,
                cabinet_url=row.cabinet_url,
                description=row.description,
                supports_accrual=row.supports_accrual,
                supports_meter_submit=row.supports_meter_submit,
                is_active=row.is_active,
                created_at=row.created_at,
            )
        )
    return out

def _automation_template_out(row: AutomationTemplate) -> AutomationTemplateOut:
    return AutomationTemplateOut(
        id=row.id,
        code=row.code,
        name=row.name,
        provider_id=row.provider_id,
        provider_name=row.provider.name_full if row.provider else None,
        utility_type=row.utility_type,
        cabinet_url=row.cabinet_url,
        description=row.description,
        supports_accrual=row.supports_accrual,
        supports_meter_submit=row.supports_meter_submit,
        is_active=row.is_active,
        created_at=row.created_at,
    )

@router.post(
    "/automation-templates",
    response_model=AutomationTemplateOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write_access)],
)
def create_automation_template(payload: AutomationTemplateCreate, db: Session = Depends(get_db)):
    provider = db.get(Provider, payload.provider_id) if payload.provider_id else None
    if payload.provider_id and provider is None:
        raise HTTPException(status_code=404, detail="Provider not found.")
    row = AutomationTemplate(
        code=payload.code.strip(),
        name=payload.name.strip(),
        provider_id=payload.provider_id,
        utility_type=payload.utility_type,
        cabinet_url=payload.cabinet_url,
        description=payload.description,
        supports_accrual=payload.supports_accrual,
        supports_meter_submit=payload.supports_meter_submit,
        is_active=payload.is_active,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Automation template code already exists.")
    db.refresh(row)
    return _automation_template_out(row)

@router.put(
    "/automation-templates/{template_id}",
    response_model=AutomationTemplateOut,
    dependencies=[Depends(require_write_access)],
)
def update_automation_template(template_id: int, payload: AutomationTemplateUpdate, db: Session = Depends(get_db)):
    row = db.get(AutomationTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Automation template not found.")
    provider = db.get(Provider, payload.provider_id) if payload.provider_id else None
    if payload.provider_id and provider is None:
        raise HTTPException(status_code=404, detail="Provider not found.")
    row.code = payload.code.strip()
    row.name = payload.name.strip()
    row.provider_id = payload.provider_id
    row.utility_type = payload.utility_type
    row.cabinet_url = payload.cabinet_url
    row.description = payload.description
    row.supports_accrual = payload.supports_accrual
    row.supports_meter_submit = payload.supports_meter_submit
    row.is_active = payload.is_active
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Automation template code already exists.")
    db.refresh(row)
    return _automation_template_out(row)

@router.delete("/automation-templates/{template_id}", dependencies=[Depends(require_write_access)])
def delete_automation_template(template_id: int, db: Session = Depends(get_db)):
    row = db.get(AutomationTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Automation template not found.")
    linked = db.scalar(select(ApartmentAutomation.id).where(ApartmentAutomation.template_id == template_id).limit(1))
    if linked is not None:
        raise HTTPException(status_code=409, detail="Automation template is linked to apartments.")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}

@router.get("/apartments/{apartment_id}/automations", response_model=list[ApartmentAutomationOut])
def apartment_automations(apartment_id: int, db: Session = Depends(get_db)):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    rows = db.scalars(
        select(ApartmentAutomation)
        .where(ApartmentAutomation.apartment_id == apartment_id)
        .order_by(ApartmentAutomation.id.desc())
    ).all()
    out: list[ApartmentAutomationOut] = []
    for row in rows:
        out.append(_apartment_automation_out(row, apartment))
    return out

@router.put("/apartments/{apartment_id}/automations", response_model=ApartmentAutomationOut, dependencies=[Depends(require_write_access)])
def upsert_apartment_automation(apartment_id: int, payload: ApartmentAutomationUpsert, db: Session = Depends(get_db)):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    template = db.get(AutomationTemplate, payload.template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Automation template not found.")
    provider = db.get(Provider, payload.provider_id) if payload.provider_id else None
    if payload.provider_id and provider is None:
        raise HTTPException(status_code=404, detail="Provider not found.")
    row = db.scalar(
        select(ApartmentAutomation)
        .where(ApartmentAutomation.apartment_id == apartment_id)
        .where(ApartmentAutomation.template_id == payload.template_id)
    )
    if row is None:
        row = ApartmentAutomation(apartment_id=apartment_id, template_id=payload.template_id)
        db.add(row)
    row.provider_id = payload.provider_id or template.provider_id
    row.personal_account = payload.personal_account
    row.cabinet_url = payload.cabinet_url or template.cabinet_url
    row.cabinet_login = payload.cabinet_login
    if payload.cabinet_password is not None:
        row.cabinet_password_encrypted = encrypt_text(payload.cabinet_password)
    row.is_enabled = payload.is_enabled
    row.accrual_enabled = payload.accrual_enabled
    row.accrual_time = payload.accrual_time or "09:00"
    row.accrual_window_day_from = payload.accrual_window_day_from
    row.accrual_window_day_to = payload.accrual_window_day_to
    row.submit_enabled = payload.submit_enabled
    row.submit_time = payload.submit_time or "09:00"
    row.submit_window_day_from = payload.submit_window_day_from
    row.submit_window_day_to = payload.submit_window_day_to
    db.commit()
    db.refresh(row)
    return _apartment_automation_out(row, apartment)

@router.delete("/apartments/{apartment_id}/automations/{template_id}", dependencies=[Depends(require_write_access)])
def delete_apartment_automation(apartment_id: int, template_id: int, db: Session = Depends(get_db)):
    row = db.scalar(
        select(ApartmentAutomation)
        .where(ApartmentAutomation.apartment_id == apartment_id)
        .where(ApartmentAutomation.template_id == template_id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Apartment automation not found.")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}

@router.get("/automations/{automation_id}/logs", response_model=list[AutomationRunLogOut])
def automation_logs(automation_id: int, limit: int = 5, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(AutomationRunLog)
        .where(AutomationRunLog.automation_id == automation_id)
        .order_by(AutomationRunLog.started_at.desc())
        .limit(max(1, min(limit, 20)))
    ).all()
    return [
        AutomationRunLogOut(
            id=row.id,
            automation_id=row.automation_id,
            apartment_id=row.apartment_id,
            service_name=row.service_name,
            register_name=row.register_name,
            target_year=row.target_year,
            target_month=row.target_month,
            mode=row.mode,
            status=row.status,
            message=row.message,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )
        for row in rows
    ]

@router.post("/automations/run", response_model=AutomationRowOut, dependencies=[Depends(require_write_access)])
def run_automation_once(automation_id: int, mode: str = "full", db: Session = Depends(get_db)):
    # Local import avoids module cycle (worker imports _recalc_from_period from this module).
    from app.workers.tariff_auto_check import run_meter_submit_for_automation, run_tariff_auto_check_for_automation

    automation = db.get(ApartmentAutomation, automation_id)
    if automation is None:
        raise HTTPException(status_code=404, detail="Automation not found.")
    apartment = db.get(Apartment, automation.apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")

    run_mode = (mode or "full").strip().lower()
    if run_mode not in {"full", "readings", "tariffs"}:
        raise HTTPException(status_code=400, detail="Invalid automation run mode.")
    try:
        if run_mode in {"full", "tariffs"}:
            run_tariff_auto_check_for_automation(db, automation=automation, now_utc=datetime.now(UTC))
        if run_mode in {"full", "readings"}:
            run_meter_submit_for_automation(db, automation=automation, now_utc=datetime.now(UTC))
    except Exception:
        db.refresh(automation)
        raise
    db.refresh(automation)
    return _automation_row_out(db, automation, apartment, _automation_service_name(db, automation=automation))

@router.post("/automations/run-cycle", response_model=AutomationCycleRunOut, dependencies=[Depends(require_write_access)])
def run_automation_cycle(db: Session = Depends(get_db)):
    from app.workers.tariff_auto_check import run_tariff_auto_checks

    result = run_tariff_auto_checks(db, trigger_mode="manual") or {}
    return AutomationCycleRunOut(
        id=int(result["id"]) if result.get("id") is not None else None,
        trigger_mode=str(result.get("trigger_mode") or "manual"),
        processed_accrual_automations=int(result.get("processed_accrual_automations", 0)),
        processed_submit_automations=int(result.get("processed_submit_automations", 0)),
        processed_legacy_settings=int(result.get("processed_legacy_settings", 0)),
        submitted_readings=int(result.get("submitted_readings", 0)),
        message=str(
            result.get("message")
            or (
                "Плановий цикл виконано: "
                f"accrual={int(result.get('processed_accrual_automations', 0))}, "
                f"submit={int(result.get('processed_submit_automations', 0))}, "
                f"submitted={int(result.get('submitted_readings', 0))}"
            )
        ),
        started_at=result.get("started_at"),
        finished_at=result.get("finished_at"),
    )

@router.get("/automations/cycle-runs", response_model=list[AutomationCycleRunOut])
def automation_cycle_runs(limit: int = 10, trigger_mode: str | None = None, db: Session = Depends(get_db)):
    safe_limit = max(1, min(limit, 50))
    query = select(AutomationCycleRun)
    if (trigger_mode or "").strip():
        query = query.where(AutomationCycleRun.trigger_mode == trigger_mode.strip().lower())
    rows = db.scalars(query.order_by(AutomationCycleRun.started_at.desc(), AutomationCycleRun.id.desc()).limit(safe_limit)).all()
    phase_rows = db.scalars(
        select(AutomationCyclePhaseRun)
        .where(AutomationCyclePhaseRun.cycle_run_id.in_([row.id for row in rows] or [-1]))
        .order_by(AutomationCyclePhaseRun.cycle_run_id.desc(), AutomationCyclePhaseRun.started_at.asc(), AutomationCyclePhaseRun.id.asc())
    ).all()
    phases_by_cycle: dict[int, list[AutomationCyclePhaseRunOut]] = {}
    for phase in phase_rows:
        phases_by_cycle.setdefault(phase.cycle_run_id, []).append(
            AutomationCyclePhaseRunOut(
                id=phase.id,
                phase=phase.phase,
                status=phase.status,
                processed_count=phase.processed_count,
                skipped_count=phase.skipped_count,
                submitted_readings=phase.submitted_readings,
                duration_ms=phase.duration_ms,
                message=phase.message,
                started_at=phase.started_at,
                finished_at=phase.finished_at,
            )
        )
    return [
        AutomationCycleRunOut(
            id=row.id,
            trigger_mode=row.trigger_mode,
            processed_accrual_automations=row.processed_accrual_automations,
            processed_submit_automations=row.processed_submit_automations,
            processed_legacy_settings=row.processed_legacy_settings,
            submitted_readings=row.submitted_readings,
            message=row.message or "Плановий цикл виконано",
            started_at=row.started_at,
            finished_at=row.finished_at,
            phases=phases_by_cycle.get(row.id, []),
        )
        for row in rows
    ]

@router.get("/automations/cycle-runs/{cycle_run_id}", response_model=AutomationCycleRunDetailOut)
def automation_cycle_run_detail(
    cycle_run_id: int,
    apartment_id: int | None = None,
    db: Session = Depends(get_db),
):
    cycle = db.get(AutomationCycleRun, cycle_run_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Automation cycle run not found.")
    phase_rows = db.scalars(
        select(AutomationCyclePhaseRun)
        .where(AutomationCyclePhaseRun.cycle_run_id == cycle_run_id)
        .order_by(AutomationCyclePhaseRun.started_at.asc(), AutomationCyclePhaseRun.id.asc())
    ).all()
    logs_query = (
        select(AutomationRunLog)
        .where(AutomationRunLog.started_at >= cycle.started_at)
        .where(AutomationRunLog.started_at <= (cycle.finished_at or cycle.started_at))
        .order_by(AutomationRunLog.started_at.desc(), AutomationRunLog.id.desc())
    )
    if apartment_id is not None:
        logs_query = logs_query.where(AutomationRunLog.apartment_id == apartment_id)
    logs = db.scalars(logs_query.limit(200)).all()
    apartment_map = {row.id: row.address for row in db.scalars(select(Apartment)).all()}
    return AutomationCycleRunDetailOut(
        id=cycle.id,
        trigger_mode=cycle.trigger_mode,
        message=cycle.message or "Плановий цикл виконано",
        started_at=cycle.started_at,
        finished_at=cycle.finished_at,
        phases=[
            AutomationCyclePhaseRunOut(
                id=phase.id,
                phase=phase.phase,
                status=phase.status,
                processed_count=phase.processed_count,
                skipped_count=phase.skipped_count,
                submitted_readings=phase.submitted_readings,
                duration_ms=phase.duration_ms,
                message=phase.message,
                started_at=phase.started_at,
                finished_at=phase.finished_at,
            )
            for phase in phase_rows
        ],
        logs=[
            AutomationCycleRunLogDetailOut(
                id=log.id,
                apartment_id=log.apartment_id,
                apartment_address=apartment_map.get(log.apartment_id, "—"),
                service_name=log.service_name,
                phase=_infer_cycle_log_phase(log),
                mode=log.mode,
                status=log.status,
                register_name=log.register_name,
                target_year=log.target_year,
                target_month=log.target_month,
                message=log.message,
                started_at=log.started_at,
                finished_at=log.finished_at,
            )
            for log in logs
        ],
    )

@router.get("/automations/run-cycle-preview", response_model=AutomationCyclePreviewOut)
def run_automation_cycle_preview(db: Session = Depends(get_db)):
    items: list[AutomationCyclePreviewItem] = []
    started_at = datetime.now(UTC)
    apartments = {a.id: a for a in db.scalars(select(Apartment)).all()}
    automations = db.scalars(
        select(ApartmentAutomation).order_by(ApartmentAutomation.apartment_id, ApartmentAutomation.id)
    ).all()
    for automation in automations:
        apartment = apartments.get(automation.apartment_id)
        if apartment is None:
            continue
        service_name = automation.template.name if automation.template else "Автоматизація"
        submit_next_at, submit_reason = _build_submit_meta(db, automation=automation, apartment=apartment)
        if automation.is_enabled and automation.accrual_enabled:
            reason_code, reason_text = _preview_reason(
                "accrual_ready" if not automation.accrual_completed_for_period else "accrual_completed",
                "Готово до планового accrual-запуску."
                if not automation.accrual_completed_for_period
                else "Accrual для поточного періоду вже завершено.",
            )
            items.append(
                AutomationCyclePreviewItem(
                    automation_id=automation.id,
                    apartment_id=automation.apartment_id,
                    apartment_address=apartment.address,
                    service_name=service_name,
                    phase="accrual",
                    action="run" if not automation.accrual_completed_for_period else "skip",
                    reason_code=reason_code,
                    reason=reason_text,
                )
            )
        if automation.submit_enabled:
            submit_code = "submit_ready"
            if submit_reason:
                low = submit_reason.casefold()
                if "вимк" in low:
                    submit_code = "submit_disabled"
                elif "бракує credentials" in low or "бракує" in low:
                    submit_code = "submit_missing_credentials"
                elif "поза вікном" in low:
                    submit_code = "submit_outside_window"
                elif "немає показника" in low:
                    submit_code = "submit_missing_reading"
                elif "вже передано" in low or "вже подано" in low:
                    submit_code = "submit_completed"
                elif "готово" in low:
                    submit_code = "submit_ready"
            items.append(
                AutomationCyclePreviewItem(
                    automation_id=automation.id,
                    apartment_id=automation.apartment_id,
                    apartment_address=apartment.address,
                    service_name=service_name,
                    phase="submit",
                    action="run" if (submit_reason or "").startswith("Готово") else "skip",
                    reason_code=submit_code,
                    reason=submit_reason or (f"Наступний submit: {submit_next_at.isoformat()}" if submit_next_at else "Невідомий стан submit."),
                )
            )
    processed_accrual = sum(1 for item in items if item.phase == "accrual" and item.action == "run")
    processed_submit = sum(1 for item in items if item.phase == "submit" and item.action == "run")
    processed_legacy = sum(1 for item in items if item.phase == "legacy" and item.action == "run")
    cycle_row = AutomationCycleRun(
        trigger_mode="dry-run",
        processed_accrual_automations=processed_accrual,
        processed_submit_automations=processed_submit,
        processed_legacy_settings=processed_legacy,
        submitted_readings=0,
        message=f"Dry-run: accrual={processed_accrual}, submit={processed_submit}, legacy={processed_legacy}"[:255],
        started_at=started_at,
        finished_at=datetime.now(UTC),
    )
    db.add(cycle_row)
    db.flush()
    for phase_name in ("accrual", "submit", "legacy"):
        phase_items = [item for item in items if item.phase == phase_name]
        db.add(
            AutomationCyclePhaseRun(
                cycle_run_id=cycle_row.id,
                phase=phase_name,
                status="completed",
                processed_count=sum(1 for item in phase_items if item.action == "run"),
                skipped_count=sum(1 for item in phase_items if item.action != "run"),
                submitted_readings=0,
                duration_ms=max(int((datetime.now(UTC) - started_at).total_seconds() * 1000), 0),
                message=f"Dry-run {phase_name}: run={sum(1 for item in phase_items if item.action == 'run')}, skip={sum(1 for item in phase_items if item.action != 'run')}"[:255],
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )
        )
    db.commit()
    return AutomationCyclePreviewOut(
        items=items,
        message=f"Підготовлено {len(items)} записів preview планового циклу.",
    )

def _automation_row_out(db: Session, automation: ApartmentAutomation, apartment: Apartment, service_name: str) -> AutomationRowOut:
    submit_next_at, submit_state_reason = _build_submit_meta(db, automation=automation, apartment=apartment)
    return AutomationRowOut(
        automation_id=automation.id,
        template_id=automation.template_id,
        template_name=automation.template.name if automation.template else None,
        template_code=automation.template.code if automation.template else None,
        apartment_id=automation.apartment_id,
        apartment_code=apartment.code,
        apartment_address=apartment.address,
        service_name=service_name,
        provider_id=automation.provider_id,
        provider_name=automation.provider.name_full if automation.provider else (automation.template.provider.name_full if automation.template and automation.template.provider else None),
        provider_company=automation.provider.name_full if automation.provider else (automation.template.provider.name_full if automation.template and automation.template.provider else None),
        personal_account=automation.personal_account,
        cabinet_url=automation.cabinet_url,
        cabinet_login=automation.cabinet_login,
        cabinet_password=decrypt_text(automation.cabinet_password_encrypted),
        auto_check_enabled=automation.is_enabled and automation.accrual_enabled,
        auto_check_time=automation.accrual_time,
        auto_check_timezone=apartment.timezone or "Europe/Kyiv",
        auto_check_window_day_from=automation.accrual_window_day_from,
        auto_check_window_day_to=automation.accrual_window_day_to,
        auto_check_target_year=automation.auto_check_target_year,
        auto_check_target_month=automation.auto_check_target_month,
        auto_check_completed_for_period=automation.accrual_completed_for_period,
        auto_check_status=automation.auto_check_status,
        auto_check_message=automation.auto_check_message,
        auto_check_last_value_raw=None,
        auto_check_last_value_rounded=None,
        auto_check_last_checked_at=automation.auto_check_last_checked_at,
        auto_check_last_updated_at=automation.auto_check_last_updated_at,
        auto_check_next_at=automation.auto_check_next_at,
        submit_enabled=automation.submit_enabled and automation.is_enabled,
        submit_time=automation.submit_time,
        submit_window_day_from=automation.submit_window_day_from,
        submit_window_day_to=automation.submit_window_day_to,
        submit_target_year=automation.submit_target_year,
        submit_target_month=automation.submit_target_month,
        submit_completed_for_period=automation.submit_completed_for_period,
        submit_next_at=submit_next_at,
        submit_state_reason=submit_state_reason,
    )

def _apartment_automation_out(row: ApartmentAutomation, apartment: Apartment) -> ApartmentAutomationOut:
    submit_next_at, submit_state_reason = _build_submit_meta(None, automation=row, apartment=apartment)
    return ApartmentAutomationOut(
        id=row.id,
        apartment_id=row.apartment_id,
        apartment_address=apartment.address,
        apartment_timezone=apartment.timezone or "Europe/Kyiv",
        template_id=row.template_id,
        template_name=row.template.name if row.template else "—",
        template_code=row.template.code if row.template else "—",
        provider_id=row.provider_id,
        provider_name=row.provider.name_full if row.provider else (row.template.provider.name_full if row.template and row.template.provider else None),
        personal_account=row.personal_account,
        cabinet_url=row.cabinet_url,
        cabinet_login=row.cabinet_login,
        cabinet_password=decrypt_text(row.cabinet_password_encrypted),
        is_enabled=row.is_enabled,
        accrual_enabled=row.accrual_enabled,
        accrual_time=row.accrual_time,
        accrual_window_day_from=row.accrual_window_day_from,
        accrual_window_day_to=row.accrual_window_day_to,
        submit_enabled=row.submit_enabled,
        submit_time=row.submit_time,
        submit_window_day_from=row.submit_window_day_from,
        submit_window_day_to=row.submit_window_day_to,
        submit_target_year=row.submit_target_year,
        submit_target_month=row.submit_target_month,
        submit_completed_for_period=row.submit_completed_for_period,
        submit_next_at=submit_next_at,
        submit_state_reason=submit_state_reason,
        auto_check_status=row.auto_check_status,
        auto_check_message=row.auto_check_message,
        auto_check_last_checked_at=row.auto_check_last_checked_at,
        auto_check_last_updated_at=row.auto_check_last_updated_at,
        auto_check_next_at=row.auto_check_next_at,
    )

def _create_automation_log(
    db: Session,
    *,
    automation_id: int | None,
    apartment_id: int,
    service_name: str,
    register_name: str | None = None,
    target_year: int | None = None,
    target_month: int | None = None,
    mode: str,
) -> AutomationRunLog:
    row = AutomationRunLog(
        automation_id=automation_id,
        apartment_id=apartment_id,
        service_name=service_name,
        register_name=register_name,
        target_year=target_year,
        target_month=target_month,
        mode=mode,
        status="running",
        started_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    return row

def _finish_automation_log(db: Session, row: AutomationRunLog, status: str, message: str | None) -> None:
    row.status = status or "unknown"
    row.message = (message or "")[:255] if message else None
    row.finished_at = datetime.now(UTC)

def _is_day_in_window(day: int, day_from: int, day_to: int) -> bool:
    if day_from <= day_to:
        return day_from <= day <= day_to
    return day >= day_from or day <= day_to

def _target_period_for_window(local_now: datetime, day_from: int, day_to: int) -> tuple[int, int]:
    if day_from > day_to:
        if local_now.day >= day_from:
            return local_now.year, local_now.month
        return _prev_month(local_now.year, local_now.month)
    return local_now.year, local_now.month

def _resolve_hhmm(value: str | None) -> tuple[int, int]:
    raw = (value or "").strip()
    if not re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", raw):
        return 9, 0
    hh, mm = raw.split(":")
    return int(hh), int(mm)

def _next_window_run_at(local_now: datetime, hh: int, mm: int, day_from: int, day_to: int) -> datetime:
    planned_today = local_now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if _is_day_in_window(local_now.day, day_from, day_to) and local_now < planned_today:
        return planned_today
    candidate = local_now + timedelta(days=1)
    for _ in range(62):
        if _is_day_in_window(candidate.day, day_from, day_to):
            return candidate.replace(hour=hh, minute=mm, second=0, microsecond=0)
        candidate += timedelta(days=1)
    return planned_today + timedelta(days=1)

def _connection_active_on(connection: ApartmentServiceConnection, target_date: date) -> bool:
    if connection.started_at and connection.started_at > target_date:
        return False
    if connection.ended_at and connection.ended_at < target_date:
        return False
    return (connection.status or "active").strip().lower() != "inactive"

def _charge_line_active_on(line: ConnectionChargeLine, target_date: date) -> bool:
    if not line.is_active:
        return False
    if line.effective_from and line.effective_from > target_date:
        return False
    if line.effective_to and line.effective_to < target_date:
        return False
    return True

def _automation_connections(
    db: Session,
    *,
    apartment_id: int,
    automation_id: int | None = None,
    provider_id: int | None = None,
    target_date: date | None = None,
) -> list[ApartmentServiceConnection]:
    query = select(ApartmentServiceConnection).where(ApartmentServiceConnection.apartment_id == apartment_id)
    if automation_id is not None:
        query = query.where(ApartmentServiceConnection.automation_id == automation_id)
    elif provider_id is not None:
        query = query.where(ApartmentServiceConnection.provider_id == provider_id)
    rows = db.scalars(query.order_by(ApartmentServiceConnection.id.asc())).all()
    if target_date is None:
        return rows
    return [row for row in rows if _connection_active_on(row, target_date)]

def _automation_service_name(
    db: Session,
    *,
    automation: ApartmentAutomation,
    target_date: date | None = None,
) -> str:
    connections = _automation_connections(
        db,
        apartment_id=automation.apartment_id,
        automation_id=automation.id,
        target_date=target_date,
    )
    service_names = sorted(
        {
            (connection.service_catalog.name or "").strip()
            for connection in connections
            if connection.service_catalog and (connection.service_catalog.name or "").strip()
        },
        key=lambda value: value.lower(),
    )
    if service_names:
        return ", ".join(service_names)
    if automation.template and (automation.template.name or "").strip():
        return automation.template.name.strip()
    if automation.provider and (automation.provider.name_full or "").strip():
        return automation.provider.name_full.strip()
    return "Автоматизація"

def _provider_meter_bindings(
    db: Session,
    *,
    apartment_id: int,
    provider_id: int | None,
    year: int,
    month: int,
) -> list[tuple[ApartmentServiceConnection, ConnectionChargeLine]]:
    if provider_id is None:
        return []
    target_date = date(year, month, 1)
    bindings: list[tuple[ApartmentServiceConnection, ConnectionChargeLine]] = []
    for connection in _automation_connections(
        db,
        apartment_id=apartment_id,
        provider_id=provider_id,
        target_date=target_date,
    ):
        charge_lines = db.scalars(
            select(ConnectionChargeLine)
            .where(ConnectionChargeLine.connection_id == connection.id)
            .where(ConnectionChargeLine.meter_id.is_not(None))
            .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
        ).all()
        for line in charge_lines:
            if line.meter_id is None or not _charge_line_active_on(line, target_date):
                continue
            bindings.append((connection, line))
    return bindings

def _has_submit_reading_for_period(
    db: Session,
    *,
    apartment_id: int,
    provider_id: int | None,
    year: int,
    month: int,
) -> bool:
    if provider_id is None:
        return False
    for _, line in _provider_meter_bindings(
        db,
        apartment_id=apartment_id,
        provider_id=provider_id,
        year=year,
        month=month,
    ):
        if line.meter_id is None:
            continue
        reading = db.scalar(
            select(MeterReading.id)
            .where(MeterReading.meter_id == line.meter_id)
            .where(MeterReading.register_name == (line.meter_register or "total"))
            .where(MeterReading.year == year)
            .where(MeterReading.month == month)
            .limit(1)
        )
        if reading is not None:
            return True
    return False

def _resolve_submit_meter_bindings(
    db: Session,
    *,
    apartment_id: int,
    service_names: list[str] | set[str],
    year: int,
    month: int,
) -> dict[str, tuple[int, str]]:
    wanted = [name for name in service_names if (name or "").strip()]
    if not wanted:
        return {}
    bindings: dict[str, tuple[int, str]] = {}
    target_date = date(year, month, 1)
    connections = db.scalars(
        select(ApartmentServiceConnection)
        .where(ApartmentServiceConnection.apartment_id == apartment_id)
        .where(ApartmentServiceConnection.started_at <= target_date)
        .where((ApartmentServiceConnection.ended_at.is_(None)) | (ApartmentServiceConnection.ended_at >= target_date))
        .where(ApartmentServiceConnection.status == "active")
        .order_by(ApartmentServiceConnection.id.asc())
    ).all()
    wanted_set = {name.strip() for name in wanted}
    for connection in connections:
        if connection.service_catalog is None or connection.service_catalog.name not in wanted_set:
            continue
        charge_lines = db.scalars(
            select(ConnectionChargeLine)
            .where(ConnectionChargeLine.connection_id == connection.id)
            .where(ConnectionChargeLine.meter_id.is_not(None))
            .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
        ).all()
        for line in charge_lines:
            if line.meter_id is None or not _charge_line_active_on(line, target_date):
                continue
            bindings.setdefault(connection.service_catalog.name, (line.meter_id, line.meter_register or "total"))
            break
    return bindings

def _build_submit_meta(
    db: Session | None,
    *,
    automation: ApartmentAutomation,
    apartment: Apartment,
) -> tuple[datetime | None, str | None]:
    if not automation.is_enabled or not automation.submit_enabled:
        return None, "Подача показників вимкнена."
    if not (automation.cabinet_url or "").strip() or not (automation.cabinet_login or "").strip() or not decrypt_text(automation.cabinet_password_encrypted):
        return None, "Бракує credentials кабінету."
    timezone_name = apartment.timezone or "Europe/Kyiv"
    try:
        from zoneinfo import ZoneInfo

        local_now = datetime.now(ZoneInfo(timezone_name))
    except Exception:
        local_now = datetime.now()
    day_from = automation.submit_window_day_from or 28
    day_to = automation.submit_window_day_to or 3
    hh, mm = _resolve_hhmm(automation.submit_time)
    next_submit_local = _next_window_run_at(local_now, hh, mm, day_from, day_to)
    target_year, target_month = _target_period_for_window(local_now, day_from, day_to)
    if automation.submit_completed_for_period and automation.submit_target_year == target_year and automation.submit_target_month == target_month:
        return next_submit_local.astimezone(UTC), "Показник за поточний період уже передано."
    if not _is_day_in_window(local_now.day, day_from, day_to):
        return next_submit_local.astimezone(UTC), "Поточна дата поза вікном подачі."
    if db is None:
        return next_submit_local.astimezone(UTC), "Стан показника буде уточнено після наступної перевірки."
    has_reading = _has_submit_reading_for_period(
        db,
        apartment_id=automation.apartment_id,
        provider_id=automation.provider_id,
        year=target_year,
        month=target_month,
    )
    if not has_reading:
        return next_submit_local.astimezone(UTC), f"Немає показника в БД за {target_month:02d}.{target_year}."
    return next_submit_local.astimezone(UTC), "Готово до подачі при наступному submit-запуску."

@router.get("/automations/meter-submit/evaluate", response_model=MeterSubmitEvaluateOut)
def evaluate_meter_submit(
    apartment_id: int,
    meter_id: int,
    register_name: str,
    year: int,
    month: int,
    db: Session = Depends(get_db),
):
    apartment = db.get(Apartment, apartment_id)
    if apartment is None:
        raise HTTPException(status_code=404, detail="Apartment not found.")
    register_name = (register_name or "total").strip() or "total"
    target_date = date(year, month, 1)
    matching_connections: list[ApartmentServiceConnection] = []
    for connection in _automation_connections(db, apartment_id=apartment_id, target_date=target_date):
        charge_lines = db.scalars(
            select(ConnectionChargeLine)
            .where(ConnectionChargeLine.connection_id == connection.id)
            .where(ConnectionChargeLine.meter_id == meter_id)
            .where(ConnectionChargeLine.meter_register == register_name)
            .order_by(ConnectionChargeLine.effective_from.desc(), ConnectionChargeLine.id.desc())
        ).all()
        if any(_charge_line_active_on(line, target_date) for line in charge_lines):
            matching_connections.append(connection)
    if not matching_connections:
        meter = db.get(Meter, meter_id)
        if meter is None or meter.apartment_id != apartment_id:
            return MeterSubmitEvaluateOut(can_submit=False, reason="Лічильник не знайдено для цього об'єкта.")
        return MeterSubmitEvaluateOut(
            can_submit=False,
            reason="Для цього показника немає підключеної послуги з прив'язкою до лічильника.",
        )
    automation_ids = {connection.automation_id for connection in matching_connections if connection.automation_id is not None}
    provider_ids = {connection.provider_id for connection in matching_connections if connection.provider_id is not None}
    if not automation_ids and not provider_ids:
        return MeterSubmitEvaluateOut(can_submit=False, reason="Для тарифу не вказано постачальника з automation.")

    automations = db.scalars(
        select(ApartmentAutomation)
        .where(ApartmentAutomation.apartment_id == apartment_id)
        .where(ApartmentAutomation.is_enabled == True)  # noqa: E712
        .where(ApartmentAutomation.submit_enabled == True)  # noqa: E712
        .order_by(ApartmentAutomation.id.desc())
    ).all()
    automations = [
        automation
        for automation in automations
        if automation.id in automation_ids or (automation.provider_id is not None and automation.provider_id in provider_ids)
    ]
    if not automations:
        return MeterSubmitEvaluateOut(can_submit=False, reason="Для постачальника не підключено automation подачі показників.")

    tz = apartment.timezone or "Europe/Kyiv"
    local_now = datetime.now()
    try:
        from zoneinfo import ZoneInfo

        local_now = datetime.now(ZoneInfo(tz))
    except Exception:
        pass

    for automation in automations:
        if not _is_day_in_window(local_now.day, automation.submit_window_day_from, automation.submit_window_day_to):
            continue
        target_year, target_month = _target_period_for_window(
            local_now,
            automation.submit_window_day_from,
            automation.submit_window_day_to,
        )
        if year != target_year or month != target_month:
            continue
        if automation.submit_target_year != target_year or automation.submit_target_month != target_month:
            automation.submit_target_year = target_year
            automation.submit_target_month = target_month
            automation.submit_completed_for_period = False
            db.add(automation)
            db.commit()
            db.refresh(automation)
        if automation.submit_completed_for_period:
            return MeterSubmitEvaluateOut(
                can_submit=False,
                reason="Показник для поточного періоду вже передано раніше.",
                automation_id=automation.id,
                template_name=automation.template.name if automation.template else None,
                target_year=target_year,
                target_month=target_month,
            )
        return MeterSubmitEvaluateOut(
            can_submit=True,
            reason="Показник відповідає поточному періоду та вікну подачі.",
            automation_id=automation.id,
            template_name=automation.template.name if automation.template else None,
            target_year=target_year,
            target_month=target_month,
        )

    return MeterSubmitEvaluateOut(
        can_submit=False,
        reason="Показник не входить у поточне вікно подачі або це не поточний період.",
    )

@router.post("/automations/meter-submit/dispatch", response_model=MeterSubmitDispatchOut, dependencies=[Depends(require_write_access)])
def dispatch_meter_submit(payload: MeterSubmitDispatchRequest, db: Session = Depends(get_db)):
    # Local import avoids module cycle.
    from app.workers.tariff_auto_check import run_meter_submit_for_automation

    check = evaluate_meter_submit(
        apartment_id=payload.apartment_id,
        meter_id=payload.meter_id,
        register_name=payload.register_name,
        year=payload.year,
        month=payload.month,
        db=db,
    )
    if not check.can_submit:
        return MeterSubmitDispatchOut(dispatched=False, message=check.reason)
    if check.automation_id is None:
        return MeterSubmitDispatchOut(dispatched=False, message="Automation не знайдено.")

    automation = db.get(ApartmentAutomation, check.automation_id)
    if automation is None:
        return MeterSubmitDispatchOut(dispatched=False, message="Automation недоступна для відправки.")
    try:
        dispatched = run_meter_submit_for_automation(db, automation=automation, now_utc=datetime.now(UTC))
    except Exception as error:
        return MeterSubmitDispatchOut(dispatched=False, message=f"Помилка запуску: {error}")
    db.refresh(automation)
    if dispatched:
        return MeterSubmitDispatchOut(dispatched=True, message="Automation подачі показника запущена.")
    return MeterSubmitDispatchOut(
        dispatched=False,
        message=automation.auto_check_message or "Automation не виконала подачу показника.",
    )
