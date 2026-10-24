FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .
COPY --chmod=755 docker-entrypoint.sh /docker-entrypoint.sh
RUN mkdir -p uploads llm_logs && chown -R app:app /app
EXPOSE 8000

# Bind-mounted source and hot reload are only used by the development stack.
FROM runtime AS development
ENV UVICORN_RELOAD=true
CMD ["/docker-entrypoint.sh"]

FROM runtime AS production
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
