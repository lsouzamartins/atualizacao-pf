# Notas do VPS (NÃO commitar em repo público — este arquivo fica só no repo privado)
- IP: 177.153.35.245
- SSH: root + usuário apppf
- Senha root: senha fornecida ao controlador — será rotacionada ao final do projeto
- Ubuntu 24.04, LibreOffice 24.2.7.2, python3-uno OK
- UFW ativo: 22 (OpenSSH), 80/tcp e 443/tcp liberados
- fail2ban habilitado (enabled)
- Unit systemd criada em /etc/systemd/system/atualizacao-pf.service (ainda não habilitada/iniciada — deploy em task posterior)
- Venv do app (/opt/atualizacao-pf/venv) ainda NÃO criado — tasks posteriores