# Automation Template For New Tariffs And Cabinets

## Purpose
Use this document as a baseline for implementing a new tariff automation with a different provider cabinet.

## A. Discovery Checklist
1. Identify exact target service name in our system (`service_name` in Tariff).
2. Confirm provider cabinet URL/login/password source.
3. Identify real data source in cabinet page:
   - visible table cell;
   - ajax endpoint;
   - modal payload.
4. Define target period rule (usually previous month).
5. Define waiting criteria (empty cell, explicit message, etc.).
6. Define completion condition for monthly cycle.

## B. Business Rules Contract
Specify explicitly:
1. Compare rule: `new <= current => no_change`, `new > current => update`.
2. Rounding rule.
3. Schedule default and configurable parts (time/timezone/day window).
4. Stop condition for current target month.
5. UI states (`waiting/no_change/updated/error`) and icon mapping.

## C. Data Contract (ApartmentTariffSetting)
Required fields for any automation:
- enable flag
- schedule (time, timezone, day window)
- target period (year, month)
- completion flag
- last status/message
- last raw/rounded values
- timestamps (checked/updated/next)

## D. Worker Contract
Worker must implement:
1. `collect` - login + fetch + parse raw value.
2. `decide` - apply business rules.
3. `apply` - persist tariff changes if needed.
4. `report` - persist status/tooltip data for UI.

## E. Quality Gates
1. Idempotent re-run.
2. No secret leakage in logs.
3. Robust parsing against extra spaces/newlines.
4. Graceful handling of network errors.
5. Recovery on next day run.

## F. Implementation Prompt (Detailed)
Use this prompt when starting a new provider implementation:

"""
Implement tariff automation for provider <PROVIDER_NAME> and service <SERVICE_NAME>.

Context:
- Project: utility-manager
- Backend: FastAPI + SQLAlchemy
- Worker entry: app/workers/provider_sync.py
- Tariff setting model: ApartmentTariffSetting

Business rules:
- target period: previous month
- window: <DAY_FROM>..<DAY_TO>
- time: <HH:MM>
- timezone: <TIMEZONE>
- waiting criteria: <DEFINE>
- compare rule: new <= db => no_change; new > db => update
- rounding: <DEFINE>
- complete cycle on status in {no_change, updated}

Provider technical details:
- login url: <URL>
- auth endpoint: <ENDPOINT>
- data endpoint/page: <ENDPOINT_OR_PAGE>
- selectors/parsing rules: <DETAILS>

Required output:
1. Backend model/migration updates for schedule+status fields if missing.
2. Worker implementation for this provider.
3. UI indicators on tariff rows with tooltip message.
4. Tests for waiting/no_change/updated/error and monthly cycle completion.
5. Documentation update in root markdown file.

Constraints:
- Keep implementation idempotent.
- Avoid exposing raw cabinet password in logs.
- Prefer deterministic parsing over visual scraping when endpoint exists.
"""

## G. Rollout Plan
1. Dry-run mode for one apartment/tariff.
2. Validate statuses for 2-3 days.
3. Enable for more tariffs gradually.
4. Add alerts for repeated `error` status.
