# Combines the per-domain admin routers into the single `router` that
# `app.main` mounts under the `/admin` prefix. Split out of one 5000+ line
# admin.py during the 2026-09 domain-router refactor; behavior/URLs unchanged.
from fastapi import APIRouter, Depends

from app.api.deps import require_authenticated_admin

from . import (
    apartments,
    automations,
    billing,
    dashboard,
    expenses,
    legacy,
    meters,
    payments,
    references,
    tariffs,
    tenants,
)

router = APIRouter(dependencies=[Depends(require_authenticated_admin)])

for module in (
    apartments,
    tenants,
    meters,
    legacy,
    tariffs,
    billing,
    payments,
    dashboard,
    references,
    automations,
    expenses,
):
    router.include_router(module.router)
