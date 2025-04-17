# Webhook Monitor

A FastAPI + Celery + Kafka application for receiving, processing, and monitoring webhooks.

## Features

- FastAPI endpoint for receiving webhooks
- HMAC signature verification
- Celery worker for async processing with retries
- Kafka integration for event streaming and DLQ
- SQLAlchemy/Postgres for persistence

## Setup

1. Clone the repo
2. Copy `.env.example` to `.env` and fill in your secrets and DB/Kafka config
3. Start services:
   ```sh
   docker-compose up --build
   ```
4. Run tests:
   ```sh
   python tests/send_webhook_test.py
   ```

## Usage

- POST `/webhook` to send a webhook event
- POST `/customers` to create a customer and get a webhook secret

## Architecture

- FastAPI for HTTP API
- Celery for background processing
- Kafka for event streaming and DLQ
- PostgreSQL for data storage

## Environment Variables

- `DATABASE_URL`
- `KAFKA_BROKER`
- `WEBHOOK_SECRET` (for tests)
- `ENV` (set to `production` in prod)

---

**Summary:**  
Add this (and expand as needed) to your `README.md` for better maintainability and onboarding.

Let me know when you’re ready for the next task!# Webhook Monitor

A FastAPI + Celery + Kafka application for receiving, processing, and monitoring webhooks.

## Features

- FastAPI endpoint for receiving webhooks
- HMAC signature verification
- Celery worker for async processing with retries
- Kafka integration for event streaming and DLQ
- SQLAlchemy/Postgres for persistence

## Setup

1. Clone the repo
2. Copy `.env.example` to `.env` and fill in your secrets and DB/Kafka config
3. Start services:
   ```sh
   docker-compose up --build
   ```
4. Run tests:
   ```sh
   python tests/send_webhook_test.py
   ```

## Usage

- POST `/webhook` to send a webhook event
- POST `/customers` to create a customer and get a webhook secret

## Architecture

- FastAPI for HTTP API
- Celery for background processing
- Kafka for event streaming and DLQ
- PostgreSQL for data storage

## Environment Variables

- `DATABASE_URL`
- `KAFKA_BROKER`
- `WEBHOOK_SECRET` (for tests)
- `ENV` (set to `production` in prod)

---


