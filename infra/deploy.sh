#!/usr/bin/env bash
set -euo pipefail
cd /opt/atualizacao-pf
git fetch origin && git reset --hard origin/main
venv/bin/pip install -q -r requirements.txt
sudo systemctl restart atualizacao-pf
echo "Deploy OK em $(date)"
