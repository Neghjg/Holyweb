FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
ARG INSTALL_DEV=0
WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN if [ "$INSTALL_DEV" = "1" ]; then pip install -r requirements-dev.txt; else pip install -r requirements.txt; fi

COPY . .
RUN chmod +x /app/docker/entrypoint.sh \
    && DJANGO_SECRET_KEY=build DJANGO_DEBUG=0 python manage.py collectstatic --noinput \
    && useradd --create-home app && chown -R app:app /app
USER app

EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
