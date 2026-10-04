# Image for the Musnid Django application.
# Python version rationale: docs/architecture/decisions/0001-python-3-12.md
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first so code changes do not invalidate this layer.
# --only-binary keeps the image free of compilers: every pin ships a wheel.
COPY requirements.txt .
RUN pip install --only-binary=:all: -r requirements.txt

COPY . .

# Settings require these variables at import time. collectstatic touches
# neither the secret nor the database, so throwaway values are enough; they
# are scoped to this RUN and never stored in the image environment.
RUN DJANGO_SECRET_KEY=collectstatic-build-only \
    POSTGRES_DB=unused POSTGRES_USER=unused POSTGRES_PASSWORD=unused \
    python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
