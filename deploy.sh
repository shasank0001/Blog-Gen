#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
export BLOG_GEN_ENV_FILE="${BLOG_GEN_ENV_FILE:-$ROOT/.env.production}"
export BLOG_GEN_PROJECT_NAME="${BLOG_GEN_PROJECT_NAME:-blog-gen-production}"

die() { echo "$*" >&2; exit 1; }
command -v docker >/dev/null || die 'Install Docker Engine/Desktop and its Compose plugin first.'
docker compose version >/dev/null 2>&1 || die 'Docker Compose v2 is required (docker compose).'
docker info >/dev/null 2>&1 || die 'Docker is not running or your user cannot access it.'

compose() {
    docker compose --env-file "$BLOG_GEN_ENV_FILE" --project-name "$BLOG_GEN_PROJECT_NAME" -f "$ROOT/compose.production.yml" "$@"
}

config_check() {
    [ -f "$BLOG_GEN_ENV_FILE" ] || die 'Run ./deploy.sh init first.'
    # Do not dump resolved configuration: it contains secrets.
    compose config --quiet
}

backup() (
    config_check
    local destination="${1:-$ROOT/backups/$(date -u +%Y%m%dT%H%M%SZ)}"
    case "$destination" in /*) ;; *) destination="$ROOT/$destination" ;; esac
    mkdir -p "$(dirname -- "$destination")"
    mkdir "$destination" || die 'Use a new backup directory; existing backups are never overwritten.'
    local running=()
    for service in backend worker; do
        if [ -n "$(compose ps --status running -q "$service")" ]; then running+=("$service"); fi
    done
    # Pause all writers so the database and uploaded originals are coherent.
    trap 'if [ "${#running[@]}" -gt 0 ]; then compose start "${running[@]}" >/dev/null; fi' EXIT
    if [ "${#running[@]}" -gt 0 ]; then compose stop "${running[@]}"; fi
    compose exec -T db pg_dump -U blog_gen -d blog_gen --format=custom > "$destination/database.dump"
    compose run --rm --no-deps -T backend tar -czf - -C /app uploads > "$destination/uploads.tar.gz"
    [ -s "$destination/database.dump" ] && [ -s "$destination/uploads.tar.gz" ]
    compose exec -T db pg_restore --list < "$destination/database.dump" >/dev/null
    printf '%s\n' 'Blog-Gen database + uploads. Copy the deployment env file separately through a secure channel.' > "$destination/COMPLETE"
    echo "Backup complete: $destination"
)

case "${1:-help}" in
    init)
        [ ! -e "$BLOG_GEN_ENV_FILE" ] || die 'The env file already exists. It was not changed.'
        env_dir="$(cd -- "$(dirname -- "$BLOG_GEN_ENV_FILE")" && pwd)"
        docker run --rm --user "$(id -u):$(id -g)" \
            -v "$ROOT:/workspace:ro" -v "$env_dir:/config" -w /workspace python:3.11-slim \
            python scripts/init_deploy.py --output "/config/$(basename -- "$BLOG_GEN_ENV_FILE")"
        ;;
    check)
        config_check
        compose build backend
        compose run --rm --no-deps -T backend python -m app.deployment_check
        ;;
    up)
        config_check
        compose build backend frontend
        compose run --rm --no-deps -T backend python -m app.deployment_check
        # Re-run migrations every release with writers stopped. Build/preflight
        # failures leave the previous deployment running.
        compose stop frontend worker backend
        compose rm -f migrate
        compose up -d --wait --wait-timeout 180
        compose ps
        echo 'Ready. Local preview: http://localhost:8080 (or the address/ports set in the env file).'
        echo 'Create your account with: ./deploy.sh create-user you@example.com'
        ;;
    down) config_check; compose down ;;
    status) config_check; compose ps ;;
    logs) config_check; shift; compose logs --follow --tail=100 "$@" ;;
    backup) shift; backup "$@" ;;
    create-user)
        config_check
        [ "$#" -eq 2 ] || die 'Usage: ./deploy.sh create-user you@example.com'
        compose exec backend python -m app.manage "$2"
        ;;
    *)
        echo 'Usage: ./deploy.sh {init|check|up|down|status|logs [service]|backup [new-directory]|create-user EMAIL}'
        ;;
esac
