#!/bin/bash
set -e

echo "Starting database initialization script..."

if [ -n "${POSTGRES_NON_ROOT_USER:-}" ] && [ -n "${POSTGRES_NON_ROOT_PASSWORD:-}" ]; then
    echo "Creating user ${POSTGRES_NON_ROOT_USER}..."
    
    # ИСПРАВЛЕНО: явно указываем базу данных в команде psql
    USER_EXISTS=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_NON_ROOT_USER}'")
    
    if [ -z "$USER_EXISTS" ]; then
        echo "User does not exist, creating..."
        psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
            CREATE USER ${POSTGRES_NON_ROOT_USER} WITH ENCRYPTED PASSWORD '${POSTGRES_NON_ROOT_PASSWORD}';
            GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_NON_ROOT_USER};
EOSQL
        
        echo "Setting schema privileges..."
        psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
            GRANT ALL ON SCHEMA public TO ${POSTGRES_NON_ROOT_USER};
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${POSTGRES_NON_ROOT_USER};
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${POSTGRES_NON_ROOT_USER};
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO ${POSTGRES_NON_ROOT_USER};
EOSQL
        echo "User ${POSTGRES_NON_ROOT_USER} created successfully!"
    else
        echo "User ${POSTGRES_NON_ROOT_USER} already exists, skipping creation."
    fi
else
    echo "SETUP INFO: No Environment variables given for non-root user!"
fi

echo "Database initialization completed."