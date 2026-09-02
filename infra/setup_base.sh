#!/usr/bin/env bash
set -euo pipefail
# Setup base do VPS — Atualização PF na nuvem (rodar como root, UMA vez)

export DEBIAN_FRONTEND=noninteractive
# Evita prompt interativo do needrestart durante o apt upgrade (Ubuntu 24.04)
export NEEDRESTART_MODE=a

apt-get update && apt-get upgrade -y

# Dependências do app
apt-get install -y python3 python3-venv python3-pip sqlite3 curl git unzip \
    ufw fail2ban caddy

# LibreOffice headless + bridge UNO para Python (integração Excel)
apt-get install -y --no-install-recommends libreoffice-calc python3-uno \
    libreoffice-script-provider-python

# Usuário do app e do deploy
id -u apppf >/dev/null 2>&1 || useradd -m -s /bin/bash apppf
install -d -o apppf -g apppf /opt/atualizacao-pf /var/log/atualizacao-pf

# Fuso horário
timedatectl set-timezone America/Sao_Paulo

# Firewall: só SSH, HTTP e HTTPS
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

# fail2ban no SSH
systemctl enable --now fail2ban

# Limite de recursos para o Streamlit (protege a RAM do VPS)
cat > /etc/systemd/system/atualizacao-pf.service <<'EOF'
[Unit]
Description=Atualizacao PF - Streamlit
After=network.target

[Service]
User=apppf
WorkingDirectory=/opt/atualizacao-pf
ExecStart=/opt/atualizacao-pf/venv/bin/streamlit run app_streamlit.py \
    --server.headless true --server.port 8501 --server.address 127.0.0.1
Restart=always
RestartSec=5
MemoryMax=1G

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload

echo "OK — base instalada. Falta: venv, deploy, Caddy (tasks posteriores)."
