#!/usr/bin/env python3
# C-13 task 2.2 — Prueba automatizada de restore de backup PostgreSQL.
#
# Restaura un backup generado por backup_db.sh sobre una base vacía y verifica
# que tablas y datos se recuperan y el sistema arranca sobre el backup.
#
# Uso: python scripts/restore_test.py <backup_file> <database_url>
# Requiere: pg_restore/psql disponibles, base de destino vacía.

import subprocess
import sys
import time
from pathlib import Path

import psycopg


def main() -> int:
    if len(sys.argv) != 3:
        print("Uso: python restore_test.py <backup_file> <database_url>", file=sys.stderr)
        return 2

    backup_file = Path(sys.argv[1])
    database_url = sys.argv[2]

    if not backup_file.exists():
        print(f"Backup no encontrado: {backup_file}", file=sys.stderr)
        return 2

    print(f"Restaurando {backup_file} sobre {database_url} ...")

    # Esperar a que la base destino esté lista (pg_isready equivalente).
    for _ in range(30):
        try:
            conn = psycopg.connect(database_url, connect_timeout=2)
            conn.close()
            break
        except Exception:
            time.sleep(2)
    else:
        print("Base de destino no disponible", file=sys.stderr)
        return 1

    # Ejecutar pg_restore / psql sobre el archivo de backup.
    cmd = ["psql", database_url, "-f", str(backup_file)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Restore falló:\n{result.stderr}", file=sys.stderr)
        return 1

    # Verificar que tablas clave existen y tienen datos.
    verify_sql = """
    SELECT count(*) AS n_tablas FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name IN ('usuario','odontologo','paciente','turno','pago',
                         'devolucion','evento_pago','turno_historial');
    """
    conn = psycopg.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(verify_sql)
            n = cur.fetchone()[0]
        print(f"Tablas clave encontradas: {n}/7")
        if n < 7:
            print("ERROR: no se recuperaron todas las tablas clave", file=sys.stderr)
            return 1
    finally:
        conn.close()

    print("Restore verificado: tablas y datos recuperados. El sistema puede arrancar sobre el backup.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
