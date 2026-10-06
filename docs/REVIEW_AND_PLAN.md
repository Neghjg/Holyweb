# Ревью ТЗ и план реализации: «Сохранить объём работ» (Backend / Plan)

Документ состоит из четырёх частей:

1. Критический разбор ТЗ: противоречия, неоднозначности, пробелы.
2. Принятые решения (допущения) с обоснованием. Это **нормативная часть для кодогенератора**: если код расходится с разделом 2, ошибка в коде.
3. Детальный план реализации: файлы и содержимое каждого.
4. Критерии приёмки (чек-лист для финального критика).

Исходные артефакты ТЗ: `readme.md`, `c4.drawio`, `er.puml`, `use_case_map.puml`, `V_b_24.puml`, `request.schema.json`. Все они прочитаны целиком.

---

## 0. Краткое содержание ТЗ (что именно требуется)

- Django-проект **Backend** с приложением **Plan** (в C4 это компонент `V.b.iii. Plan [Component: Django App]` внутри контейнера `V.b. Backend`).
- Реализовать use case «Сохранить объём работ» (`V_b_24`): `POST /work-volume-list/`, тело описано в `request.schema.json`. Акторы: «Представитель ЗМК» и «Менеджер по взаимодействию с ЗМК», связь JSON/HTTP.
- Хранилища: `V.c. taDB` = Postgres (Factory, FactoryUser, WorkVolume, а также Django User/Group) и `V.d. tsDB` = ClickHouse (WorkVolumeRecord). Связи Plan → БД подписаны в C4 как «SQL».
- Подготовить docker-compose и выложить результат в публичный git-репозиторий.

---

## 1. Критический разбор ТЗ

Важность: **К** — критично, без решения код не написать; **С** — существенно, влияет на поведение API; **М** — мелочь или косметика.

| # | Где | Проблема | Важн. |
|---|-----|----------|-------|
| P1 | schema vs ER | `start`/`finish` в запросе имеют тип `integer`, а в ER это `date`. Формат не указан: Unix timestamp в секундах или миллисекундах, `YYYYMMDD`, число дней от эпохи? Часовой пояс тоже не указан. | К |
| P2 | schema vs ER | `factory` в запросе имеет тип `integer`, а в `WorkVolumeRecord.factory` лежит `uuid` (внешний идентификатор). Не сказано, что приходит в запросе: `Factory.id` или что-то иное. | К |
| P3 | schema vs sequence | `author` передаётся в теле, но в диаграмме проверки идут по «Пользователю», который отправил запрос. Не сказано, кого проверять на группу и привязку к ЗМК: `author` или аутентифицированного пользователя. Аутентификация в ТЗ вообще не упоминается. Если доверять `author` из тела, проверки прав обходятся простой подменой id. | К |
| P4 | sequence | Нет ветки «пользователь не входит ни в одну из групп»: ответ не определён. | К |
| P5 | sequence | Нет ветки «пользователь входит в обе группы»: порядок `alt` даёт приоритет «Представителю», и такой пользователь может получить 404 там, где менеджер получил бы 201. | С |
| P6 | sequence | Во вложенной ветке «пользователь является пользователем ЗМК → else» подпись «ЗМК не существует» не соответствует условию: на деле пользователь просто не привязан к ЗМК. Похоже на copy-paste, но код ответа `404 / errorCode=174` указан явно. | С |
| P7 | sequence | Для незаполненных полей указан `406 Not Acceptable`. По RFC 9110 код 406 относится к согласованию контента (заголовок `Accept`), для невалидного тела правильнее 400 или 422. Кроме того, проверяется только «заполненность»: ответ на неверный тип (строка, float, bool) и на семантически неверные значения не определён. | С |
| P8 | sequence | Формат тела ошибки не задан: есть только `errorCode=NNN`. Тип errorCode (число или строка), наличие сообщения и деталей неизвестны. | С |
| P9 | sequence | Тело успешного ответа `201` не описано. Кроме того, 201 Created возвращается и при **обновлении** существующей записи, что семантически неточно (обычно 200). | М |
| P10 | sequence/ER | «Объём работ ЗМК за период уже присутствует» (в диаграмме опечатка «присутствие»): ключ «того же периода» не задан. Точное совпадение `(factory, start, finish)` или пересечение интервалов? В ER нет ни уникального ограничения, ни правил для пересекающихся периодов. | К |
| P11 | ER | Поле `created` при upsert **обновляется** (по диаграмме обновляются «weight и created»), то есть по смыслу это `updated_at`/`last_saved`, а не дата создания. Тип `date` теряет время, хотя для журнала в ClickHouse время полезно. | С |
| P12 | ER | `FactoryUser }o--o{ User` означает «многие-ко-многим» между связующей сущностью и User, что для связующей таблицы бессмысленно. Скорее всего имелось в виду: User M:N Factory через FactoryUser (одна строка = один пользователь + один завод). Уникальность пары не указана. | С |
| P13 | ER | `WorkVolumeRecord }o-l-|| Factory` рисует связь между сущностями в **разных СУБД** (ClickHouse → Postgres). FK невозможен, связь только логическая, через `external_id`. | М |
| P14 | ER | `WorkVolumeRecord.id: integer`, но в ClickHouse нет автоинкремента. Как генерировать id, не сказано. | С |
| P15 | ER | `WorkVolumeRecord.author: User`: в ClickHouse нет FK на Django User. Что хранить (id, username), не сказано. | М |
| P16 | schema | Валидации значений нет: `start <= finish`, `weight >= 0`, диапазоны, положительность id. Нет `additionalProperties`, нет `minimum`. Схема draft-04. | С |
| P17 | architecture | Запись идёт в две СУБД (Postgres + ClickHouse) без распределённой транзакции. Порядок операций и поведение при сбое ClickHouse не определены. | К |
| P18 | architecture | Способ работы с ClickHouse из Django не задан: драйвер, создание таблицы, движок. ORM Django ClickHouse не поддерживает, миграции Django к нему не применимы. | К |
| P19 | sequence | Порядок проверок: существование ЗМК проверяется **до** проверки прав. Любой аутентифицированный пользователь, даже без групп, может перебором выяснить, какие `factory id` существуют (404 против 403). В диаграмме нет и шага аутентификации. | С |
| P20 | sequence | После `404` в первом `alt` «ЗМК не существует» поток формально продолжается: нет `return`/`break`. Надо явно трактовать это как завершение обработки. | М |
| P21 | ограничение ClickHouse | Тип `Date` в ClickHouse покрывает только 1970-01-01..2149-06-06, `Date32` покрывает 1900..2299. Без ограничения диапазона в API вставка «далёких» дат в tsDB молча переполнится или упадёт уже после записи в Postgres. | С |
| P22 | readme | Название проекта `Backend` и приложения `Plan` с заглавной буквы противоречит PEP 8 (имена модулей в нижнем регистре). | М |
| P23 | репозиторий | Исходный `readme.md` (ТЗ) и будущий `README.md` проекта на регистронезависимых ФС (macOS, Windows) превращаются в один файл: в публичном репозитории это сломает checkout. | С |
| P24 | readme | Не указано, нужны ли тестовые данные (ЗМК, пользователи) и как проверяющий получит пользователя с нужной группой. Без seed проверить сценарий нельзя. | С |
| P25 | C4 | Связь Plan → tsDB подписана «SQL». У ClickHouse есть HTTP (8123) и native TCP (9000), SQL ходит по обоим. Это не противоречие, но выбор транспорта остаётся за нами. | М |
| P26 | sequence | Для внутренних ошибок (недоступна БД) ответ не определён. | М |

---

## 2. Принятые решения (нормативно для кодогенератора)

### D1. Формат дат `start`/`finish` (P1, P21)

- Целое число трактуется как **Unix timestamp в секундах, UTC**.
- Значение **обязано** приходиться на полночь UTC: `ts % 86400 == 0`. Иначе `400 / errorCode=901` с сообщением «start must be a UTC midnight unix timestamp (seconds)».
  - Обоснование. Если молча усекать время, клиент из UTC+3, отправивший «свою» полночь (21:00 UTC предыдущего дня), получил бы сдвиг даты на сутки. Явная ошибка лучше скрытой порчи данных.
- Допустимый диапазон: `0 <= ts <= 5662224000` (1970-01-01..2149-06-06), то есть ровно диапазон `Date` в ClickHouse.
  - Обоснование. Ограничение tsDB проверяется до записи в БД. Заодно отсекаются миллисекундные timestamp (~1.7e12), самая частая ошибка клиентов.
- Внутри приложения после валидации значения хранятся как `datetime.date` (`DateField` в Postgres, `Date` в ClickHouse).
- В ответе `start`/`finish` возвращаются **в том же формате, что и в запросе** (целые секунды на полночь UTC): API симметричен.

### D2. Поле `factory` в запросе (P2, P13)

- `factory` — это `Factory.id` (PK в Postgres), единственный целочисленный идентификатор ЗМК в ER.
- В ClickHouse (`WorkVolumeRecord.factory`) пишется `Factory.external_id` (UUID) найденного завода. Связь с Factory только логическая, FK нет.

### D3. Аутентификация и поле `author` (P3, P19)

- Эндпоинт требует аутентификации (`IsAuthenticated`). Без неё ответ `401 / errorCode=900`.
- Схемы аутентификации DRF в таком порядке: `BasicAuthentication` (первой, чтобы DRF отдавал 401 с `WWW-Authenticate`, а не 403), `TokenAuthentication` (`rest_framework.authtoken`), `SessionAuthentication` (для browsable API и админки; CSRF для сессий DRF проверяет сам).
- **Все проверки прав (группы, привязка к ЗМК) выполняются для `request.user`**, а не для `author` из тела.
- `author` обязателен по схеме и должен совпадать с `request.user.id`. Иначе `403 / errorCode=903` («author must match the authenticated user»).
  - Обоснование. Схема соблюдается (поле обязательно), подмена авторства исключена, автор записи в tsDB достоверен. Сценарий «менеджер вводит от имени другого» в ТЗ не описан, поэтому он запрещён.
- Неактивные пользователи (`is_active=False`) отсекаются штатными механизмами Django/DRF и получают 401.
- Суперпользователь никаких обходов **не получает**: права определяются только группами, строго по диаграмме.

### D4. Группы и ветвление (P4, P5, P6)

- Имена групп в точности как в ТЗ (константы в `plan/constants.py`):
  - `GROUP_FACTORY_REPRESENTATIVE = "Представитель ЗМК"`
  - `GROUP_FACTORY_MANAGER = "Менеджер по взаимодействию с ЗМК"`
- Группы создаются **data-миграцией** (идемпотентно, `get_or_create`; обратная операция удаляет их).
- Логика:
  1. Пользователь в группе «Менеджер…»: может сохранять объём для **любого** существующего ЗМК. Если пользователь состоит в обеих группах, **приоритет у менеджера**: роль с бо́льшими правами не должна сужаться из-за второй роли. Это отступление от буквального порядка `alt`, оно зафиксировано в README.
  2. Пользователь только в группе «Представитель…»: нужна строка `FactoryUser(user=request.user, factory=factory)`. Если её нет, ответ **`404 / errorCode=174`**, как в диаграмме. Подпись «ЗМК не существует» трактуется так: «ЗМК не существует для данного пользователя». Это осознанная практика: не раскрывать представителю существование чужих ЗМК. В README и в комментарии кода это помечено как трактовка опечатки.
  3. Пользователь не состоит ни в одной группе: **`403 / errorCode=902`** («user has no role permitted to save work volume»).

### D5. Порядок проверок (P19, P20)

Строго такой. Каждый шаг при неудаче **завершает** обработку:

1. Аутентификация → 401/900.
2. Тело — JSON-объект. Ошибка парсинга JSON или тело не объект (массив, строка) → 400/901. Content-Type не `application/json` → 415/906.
3. **Заполненность**: ключи `factory, start, finish, weight, author` присутствуют, значение не `null` и не `""` → иначе **406/279** со списком `missing` в `details`.
4. Типы и значения (D7) → 400/901 с детализацией по полям.
5. **Существование ЗМК** (`Factory.objects.filter(pk=factory)`) → 404/174.
6. `author == request.user.id` → 403/903.
7. Группы и привязка (D4) → 403/902 или 404/174.
8. Сохранение (D9, D10) → 201. При недоступности ClickHouse → 503/904.

Обоснование: шаги 3, 5 и 7 повторяют порядок диаграммы. Шаги 1, 2, 4 и 6 добавлены нами, они нужны, чтобы решение было корректным и безопасным. Утечка «существует ли ЗМК» на шаге 5 для пользователей без групп принимается как следствие диаграммы (ТЗ явно ставит проверку ЗМК до проверки групп) и описана в README.

### D6. Коды ответов и формат ошибок (P7, P8, P9, P26)

Единый формат тела **любой** ошибки:

```json
{"errorCode": 279, "message": "Required fields are missing", "details": {"missing": ["start", "weight"]}}
```

- `errorCode` — целое число, `message` — строка на английском, `details` — объект (может быть `{}`).
- Ошибки DRF приводятся к этому формату кастомным `EXCEPTION_HANDLER`.

| HTTP | errorCode | Когда | Источник |
|------|-----------|-------|----------|
| 201 | — | создан **или обновлён** WorkVolume и создана запись в tsDB | ТЗ (201 в обеих ветках; оставляем 201 и для update, как в диаграмме) |
| 400 | 901 | невалидный JSON, тело не объект, неверный тип, нарушение правил D7 | **наше** |
| 401 | 900 | нет или неверные учётные данные | **наше** |
| 403 | 902 | пользователь не в разрешённой группе | **наше** (P4) |
| 403 | 903 | `author != request.user.id` | **наше** (D3) |
| 404 | 174 | ЗМК не существует, либо представитель не привязан к ЗМК | ТЗ |
| 405 | 905 | метод не POST | **наше** |
| 406 | 279 | не заполнены обязательные поля (отсутствует, `null`, `""`) | ТЗ |
| 415 | 906 | Content-Type не JSON | **наше** |
| 503 | 904 | tsDB (ClickHouse) недоступна, изменения в taDB откатаны | **наше** |

- Код 406 для незаполненных полей **сохраняется**, как в ТЗ, хотя он семантически спорен. ТЗ явно задаёт контракт, и проверяющий будет проверять именно его. Неверные типы и значения ТЗ не покрывает, поэтому для них используется корректный 400 с отдельным кодом, а не 406/279: смешивать «не заполнено» и «заполнено неверно» нельзя.
- Коды 900–906 придуманы нами, их диапазон выбран заведомо далеко от кодов ТЗ (174, 279). Все коды заданы в `plan/constants.py` (`IntEnum ErrorCode`) и перечислены в README.
- DRF сам может вернуть 406 из-за заголовка `Accept`. Кастомный handler отдаёт его как 406/907 («not acceptable media type»), чтобы не путать с 279.
- Тело **успешного** ответа 201:

```json
{"id": 12, "factory": 1, "start": 1735689600, "finish": 1738281600, "weight": 1500, "created": "2026-10-06T10:15:00.123456Z"}
```

`id` и `factory` — PK в Postgres, `created` — ISO 8601 UTC.

### D7. Валидация значений (P16)

- Все пять полей — **строго** JSON integer. Отклоняются `bool` (в Python `True` — это `int`!), `str` (даже `"5"`), `float` (даже `5.0`). Стандартный `serializers.IntegerField` DRF принимает строку `"5"`, поэтому нужно кастомное поле `StrictIntegerField`.
- `factory >= 1`, `author >= 1`.
- `weight`: `0 <= weight <= 2147483647`. Ноль допустим (в этом периоде объёма нет), верхняя граница — `int4` Postgres.
- `start`/`finish` по D1, плюс `start <= finish` (ошибка в `details.non_field_errors` или `details.finish`).
- Лишние поля в теле **игнорируются**: в схеме нет `additionalProperties: false`, а draft-04 по умолчанию допускает дополнительные свойства.

### D8. Модели taDB (P10, P11, P12)

- `Factory`: `id` BigAutoField, `external_id` UUIDField(unique, default=uuid4, editable=False), `name` CharField(max_length=255). `__str__` возвращает name.
- `FactoryUser` — связующая таблица User M:N Factory:
  - `user` FK → `settings.AUTH_USER_MODEL`, on_delete=CASCADE, related_name=`factory_links`;
  - `factory` FK → Factory, on_delete=CASCADE, related_name=`user_links`;
  - `UniqueConstraint(fields=["user", "factory"], name="uniq_factory_user")`.

  Обоснование: `}o--o{` трактуется как M:N между User и Factory через FactoryUser. Пользователь может быть представителем нескольких ЗМК.
- `WorkVolume`:
  - `factory` FK → Factory, on_delete=PROTECT, related_name=`work_volumes` (объёмы не должны пропадать вместе с удалённым заводом);
  - `start` DateField, `finish` DateField;
  - `weight` PositiveIntegerField (вес в кг);
  - `created` DateTimeField;
  - `UniqueConstraint(fields=["factory","start","finish"], name="uniq_work_volume_factory_period")`;
  - `CheckConstraint(start <= finish)` и `CheckConstraint(weight >= 0)`. В Django 5.1+ параметр называется `condition=`, а `check=` устарел.
- «Тот же период» означает **точное совпадение** `(factory, start, finish)`. Пересекающиеся, но не совпадающие периоды допускаются как разные записи: ТЗ не задаёт правил слияния, а запрет пересечений меняет бизнес-логику без основания.
- `created`: **DateTimeField (UTC)**, а не DateField. При обновлении значение перезаписывается текущим временем, как требует диаграмма («обновление weight и created»). Обоснование: datetime — надмножество date и нужен для упорядочивания записей журнала в tsDB в пределах дня. Имя поля сохранено, как в ER, хотя по смыслу это «дата последнего сохранения». Это отмечено в README.
- `DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"`.

### D9. tsDB / ClickHouse (P14, P15, P18, P25)

- Драйвер **`clickhouse-connect`** (официальный, HTTP 8123, не требует нативного протокола).
- Таблица создаётся **management-командой `init_clickhouse`** (идемпотентно, `IF NOT EXISTS`), её вызывает entrypoint после `migrate`. Миграции Django к ClickHouse не применимы, а init-скрипт в образе ClickHouse разнёс бы схему по двум местам. Команда — единый источник истины на Python, её легко тестировать.
- DDL (БД задаётся `CLICKHOUSE_DATABASE`, по умолчанию `plan`):

```sql
CREATE DATABASE IF NOT EXISTS plan;
CREATE TABLE IF NOT EXISTS plan.work_volume_record
(
    id       UInt64 DEFAULT generateSnowflakeID(),
    factory  UUID,
    start    Date,
    finish   Date,
    weight   UInt32,
    author   UInt64,
    created  DateTime64(6, 'UTC')
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(created)
ORDER BY (factory, start, finish, created);
```

- `id`: в ClickHouse нет автоинкремента, поэтому используется `generateSnowflakeID()` (есть с 24.6). Это целое, монотонное по времени и уникальное значение, что соответствует ER (`id: integer`) без привязки к Postgres. Требуется образ **`clickhouse/clickhouse-server:24.8`** (LTS).
- `author`: id пользователя Django (`UInt64`). Username не дублируется.
- Партиционирование по `created` (ограничено «сейчас»), а **не** по `start`: произвольные даты периода могли бы породить тысячи партиций.
- `created` в записи равен `WorkVolume.created`: используется одно значение `now = timezone.now()` на запрос.
- Запись — синхронный `client.insert(...)` с явным `column_names` и настройкой `async_insert=0`, чтобы ошибка вставки была видна в запросе.
- Слой доступа (`plan/tsdb.py`):
  - `get_clickhouse_client()` — ленивый кэшируемый клиент из settings;
  - `WorkVolumeRecordRepository` с методом `add(record: WorkVolumeRecordDTO) -> None` и функцией `ensure_schema()`;
  - сервис получает репозиторий через функцию-фабрику `get_work_volume_record_repository()`, чтобы тесты могли подменить её фейком.
  - Исключения драйвера (`clickhouse_connect.driver.exceptions.ClickHouseError`, `OperationalError`, сетевые `OSError`) оборачиваются в `TsDBUnavailable`.

### D10. Согласованность Postgres ↔ ClickHouse (P17)

Распределённой транзакции нет. Выбран порядок **«Postgres внутри открытой транзакции → ClickHouse → commit»**:

```
with transaction.atomic():
    upsert WorkVolume (INSERT ... ON CONFLICT (factory,start,finish) DO UPDATE SET weight, created)
    tsdb_repo.add(record)        # при ошибке → исключение → ROLLBACK → 503/904
# commit
```

- Upsert выполняется через `WorkVolume.objects.bulk_create([obj], update_conflicts=True, unique_fields=["factory","start","finish"], update_fields=["weight","created"])`. Это атомарный `INSERT ... ON CONFLICT DO UPDATE`, без гонки «select → insert». В Postgres (Django 5.x) `pk` объекта после вызова заполнен. Если `pk` вдруг `None`, объект перечитывается по уникальному ключу.
- Если ClickHouse упал, Postgres откатывается и клиент получает 503/904. Состояние **согласовано**, повтор безопасен (upsert идемпотентен).
- Остаточный риск: ClickHouse записал, а `COMMIT` в Postgres упал (крайне редкий сбой). Тогда в журнале tsDB появится «лишняя» запись о попытке. Для журнала-истории (append-only) это меньшее зло, чем потерянная запись при обратном порядке.
- Блокировка строки WorkVolume удерживается на время вставки в ClickHouse: конкурентные запросы с тем же ключом сериализуются. Это допустимо.
- Production-альтернатива (transactional outbox + воркер) описана в README как развитие и **не** реализуется.

### D11. Структура проекта и имена (P22, P23)

- Django-проект — Python-пакет `backend` (`django-admin startproject backend .`), приложение — `plan`. Нижний регистр выбран по PEP 8. `AppConfig.verbose_name = "Plan"`. Соответствие «Backend → backend, Plan → plan» указано в README.
- Исходные файлы ТЗ в корне **не изменяются и не удаляются**. Их копии кладутся в `docs/task/` (относительные ссылки между puml и schema сохраняются, потому что копируется вся группа). Корневые оригиналы исключаются из git через `.gitignore`. Так в публичном репозитории не окажутся одновременно `readme.md` и `README.md`, которые на macOS/Windows сливаются в один файл.

### D12. Демо-данные (P24)

- Management-команда `seed_demo` (идемпотентная) создаёт:
  - ЗМК: `Factory(id=1, "ЗМК Север")` и `Factory(id=2, "ЗМК Юг")` (через get_or_create по name; id не хардкодить, а печатать);
  - пользователей (пароли берутся из env `DEMO_PASSWORD`, по умолчанию `demo12345`):
    - `rep` — группа «Представитель ЗМК», `FactoryUser(rep, ЗМК Север)`;
    - `manager` — группа «Менеджер по взаимодействию с ЗМК»;
    - `nobody` — без групп;
  - DRF-токены для всех трёх.
- Команда печатает таблицу `username / user_id / token / factory ids`.
- Entrypoint вызывает её только при `SEED_DEMO=1` (в `.env.example` стоит `1`, в README есть предупреждение, что это только для демо).

---

## 3. План реализации

### 3.1 Версии и зависимости

`requirements.txt` (версии зафиксированы):

```
Django==5.2.*            # LTS
djangorestframework==3.16.*
psycopg[binary]==3.2.*
clickhouse-connect==0.8.*
gunicorn==23.*
whitenoise==6.*
```

`requirements-dev.txt`:

```
-r requirements.txt
pytest==8.*
pytest-django==4.*
ruff==0.*
```

Python 3.12 (`python:3.12-slim`). Postgres `postgres:16-alpine`. ClickHouse `clickhouse/clickhouse-server:24.8`.

Конкретные patch-версии генератор фиксирует сам на момент генерации. Обязательно: `pip install` в образе проходит без ошибок.

### 3.2 Дерево репозитория (корень: `/home/andrew/Downloads/task`)

```
.
├── readme.md, c4.drawio, er.puml, use_case_map.puml, V_b_24.puml, request.schema.json   # оригиналы ТЗ: НЕ ТРОГАТЬ, исключены .gitignore
├── README.md
├── .gitignore
├── .dockerignore
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── docker/
│   └── entrypoint.sh
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── manage.py
├── backend/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── plan/
│   ├── __init__.py
│   ├── apps.py
│   ├── admin.py
│   ├── constants.py
│   ├── errors.py
│   ├── fields.py
│   ├── models.py
│   ├── serializers.py
│   ├── services.py
│   ├── tsdb.py
│   ├── views.py
│   ├── urls.py
│   ├── migrations/
│   │   ├── __init__.py
│   │   ├── 0001_initial.py
│   │   └── 0002_create_groups.py
│   └── management/
│       ├── __init__.py
│       └── commands/
│           ├── __init__.py
│           ├── init_clickhouse.py
│           └── seed_demo.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_fields.py
│   ├── test_serializers.py
│   ├── test_api_work_volume.py
│   ├── test_services.py
│   ├── test_groups_migration.py
│   ├── test_tsdb.py
│   └── test_clickhouse_integration.py
└── docs/
    ├── REVIEW_AND_PLAN.md   # этот файл
    └── task/                # копии файлов ТЗ (байт в байт)
```

### 3.3 Содержимое файлов

**`.gitignore`**: `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `.env`, `staticfiles/`, `.pytest_cache/`, `.ruff_cache/`, `*.sqlite3`, `.idea/`, `.vscode/`, а также корневые оригиналы ТЗ с якорем `/`: `/readme.md`, `/c4.drawio`, `/er.puml`, `/use_case_map.puml`, `/V_b_24.puml`, `/request.schema.json`.

**`.dockerignore`**: `.git`, `.venv`, `venv`, `__pycache__`, `*.pyc`, `.env`, `docs/`, `staticfiles/`, `.pytest_cache`, корневые файлы ТЗ.

**`.env.example`** (все переменные с безопасными для локального демо значениями и комментариями):

```
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,backend
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=plan
POSTGRES_USER=plan
POSTGRES_PASSWORD=plan
CLICKHOUSE_HOST=clickhouse
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=plan
CLICKHOUSE_PASSWORD=plan
CLICKHOUSE_DATABASE=plan
SEED_DEMO=1
DEMO_PASSWORD=demo12345
```

**`pyproject.toml`**: `[tool.pytest.ini_options]` с `DJANGO_SETTINGS_MODULE = "backend.settings"`, `testpaths = ["tests"]`, `markers = ["clickhouse: needs real ClickHouse"]` и `addopts = "-m 'not clickhouse'"`. Плюс `[tool.ruff]` с `target-version = "py312"` и `line-length = 100`.

**`backend/settings.py`**:
- Конфигурация только из `os.environ`, без лишних зависимостей. Хелперы `env_bool` и `env_list`.
- `SECRET_KEY` обязателен при `DEBUG=0`: если его нет, `ImproperlyConfigured`. При `DEBUG=1` допускается дефолтный dev-ключ.
- `INSTALLED_APPS`: admin, auth, contenttypes, sessions, messages, staticfiles, `rest_framework`, `rest_framework.authtoken`, `plan.apps.PlanConfig`.
- `MIDDLEWARE` включает `whitenoise.middleware.WhiteNoiseMiddleware` сразу после SecurityMiddleware.
- `DATABASES["default"]` — `django.db.backends.postgresql` из `POSTGRES_*`.
- `CLICKHOUSE = {host, port, username, password, database}` из `CLICKHOUSE_*`.
- `USE_TZ = True`, `TIME_ZONE = "UTC"`, `LANGUAGE_CODE = "ru-ru"`.
- `STATIC_ROOT = BASE_DIR / "staticfiles"`, `DEFAULT_AUTO_FIELD = BigAutoField`.
- `REST_FRAMEWORK`:
  - `DEFAULT_AUTHENTICATION_CLASSES`: Basic, Token, Session — порядок важен (D3);
  - `DEFAULT_PERMISSION_CLASSES`: `IsAuthenticated`;
  - `DEFAULT_PARSER_CLASSES`: `JSONParser`;
  - `DEFAULT_RENDERER_CLASSES`: `JSONRenderer` (+ `BrowsableAPIRenderer` при DEBUG);
  - `EXCEPTION_HANDLER`: `plan.errors.api_exception_handler`.
- `LOGGING`: консоль, уровень INFO; логгер `plan`.

**`backend/urls.py`**: `admin/` и `include("plan.urls")` в корне, чтобы путь был ровно `/work-volume-list/`.

**`plan/apps.py`**: `PlanConfig(name="plan", verbose_name="Plan")`.

**`plan/constants.py`**:
- `GROUP_FACTORY_REPRESENTATIVE`, `GROUP_FACTORY_MANAGER` (D4);
- `REQUIRED_FIELDS = ("factory", "start", "finish", "weight", "author")`;
- `SECONDS_PER_DAY = 86400`;
- `MAX_DATE_TS = 5662224000` (2149-06-06 00:00:00 UTC);
- `MAX_WEIGHT = 2147483647`;
- `class ErrorCode(IntEnum)`: `FACTORY_NOT_FOUND=174`, `REQUIRED_FIELDS_MISSING=279`, `NOT_AUTHENTICATED=900`, `VALIDATION_ERROR=901`, `NO_PERMITTED_GROUP=902`, `AUTHOR_MISMATCH=903`, `TSDB_UNAVAILABLE=904`, `METHOD_NOT_ALLOWED=905`, `UNSUPPORTED_MEDIA_TYPE=906`, `NOT_ACCEPTABLE=907`, `INTERNAL_ERROR=999`.

**`plan/errors.py`**:
- Базовый класс `ApiError(Exception)` с атрибутами `status_code`, `error_code`, `message`, `details`.
- Подклассы:
  - `RequiredFieldsMissing` (406/279),
  - `ValidationFailed` (400/901),
  - `FactoryNotFound` (404/174),
  - `AuthorMismatch` (403/903),
  - `NoPermittedGroup` (403/902),
  - `TsDBUnavailable` (503/904).
- `api_exception_handler(exc, context)`:
  - `ApiError` → `Response({"errorCode", "message", "details"}, status)`;
  - DRF `NotAuthenticated`/`AuthenticationFailed` → 401/900 с сохранением заголовка `WWW-Authenticate`;
  - `ParseError` → 400/901;
  - `ValidationError` → 400/901 с `details = exc.detail`;
  - `MethodNotAllowed` → 405/905;
  - `UnsupportedMediaType` → 415/906;
  - `NotAcceptable` → 406/907;
  - `PermissionDenied` → 403/902;
  - `NotFound`/`Http404` → 404 с кодом 174 только если это `FactoryNotFound`, иначе 404/999;
  - прочие исключения → вернуть `None`, чтобы Django отдал 500. Опционально 500/999 с логированием.

**`plan/fields.py`**:
- `StrictIntegerField(serializers.IntegerField)`: в `to_internal_value` проверяет `type(data) is int` (bool и str отклоняются), затем `super()` для `min_value`/`max_value`.
- `UnixMidnightDateField(serializers.Field)`:
  - вход — strict int в `[0, MAX_DATE_TS]`, кратный 86400 → `date` через `datetime.fromtimestamp(ts, tz=UTC).date()`;
  - выход (`to_representation`) — `date` → `int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())`.

**`plan/models.py`**: модели по D8 с `Meta` (`verbose_name` на русском, constraints, `ordering`) и `__str__`.

**`plan/migrations/0001_initial.py`**: генерируется `makemigrations`, править руками нельзя. Проверить, что внутри есть оба UniqueConstraint и оба CheckConstraint.

**`plan/migrations/0002_create_groups.py`**:
- `RunPython(create_groups, delete_groups)`;
- `create_groups` через `apps.get_model("auth","Group")` делает `get_or_create` обеих групп;
- зависимости: `("plan","0001_initial")` и `("auth", "0012_alter_user_first_name_max_length")` (или актуальная последняя миграция auth в Django 5.2).

**`plan/admin.py`**:
- `FactoryAdmin` (list_display id, name, external_id; readonly external_id);
- `FactoryUserAdmin` (list_display user, factory; autocomplete_fields);
- `WorkVolumeAdmin` (list_display factory, start, finish, weight, created; list_filter factory).

**`plan/serializers.py`**:
- `WorkVolumeRequestSerializer(serializers.Serializer)`:
  - `factory` — `StrictIntegerField(min_value=1)`;
  - `start`, `finish` — `UnixMidnightDateField()`;
  - `weight` — `StrictIntegerField(min_value=0, max_value=MAX_WEIGHT)`;
  - `author` — `StrictIntegerField(min_value=1)`;
  - `validate()` проверяет `start <= finish`, иначе ошибка `{"finish": ["finish must be >= start"]}`.
- `WorkVolumeResponseSerializer(serializers.ModelSerializer)`: поля `id`, `factory` (PK), `start`, `finish` (`UnixMidnightDateField`), `weight`, `created`.
- Проверку **заполненности** делает не сериализатор, а отдельная функция `check_required_fields(data) -> list[str]` в `serializers.py`. Она возвращает отсутствующие поля в порядке `REQUIRED_FIELDS`: ключ отсутствует, значение `None` или `""`. Причина: DRF сам выдал бы 400 «This field is required.», а нам нужен 406/279 **до** проверки типов.

**`plan/tsdb.py`**:
- `@dataclass(frozen=True) WorkVolumeRecordDTO(factory: UUID, start: date, finish: date, weight: int, author: int, created: datetime)`.
- `TABLE_NAME = "work_volume_record"`, константы DDL (D9) с подстановкой имени БД через проверенный идентификатор: только `[A-Za-z0-9_]`, иначе `ImproperlyConfigured`.
- `get_clickhouse_client(database: str | None = ...)` — `clickhouse_connect.get_client(host, port, username, password, database=...)`, кэш в модуле с потокобезопасной инициализацией (`threading.Lock`) или `functools.lru_cache`.
- `ensure_schema()`: подключение без `database` (или к `default`), затем `CREATE DATABASE IF NOT EXISTS` и `CREATE TABLE IF NOT EXISTS`.
- `class ClickHouseWorkVolumeRecordRepository`, метод `add(dto)`:
  - `client.insert(f"{db}.{TABLE_NAME}", [[dto.factory, dto.start, dto.finish, dto.weight, dto.author, dto.created]], column_names=["factory","start","finish","weight","author","created"], settings={"async_insert": 0})`;
  - исключения драйвера и `OSError` → `raise TsDBUnavailable from e`.
- `get_work_volume_record_repository()` возвращает экземпляр репозитория (точка подмены в тестах).

**`plan/services.py`**:
- `save_work_volume(*, user, factory_id, start, finish, weight, author_id, repo=None) -> WorkVolume`.
- Шаги D5 начиная с 5-го:
  1. Factory по pk, иначе `FactoryNotFound`.
  2. `author_id != user.pk` → `AuthorMismatch`.
  3. Имена групп пользователя одним запросом: `set(user.groups.values_list("name", flat=True))`.
  4. Если менеджер (приоритет), доступ разрешён. Иначе, если представитель, проверить `FactoryUser.objects.filter(user=user, factory=factory).exists()`, при отсутствии — `FactoryNotFound`. Иначе `NoPermittedGroup`.
  5. `now = timezone.now()`.
  6. `transaction.atomic()`: upsert через `bulk_create(update_conflicts=...)` (D10), получить объект (pk; если `None` — `get` по ключу), затем `repo.add(WorkVolumeRecordDTO(factory=factory.external_id, ..., author=user.pk, created=now))`.
  7. Вернуть объект WorkVolume.
- Логирование: INFO «work volume saved» (factory_id, period, user_id), WARNING при `TsDBUnavailable`.

**`plan/views.py`**:
- `WorkVolumeListView(APIView)`, `http_method_names = ["post", "options"]` (или только `post`).
- `post(request)`:
  1. `data = request.data`; если не `dict` → `ValidationFailed("Request body must be a JSON object")`.
  2. `missing = check_required_fields(data)` → `RequiredFieldsMissing(details={"missing": missing})`.
  3. `serializer = WorkVolumeRequestSerializer(data=data)`; если не валиден → `ValidationFailed(details=serializer.errors)`.
  4. `wv = save_work_volume(user=request.user, **mapped validated_data)`.
  5. `Response(WorkVolumeResponseSerializer(wv).data, status=201)`.
- Никакой бизнес-логики во view, только оркестрация.

**`plan/urls.py`**: `path("work-volume-list/", WorkVolumeListView.as_view(), name="work-volume-list")`.

**`plan/management/commands/init_clickhouse.py`**: вызывает `ensure_schema()`. Делает ретраи: до N=30 попыток с паузой 1 с, на случай если healthcheck ещё «зелёный», а HTTP не готов. Код выхода не 0 при неудаче.

**`plan/management/commands/seed_demo.py`**: по D12. Идемпотентна, выполняется в `transaction.atomic`, в конце печатает таблицу.

**`Dockerfile`**:
- `FROM python:3.12-slim`;
- `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1`;
- `ARG INSTALL_DEV=0`; `WORKDIR /app`;
- копирование `requirements*.txt`, затем `pip install -r requirements.txt` (или `requirements-dev.txt`, если `INSTALL_DEV=1`);
- `COPY . .`;
- `RUN DJANGO_SECRET_KEY=build DJANGO_DEBUG=0 python manage.py collectstatic --noinput`;
- непривилегированный пользователь `app` (`useradd`), `USER app`;
- `EXPOSE 8000`;
- `ENTRYPOINT ["/app/docker/entrypoint.sh"]`;
- `CMD ["gunicorn","backend.wsgi:application","--bind","0.0.0.0:8000","--workers","3","--access-logfile","-"]`.
- У `entrypoint.sh` должен быть бит исполнения: `chmod +x` в git и/или `RUN chmod +x` в Dockerfile.

**`docker/entrypoint.sh`**:
- `#!/bin/sh`, `set -e`;
- `python manage.py migrate --noinput`;
- `python manage.py init_clickhouse`;
- `if [ "${SEED_DEMO:-0}" = "1" ]; then python manage.py seed_demo; fi`;
- `exec "$@"`.

Благодаря `exec "$@"` команда `docker compose run --rm backend pytest` тоже пройдёт через migrate/init. Для тестов это безвредно, но лучше в `docker-compose.yml` не переопределять entrypoint, а в README указать `docker compose run --rm --entrypoint "" backend pytest`.

**`docker-compose.yml`** (без устаревшего ключа `version:`):

- `postgres`:
  - `image: postgres:16-alpine`;
  - env `POSTGRES_DB/USER/PASSWORD` из `.env`;
  - volume `pg_data:/var/lib/postgresql/data`;
  - healthcheck `pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB` (interval 5s, retries 20).
- `clickhouse`:
  - `image: clickhouse/clickhouse-server:24.8`;
  - env `CLICKHOUSE_DB`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1`;
  - `ulimits: nofile: {soft: 262144, hard: 262144}`;
  - volume `ch_data:/var/lib/clickhouse`;
  - healthcheck `wget --spider -q http://localhost:8123/ping || exit 1` (interval 5s, retries 30);
  - порт 8123 наружу публикуется опционально (закомментировать или оставить, по README).
- `backend`:
  - `build: { context: ., args: { INSTALL_DEV: "1" } }` — dev-зависимости в образе, чтобы тесты запускались одной командой; осознанный компромисс тестового задания, указан в README;
  - `env_file: .env`, но compose не должен падать без `.env`: для всех переменных заданы дефолты через `${VAR:-default}` в `environment:`, тогда `docker compose up` работает сразу после clone; `.env.example` служит документацией;
  - `depends_on: postgres: condition: service_healthy, clickhouse: condition: service_healthy`;
  - `ports: ["8000:8000"]`;
  - healthcheck опционален.
- `volumes: pg_data, ch_data`.

**`README.md`** (на русском):
1. Описание и ссылки на `docs/task/` (ТЗ) и `docs/REVIEW_AND_PLAN.md` (допущения).
2. Стек и версии.
3. Быстрый старт: `cp .env.example .env` (опционально), `docker compose up --build`. Что происходит при старте: migrate, init_clickhouse, seed_demo.
4. Демо-пользователи и где взять токены (вывод `seed_demo` в логах; повторно: `docker compose exec backend python manage.py seed_demo`).
5. Контракт API: запрос, формат дат (D1), таблица кодов ответов (D6), пример ответа 201.
6. Примеры curl. Даты: `1735689600` = 2025-01-01, `1738281600` = 2025-01-31:
   - менеджер, Basic:
     `curl -i -u manager:demo12345 -H 'Content-Type: application/json' -d '{"factory":1,"start":1735689600,"finish":1738281600,"weight":1500,"author":<manager_id>}' http://localhost:8000/work-volume-list/`
   - представитель с токеном: `-H 'Authorization: Token <token>'`, свой завод → 201, чужой завод → 404/174;
   - `nobody` → 403/902; без полей → 406/279; `start` не в полночь → 400/901; несуществующий factory → 404/174; чужой `author` → 403/903; без авторизации → 401/900.
7. Как посмотреть записи tsDB: `docker compose exec clickhouse clickhouse-client --user plan --password plan -q "SELECT * FROM plan.work_volume_record ORDER BY created"`.
8. Тесты: `docker compose run --rm --entrypoint "" backend pytest` (требуется запущенный postgres; compose поднимет его по depends_on). Интеграционный тест ClickHouse: `... backend pytest -m clickhouse`.
9. Принятые допущения: краткий список D1–D12 со ссылкой на этот документ. Отдельно перечислить отступления от буквы ТЗ: приоритет менеджера, 400/901 для типов, `created` как datetime, нижний регистр имён пакетов, аутентификация, 404/174 для непривязанного представителя.
10. Ограничения и развитие: outbox для гарантированной доставки в tsDB, пересечения периодов, отказ от 406.

### 3.4 Тесты

Тесты работают с Postgres из compose. ClickHouse подменяется фейковым репозиторием (in-memory список) через `monkeypatch` на `plan.services.get_work_volume_record_repository` (или на точку, откуда его импортирует сервис). Интеграционный тест с реальным ClickHouse помечен `@pytest.mark.clickhouse`.

**`tests/conftest.py`**, фикстуры:
- `api_client`;
- `factory_a`, `factory_b`;
- `rep_user` (группа «Представитель», привязан к `factory_a`);
- `manager_user`, `both_roles_user` (обе группы, без привязки), `nobody_user`;
- `fake_tsdb` (список вставленных DTO);
- `failing_tsdb` (бросает `TsDBUnavailable`);
- `payload(**overrides)` — валидное тело с датами 2025-01-01..2025-01-31.

Группы берутся из data-миграции, не создаются в фикстурах заново: заодно проверяется миграция.

**`tests/test_fields.py`**:
- `StrictIntegerField` отклоняет `True`, `"5"`, `5.0`, `None` и принимает `5`;
- `UnixMidnightDateField`:
  - принимает 0 и `MAX_DATE_TS`;
  - отклоняет −86400, `MAX_DATE_TS + 86400`, `1735689601` (не полночь) и миллисекунды `1735689600000`;
  - круговое преобразование `to_representation(to_internal_value(x)) == x`.

**`tests/test_serializers.py`**:
- `check_required_fields`: пустой `{}` даёт все 5 полей в порядке `REQUIRED_FIELDS`; `null` и `""` считаются незаполненными, а `0` — заполненным;
- `start > finish` → ошибка; `start == finish` → ок; `weight = 0` → ок, `weight = -1` → ошибка;
- лишнее поле игнорируется.

**`tests/test_api_work_volume.py`**. Проверять статус, `errorCode`, а где важно — состояние БД и `fake_tsdb`:
1. Без авторизации → 401, errorCode 900, есть заголовок `WWW-Authenticate`.
2. GET → 405/905.
3. Тело-массив → 400/901; битый JSON → 400/901; `text/plain` → 415/906.
4. `{}` → 406/279, `details.missing` содержит все 5 полей; `{"factory":1,"start":null,...}` → 406/279 с `missing == ["start"]`.
5. Неверные типы (`"factory":"1"`, `"weight":true`) → 400/901.
6. `start > finish`, `weight < 0`, `start` не в полночь → 400/901.
7. Несуществующий factory (любой пользователь, в том числе `nobody`) → 404/174 (порядок D5).
8. `author != request.user.id` → 403/903, в БД и tsDB пусто.
9. `nobody_user` → 403/902.
10. Менеджер, новый период → 201; одна строка WorkVolume; одна запись в `fake_tsdb` с `factory == factory_a.external_id`, `author == manager.pk` и `created == WorkVolume.created`; тело ответа соответствует D6 (`start`/`finish` — целые).
11. Менеджер, тот же период повторно с другим weight → 201; WorkVolume по-прежнему одна, weight обновлён, `created` увеличился; в `fake_tsdb` **две** записи.
12. Менеджер, другой завод (`factory_b`) → 201.
13. Представитель, свой завод → 201; чужой (`factory_b`) → 404/174, в БД и tsDB пусто.
14. Пользователь в обеих группах на непривязанный завод → 201 (приоритет менеджера, D4).
15. Пересекающийся, но не совпадающий период → создаётся вторая строка WorkVolume.
16. `failing_tsdb` → 503/904; в WorkVolume **нет** изменений: ни новой строки, ни обновлённого weight у существующей (rollback, D10).
17. Аутентификация по токену работает (тот же сценарий, что в п. 10, через `Authorization: Token`).
18. Лишнее поле в теле не мешает → 201.

**`tests/test_services.py`**: юнит-тесты `save_work_volume` (ветки прав, upsert, вызов `repo.add` с правильным DTO).

**`tests/test_groups_migration.py`**: после миграций обе группы существуют с точными именами.

**`tests/test_tsdb.py`** (ClickHouse-клиент замокан через `unittest.mock`):
- `ensure_schema()` выполняет `CREATE DATABASE IF NOT EXISTS` и `CREATE TABLE IF NOT EXISTS ... MergeTree`;
- `add()` вызывает `client.insert` с ожидаемыми `column_names` и порядком значений;
- исключение драйвера превращается в `TsDBUnavailable`;
- невалидное имя БД → `ImproperlyConfigured`.

**`tests/test_clickhouse_integration.py`** (`@pytest.mark.clickhouse`): `ensure_schema()`, затем `add()`, затем `SELECT count()` по factory даёт 1. Запускается вручную внутри compose.

### 3.5 Порядок работы генератора

1. Скопировать файлы ТЗ в `docs/task/` байт в байт: `cp`, без правки. Оригиналы в корне не трогать.
2. `requirements*.txt`, `pyproject.toml`, `manage.py`, `backend/*`.
3. `plan/constants.py`, `errors.py`, `fields.py`, `models.py`, затем `makemigrations` (выполнить реально в контейнере или venv, а не писать миграцию руками), затем `0002_create_groups.py`.
4. `tsdb.py`, `services.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`, management-команды.
5. Docker-файлы, `.env.example`, `.gitignore`, `.dockerignore`.
6. Тесты.
7. README.
8. Проверка (обязательно):
   - `docker compose up --build -d`;
   - прогнать curl-сценарии из README;
   - `docker compose run --rm --entrypoint "" backend pytest` — зелёный;
   - `pytest -m clickhouse` — зелёный;
   - `ruff check .` — чисто;
   - `docker compose down -v`.
9. `git init` и первый коммит — только если оркестратор это явно разрешит. Публикация (push) остаётся за пользователем.

---

## 4. Критерии приёмки (чек-лист финального критика)

### Структура и репозиторий
- [ ] Django-проект `backend` и приложение `plan` (соответствие Backend/Plan пояснено в README).
- [ ] Оригиналы ТЗ в корне не изменены (сверить `sha256sum` с `docs/task/*`); копии лежат в `docs/task/`; корневые оригиналы в `.gitignore`; нет коллизии `readme.md`/`README.md` в отслеживаемых файлах.
- [ ] В репозитории нет `.env`, `__pycache__`, секретов, `staticfiles/`.
- [ ] Зависимости зафиксированы; Python 3.12, Django 5.2, DRF, psycopg 3, clickhouse-connect.

### Модели и БД
- [ ] Factory (`external_id` UUID unique), FactoryUser (уникальная пара user+factory), WorkVolume (UniqueConstraint factory+start+finish, Check start<=finish и weight>=0, FK factory PROTECT).
- [ ] Миграции сгенерированы `makemigrations`; `python manage.py makemigrations --check --dry-run` не находит изменений.
- [ ] Data-миграция создаёт обе группы с точными русскими именами, обратима.
- [ ] Таблица ClickHouse `work_volume_record` (MergeTree, колонки по D9) создаётся `init_clickhouse` идемпотентно; повторный запуск не падает.

### API (сверка с `V_b_24.puml` и D5/D6)
- [ ] Путь ровно `POST /work-volume-list/`.
- [ ] Порядок проверок соответствует D5: 401 → 400/415 (тело) → 406/279 → 400/901 → 404/174 → 403/903 → 403/902 или 404/174 → 201/503.
- [ ] Все ошибки имеют формат `{"errorCode": int, "message": str, "details": object}`.
- [ ] 406/279 возвращается для отсутствующих, `null` и `""` полей, `details.missing` перечисляет их.
- [ ] Строковые, bool и float значения отклоняются (400/901); `start` не в полночь UTC и миллисекундные timestamp отклоняются.
- [ ] Менеджер: 201 для любого существующего ЗМК. Представитель: 201 только для привязанного ЗМК, иначе 404/174. Без групп: 403/902. Обе группы: права менеджера.
- [ ] Повторный POST того же `(factory,start,finish)` обновляет weight и created и не создаёт дубль в Postgres; в ClickHouse при этом добавляется новая запись.
- [ ] В ClickHouse пишется `factory = external_id` (UUID), `author = request.user.id`, `created` совпадает с `WorkVolume.created`.
- [ ] При недоступности ClickHouse ответ 503/904, а Postgres не изменился (rollback).
- [ ] Ответ 201 соответствует D6, `start`/`finish` — целые timestamp.

### Код
- [ ] Бизнес-логика в `services.py`, view тонкий; ClickHouse изолирован в `tsdb.py` за репозиторием.
- [ ] Upsert атомарный (`ON CONFLICT`), без гонки select→insert.
- [ ] Нет SQL-инъекций: имя БД ClickHouse валидируется, значения передаются через `insert`, а не через f-строку в SQL.
- [ ] `SECRET_KEY`/пароли берутся из env; `DEBUG` по умолчанию выключен.
- [ ] `ruff check .` проходит.

### Docker
- [ ] `docker compose up --build` на чистой машине (без `.env`) поднимает все 3 сервиса; backend стартует после healthy postgres и clickhouse; entrypoint выполняет migrate, init_clickhouse, seed_demo.
- [ ] Контейнер backend работает не от root, запущен через gunicorn; админка открывается со статикой.
- [ ] Данные сохраняются в именованных volumes.

### Тесты
- [ ] `docker compose run --rm --entrypoint "" backend pytest` — все тесты зелёные; покрыты все сценарии из п. 3.4 (как минимум 1–18 из `test_api_work_volume.py`).
- [ ] ClickHouse в юнит/API-тестах замокан; интеграционный тест помечен маркером и проходит в compose.

### README
- [ ] Инструкция запуска в 1–2 команды, демо-учётки и токены, curl-примеры на каждый код ответа, команда просмотра записей ClickHouse, команда запуска тестов.
- [ ] Перечислены все допущения и отступления от ТЗ со ссылкой на `docs/REVIEW_AND_PLAN.md`.
