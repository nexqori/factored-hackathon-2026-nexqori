FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /lab
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10002 --create-home lab
COPY lab ./lab
COPY migrations ./migrations
COPY alembic.ini .
COPY tests ./tests
USER lab
