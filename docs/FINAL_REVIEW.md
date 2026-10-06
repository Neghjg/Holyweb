# Финальное ревью: «Сохранить объём работ» (Backend / Plan)

Объект ревью: коммит `4966709` («Implement 'Save work volume' use case (Backend/Plan)»), рабочее дерево `/home/andrew/Downloads/task`.
Основание: файлы ТЗ (`readme.md`, `c4.drawio`, `er.puml`, `use_case_map.puml`, `V_b_24.puml`, `request.schema.json`) и нормативный план `docs/REVIEW_AND_PLAN.md` (D1–D12, чек-лист раздела 4).

## Вердикт

**Готово с замечаниями.**

Функционально use case реализован верно и соответствует sequence-диаграмме с задокументированными отступлениями. Все заявления автора подтвердились:

- 64 теста проходят на SQLite;
- 64 теста плюс интеграционный тест проходят в Docker на Postgres и ClickHouse;
- curl-сценарии из README дают заявленные коды.

Критических дефектов нет. Есть два Major-дефекта, которые стоит исправить до сдачи:

1. У клиента ClickHouse не настроены таймауты. Если ClickHouse зависает, клиент через 30 с получает HTML `500`, а не `503/904`: gunicorn убивает воркер.
2. Небезопасные значения по умолчанию в compose. Известный `SECRET_KEY` фактически обходит защиту из `settings.py`, демо-пользователи с известным паролем публикуются на `0.0.0.0`, а пароль сбрасывается при каждом старте.

Итого: Critical 0, Major 2, Minor 12.

---

## Таблица чек-листа (раздел 4 плана)

| # | Пункт | Статус | Комментарий |
|---|-------|--------|-------------|
| **Структура** ||||
| 1 | Проект `backend`, приложение `plan`, соответствие пояснено в README | Выполнено | README:8 |
| 2 | Оригиналы ТЗ не изменены, копии в `docs/task/`, корневые в `.gitignore`, нет коллизии `readme.md`/`README.md` | Выполнено | sha256 всех 6 файлов совпадают; в `git ls-files` только `README.md` и `docs/task/readme.md` |
| 3 | Нет `.env`, `__pycache__`, секретов, `staticfiles/` в репозитории | Выполнено | `git ls-files` чистый. Слабые дефолтные значения в compose см. M2 |
| 4 | Зависимости зафиксированы; Py 3.12, Django 5.2, DRF, psycopg 3, clickhouse-connect | Частично | Только маски `==5.2.*`, patch-версии не зафиксированы (m9) |
| **Модели и БД** ||||
| 5 | Factory / FactoryUser / WorkVolume, ограничения, PROTECT | Выполнено | `plan/models.py`, `0001_initial.py` |
| 6 | `makemigrations --check` чисто | Выполнено | Проверено на SQLite и в контейнере на Postgres |
| 7 | Data-миграция групп с точными именами, обратима | Выполнено | Проверены `migrate plan 0001` (группы удаляются), `zero` и затем снова вперёд |
| 8 | Таблица CH через `init_clickhouse`, идемпотентно | Выполнено | Двойной `ensure_schema()` в интеграционном тесте, рестарт backend без ошибок |
| **API** ||||
| 9 | Путь ровно `POST /work-volume-list/` | Выполнено | Без слэша отвечает `301`, см. m1 |
| 10 | Порядок проверок D5 | Частично | Неподходящий `Accept` даёт 406/907 раньше 401 (m2), в остальном порядок соблюдён |
| 11 | Все ошибки в формате `{errorCode, message, details}` | Частично | HTML 500 на глубоко вложенный JSON и на зависание CH (m1, M1) |
| 12 | 406/279 для отсутствующих, `null`, `""`; `details.missing` | Выполнено | curl и тесты |
| 13 | str/bool/float → 400/901; не полночь и миллисекунды → 400/901 | Выполнено | curl: `1.0`, `true`, `"1"`, `NaN`, `1735689601`, `1735689600000` |
| 14 | Менеджер / представитель / без групп / обе группы | Выполнено | curl и тесты |
| 15 | Повторный POST обновляет weight и created без дубля, в CH новая запись | Выполнено | Проверено SELECT-ами в PG и CH |
| 16 | В CH `factory=external_id`, `author=request.user.id`, `created == WorkVolume.created` | Выполнено | Сверено построчно (PG и CH, микросекунды совпадают) |
| 17 | CH недоступен → 503/904, Postgres откатан | Частично | `stop clickhouse` даёт 503/904 с откатом. `pause clickhouse` (зависание) даёт **500 HTML через 30 с** (M1) |
| 18 | Ответ 201 по D6, даты целые | Выполнено | |
| **Код** ||||
| 19 | Логика в `services.py`, view тонкий, CH за репозиторием | Выполнено | |
| 20 | Атомарный upsert `ON CONFLICT` | Выполнено | 40 параллельных запросов на один ключ: 40×201, одна строка в PG, 40 записей в CH |
| 21 | Нет SQL-инъекций | Выполнено | Имя БД проверяется регуляркой, значения идут через `insert` |
| 22 | SECRET_KEY и пароли из env, DEBUG по умолчанию выключен | Частично | В `settings.py` верно, но compose подставляет `change-me` (M2) |
| 23 | `ruff check .` | Выполнено | `ruff check` и `ruff format --check` чистые |
| **Docker** ||||
| 24 | `up --build` без `.env` поднимает 3 сервиса, порядок по healthcheck, entrypoint выполняет migrate, init и seed | Выполнено | |
| 25 | Не root, gunicorn, админка со статикой | Выполнено | `uid=1000(app)`, `/admin/login/` 200, `/static/admin/css/base.css` 200 |
| 26 | Именованные volumes | Выполнено | `pg_data`, `ch_data` |
| **Тесты** ||||
| 27 | Все тесты зелёные, сценарии 1–18 покрыты | Выполнено | Все 18 сценариев из п. 3.4 нашлись в `test_api_work_volume.py` |
| 28 | CH замокан; интеграционный тест под маркером и проходит | Выполнено | Тест пишет в боевую таблицу (m5) |
| **README** ||||
| 29 | Запуск, учётки, токены, curl на каждый код, просмотр CH, тесты | Частично | Нет curl для 400 (типы и JSON), 405, 415, 406/907, 503; нет `createsuperuser` для админки (m11) |
| 30 | Допущения и отступления со ссылкой на план | Выполнено | README:128–139. Утверждение про SECRET_KEY вводит в заблуждение (M2) |

Итог: 23 пункта выполнено, 7 частично, 0 не выполнено.

---

## Соответствие `V_b_24.puml`

| Элемент диаграммы | Реализация | Статус |
|---|---|---|
| `POST /work-volume-list/`, тело по `request.schema.json` | `plan/urls.py:6`, `views.py:17` | Соответствует |
| Проверка заполненности → `406 / errorCode=279` | `views.py:22-24`, `serializers.py:8-10` | Соответствует. Отсутствие, `null` и `""` дают 406/279 |
| Проверка существования ЗМК → `404 / 174` | `services.py:31-33` | Соответствует. Выполняется до проверки групп, как на диаграмме |
| Группа «Представитель ЗМК» и привязка к ЗМК, иначе `404 / 174` | `services.py:41-45` | Соответствует (трактовка «не существует для пользователя») |
| Группа «Менеджер…» без проверки привязки | `services.py:39-40` | Соответствует. При двух группах приоритет у менеджера, это отступление от порядка `alt` (D4, README:133) |
| Объём за период есть → обновить `weight` и `created`, иначе создать | `services.py:56-61`, `bulk_create(update_conflicts=…)` | Соответствует. Атомарный `ON CONFLICT DO UPDATE` |
| `tsDB`: создание записи объёма работы | `services.py:64-73`, `tsdb.py:94-113` | Соответствует. Пишутся `external_id`, `author=request.user.id`, тот же `created` |
| `201` в обеих ветках | `views.py:39-41` | Соответствует |
| Нет ветки «без групп» | 403/902 | Дополнение (D4) |
| Нет аутентификации | 401/900; `author` обязан совпадать с пользователем, иначе 403/903 | Дополнение (D3) |
| Неверные типы и значения | 400/901 | Дополнение (D7) |

Ветвления, коды ответов и errorCode совпадают с диаграммой. Отступления (приоритет менеджера, дополнительные коды 400, 401, 403, 415, 503) соответствуют плану и описаны в README.

---

## Найденные проблемы

### Critical

Нет.

### Major

#### M1. У клиента ClickHouse нет таймаутов: при зависании CH клиент получает HTML 500, а воркер убивается

- **Где:** `plan/tsdb.py:59-69` (`_connect`: `clickhouse_connect.get_client` без `connect_timeout` и `send_receive_timeout`); `Dockerfile:18` (gunicorn с таймаутом по умолчанию 30 с).
- **Суть:** по умолчанию в clickhouse-connect `connect_timeout=10` и `send_receive_timeout=300`. Если CH принимает TCP-соединение, но не отвечает (перегрузка, GC, сетевой «чёрный ящик»), `insert` ждёт до 300 с. Через 30 с gunicorn с ошибкой `WORKER TIMEOUT` убивает воркер. Клиент получает HTML `Internal Server Error` вместо контракта `503/904`. Всё это время транзакция Postgres держит блокировку строки WorkVolume и блокирует запросы с тем же ключом. Postgres при этом остаётся согласованным: соединение рвётся, транзакция откатывается.
- **Воспроизведение (проверено):**
  ```bash
  docker compose -p task pause clickhouse
  curl -s -m 90 -w ' http=%{http_code}\n' -u manager:demo12345 -H 'Content-Type: application/json' \
    -d '{"factory":1,"start":1735689600,"finish":1738281600,"weight":5555,"author":2}' \
    http://127.0.0.1:18000/work-volume-list/
  # -> HTML "Internal Server Error" http=500, elapsed=30s
  # логи: [CRITICAL] WORKER TIMEOUT (pid:10)
  ```
- **Исправление:** передавать в `_connect` значения `connect_timeout` и `send_receive_timeout` из настроек (например, 3 с и 10 с), заметно меньше таймаута gunicorn. Тогда `OperationalError` превратится в `TsDBUnavailable` и ответ будет 503/904. Желательно явно задать `--timeout` в `CMD` и добавить тест, который проверяет, что таймаут передаётся в `get_client`.

#### M2. Небезопасные значения по умолчанию в compose обходят защиту SECRET_KEY и публикуют демо-доступ

- **Где:**
  - `docker-compose.yml:41`: `DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:-change-me}`;
  - `docker-compose.yml:54`: `SEED_DEMO: ${SEED_DEMO:-1}`;
  - `docker-compose.yml:62`: порт публикуется на `0.0.0.0`;
  - `plan/management/commands/seed_demo.py:31-33`: `set_password` и `groups.set` при каждом запуске;
  - `README.md:139`: «`SECRET_KEY` обязателен при `DJANGO_DEBUG=0`».
- **Суть:**
  1. Проверка в `backend/settings.py:22-27` задумана как защита от запуска без секрета. Compose всегда подставляет публично известный `change-me`, и проверка не срабатывает. Утверждение README:139 на практике неверно. `check --deploy` выдаёт `security.W009`.
  2. После `docker compose up` на любой машине в сети доступны пользователи `manager`, `rep`, `nobody` с паролем `demo12345` и правом записи. Порт слушается на всех интерфейсах, токены выводятся в логи.
  3. `seed_demo` при каждом рестарте сбрасывает пароль и группы демо-пользователей. Если оператор сменил пароль `manager` в админке, после рестарта снова действует `demo12345`.
- **Воспроизведение:** `docker compose up -d` без `.env` → `curl -u manager:demo12345 …` даёт 201. `docker compose restart backend` → пароль снова `demo12345`.
- **Исправление:**
  - использовать `DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:?set DJANGO_SECRET_KEY in .env}` или генерировать ключ в entrypoint и сохранять его в volume;
  - по умолчанию ставить `SEED_DEMO=0` и включать демо-данные явно через `.env`;
  - публиковать порт как `127.0.0.1:${BACKEND_PORT:-8000}:8000`;
  - в `seed_demo` вызывать `set_password` и `groups.set` только для только что созданного пользователя (`created=True`).

### Minor

#### m1. Часть ответов выходит за единый формат ошибок (HTML 500, 301, 404)

- **Где:** `plan/errors.py:71-73` (необработанное исключение возвращает `None`, и Django отдаёт HTML); `plan/views.py:18` (`request.data`); `APPEND_SLASH` по умолчанию.
- **Воспроизведение (проверено):**
  - `python3 -c "print('['*100000+']'*100000)" > deep.json; curl -u manager:demo12345 -H 'Content-Type: application/json' --data-binary @deep.json …/work-volume-list/` даёт HTML `500`. `RecursionError` в `json.loads` не является `ValueError`, поэтому DRF не превращает его в `ParseError`.
  - `POST /work-volume-list` без слэша даёт `301`, тело теряется.
  - Неизвестный URL отдаёт HTML 404, но он вне эндпоинта, это допустимо.
- **Исправление:** в `api_exception_handler` для прочих исключений логировать и возвращать `500/999` в JSON-формате. Добавить `re_path(r"^work-volume-list/?$", …)` или явно задокументировать слэш.

#### m2. Неподходящий `Accept` проверяется раньше аутентификации

- **Где:** порядок в DRF `APIView.initial()` (content negotiation идёт до `perform_authentication`); `plan/errors.py:91-92`.
- **Воспроизведение (проверено):** `curl -H 'Content-Type: application/json' -H 'Accept: application/xml' -d '{}' …` без учётных данных даёт `406/907`, а не `401/900`. Это нарушает пункт 1 порядка D5.
- **Исправление:** задокументировать или переопределить `initial()`, чтобы `perform_authentication` и `check_permissions` выполнялись до `perform_content_negotiation`. Можно также игнорировать `Accept` через `DefaultContentNegotiation` с fallback на JSON.

#### m3. Отказ CSRF при сессионной аутентификации получает errorCode 902 («нет разрешённой группы»)

- **Где:** `plan/errors.py:93-94`. Любой `PermissionDenied` отображается в `ErrorCode.NO_PERMITTED_GROUP`.
- **Воспроизведение (проверено):** войти в `/admin/` под `manager` и отправить POST с cookie сессии без `X-CSRFToken`. Ответ: `403 {"errorCode":902,"message":"CSRF Failed: CSRF token missing.",…}`.
- **Исправление:** для `PermissionDenied`, не порождённого бизнес-логикой (CSRF), возвращать отдельный код, например 908, или общий 403/999.

#### m4. Сообщения ошибок на русском и английском вперемешку, хотя D6 требует английский

- **Где:** `backend/settings.py:109` (`LANGUAGE_CODE = "ru-ru"`), `plan/errors.py:79` (`message = str(exc.detail)`), `details` из валидаторов DRF.
- **Воспроизведение (проверено):** 401 отдаёт `"Учетные данные не были предоставлены."`, 405 — `"Метод \"GET\" не разрешен."`. `details.weight` при `2147483648` содержит `"Убедитесь, что это значение меньше либо равно…"`, а `not_midnight` выдаёт английское сообщение.
- **Исправление:** во `views` или в обработчике ошибок форсировать `translation.override("en")` либо явно задавать английские `message` для каждого кода.

#### m5. Интеграционный тест пишет в боевую таблицу tsDB

- **Где:** `tests/test_clickhouse_integration.py:12-24`. Используется `settings.CLICKHOUSE["database"]`, то есть `plan`.
- **Воспроизведение (проверено):** до `pytest -m clickhouse` в таблице было `count()=6`, после стало 7. Появилась запись с `author=1` (это реальный пользователь `rep`), случайным `factory` и `weight=10`.
- **Исправление:** в фикстуре переопределять `CLICKHOUSE.database` на `plan_test_<uuid>`, а в teardown выполнять `DROP DATABASE`.

#### m6. Фантомная запись в tsDB, если вставка прошла, а ответ CH потерян; README описывает только обратный случай

- **Где:** `plan/services.py:51-78`, `README.md:138`.
- **Суть:** при read-timeout или обрыве после того, как сервер принял `INSERT`, возникает `TsDBUnavailable`. Postgres откатывается, а в ClickHouse запись уже есть. Если исправить M1 короткими таймаутами, вероятность такого исхода вырастет. В README описан только случай «CH записал, а commit упал».
- **Исправление:** дописать этот сценарий в README. Для идемпотентности можно передавать в CH `insert_deduplication_token` или request-id (`ReplacingMergeTree` или ключ дедупликации).

#### m7. Метка `created` берётся до захвата блокировки строки, поэтому возможна инверсия порядка

- **Где:** `plan/services.py:50` (`now = timezone.now()` до `transaction.atomic` и `ON CONFLICT`).
- **Суть:** запросы A (`now=t1`) и B (`now=t2>t1`) на один ключ. Если B первым захватит блокировку строки, то A, закоммиченный позже, перезапишет PG значениями `weight=wA`, `created=t1`. Тогда в PG `created` уйдёт назад, а последняя по `created` запись в CH (`wB`) не совпадёт с итоговым состоянием taDB. Окно микросекундное: в 6 сериях по 30 параллельных запросов воспроизвести не удалось (PG и `argMax(weight, created)` в CH всегда совпадали). Дефект теоретический.
- **Исправление:** брать время из БД внутри транзакции (`Now()` в `update_fields` и затем перечитать), либо обновлять с условием `WHERE excluded.created > plan_workvolume.created`.

#### m8. `seed_demo` может сделать backend незапускаемым

- **Где:** `plan/management/commands/seed_demo.py:21-22` (`get_or_create(name=…)` по неуникальному полю), `docker/entrypoint.sh:2,6-7` (`set -e`).
- **Воспроизведение:** создать в админке второй завод «ЗМК Север» и перезапустить backend. `MultipleObjectsReturned` → entrypoint завершается → контейнер не стартует при `SEED_DEMO=1`.
- **Исправление:** `filter(name=…).first()` с последующим `create`, либо выполнять seed только при пустой БД, либо не прерывать запуск из-за ошибки seed.

#### m9. Версии зависимостей не зафиксированы до patch

- **Где:** `requirements.txt:1-6`, `requirements-dev.txt:2-4` (`Django==5.2.*`, `ruff==0.*` и т. п.).
- **Суть:** сборка невоспроизводима. План (п. 3.1) требовал фиксировать patch-версии. `ruff==0.*` между минорами меняет правила, и `ruff check` может начать падать.
- **Исправление:** зафиксировать фактические версии: Django 5.2.17, DRF 3.16.1, psycopg 3.2.13, clickhouse-connect 0.8.18, pytest 8.4.2, pytest-django 4.14.0, ruff 0.16.10, а также gunicorn и whitenoise. Ещё лучше — lock-файл.

#### m10. `.dockerignore` не исключает вложенные кэши

- **Где:** `.dockerignore:4-5,9`. Шаблоны `__pycache__` и `.pytest_cache` срабатывают только в корне контекста, `.ruff_cache` не указан совсем.
- **Воспроизведение (проверено):** в образе есть `/app/plan/__pycache__` и `/app/.ruff_cache`.
- **Исправление:** использовать `**/__pycache__`, `**/*.pyc`, `.ruff_cache`.

#### m11. Пробелы в README

- **Где:** `README.md:76-111`, а также `README.md:21` и `README.md:139`.
- **Суть:**
  - нет curl-примеров для 400/901 (типы, битый JSON, массив), 405/905, 415/906, 406/907 и 503/904, хотя чек-лист требует пример «на каждый код ответа»;
  - не сказано, как попасть в админку (`createsuperuser`);
  - утверждение про обязательный SECRET_KEY см. в M2.
- **Исправление:** дополнить примеры, например `docker compose stop clickhouse` для 503, и добавить `docker compose exec backend python manage.py createsuperuser`.

#### m12. Один кэшированный клиент ClickHouse с автосгенерированным `session_id` небезопасен при многопоточности

- **Где:** `plan/tsdb.py:59-79`. В clickhouse-connect по умолчанию `autogenerate_session_id=True`.
- **Суть:** при gunicorn `sync` проблема не проявляется. Но если перейти на `gthread` или `runserver` (там потоки), параллельные вставки через один клиент дадут `ProgrammingError: Attempt to execute concurrent queries within the same session`, и пользователь получит ложный 503. Дефект латентный.
- **Исправление:** `get_client(..., autogenerate_session_id=False)` или отдельный клиент на поток (`threading.local`).

---

## Что проверено фактически

| Проверка | Команда | Итог |
|---|---|---|
| venv | `python3 -m venv …/scratchpad/venv-review && pip install -r requirements-dev.txt` | Django 5.2.17, DRF 3.16.1, psycopg 3.2.13, clickhouse-connect 0.8.18, pytest 8.4.2, ruff 0.16.10 |
| Тесты на SQLite | `DJANGO_DB_ENGINE=sqlite SQLITE_PATH=<scratchpad> DJANGO_DEBUG=1 pytest -q -p no:cacheprovider` | **64 passed, 1 deselected** |
| Django check | `manage.py check` | No issues |
| Миграции | `manage.py makemigrations --check --dry-run` (SQLite и в контейнере на Postgres) | No changes detected |
| Deploy check | `DJANGO_DEBUG=0 DJANGO_SECRET_KEY=x manage.py check --deploy` | 5 предупреждений, ожидаемых для HTTP-демо (HSTS, SSL redirect, secure cookies, слабый ключ) |
| Обратимость data-миграции | `migrate`, затем `migrate plan 0001`, `migrate plan zero`, `migrate` | Группы создаются и удаляются, повторный прогон вперёд ОК |
| Линтер | `ruff check --no-cache .`, `ruff format --check --no-cache .` | Чисто |
| Иерархия исключений драйвера | инспекция `clickhouse_connect.driver.exceptions` | `OperationalError`, `DatabaseError` и др. наследуют `ClickHouseError`, обёртка в `TsDBUnavailable` корректна |
| Копии ТЗ | `sha256sum` корень и `docs/task/*` | Все 6 совпадают |
| C4 | разбор атрибутов `c4.drawio` | taDB = Postgres, tsDB = ClickHouse, Plan = Django App, JSON/HTTP и SQL: соответствует |
| Сборка и запуск | `BACKEND_PORT=18000 docker compose -p task up -d --build` | 3 сервиса; postgres и clickhouse healthy; migrate, init_clickhouse, seed_demo выполнены; gunicorn с 3 воркерами |
| Тесты в Docker на Postgres | `docker compose -p task run --rm --entrypoint "" backend pytest -q` | **64 passed, 1 deselected** |
| Интеграция с CH | `… backend pytest -q -m clickhouse` | **1 passed**; запись осталась в боевой таблице (m5) |
| curl: сценарии README | скрипт `scratchpad/curl_scenarios.sh` | 201 create; 201 update (тот же id, weight обновлён); 201 rep по токену; 404/174 rep на чужой ЗМК; 406/279; 404/174; 400/901; 403/903; 403/902; 401/900 — все как заявлено |
| curl: крайние случаи | тот же скрипт | `""` → 406/279; неверный пароль, неверный токен и неактивный пользователь → 401/900; GET → 405/905; text/plain → 415/906; битый JSON, массив, NaN, `1.0`, `true` → 400/901; `factory=1e30` и `2^63` → 404/174 (без 500); `weight=2147483647` → 201, `+1` → 400; `start=0`, `finish=5662224000` → 201, в CH `1970-01-01..2149-06-06`; `charset=utf-8` → 201; Accept xml без авторизации → 406/907 (m2); без слэша → 301 (m1); вложенность 100000 → HTML 500 (m1); CSRF → 403/902 (m3) |
| Согласованность PG и CH | `SELECT` в обеих БД | `external_id`, author, start, finish, weight и `created` (до микросекунд) совпадают; в CH 1 запись на каждый успешный POST |
| CH остановлен | `docker compose stop clickhouse` + POST | **503/904**, weight в PG не изменился (откат); после `start` снова 201 |
| CH завис | `docker compose pause clickhouse` + POST | **HTML 500 через 30 с**, `WORKER TIMEOUT` (M1); PG откатан, в CH записи нет |
| Конкурентный upsert | 40 параллельных POST на один ключ; ещё 6 серий по 30 | 40×201, 1 строка в PG, 40 записей в CH; итоговое состояние PG совпадало с `argMax(weight, created)` в CH во всех сериях |
| Админка и статика | `curl /admin/login/`, `/static/admin/css/base.css` | 200 / 200 (whitenoise) |
| Пользователь контейнера | `docker compose exec backend id` | `uid=1000(app)` |
| Рестарт | `docker compose restart backend` | migrate, init и seed идемпотентны, токены сохраняются |
| Уборка | `docker compose -p task down -v`, `docker image rm task-backend` | Контейнеры, сеть, volumes и образ проекта удалены; чужие контейнеры (`test_app-*`) не тронуты |

Код не изменялся, коммиты не создавались. Временные файлы (venv, sqlite, curl-скрипт, cookie jar) лежат в scratchpad.
