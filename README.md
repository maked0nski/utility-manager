## Utility Manager

Monorepo для керування комунальними нарахуваннями, орендою та операціями по об'єктах нерухомості.

## Структура

```text
utility-manager/
  .env                      # локальні змінні середовища (не комітиться)
  .env.example              # приклад env
  docker-compose.yml
  PROJECT_DOCUMENTATION.md  # повна документація
  TODO.md                   # актуальний план робіт
  docker/                   # інфраструктурні артефакти (init/sql тощо)
  backend/                  # FastAPI + SQLAlchemy + Alembic
    app/
    alembic/
    tests/                  # backend інтеграційні/API тести (pytest)
  frontend/                 # React + Vite + TypeScript
    src/
    Dockerfile
```

## Принцип розміщення файлів

- Все спільне для backend/frontend: тільки в root (`.env`, документація, docker-compose).
- Все сервіс-специфічне: тільки у відповідному каталозі (`backend/*`, `frontend/*`).
- Тести зберігаються в межах сервісу:
  - backend: `backend/tests`
  - frontend: `frontend/src/**/*.test.*`

## Швидкий старт

1. Створити локальний env:
   - `copy .env.example .env`
2. Запустити контейнери:
   - `docker compose up -d --build`
3. Перевірити:
   - API: `http://localhost:<API_PORT>/health`
   - Frontend: `http://localhost:<FRONTEND_PORT>`
   - Adminer: `http://localhost:<ADMINER_PORT>`
   - Worker (optional run): `docker compose run --rm worker`

Альтернатива через root script:
- `npm run dev:up`

## Локальна розробка без Docker

Backend:
- `cd backend`
- `.\.venv\Scripts\python -m pytest -q`
- `.\.venv\Scripts\uvicorn app.main:app --reload`

Frontend:
- `cd frontend`
- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run dev`
- `npm run ui:add button` (додавання shadcn компонентів)

## Якість коду перед комітом

- Backend: `cd backend && .\.venv\Scripts\python -m pytest -q`
- Frontend: `cd frontend && npm run lint && npm run typecheck && npm run test`
- Все разом з root: `npm run check:all`

## CI

Workflow: `.github/workflows/ci.yml`
- backend: `pytest -q`
- frontend: `lint + typecheck + test + build`

## UI Toolkit

- Tailwind + shadcn база налаштована у `frontend/`:
  - `tailwind.config.ts`
  - `postcss.config.cjs`
  - `components.json`
  - `src/styles/tailwind.css`
