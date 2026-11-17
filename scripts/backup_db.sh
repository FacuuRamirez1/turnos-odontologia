#!/bin/bash
# C-13 task 2.1 — Backup periódico de PostgreSQL (pg_dump del volumen pgdata).
# Ejecutar desde un contenedor del servicio db o cron del host.
# Variables de entorno: DATABASE_URL, BACKUP_DIR (default /backups).

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/turnos_backup_${TIMESTAMP}.sql"

mkdir -p "${BACKUP_DIR}"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL no definida" >&2
  exit 1
fi

# pg_dump sobre la base configurada (volumen pgdata).
pg_dump "${DATABASE_URL}" > "${BACKUP_FILE}"

echo "Backup creado: ${BACKUP_FILE}"
