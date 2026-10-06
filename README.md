# Сохранить объём работ (Backend / Plan)

Реализация use case «Сохранить объём работ» (`POST /work-volume-list/`) из тестового задания.

- Исходное ТЗ: [`docs/task/`](docs/task/) (readme, C4, ER, use case, sequence, JSON-схема).
- Ревью ТЗ и принятые решения D1-D12: [`docs/REVIEW_AND_PLAN.md`](docs/REVIEW_AND_PLAN.md).

Соответствие имён: Django-проект **Backend** -> пакет `backend`, приложение **Plan** -> `plan` (нижний регистр по PEP 8).

## Стек

Python 3.12, Django 5.2 LTS, Django REST Framework 3.16, PostgreSQL 16 (taDB), ClickHouse 24.8 (tsDB, драйвер `clickhouse-connect`), gunicorn, whitenoise.

## Быстрый старт

```bash
cp .env.example .env   # необязательно: те же значения по умолчанию есть в docker-compose.yml
docker compose up --build
```

При старте backend выполняет `migrate`, `init_clickhouse` (создание БД и таблицы `plan.work_volume_record`, идемпотентно) и, если `SEED_DEMO=1`, `seed_demo`. API доступно на `http://localhost:8000` (порт меняется переменной `BACKEND_PORT`).

> `SEED_DEMO=1` создаёт пользователей с известным паролем. Только для демо!

## Демо-пользователи

`seed_demo` создаёт ЗМК «ЗМК Север» и «ЗМК Юг» и пользователей (пароль `DEMO_PASSWORD`, по умолчанию `demo12345`):

| username | группа | доступ |
|----------|--------|--------|
| `rep` | Представитель ЗМК | привязан к «ЗМК Север» |
| `manager` | Менеджер по взаимодействию с ЗМК | любой ЗМК |
| `nobody` | нет | запрещено |

Команда печатает таблицу `username / user_id / token / factory ids` (смотрите логи `docker compose logs backend`). Повторно:
`docker compose exec backend python manage.py seed_demo`.

## Контракт API

`POST /work-volume-list/`, `Content-Type: application/json`, аутентификация Basic, `Authorization: Token <token>` или сессия.

```json
{"factory": 1, "start": 1735689600, "finish": 1738281600, "weight": 1500, "author": 2}
```

- `factory` - `Factory.id` (в ClickHouse пишется `Factory.external_id`).
- `start`, `finish` - Unix timestamp в **секундах** ровно на полночь UTC, диапазон `0..5662224000` (1970-01-01..2149-06-06, диапазон `Date` ClickHouse).
- `weight` - `0..2147483647`, кг. `author` - должен совпадать с id аутентифицированного пользователя.
- Все поля - строго JSON-целые (строки, bool, float отклоняются). Лишние поля игнорируются.
- «Тот же период» - точное совпадение `(factory, start, finish)`: тогда обновляются `weight` и `created`, иначе создаётся новая запись. В ClickHouse каждый раз добавляется новая запись (журнал).

Ответ 201 (и при создании, и при обновлении):

```json
{"id": 12, "factory": 1, "start": 1735689600, "finish": 1738281600, "weight": 1500, "created": "2026-10-06T10:15:00.123456Z"}
```

Любая ошибка: `{"errorCode": <int>, "message": "<str>", "details": {...}}`.

| HTTP | errorCode | Когда |
|------|-----------|-------|
| 201 | - | создано или обновлено |
| 400 | 901 | невалидный JSON, тело не объект, неверный тип или значение |
| 401 | 900 | нет или неверные учётные данные |
| 403 | 902 | пользователь не в разрешённой группе |
| 403 | 903 | `author` не совпадает с пользователем |
| 404 | 174 | ЗМК не существует, либо представитель не привязан к ЗМК |
| 405 | 905 | метод не POST |
| 406 | 279 | не заполнены обязательные поля (`details.missing`) |
| 406 | 907 | неподходящий `Accept` |
| 415 | 906 | Content-Type не JSON |
| 503 | 904 | ClickHouse недоступен, изменения в Postgres откатены |

Порядок проверок: аутентификация -> тело (400/415) -> заполненность (406/279) -> типы и значения (400/901) -> существование ЗМК (404/174) -> author (403/903) -> группы и привязка (403/902, 404/174) -> сохранение (201/503).

## Примеры curl

Подставьте `<manager_id>`, `<rep_id>`, `<token>` из вывода `seed_demo`. Даты: `1735689600` = 2025-01-01, `1738281600` = 2025-01-31.

```bash
URL=http://localhost:8000/work-volume-list/
H='Content-Type: application/json'

# 201: менеджер (Basic)
curl -i -u manager:demo12345 -H "$H" -d '{"factory":1,"start":1735689600,"finish":1738281600,"weight":1500,"author":<manager_id>}' $URL

# 201: повтор того же периода - обновление weight и created
curl -i -u manager:demo12345 -H "$H" -d '{"factory":1,"start":1735689600,"finish":1738281600,"weight":1700,"author":<manager_id>}' $URL

# 201: представитель по токену, свой завод; 404/174: чужой завод (factory=2)
curl -i -H 'Authorization: Token <token>' -H "$H" -d '{"factory":1,"start":1735689600,"finish":1738281600,"weight":10,"author":<rep_id>}' $URL
curl -i -H 'Authorization: Token <token>' -H "$H" -d '{"factory":2,"start":1735689600,"finish":1738281600,"weight":10,"author":<rep_id>}' $URL

# 406/279: не заполнены поля
curl -i -u manager:demo12345 -H "$H" -d '{"factory":1}' $URL

# 404/174: несуществующий ЗМК
curl -i -u manager:demo12345 -H "$H" -d '{"factory":999,"start":1735689600,"finish":1738281600,"weight":1,"author":<manager_id>}' $URL

# 400/901: start не в полночь UTC
curl -i -u manager:demo12345 -H "$H" -d '{"factory":1,"start":1735689601,"finish":1738281600,"weight":1,"author":<manager_id>}' $URL

# 403/903: чужой author
curl -i -u manager:demo12345 -H "$H" -d '{"factory":1,"start":1735689600,"finish":1738281600,"weight":1,"author":999}' $URL

# 403/902: пользователь без групп
curl -i -u nobody:demo12345 -H "$H" -d '{"factory":1,"start":1735689600,"finish":1738281600,"weight":1,"author":<nobody_id>}' $URL

# 401/900: без авторизации
curl -i -H "$H" -d '{}' $URL
```

## Записи в ClickHouse

```bash
docker compose exec clickhouse clickhouse-client --user plan --password plan -q "SELECT * FROM plan.work_volume_record ORDER BY created"
```

## Тесты

```bash
docker compose run --rm --entrypoint "" backend pytest            # ClickHouse подменён заглушкой
docker compose run --rm --entrypoint "" backend pytest -m clickhouse   # интеграционный, нужен ClickHouse
```

Postgres поднимается по `depends_on`. Образ собирается с dev-зависимостями (`INSTALL_DEV=1`) - осознанный компромисс тестового задания. Без Postgres тесты можно запустить локально на SQLite: `DJANGO_DB_ENGINE=sqlite DJANGO_DEBUG=1 pytest`.

## Принятые допущения и отступления от ТЗ

Подробно в [`docs/REVIEW_AND_PLAN.md`](docs/REVIEW_AND_PLAN.md) (D1-D12). Кратко:

- Добавлена аутентификация; права проверяются для `request.user`, `author` обязан совпадать с ним (D3).
- Пользователь в обеих группах получает права менеджера (D4) - отступление от буквального порядка `alt`.
- «ЗМК не существует» для непривязанного представителя трактуется как «не существует для этого пользователя» (404/174).
- Неверные типы и значения - 400/901, а не 406; 406/279 только для незаполненных полей. Коды 900-907, 999 придуманы нами.
- Порядок проверок по диаграмме: существование ЗМК проверяется до групп, поэтому пользователь без групп может узнать, существует ли ЗМК (404 против 403).
- `created` - `DateTimeField` (UTC), перезаписывается при обновлении, по смыслу это «время последнего сохранения».
- Postgres и ClickHouse: upsert в Postgres внутри транзакции -> вставка в ClickHouse -> commit. При сбое ClickHouse - откат и 503. Остаточный риск: ClickHouse записал, а commit упал - в журнале останется лишняя запись.
- `SECRET_KEY` обязателен при `DJANGO_DEBUG=0`.

## Ограничения и развитие

- Transactional outbox для гарантированной доставки в tsDB.
- Правила для пересекающихся периодов.
- Пересмотр кода 406 для незаполненных полей (семантически корректнее 400/422).
