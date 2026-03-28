FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/

RUN pip install --no-cache-dir .

RUN mkdir -p /data

ENV LOGBOOK_DB_PATH=/data/logbook.db
ENV LOGBOOK_HOST=0.0.0.0
ENV LOGBOOK_PORT=8000

EXPOSE 8000

CMD alembic upgrade head && \
    uvicorn logbook.main:app --host $LOGBOOK_HOST --port $LOGBOOK_PORT
