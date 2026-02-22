from contextlib import asynccontextmanager
from pathlib import Path
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.core.auth import hash_password
from app.core.config import settings
from app.api.tenant import router as tenant_router
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import AdminUser


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for _ in range(30):
        db: Session = SessionLocal()
        try:
            Base.metadata.create_all(bind=engine)
            existing = db.scalar(select(AdminUser).where(AdminUser.username == settings.admin_username))
            if existing is None:
                db.add(
                    AdminUser(
                        username=settings.admin_username,
                        password_hash=hash_password(settings.admin_password),
                    )
                )
                db.commit()
            last_error = None
            break
        except OperationalError as exc:
            last_error = exc
            time.sleep(2)
        finally:
            db.close()
    if last_error is not None:
        raise last_error
    yield


app = FastAPI(title="UtilityManager API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(tenant_router, prefix="/tenant", tags=["tenant"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
