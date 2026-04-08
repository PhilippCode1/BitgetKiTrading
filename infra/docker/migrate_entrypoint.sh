#!/bin/sh
# Zwei Phasen: kanonische Schema-Migrationen, dann optionale Demo-Seeds (nur mit ENV-Flag).
set -eu
python /app/infra/migrate.py || exit "$?"
python /app/infra/migrate.py --demo-seeds || exit "$?"
