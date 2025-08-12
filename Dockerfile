FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# add git so pip can install VCS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY app app

RUN python3 -m pip install --upgrade pip && \
    pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]