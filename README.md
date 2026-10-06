# Сохранить объём работ (Backend / Plan)

Реализация use case «Сохранить объём работ» (`POST /work-volume-list/`) из тестового задания.

- Исходное ТЗ: [`docs/task/`](docs/task/) (readme, C4, ER, use case, sequence, JSON-схема).
- Допущения и трактовки ТЗ, ограничения и коды ошибок описаны ниже в этом README.

Соответствие имён: Django-проект **Backend** -> пакет `backend`, приложение **Plan** -> `plan` (нижний регистр по PEP 8).

## Стек

Python 3.12, Django 5.2 LTS, Django REST Framework 3.16, PostgreSQL 16 (taDB), ClickHouse 24.8 (tsDB, драйвер `clickhouse-connect`), gunicorn, whitenoise.

## Быстрый старт

```bash
docker compose up -d --build
```

`.env` не нужен: по умолчанию compose запускается в **демо-конфигурации**: `DJANGO_DEBUG=1`, `SEED_DEMO=1` (демо-пользователи с известным паролем `demo12345`) и встроенный dev-ключ `DJANGO_SECRET_KEY`. Это небезопасно для реальной среды. Для prod-подобного запуска создайте `.env` из шаблона и задайте свои значения: `DJANGO_DEBUG=0`, собственный случайный `DJANGO_SECRET_KEY` (например, `python3 -c "import secrets; print(secrets.token_hex(32))"`), `SEED_DEMO=0`:

```bash
cp .env.example .env   # затем впишите свой DJANGO_SECRET_KEY
docker compose up -d --build
```

При `DJANGO_DEBUG=0` приложение не стартует без собственного ключа (dev-ключ отвергается с `ImproperlyConfigured`).

При старте backend выполняет `migrate`, `init_clickhouse` (создание БД и таблицы `plan.work_volume_record`, идемпотентно) и, если `SEED_DEMO=1`, `seed_demo`. API доступно на `http://127.0.0.1:8000`. Порт публикуется только на loopback; хост и порт меняются переменными `BACKEND_HOST` и `BACKEND_PORT` (например, `BACKEND_HOST=0.0.0.0`, если нужен доступ из сети).

> `seed_demo` создаёт пользователей с **известным паролем** (`demo12345`), только для демо. Он создаёт лишь отсутствующих пользователей и не сбрасывает пароли и группы существующих.

Админка (`/admin/`): `docker compose exec backend python manage.py createsuperuser`. Суперпользователь прав на use case не получает, права определяются только группами.

## Демо-пользователи

`seed_demo` создаёт ЗМК «ЗМК Север» и «ЗМК Юг» и пользователей (пароль `DEMO_PASSWORD`, по умолчанию `demo12345`):

| username | группа | доступ |
|----------|--------|--------|
| `rep` | Представитель ЗМК | привязан к «ЗМК Север» |
| `manager` | Менеджер по взаимодействию с ЗМК | любой ЗМК |
| `nobody` | нет | запрещено |

Команда печатает таблицу `username / user_id / token / factory ids` (смотрите логи `docker compose logs backend`). Повторно (идемпотентно, уже существующих пользователей не меняет):
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
| 403 | 908 | прочий отказ в доступе, например CSRF при сессионной аутентификации |
| 404 | 174 | ЗМК не существует, либо представитель не привязан к ЗМК |
| 404 | 909 | неизвестный URL (JSON-тело вместо HTML; при `DJANGO_DEBUG=1` Django показывает свою отладочную страницу) |
| 405 | 905 | метод не POST |
| 406 | 279 | не заполнены обязательные поля (`details.missing`) |
| 406 | 907 | неподходящий `Accept` (проверяется после аутентификации) |
| 415 | 906 | Content-Type не JSON |
| 500 | 999 | необработанная внутренняя ошибка (тоже в JSON-формате) |
| 503 | 904 | ClickHouse недоступен, изменения в Postgres откатены |

Путь `/work-volume-list/` принимается и без завершающего слэша. Сообщения об ошибках на английском.

Порядок проверок: аутентификация -> тело (400/415) -> заполненность (406/279) -> типы и значения (400/901) -> author (403/903) -> существование ЗМК (404/174) -> группы и привязка (403/902, 404/174) -> сохранение (201/503). Проверка `author` стоит до поиска ЗМК намеренно: иначе по разнице 403/404 можно было бы выяснить, какие ЗМК существуют.

## Примеры curl

Подставьте `<manager_id>`, `<rep_id>`, `<nobody_id>` (id пользователей `manager`, `rep`, `nobody`) и `<token>` (токен пользователя `rep`) из вывода `seed_demo` (`docker compose logs backend`). Даты: `1735689600` = 2025-01-01, `1738281600` = 2025-01-31.

```bash
URL=http://127.0.0.1:8000/work-volume-list/
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

# 400/901: неверный тип (строка вместо числа), битый JSON, тело-массив
curl -i -u manager:demo12345 -H "$H" -d '{"factory":"1","start":1735689600,"finish":1738281600,"weight":1,"author":<manager_id>}' $URL
curl -i -u manager:demo12345 -H "$H" -d '{bad' $URL
curl -i -u manager:demo12345 -H "$H" -d '[1,2]' $URL

# 405/905: не POST; 415/906: не JSON; 406/907: неподходящий Accept
curl -i -u manager:demo12345 $URL
curl -i -u manager:demo12345 -H 'Content-Type: text/plain' -d 'x' $URL
curl -i -u manager:demo12345 -H "$H" -H 'Accept: application/xml' -d '{}' $URL

# 503/904: ClickHouse недоступен (изменения в Postgres откатываются)
docker compose stop clickhouse
curl -i -u manager:demo12345 -H "$H" -d '{"factory":1,"start":1735689600,"finish":1738281600,"weight":1,"author":<manager_id>}' $URL
docker compose start clickhouse
```

Если ClickHouse не отвечает (завис), клиент ClickHouse обрывает запрос по таймаутам `CLICKHOUSE_CONNECT_TIMEOUT` (5 с) и `CLICKHOUSE_SEND_RECEIVE_TIMEOUT` (10 с), и ответ тоже 503/904. Сумма заметно меньше `--timeout 30` у gunicorn.

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

- Добавлена аутентификация; права проверяются для `request.user`, `author` обязан совпадать с ним, иначе подменой `author` можно обойти проверку прав.
- `factory` - это `Factory.id`; в ClickHouse пишется `Factory.external_id` (uuid из ER).
- `start`/`finish` - Unix-время в секундах строго на полночь UTC (иначе 400/901); в БД хранятся как даты.
- Пользователь в обеих группах получает права менеджера - отступление от буквального порядка `alt` на диаграмме.
- «ЗМК не существует» для непривязанного представителя трактуется как «не существует для этого пользователя» (404/174), чужие ЗМК не раскрываются. Для этого `author` проверяется до поиска ЗМК. Пользователь без групп всё же может отличить существующий ЗМК (403/902) от несуществующего (404/174): так требует порядок диаграммы.
- Неверные типы и значения - 400/901, а не 406; 406/279 только для незаполненных полей. Коды 900-909 и 999 придуманы нами, ТЗ задаёт только 174 и 279.
- `created` - `DateTimeField` (UTC), а не дата, как в ER; перезаписывается при обновлении, по смыслу это «время последнего сохранения».
- Postgres и ClickHouse: upsert в Postgres внутри транзакции -> вставка в ClickHouse -> commit. При сбое ClickHouse - откат и 503. Ошибки ClickHouse-клиента и сети дают 503/904; программные ошибки - 500/999.
- Права на use case определяются только группами (суперпользователь без групп получает 403/902). `WorkVolume` в админке доступен только для чтения: записи создаются через API, который пишет и в ClickHouse. `Factory` и `FactoryUser` в админке редактируются.
- Секретный ключ: при `DJANGO_DEBUG=1` допускается встроенный dev-ключ (демо и тесты), при `DJANGO_DEBUG=0` нужен собственный ключ.
- Язык сообщений API - английский (`LANGUAGE_CODE=en-us`); имена групп и демо-данные остаются русскими, как в ТЗ.

## Ограничения и развитие

Известные ограничения (сознательно не исправлены):

- Нет распределённой транзакции Postgres + ClickHouse. Возможны два рассогласования: (1) ClickHouse записал, а `COMMIT` в Postgres упал; (2) вставка в ClickHouse дошла до сервера, но ответ потерян или истёк таймаут: клиент получает 503, Postgres откатан, а в ClickHouse запись уже есть (фантомная). Короткие таймауты делают второй случай вероятнее. Журнал append-only, повтор запроса безопасен для Postgres (upsert), но в ClickHouse появится дубль. Лечится transactional outbox или дедупликацией (`insert_deduplication_token`, `ReplacingMergeTree`).
- `created` берётся в приложении до захвата блокировки строки, поэтому при гонке двух запросов на один период теоретически возможна инверсия порядка `created` между Postgres и ClickHouse (окно в микросекунды, на практике не воспроизводилось).
- Блокировка строки `WorkVolume` удерживается на время вставки в ClickHouse (до 15 с при зависшем ClickHouse); запросы с тем же ключом ждут.
- Образ собирается с dev-зависимостями (`INSTALL_DEV=1`) ради запуска тестов одной командой.
- Зависимости зафиксированы до patch-версии, но без lock-файла с хэшами и транзитивными пакетами.

Развитие:

- Transactional outbox для гарантированной доставки в tsDB.
- Правила для пересекающихся периодов.
- Пересмотр кода 406 для незаполненных полей (семантически корректнее 400/422).
