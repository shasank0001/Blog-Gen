#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0

while ! nc -z db 5432; do
    attempt=$((attempt + 1))
    if [ $attempt -eq $max_attempts ]; then
        echo "ERROR: PostgreSQL not ready after $max_attempts attempts"
        exit 1
    fi
    echo "Waiting for database... ($attempt/$max_attempts)"
    sleep 1
done

echo "PostgreSQL is ready!"

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the application
echo "Starting uvicorn server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
