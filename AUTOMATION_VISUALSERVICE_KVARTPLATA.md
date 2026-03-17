# Automation: VisualService / Квартплата

## 1. Ціль
Автоматично отримувати нарахування для послуги `Квартплата` за попередній місяць, порівнювати з діючим тарифом у БД, оновлювати лише якщо значення більше, і вести прозорий статус перевірки.

## 2. Бізнес-правила
1. Цільовий місяць: попередній відносно поточного місяця.
   - Наприклад, у березні 2026 перевіряється лютий 2026.
2. Перевірка виконується в налаштовуваному вікні днів місяця (за замовчуванням 1..10) о налаштовуваному часі (за замовчуванням 09:00 Europe/Kyiv).
3. Якщо в колонці `Нараховано, грн` значення порожнє -> `waiting`.
4. Якщо значення знайдено:
   - `new <= current_db` -> `no_change`;
   - `new > current_db` -> округлити вгору до кроку 0.5 та оновити тариф з `effective_from=YYYY-MM-01`.
5. Після успішного `no_change` або `updated` цикл для цього цільового місяця завершується (`completed_for_period=true`) до наступного місяця.

## 3. Округлення
- Формула: `ceil(value * 2) / 2`
- Приклади:
  - `350.35 -> 350.50`
  - `350.51 -> 351.00`

## 4. Джерела даних на VisualService
- Login page: `https://portal-guc.tis.if.ua/login/`
- Balance page: `https://portal-guc.tis.if.ua/balance/`
- Деталізація місяця: `POST /ajax/balance/charges.php` з параметрами `p,s,b`.

Примітка:
- У `onclick="chargesData(..., b)"` параметр `b` не використовується як джерело істини для нашого правила `waiting`.
- Для рішення `waiting/found` використовується колонка `td[data-label="Нараховано, грн"]`.

## 5. Статуси UI
- `waiting` -> `⏳ Очікування`
- `no_change` -> `✅ Без змін`
- `updated` -> `✅ Оновлено` (або `✅ + badge`)
- `error` -> `⚠ Помилка`

Tooltip має показувати `auto_check_message`.

## 6. Дані, що зберігаються в налаштуванні тарифу
- `auto_check_enabled`
- `auto_check_time`
- `auto_check_timezone`
- `auto_check_window_day_from`
- `auto_check_window_day_to`
- `auto_check_target_year`
- `auto_check_target_month`
- `auto_check_completed_for_period`
- `auto_check_status`
- `auto_check_message`
- `auto_check_last_value_raw`
- `auto_check_last_value_rounded`
- `auto_check_last_checked_at`
- `auto_check_last_updated_at`
- `auto_check_next_at`

## 7. Потік воркера
1. Вибрати `apartment_tariff_settings` з `auto_check_enabled=true`.
2. Для кожного запису:
   - обчислити target period (prev month);
   - перевірити day-window/time;
   - якщо цикл для target періоду завершено, skip;
   - зайти в кабінет і прочитати `Нараховано` для потрібного рядка;
   - застосувати правила `waiting/no_change/updated/error`;
   - оновити статус і `next_at`.

## 8. Безпека
- Паролі зберігати тільки в зашифрованому вигляді.
- В логах не виводити пароль.
- В UI дозволити ручний reveal пароля через explicit toggle.

## 9. Тест-кейси (мінімум)
1. Порожнє `Нараховано` -> `waiting`.
2. `Нараховано=334.50`, current=334.50 -> `no_change`.
3. `Нараховано=334.51`, current=334.50 -> `updated`, rounded=335.00.
4. `completed_for_period=true` -> повторно не оновлювати в тому ж цільовому періоді.
5. Новий місяць -> reset циклу на новий target period.
