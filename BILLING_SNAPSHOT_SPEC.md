# Billing Snapshot And Statement Spec

## Мета
- Розділити `підсумок місяця` і `рахунок до відправки`.
- Фіксувати confirmed-стан місяця окремо від live-стану розрахунків.
- Враховувати оплати, отримані до моменту формування рахунку.
- Підтримати історичне первинне заповнення та контрольоване `reopen`.

## Основні сутності

### 1. Billing Month Snapshot
Незмінний підсумок підтвердженого місяця.

Поля:
- `apartment_id`
- `year`
- `month`
- `status`
- `opening_balance`
- `utility_accrual`
- `compensation_total`
- `month_total`
- `payments_in_month`
- `closing_balance`
- `rows_json`
- `confirmed_at`
- `confirmed_by`
- `reopened_at`
- `reopened_by`
- `reopen_reason`

Правило:
- створюється/оновлюється при `Підтвердити нарахування`
- є бухгалтерською правдою місяця

### 2. Billing Statement
Знімок того, що саме було підготовлено/відправлено орендарю.

Поля:
- `snapshot_id`
- `version`
- `status`
- `generated_at`
- `generated_by`
- `month_closing_balance_snapshot`
- `payments_after_month_to_generated_at`
- `balance_due_on_generated_at`
- `payload_json`
- `sent_at`
- `sent_channel`
- `sent_to`
- `note`

Правило:
- формується тільки для confirmed-місяця
- враховує оплати після закриття місяця і до `generated_at`

## Формули

### Підсумок місяця
- `opening_balance = closing_balance попереднього confirmed-місяця`
- `month_total = utility_accrual - compensation_total`
- `closing_balance = opening_balance + month_total - payments_in_month`

### Рахунок до відправки
- `payments_after_month_to_generated_at = сума оплат після кінця місяця і до generated_at`
- `balance_due_on_generated_at = month_closing_balance_snapshot - payments_after_month_to_generated_at`

## Статуси

### Snapshot
- `confirmed`
- `reopened`

### Statement
- `draft`
- `prepared`
- `sent`
- `cancelled`

## UI правила

### Верхні KPI
- `Борг на початок місяця`
- `Нараховано за місяць`
- `Оплачено в місяці`
- `Борг на кінець місяця`

Окремо:
- `Поточний баланс`
- `Остання оплата`

### Звіт за місяць
Секція 1:
- підсумок місяця

Секція 2:
- рахунок до відправки
- статус
- оплати після закриття місяця
- до сплати на дату формування

Секція 3:
- історія сформованих рахунків

## Початкове заповнення
- дозволене заднім числом
- confirmed-місяці заповнюються послідовно
- якщо старий confirmed-місяць змінюється:
  - місяць переходить у `reopened`
  - зберігається причина
  - наступні confirmed-місяці автоматично розблоковуються каскадом
  - `confirm/recalculate` перераховують invoice-chain від зміненого місяця
  - UI показує список фактично зачеплених періодів

## Аудит
Логувати:
- confirm
- reopen
- prepare statement
- send statement
- зміну ключових сум

## Статус реалізації
- ORM/БД: зроблено
- backend snapshot/statement API: зроблено
- KPI + ReportTab на snapshot/statement: зроблено
- історія statement-ів в UI: зроблено
- reopen UX з причиною: зроблено
- cascade unlock + chain recalc feedback: зроблено
