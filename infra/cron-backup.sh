#!/usr/bin/env bash
set -euo pipefail
# Backup diário do banco (30 cópias) + limpeza de saídas com 30+ dias
mkdir -p /opt/atualizacao-pf/backups /opt/atualizacao-pf/saída
DATA=$(date +%F)
sqlite3 /opt/atualizacao-pf/dados/pf.db ".backup /opt/atualizacao-pf/backups/pf-${DATA}.db"
ls -1 /opt/atualizacao-pf/backups/pf-*.db | sort | head -n -30 | xargs -r rm -f
find /opt/atualizacao-pf/saída -type f -mtime +30 -delete
