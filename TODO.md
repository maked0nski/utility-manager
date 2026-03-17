# UtilityManager TODO (актуальний план)

## P0 — Нова модель billing/reporting (місячний snapshot + рахунок до відправки)
- [ ] Зафіксувати `confirmed month snapshot` як окремий незмінний підсумок місяця:
  - [ ] `opening_balance`
  - [ ] `utility_accrual`
  - [ ] `compensation_total`
  - [ ] `month_total`
  - [ ] `payments_in_month`
  - [ ] `closing_balance`
  - [ ] `confirmed_at/by`
- [ ] Ввести окрему сутність `billing_statement` / `invoice_snapshot` для рахунку орендарю:
  - [ ] `generated_at/by`
  - [ ] `status: draft/prepared/sent/cancelled`
  - [ ] `month_closing_balance_snapshot`
  - [ ] `payments_after_month_to_generated_at`
  - [ ] `balance_due_on_generated_at`
  - [ ] `sent_at / sent_channel / sent_to`
  - [ ] `payload_json`
- [ ] Розвести бізнес-логіку:
  - [ ] `Підсумок місяця` = тільки рухи всередині місяця
  - [ ] `Рахунок до відправки` = стан на дату формування з урахуванням оплат після закриття місяця
  - [ ] `Поточний баланс` = live ledger стан на сьогодні
- [ ] Підтримати історичне первинне заповнення бази:
  - [ ] режим `initial backfill`
  - [ ] послідовне підтвердження місяців
  - [ ] контрольоване `reopen` підтверджених місяців з причиною й аудитом
  - [ ] автоматичний перерахунок усіх наступних місяців після зміни старого confirmed-періоду

### Етап A — БД / доменна модель
- [ ] Додати таблицю `billing_month_snapshots` або еквівалентну модель confirmed-місяця.
- [ ] Додати таблицю `billing_statements`.
- [ ] Додати поле/стан `reopened` і аудит причин перерахунку історії.
- [ ] Додати індекси для швидкого пошуку snapshot/statement по `apartment_id + year + month`.

### Етап B — Backend
- [ ] Переробити confirm month: при підтвердженні створювати/оновлювати місячний snapshot.
- [ ] Додати сервіс побудови `billing statement` від confirmed snapshot + оплат до `generated_at`.
- [ ] Додати API:
  - [ ] `POST /billing-statements/prepare`
  - [ ] `POST /billing-statements/{id}/send`
  - [ ] `GET /billing-statements?apartment_id&year&month`
  - [ ] `POST /billing-months/{year}/{month}/reopen`
- [ ] Винести KPI-обчислення в окремі backend-поля:
  - [ ] на початок місяця
  - [ ] на кінець місяця
  - [ ] live balance today
- [ ] Додати backend тести на сценарії:
  - [ ] оплата після закриття місяця, але до формування рахунку
  - [ ] історичне заповнення заднім числом
  - [ ] reopen і перерахунок наступних місяців

### Етап C — UI
- [ ] Переробити верхні KPI:
  - [ ] `Борг на початок місяця`
  - [ ] `Нараховано за місяць`
  - [ ] `Оплачено в місяці`
  - [ ] `Борг на кінець місяця`
- [ ] Винести окремо `Поточний баланс` і `Останню оплату`.
- [ ] Переробити вкладку `Звіт за місяць` у 2 секції:
  - [ ] `Підсумок місяця`
  - [ ] `Рахунок до відправки`
- [ ] Додати статус рахунку `Чернетка / Підготовлено / Відправлено / Скасовано`.
- [ ] Додати UI для історії сформованих/відправлених рахунків.
- [ ] Додати UX для `reopen місяця` з попередженням про ланцюговий перерахунок.

### Етап D — Міграція робочого процесу
- [ ] Перевести поточний `ReportTab` з live-обчислення на snapshot + statement.
- [ ] Прибрати змішування `на кінець місяця` і `на дату формування` в одному блоці.
- [ ] Залишити PDF як експорт, але головною сутністю зробити статус `Відправлено`.

## Scope-рішення (зафіксовано)
- [x] Квартплата на поточному етапі ведеться як агрегована помісячна сума `Нараховано` (без деталізації на підпослуги).
- [x] Будинкові лічильники і будь-які розподіли за будинковими формулами виключені з roadmap проєкту.

## P0 — Переписування доменної моделі послуг і тарифів
- [x] Ввести довідник послуг `service_catalog` як головне джерело правди для UI та розрахунків.
- [x] Винести підключення послуг об'єкта в окрему сутність `apartment_service_connections`.
- [x] Винести арифметику в `connection_charge_lines`, щоб одна послуга могла мати кілька рядків розрахунку.
- [~] Перевести `Електроенергія` на модель `одне підключення + дочірні лінії day/night/tri-zone`.
- [x] Перевести `Водовідведення` на похідний розрахунок від `Водопостачання` без окремого лічильника.
- [~] Відв'язати `Meter` від бізнес-назв послуг: лічильник має бути лише фізичним пристроєм.
  - [x] UI/API більше не спираються на `meter.service_name` для відображення та робочої логіки.
  - [x] Legacy-колонка `meters.service_name` фізично видалена зі startup migration і ORM-моделі.
- [~] Прибрати дублювання між legacy-сутностями `Tariff`, `ApartmentTariffSetting`, `ApartmentService`, `ElectricityMeterPlan`.
  - [x] Legacy `tariffs` / `electricity plan` UI та публічні API вимкнені.
  - [x] Legacy `tariffs/settings` UI-виклики прибрані; endpoint вимкнений через `410 Gone`.
  - [x] Legacy-phase у worker вимкнена; активний цикл працює через `ApartmentAutomation`.
  - [~] Провайдерні adapter-и вже не мають fallback на `ApartmentTariffSetting`, а оновлення цін у worker частково переведено на `ConnectionChargeLine`; лишається дочистити решту legacy-paths.
- [x] Старі таблиці `tariffs`, `apartment_tariff_settings`, `apartment_services`, `electricity_meter_plans` видаляються startup migration; нова модель є єдиним runtime-джерелом правди.
- [~] Переробити UI `Тарифи` в `Послуги об'єкта` з формою `Підключити послугу`.
- [x] Додати grouped-вигляд у `Розрахунок`: послуга верхнього рівня + дочірні рядки розрахунку.

### Етап 1 — Backend foundation
- [x] Додати нові enum-и і таблиці: `service_catalog`, `apartment_service_connections`, `connection_charge_lines`.
- [x] Додати startup migration / Alembic migration для нових таблиць без видалення legacy-структур.
- [x] Додати seed базових послуг з довідника.
- [x] Додати backend DTO/schemas для catalog, connections і charge lines.

### Етап 2 — API і business logic
- [x] Додати CRUD для довідника послуг.
- [x] Додати CRUD для підключень послуг об'єкта.
- [x] Додати CRUD для тарифних ліній усередині підключення.
- [x] Додати backend grouping для multi-line послуг у відповіді API.
- [x] Додати перерахунок `derived`-послуг через line-донор.

### Етап 3 — UI
- [x] Винести `Послуги` в `Налаштування` як окремий довідник.
- [x] Переробити вкладку об'єкта: `Лічильники` окремо, `Послуги об'єкта` окремо.
- [x] Переробити майстер створення послуги від довідника `Послуг`, а не від вільного сценарію.
- [x] Для `Електроенергії` показувати одну послугу з вкладеними лініями `День/Ніч/Пік`.
- [x] Для `Розрахунку` додати grouped-row rendering з підпунктами.

### Етап 4 — Migration and cleanup
- [~] Прибрати fallback-и `meter -> service_name` у backend розрахунках, automation worker та API.
- [~] Написати migration script зі старих `tariffs + apartment_tariff_settings + electricity_meter_plans`.
  - [x] Автоматичний startup-backfill legacy-даних вимкнено і більше не використовується в runtime-сценарії.
  - [x] `electricity_meter_plans` більше не є джерелом правди: стартові показники зберігаються в `connection_charge_lines.initial_reading`, а legacy-таблиця видаляється під час startup migration.
- [ ] Перевірка на старому дампі поки не актуальна: прийнято сценарій нового старту з чистим заповненням.
- [~] Після стабілізації прибрати legacy UI і legacy API.
  - [x] Legacy UI прибрано з вкладки `Тарифи`; основний сценарій працює через `Послуги об'єкта`.
  - [x] Legacy tariff/electricity-plan API вимкнені через `410 Gone`.
  - [x] Legacy `tariffs/settings` більше не використовується активним frontend-потоком.
  - [x] Legacy frontend-файли `use-tariff-actions` і `TariffEditModal` видалені.
  - [~] Automation list/run переведені на `ApartmentAutomation + ApartmentServiceConnection`; worker переведено на automation-cycle без legacy phase і без fallback на `ApartmentTariffSetting`, lookup charge-lines у worker переведений на `connection_id/service_catalog_id`, provider-sync staging нормалізує записи через `service_catalog_code`, а Vodokanal/ATP routing і parser selection уже спираються на `service_catalog.code`; назва послуги лишилася тільки як display/external matching value для конкретних кабінетів постачальників.

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
- [x] Додати тест на `payments/utilities` для накопичення кількох оплат у межах одного місяця.
- [x] Додати тест на окремі `paid_at` по різних місяцях.
- [x] Перевірити всі модалки/форми на коректну Enter/Tab-навігацію (уніфіковано через shared form-controls).
- [x] Додано спрощений `service ledger` для fixed-послуг: помісячні `Нараховано/Оплачено/Баланс` з формулою перерахунку.
- [x] У вкладці `Тарифи` додано UI для ведення агрегованих помісячних сум по обраній fixed-послузі.
- [x] Додано backend тести на перерахунок ledger-балансу при зміні минулого місяця.
- [x] Реалізовано базову “паспортну картку об'єкта”: площа, гео-координати, локаційна примітка, технічні нотатки.
- [x] Реалізовано реєстр обладнання об'єкта з CRUD і базовим сервісним графіком (останній/наступний сервіс, інтервал, інструкція).
- [x] Реалізовано життєвий цикл лічильника: заміна лічильника без втрати історії (`/admin/meters/{id}/replace`).
- [x] Реалізовано керований флоу тарифного плану електрики `single ↔ day/night` через окремий endpoint та UI.

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
- [~] Tenant portal (MVP):
  - [x] Розділено frontend-потоки: `/admin` (адмін) і `/` (орендар).
  - [x] Додано базовий кабінет орендаря: `login/dashboard/history/profile`.
  - [x] Додано endpoint `GET /tenant/me/meters` для форми подачі показників.
  - [x] Дороблено UX tenant-кабінету (деталізація рахунків, стани завантаження/помилок, локалізовані статуси, inline-повідомлення).
  - [x] Додати tenant guard на рівні маршрутизатора (`react-router`) та прибрати ручний `window.history` з навігації.
  - [x] Перейти на вкладений tenant-routing: `history/:invoiceId` + layout через `Routes/Outlet`.
  - [x] Винести tenant DTO (`TenantMe`, `TenantDashboard`, `TenantHistory`, `TenantInvoice`) у `shared/api/types`.
  - [x] Декомпозувати `TenantApp` на `components/pages/utils` (без монолітного файлу).
  - [x] Додати frontend smoke-test tenant-flow (`login -> dashboard -> history/:invoiceId -> profile`).
  - [x] Додати edge-case тести tenant-flow: `invalid credentials`, `portal disabled`, `invoice not found`, `meter submit disabled`.
  - [x] A11y-поліш tenant-форм: `label htmlFor` + `input id`, перевірки через `getByLabelText` у RTL.
  - [x] Сесійна безпека tenant: `access+refresh` токени, TTL, `POST /tenant/refresh`, `POST /tenant/me/logout-all`.
  - [x] Примусова ревокація tenant-сесій при зміні email/пароля (`session_version`).
  - [ ] Forgot password для орендаря (email/token reset, зараз у UI лише заглушка "Зверніться до адміністратора").
  - [x] Backend API тести tenant endpoint-ів на `403/404/409` + сценарії refresh/revocation.
  - [x] Прибрано router future warnings (`future` flags для BrowserRouter/MemoryRouter).
  - [~] Dependency hardening (frontend): оновлено direct-risk пакети (`jspdf@4.2.0`, `@typescript-eslint/*@8.56.1`), залишок audit вимагає major-upgrade (`eslint@10`, `vitest@4`).

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
- [~] Worker-контейнер для оновлення тарифів постачальників.
  - [x] Додано skeleton worker + adapter registry + staging-таблиці імпорту (`provider_import_batches`, `provider_import_rows`).
  - [~] Додати real adapters для конкретних постачальників (кабінети/API) та правила мапінгу.
    - [x] Додано перший real adapter для `АТП-0928` (`if_atp0928_waste` / `atp0928_if`) з авто-виявленням цілей sync по активних automation.
    - [x] Додано `VisualService` adapter для fixed-послуг (`visualservice_fixed`).
    - [x] Додано `Vodokanal` adapter (`if_vodokanal` / `vodokanal_if`) з читанням bridge payload і спробою витягнути помісячні нарахування по відомих ключах.
    - [ ] За потреби уточнити/розширити мапінг полів `Vodokanal`, якщо реальний payload відрізняється від поточних очікувань.
- [ ] Правило округлення тарифів до 2 знаків при імпорті.
- [ ] OCR-пайплайн для фото лічильників.
- [ ] Telegram-бот для подачі показників та нагадувань.

## P2 — Електроенергія (тарифні режими)
- [ ] Додати повну tri-zone математику в UI/розрахунках (`піковий`, `напівпіковий`, `нічний`) для одного фізичного лічильника з історією переходів між режимами `single ↔ day/night ↔ tri-zone`.

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
