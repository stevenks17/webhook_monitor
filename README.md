# Webhook Monitor

A FastAPI + Celery + Kafka application for receiving, processing, and monitoring webhooks.

## Features

- FastAPI endpoint for receiving webhooks and verifying HMAC signatures
- Kafka integration for event streaming and main processing
- Celery worker for handling processing failures and retries, with DLQ support
- SQLAlchemy/Postgres for persistence and audit logging
- Prometheus/Grafana monitoring for performance and health metrics

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

- **POST `/webhook`**  
  Send a webhook event. The endpoint will verify the HMAC, record the event, and asynchronously enqueue the task via Celery (with sharding across multiple queues).

- **POST `/customers`**  
  Create a customer and get a webhook secret.

- **GET `/webhooks`**  
  Retrieve processed webhook events for a customer.

## Architecture

- **FastAPI**: Handles HTTP API requests and webhook validation.
- **Celery**: Processes webhook tasks asynchronously, with built-in retries and DLQ (Dead Letter Queue) handling.
- **Kafka**: Streams events downstream and handles failed events via DLQ.
- **PostgreSQL**: Stores webhook events, audit logs, and customer data.
- **Prometheus & Grafana**: Monitor application metrics including processing latency, success/failure counts, and overall throughput.

## Environment Variables

Ensure your `.env` file (or environment configuration) contains:

- `DATABASE_URL` – PostgreSQL connection string.
- `KAFKA_BROKER` – Kafka broker address.
- `WEBHOOK_SECRET` – Default webhook secret (used for tests).
- `ENV` – Set to `production` in production environments.
- Additional variables as needed for RabbitMQ, Prometheus (`RUN_PROM_METRICS`), and Celery.

## Database Migrations / Seeding

- Run any required migrations using your migration tool (e.g., Alembic) or execute the provided seed scripts to populate customer data and test records.

## Monitoring & Troubleshooting

- **Prometheus Metrics**:  
  Metrics are exposed on `/metrics` endpoints (configured to work with Prometheus multiprocess mode).  
  Check Prometheus at [http://localhost:9090](http://localhost:9090) and Grafana dashboards for detailed performance data.

- **Troubleshooting**:  
  - Verify that environment variables match in the backend and Celery worker.
  - Use `docker-compose logs` to check for errors in Celery, FastAPI, or Kafka.
  - If tasks are retried or sent to the DLQ unexpectedly, review your HMAC verification and database logs.
  - Validate YAML configurations with `docker-compose config`.

## Testing

- The tests include scenarios for successful webhook processing and task failure handling (DLQ behavior).  
- To run tests:
  ```sh
  pytest
  ```
- Example test files include:  
  - `tests/send_webhook_test.py`
  - `tests/task_failure_test.py`

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [Prometheus Client Python](https://github.com/prometheus/client_python)
- [Grafana Documentation](https://grafana.com/docs/)

---

Happy monitoring!


