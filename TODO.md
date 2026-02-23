# UtilityManager TODO (актуальний план)

## Scope-рішення (зафіксовано)
- [x] Квартплата на поточному етапі ведеться як агрегована помісячна сума `Нараховано` (без деталізації на підпослуги).
- [x] Будинкові лічильники і будь-які розподіли за будинковими формулами виключені з roadmap проєкту.

## P0 — Структура репозиторію і чистота проєкту
- [x] Нормалізувати структуру monorepo: спільні артефакти в root (`.env`, документація).
- [x] Додати root `.gitignore` для backend/frontend та локальних артефактів.
- [x] Додати root `.env.example` з єдиним переліком змінних.
- [x] Прибрати з backend випадкові frontend-залежності та legacy-файли.
- [x] Прибрати з frontend legacy entry-файли поза `src/`.
- [x] Узгодити backend-конфіг для читання env з root (`.env` / `../.env`) без падіння на зайвих змінних.
- [x] Вирівняти frontend ESLint/TS-конфіг до стабільного прохідного стану.
- [x] Ініціалізувати git в `utility-manager` і перейти на feature-гілку для подальшої розробки.
- [x] Додати єдиний CI workflow для `backend tests + frontend lint/typecheck/test/build`.
- [x] Додати root scripts для щоденної розробки (`check:all`, `dev:up`, `dev:down`).
- [x] Прибрати локальні сміттєві артефакти backend (`node_modules`, `.pytest_cache`).
- [x] Додати `.gitattributes` для стабільних line endings у кросплатформеній команді.
- [x] Перезібрати docker-стек із очисткою застарілих ресурсів без видалення БД volume.

## P0 — Стабілізація поточної версії
- [x] У вкладці `Об'єкт` реалізовано список встановлених лічильників з CRUD (додати/редагувати/видалити).
- [x] Додано тести для CRUD лічильників: frontend hook tests + backend `409` при видаленні прив'язаного лічильника.
- [x] UX-polish лічильників: читабельні типи, валідація числового поля, дружні повідомлення API-помилок (`conflict/not found`).
- [x] Прогнати повний smoke-тест сценарію: вересень 2024 -> поточний місяць.
- [x] Додати API/Service тести формул:
  - [x] `Борг на зараз = Борг з минулого + Нараховано - Оплачено`
  - [x] перенос балансу тільки з підтверджених місяців
  - [x] відшкодування мінусує суму до оплати
- [x] Додати тест на `payments/utilities` як upsert (без дублювання платежу).
- [x] Додати тест на окремі `paid_at` по різних місяцях.
- [x] Перевірити всі модалки/форми на коректну Enter/Tab-навігацію (уніфіковано через shared form-controls).

## P1 — Технічний борг
- [x] Підключити Alembic-міграції для керованих змін БД.
- [x] Додати відсутні індекси для швидких запитів.
- [~] Розбити `frontend/src/App.jsx` на модулі:
  - [x] Винесено shared-шар (`constants`, `utils`, `ui`, `api client`)
  - [x] Винесено `TariffRow` та утиліти сортування послуг у feature-папки
  - [x] `tabs/TariffsTab`
  - [x] `tabs/CalculationTab`
  - [x] `tabs/TenantTab`
  - [x] `tabs/OwnerCostsTab`
  - [x] `tabs/ReportTab`
  - [~] Винесено orchestration-хуки: `useDashboardData`, `useDashboardStateSync`, `useSortedRows`, `useRowEditing`, `useBillingActions`, `useTenantActions`, `usePropertyActions`, `useOwnerActions`, `useAuthActions`, `useAdminUserActions`, `useTariffActions`
  - [~] Винесено layout-компоненти: `LoginScreen`, `AdminHeader`, `PropertyDrawer`, `DashboardContent`, `AppModals`
  - [x] Винесено локальні form-state hooks: `useTenantFormState`, `useTariffFormState`, `useOwnerFormState`
- [x] Винести API-клієнт у окремий шар (`frontend/src/shared/api/client.js`).
- [x] Абсолютні імпорти `@/*` (`vite alias` + `jsconfig`).
- [x] Додати ESLint + Prettier + npm scripts (`lint`, `format`, `format:check`).
- [x] Додати базові custom hooks (`useSession`, `usePeriod`).
- [x] Додати CI (`backend tests`, `frontend lint/build`).

## P1 — UX/продукт
- [x] Додати збереження сортування таблиці в `localStorage`.
- [x] Додати “підсвітку змінених значень” перед збереженням.
- [x] Додати явний статус місяця: `Чернетка / Підтверджено`.
- [x] Додати історію змін розрахунку місяця (мінімум timestamp + user).

## P1 — Фінанси і звіти
- [~] Реалізувати “Фактура за місяць”:
  - [x] формат A5 landscape (компактний one-page print layout)
  - [x] україномовний шаблон
  - [~] комуналка + оренда + витрати власника (one-page версія пріоритезує комуналку+оренду; деталізацію витрат виносити окремо за потреби)
  - [x] експорт у зображення/PDF для відправки
 - [x] Підтримка multi-register для одного лічильника (`meter_register`) та похідних послуг (`source_service_name`) в API/розрахунку.
 - [x] Frontend форми тарифів/показників: `meter_id`, `register_name`, `source_service_name`.

## P2 — Безпека і доступ
- [~] Ролі: `admin`, `operator`, `read_only`.
- [x] Backend: додано role-based перевірки доступу (read/write/admin-only).
- [x] Frontend: UI управління ролями користувачів.
- [x] Маскування/розкриття чутливих полів (паролі кабінетів постачальників) у UI-модалці тарифів.
- [x] Політика паролів + нагадування про ротацію.
- [x] Обмежити прямий доступ до storage-файлів (через backend `/admin/storage/{path}`).

## P2 — Рефакторинг Frontend (погоджено)
- [~] Архітектура (feature-based):
  - [x] `features/billing` (винесено `CalculationTab`)
  - [x] `features/tenants` (винесено `TenantTab`)
  - [~] `features/properties` (винесено `PropertyDrawer`; лишається секція об'єкта)
  - [x] `features/expenses` (винесено `OwnerCostsTab`)
  - [~] `App.jsx` зведено до orchestration/layout (додатково винесено модалки/контент/layout/auth hooks і form-state hooks; лишаються точкові локальні стани UI)
- [~] TanStack Query:
  - [x] замінити `lp/lc/reload` на `useQuery` (core loading для apartments/detail bundle)
  - [x] перевести save/update/delete на `useMutation` (оплата/рядки/орендар/об’єкти/тарифи/витрати/auth/admin users)
  - [x] `invalidateQueries` після мутацій
- [~] Zustand:
  - [x] глобальний store для `token`, `selectedApartment`, `period`
  - [ ] прибрати дубльований локальний state там, де це глобальні дані
- [~] React Hook Form + Zod:
  - [x] модалки тарифів/оплат/витрат/ремонтів
  - [x] схема валідації сум, дат, обов'язкових полів для цих модалок
- [ ] Date-fns:
  - [x] уніфікувати роботу з періодами та форматами дат
  - [x] прибрати ручні `toISOString().slice(...)` у бізнес-логіці
- [ ] UX:
  - [~] loading/skeleton для завантаження таблиць і вкладок (додано базові loading-стани текстом)
  - [x] toast-повідомлення замість `ok/err` блоків внизу
  - [x] confirm modal для небезпечних дій (`delAp`, `delT`, інше delete)
- [ ] Технічна декомпозиція обчислень:
  - [x] винести `sortedRows`, `totals`, інші селектори в `shared/utils` (додано `billing-selectors`)
  - [x] додати unit-тести на сортування/агрегації
- [ ] TypeScript (поетапно):
  - [x] етап 1: `shared` + `api types`
  - [x] етап 2: `features/*`
- [x] етап 3: повний перехід `App.jsx`/entry points
- [x] підетап: зняти тимчасові `@ts-nocheck` з feature-компонентів і додати строгі типи пропсів/DTO
    - [x] `@ts-nocheck` прибрано з `App.tsx` і всіх `features/*`
    - [x] додано TS-містки типів для `shared/ui/*.jsx` через `ui-jsx-bridges.d.ts`

## P1 — Якість коду (поетапне посилення)
- [x] Поступово посилювати ESLint правила замість глобального `off` (етапи 1-3 для feature-модулів завершено).
- [x] Етап 1: посилені правила для `frontend/src/features/properties/**/*` (`react-hooks/exhaustive-deps`, `@typescript-eslint/no-unused-vars`, `no-undef`).
- [x] Етап 2: поширити строгі правила на `features/tariffs`.
- [x] Етап 3: поширити строгі правила на `features/layout` і `features/dashboard`.

## P2 — Автоматизація
- [ ] Worker-контейнер для оновлення тарифів постачальників.
- [ ] Правило округлення тарифів до 2 знаків при імпорті.
- [ ] OCR-пайплайн для фото лічильників.
- [ ] Telegram-бот для подачі показників та нагадувань.

## P3 — Масштабування
- [ ] Мульти-об’єктний дашборд з фільтрами/пошуком.
- [ ] Аналітика споживання (порівняння рік-до-року).
- [ ] Аномалії споживання (алерти).
- [ ] Підготовка до mobile/PWA.

## Операційні checklists

## Щомісячно
- [ ] Заповнити показники.
- [ ] Перевірити/оновити тарифи.
- [ ] Заповнити місяць послугами.
- [ ] Внести оплату/відшкодування.
- [ ] Підтвердити нарахування місяця.

## Після оновлення коду
- [ ] `docker compose build --no-cache frontend api`
- [ ] `docker compose up -d --force-recreate frontend api`
- [ ] hard refresh браузера (`Ctrl+F5`)
- [ ] якщо build падає на контексті frontend: перевірити `frontend/.dockerignore` (виключено `node_modules`, `dist`, `build`)
