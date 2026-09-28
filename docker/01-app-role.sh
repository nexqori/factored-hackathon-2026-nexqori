#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=app_password="$APP_DATABASE_PASSWORD" <<'EOSQL'
CREATE ROLE nexqori_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
GRANT CONNECT ON DATABASE nexqori TO nexqori_app;
GRANT USAGE, CREATE ON SCHEMA public TO nexqori_app;
EOSQL
