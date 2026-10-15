FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY pytest.ini .

EXPOSE 8000

# api: sobreeescrito en compose (uvicorn). worker: python -m app.workers.main
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
