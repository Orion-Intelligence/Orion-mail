#!/bin/bash
set -e
set -o pipefail

cd "$(dirname "$0")"

PROJECT_NAME="orion-mail"
ENV_FILE=".env"
DOMAIN="mail.orionintelligence.org"
WEB_CONTAINER="orion-mail-web"
NGINX_CONTAINER="orion-mail-nginx"
EDGE_CONTAINER="trusted-web-nginx"
MAINTENANCE_FLAG="backend/static/.maintenance"
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"
COMPOSE_FILE="docker-compose.yml"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-180}"

usage() {
    cat <<'USAGE'
Usage: ./run.sh <command>
  build -d            Development: API + Mongo in Docker, mail via the host Postfix (run `npm start` in client/ separately)
  build -t            Testing:     Istanbul-instrumented client + dev stack, for Cypress coverage runs
  build -p [-full]    Production:  build client + image, (re)start stack behind nginx on :80/:443
  production          Production:  restart the stack without rebuilding
  cert                Production:  one-time Let's Encrypt issuance for mail.orionintelligence.org
  renew               Production:  renew the certificate and reload nginx (cron-friendly)
  lint [fix]          Lint client (eslint + stylelint) and backend (pyflakes + bandit); fix applies automatic fixes first
  test [-c]           Run the backend test suite (pytest); -c also writes backend/coverage.xml
  logs [service]      Tail logs of the running stack
  backup [dir]        Dump MongoDB + attachments to a timestamped archive (default: ./backups)
  restore <archive>   Restore MongoDB + attachments from a backup archive (destructive)
  perms               Recreate the runtime directories and reset their ownership to APP_UID:APP_GID
  stop                Stop everything
USAGE
    exit 1
}

mongo_container() {
    docker ps --format '{{.Names}}' | grep -E "^${PROJECT_NAME}-mongodb$" | head -1
}

load_mongo_credentials() {
    MONGO_ROOT_USERNAME=$(sed -n 's/^MONGO_ROOT_USERNAME=//p' "$ENV_FILE" | tail -1 | tr -d '\042\047')
    MONGO_ROOT_PASSWORD=$(sed -n 's/^MONGO_ROOT_PASSWORD=//p' "$ENV_FILE" | tail -1 | tr -d '\042\047')
    if [ -z "$MONGO_ROOT_USERNAME" ] || [ -z "$MONGO_ROOT_PASSWORD" ]; then
        echo "MONGO_ROOT_USERNAME/MONGO_ROOT_PASSWORD are missing from $ENV_FILE" >&2
        exit 1
    fi
}

backup_data() {
    local target_dir="$1"
    load_mongo_credentials
    local stamp
    stamp="$(date +%Y%m%d-%H%M%S)"
    local container
    container="$(mongo_container)"
    if [ -z "$container" ]; then
        echo "MongoDB container ${PROJECT_NAME}-mongodb is not running. Start the stack first." >&2
        exit 1
    fi

    mkdir -p "$target_dir"
    local staging="$target_dir/orion-mail-$stamp"
    mkdir -p "$staging"

    echo "Dumping MongoDB..."
    docker exec "$container" mongodump --username "$MONGO_ROOT_USERNAME" --password "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin --archive=/tmp/orion-mail.archive --gzip >/dev/null
    docker cp "$container:/tmp/orion-mail.archive" "$staging/mongo.archive.gz"
    docker exec "$container" rm -f /tmp/orion-mail.archive

    echo "Archiving attachments..."
    tar -czf "$staging/attachments.tar.gz" -C backend/static/resource attachments 2>/dev/null || tar -czf "$staging/attachments.tar.gz" -T /dev/null

    tar -czf "$target_dir/orion-mail-$stamp.tar.gz" -C "$target_dir" "orion-mail-$stamp"
    rm -rf "$staging"
    echo "Backup written to $target_dir/orion-mail-$stamp.tar.gz"
}

restore_data() {
    local archive="$1"
    load_mongo_credentials
    if [ -z "$archive" ] || [ ! -f "$archive" ]; then
        echo "Usage: ./run.sh restore <archive.tar.gz>" >&2
        exit 1
    fi

    local container
    container="$(mongo_container)"
    if [ -z "$container" ]; then
        echo "MongoDB container ${PROJECT_NAME}-mongodb is not running. Start the stack first." >&2
        exit 1
    fi

    printf 'This overwrites the current database and attachments. Continue? [y/N] '
    read -r confirmation
    case "$confirmation" in
        y|Y) ;;
        *) echo "Restore cancelled"; exit 1 ;;
    esac

    local staging
    staging="$(mktemp -d)"
    tar -xzf "$archive" -C "$staging"
    local payload
    payload="$(find "$staging" -maxdepth 1 -mindepth 1 -type d | head -1)"

    echo "Restoring MongoDB..."
    docker cp "$payload/mongo.archive.gz" "$container:/tmp/orion-mail.archive"
    docker exec "$container" mongorestore --username "$MONGO_ROOT_USERNAME" --password "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin --archive=/tmp/orion-mail.archive --gzip --drop >/dev/null
    docker exec "$container" rm -f /tmp/orion-mail.archive

    if [ -f "$payload/attachments.tar.gz" ]; then
        echo "Restoring attachments..."
        mkdir -p backend/static/resource
        tar -xzf "$payload/attachments.tar.gz" -C backend/static/resource
        ensure_runtime_dirs
    fi

    rm -rf "$staging"
    echo "Restore complete"
}

compose() {
    docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" "$@"
}

require_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        echo "Missing $ENV_FILE. Copy .env.example to .env and fill in the values." >&2
        exit 1
    fi
    chmod 600 "$ENV_FILE"
}

is_nginx_running() {
    docker inspect -f '{{.State.Running}}' "$NGINX_CONTAINER" 2>/dev/null | grep -qx true
}

cert_exists() {
    sudo test -f "$CERT_DIR/fullchain.pem" 2>/dev/null || test -f "$CERT_DIR/fullchain.pem" 2>/dev/null
}

enable_maintenance_mode() {
    touch "$MAINTENANCE_FLAG"
}

disable_maintenance_mode() {
    rm -f "$MAINTENANCE_FLAG"
}

ensure_runtime_dirs() {
    mkdir -p backend/static/resource/attachments/incoming backend/static/resource/attachments/outgoing backend/static/resource/attachments/raw client/build
    local app_uid app_gid
    app_uid="$(sed -n 's/^APP_UID=//p' "$ENV_FILE" 2>/dev/null | tail -1)"
    app_gid="$(sed -n 's/^APP_GID=//p' "$ENV_FILE" 2>/dev/null | tail -1)"
    chown -R "${app_uid:-1000}:${app_gid:-1000}" backend/static/resource/attachments 2>/dev/null || true
}

stop_docker() {
    docker compose -p "$PROJECT_NAME" -f docker-compose-production.yml down --remove-orphans 2>/dev/null || true
    docker compose -p "$PROJECT_NAME" -f docker-compose.yml down --remove-orphans 2>/dev/null || true
}

stop_production_services_preserving_nginx() {
    compose stop web
    compose rm -f web
}

reload_edge_proxy() {
    docker exec "$EDGE_CONTAINER" nginx -s reload >/dev/null 2>&1 || true
}

reload_nginx() {
    compose exec -T nginx nginx -t
    compose exec -T nginx nginx -s reload
}

install_client_dependencies() {
    cd client || exit 1
    if [ ! -f package-lock.json ] && [ ! -f npm-shrinkwrap.json ]; then
        echo "Missing client lockfile; refusing unpinned dependency install" >&2
        exit 1
    fi
    npm ci
    npm run lint
    cd ..
}

lint_client() {
    cd client || exit 1
    if [ "$1" = "fix" ]; then
        npx stylelint "src/**/*.{css,scss}" --fix
        npm run lint:fix
    fi
    npm run lint
    cd ..
}

lint_backend() {
    docker run --rm -v "$PWD/backend:/src:ro" python:3.12-slim sh -c "pip install -q --root-user-action=ignore pyflakes bandit && cd /src && pyflakes main.py cronjobs.py cleanup_attachments.py postfix_incoming_handler.py configs routes orion && bandit -q -r main.py cronjobs.py cleanup_attachments.py postfix_incoming_handler.py configs routes orion"
}

client_build() {
    cd client || exit 1
    rm -rf build
    if [ "${1:-}" = "instrumented" ]; then
        npm run build:instrumented
    else
        npx ng build --configuration production
    fi
    test -f build/index.html
    cd ..
}

run_backend_tests() {
    cd backend || exit 1
    python3 -m pytest "$@"
    cd ..
}

wait_for_application_services() {
    local health deadline
    deadline=$((SECONDS + HEALTH_TIMEOUT))

    echo "Waiting for $WEB_CONTAINER to become healthy..."
    until health="$(docker inspect -f '{{.State.Health.Status}}' "$WEB_CONTAINER" 2>/dev/null)" \
        && [ "$health" = "healthy" ]; do
        if docker logs --since 30s "$WEB_CONTAINER" 2>&1 | grep -q "Application startup failed"; then
            echo "$WEB_CONTAINER failed to start:" >&2
            docker logs --tail 40 "$WEB_CONTAINER" 2>&1 | grep -E "Error|error|failed" | tail -5 >&2 || true
            if docker logs --since 30s "$WEB_CONTAINER" 2>&1 | grep -q "Authentication failed"; then
                echo "MongoDB rejected MONGO_ROOT_USERNAME/MONGO_ROOT_PASSWORD from $ENV_FILE. The volume ${PROJECT_NAME}_mongo was initialised with different credentials: either restore them in $ENV_FILE or reset the volume with: ./run.sh stop && docker volume rm ${PROJECT_NAME}_mongo" >&2
            fi
            return 1
        fi
        if [ "${health:-}" = "unhealthy" ] || [ "$SECONDS" -ge "$deadline" ]; then
            echo "$WEB_CONTAINER did not become healthy (status: ${health:-missing})." >&2
            docker logs --tail 100 "$WEB_CONTAINER" >&2 || true
            return 1
        fi
        sleep 2
    done
    echo "$WEB_CONTAINER is healthy."
}

use_nginx_config() {
    cp "nginx/$1" nginx/nginx.conf
}

publish_certificate() {
    compose run --rm --entrypoint sh certbot -c "cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem /etc/letsencrypt/live/$DOMAIN/privkey.pem /certs/ && chown 101:101 /certs/fullchain.pem /certs/privkey.pem && chmod 640 /certs/fullchain.pem /certs/privkey.pem"
}

issue_certificate() {
    local email
    email="$(sed -n 's/^LETSENCRYPT_EMAIL=//p' "$ENV_FILE" | tr -d '"' | tail -n1)"
    if [ -z "$email" ]; then
        echo "LETSENCRYPT_EMAIL must be set in $ENV_FILE" >&2
        exit 1
    fi

    sudo mkdir -p /etc/letsencrypt
    use_nginx_config nginx-bootstrap.conf
    compose up -d --no-deps nginx
    compose run --rm certbot certonly \
        --webroot -w /var/www/letsencrypt \
        -d "$DOMAIN" \
        --email "$email" --agree-tos --no-eff-email --non-interactive
    publish_certificate
    use_nginx_config nginx-prod.conf
    echo "Certificate issued for $DOMAIN. Run ./run.sh build -p to start the production stack."
}

renew_certificate() {
    compose run --rm certbot renew --webroot -w /var/www/letsencrypt --quiet
    publish_certificate
    if is_nginx_running; then
        reload_nginx
    fi
}

COMMAND="${1:-}"
FLAG="${2:-}"
EXTRA_FLAG="${3:-}"

case "$COMMAND" in
    stop)
        stop_docker
        disable_maintenance_mode
        echo "Orion Mail service stopped"
        exit 0
        ;;
    lint)
        lint_client "$FLAG"
        lint_backend
        echo "Lint passed"
        exit 0
        ;;
    test)
        if [ "$FLAG" = "-c" ]; then
            run_backend_tests --cov=. --cov-report=term-missing --cov-report=xml:coverage.xml
        else
            run_backend_tests
        fi
        exit 0
        ;;
    logs)
        if is_nginx_running; then COMPOSE_FILE="docker-compose-production.yml"; fi
        compose logs -f --tail 200 ${FLAG:+"$FLAG"}
        exit 0
        ;;
    backup)
        require_env_file
        backup_data "${FLAG:-backups}"
        exit 0
        ;;
    restore)
        require_env_file
        restore_data "${FLAG:-}"
        exit 0
        ;;
    perms)
        require_env_file
        ensure_runtime_dirs
        ls -ldn backend/static/resource/attachments backend/static/resource/attachments/incoming backend/static/resource/attachments/outgoing backend/static/resource/attachments/raw
        exit 0
        ;;
    cert)
        require_env_file
        ensure_runtime_dirs
        COMPOSE_FILE="docker-compose-production.yml"
        issue_certificate
        exit 0
        ;;
    renew)
        require_env_file
        COMPOSE_FILE="docker-compose-production.yml"
        renew_certificate
        exit 0
        ;;
    build|production)
        ;;
    *)
        usage
        ;;
esac

require_env_file
ensure_runtime_dirs

if [ "$COMMAND" = "production" ] || { [ "$COMMAND" = "build" ] && [ "$FLAG" = "-p" ]; }; then
    COMPOSE_FILE="docker-compose-production.yml"

    if ! cert_exists; then
        echo "No certificate found at $CERT_DIR. Run ./run.sh cert first." >&2
        exit 1
    fi

    enable_maintenance_mode
    trap disable_maintenance_mode EXIT
    use_nginx_config nginx-prod.conf

    if is_nginx_running; then
        stop_production_services_preserving_nginx
    else
        stop_docker
    fi

    if [ "$COMMAND" = "build" ]; then
        install_client_dependencies
        client_build
        compose build --pull web
    fi

    compose_up_services=()
    if is_nginx_running; then
        compose_up_services=(web)
    else
        publish_certificate
    fi

    if [ "$EXTRA_FLAG" = "-full" ]; then
        compose up -d --pull missing --force-recreate "${compose_up_services[@]}"
    else
        compose up -d --pull missing "${compose_up_services[@]}"
    fi

    if [ "$COMMAND" = "build" ] && is_nginx_running; then
        compose up -d --force-recreate --no-deps nginx
        reload_edge_proxy
    fi

    wait_for_application_services
    reload_nginx
    disable_maintenance_mode
    trap - EXIT
    echo "Orion Mail is live at https://$DOMAIN"

elif [ "$COMMAND" = "build" ] && { [ "$FLAG" = "-d" ] || [ "$FLAG" = "-t" ]; }; then
    COMPOSE_FILE="docker-compose.yml"
    stop_docker
    if [ "$FLAG" = "-t" ]; then
        install_client_dependencies
        client_build instrumented
    fi
    compose build --pull web
    compose up -d --pull missing
    wait_for_application_services
    cat <<MSG

Development stack is up:
  API      http://127.0.0.1:8000   (docs at /docs)
  SMTP     host Postfix on port 25 (mail.orionintelligence.org)
  Mongo    mongodb://127.0.0.1:27017

Start the Angular dev server with:  cd client && npm start   (http://localhost:4300)
With Orion Intelligence also running, use: http://mail.localhost:4200
MSG

else
    usage
fi
