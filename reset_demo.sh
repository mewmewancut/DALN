#!/bin/sh
set -eu

if [ "${1:-}" != "--confirm-local-demo" ] || [ "$#" -ne 1 ]; then
  printf '%s\n' 'Usage: sh reset_demo.sh --confirm-local-demo' >&2
  printf '%s\n' 'Chỉ xóa và tạo lại schema của database fashion_demo trong project daln-demo.' >&2
  exit 2
fi

cd "$(dirname "$0")"
compose() {
  MSYS_NO_PATHCONV=1 docker compose --project-name daln-demo --env-file .env.example -f compose.demo.yml "$@"
}

compose up -d --wait db
compose stop frontend backend
# psql uses the local Unix socket inside the demo Postgres container. No .env
# database URL or host override can route this reset to Lakebase or project daln.
compose exec -T db psql --no-psqlrc --username=fashion --dbname=fashion_demo --set=ON_ERROR_STOP=1 \
  --command='BEGIN; DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION fashion; COMMIT;'
compose up -d --build --wait backend frontend
printf '%s\n' 'Demo đã reset: http://localhost:15173 (API http://localhost:18000/docs)'
