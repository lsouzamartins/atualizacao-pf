# Atualização PF · Nuvem

Aplicação web (Streamlit) da Atualização da Posição Financeira do Hospital Israelita
Albert Sabin, publicada em **https://pf.lsm.ia.br** com HTTPS.

Recebe os arquivos do dia via navegador, processa as fases 0–4 e devolve o arquivo
Hias atualizado para download, gravando o histórico no banco local do VPS.

## Arquitetura resumida

```
Navegador ──HTTPS──> Caddy (pf.lsm.ia.br) ──> Streamlit (127.0.0.1:8501)
                                                   │
                                                   ├── dados/pf.db (SQLite, WAL)
                                                   └── saída/ (arquivos gerados)
```

- **Streamlit** roda como serviço systemd (`atualizacao-pf`), escutando apenas em
  `127.0.0.1:8501` (não fica exposto à internet) e com limite de 1 GB de RAM.
- **Caddy** recebe o tráfego HTTPS em `pf.lsm.ia.br`, repassa para o Streamlit e
  cuida dos certificados (configuração em `infra/Caddyfile`).
- **Banco:** SQLite em `dados/pf.db` (modo WAL), uma conexão por operação. Tabelas:
  `usuarios` (bcrypt, bloqueio de 5 min após 5 falhas), `execucoes` e `resumos_diarios`.
- **Motor de integração Excel:** editor cirúrgico (`integracao_excel.py`, chamado via
  `integracao_runner.py`), que altera apenas as partes XML de BD1/BD2 dentro do `.xlsx`
  e preserva pivôs/slicers/timelines byte a byte (marca as 4 pivôs com `refreshOnLoad`
  para o Excel atualizá-las ao abrir). O arquivo Hias nunca é salvo pelo openpyxl.
- **Deploy contínuo:** GitHub Actions dispara no push para `main` e atualiza o VPS.

O app tem 4 páginas após o login: **Processamento** (fases 0–4), **Resumo do dia**,
**Histórico** e **Administração** (restrita a admins).

## Como funciona o deploy

1. Um commit chega à branch `main` no GitHub.
2. O workflow `.github/workflows/deploy.yml` conecta por SSH no VPS com o usuário
   `apppf` (host e chave vêm dos Secrets `VPS_HOST` e `VPS_SSH_KEY` do repositório).
3. No VPS, roda `bash /opt/atualizacao-pf/infra/deploy.sh`:
   - `git fetch origin && git reset --hard origin/main`
   - `venv/bin/pip install -q -r requirements.txt`
   - `sudo systemctl restart atualizacao-pf`

O `reset --hard` não apaga dados de produção: `dados/`, `saída/` e `backups/` são
gitignorados (arquivos do banco e saídas geradas nunca entram no git).

Para o restart funcionar sem senha, o VPS precisa do arquivo
`/etc/sudoers.d/apppf` com:

```
apppf ALL=(ALL) NOPASSWD: /bin/systemctl restart atualizacao-pf
```

O primeiro deploy é manual (clonar o repo em `/opt/atualizacao-pf`, criar o
`venv/`, instalar o `requirements.txt` e subir a unit systemd); depois disso,
todo deploy acontece pelo push no GitHub.

## Requisitos no VPS

- Repo clonado em `/opt/atualizacao-pf` (dono: `apppf`), com `venv/` criado.
- Unit systemd `infra/atualizacao-pf.service` instalada em `/etc/systemd/system/`.
- `/etc/sudoers.d/apppf` (linha acima).
- Backup diário: `/etc/cron.d/atualizacao-pf` com
  `30 2 * * * root bash /opt/atualizacao-pf/infra/cron-backup.sh`
  e a pasta `/opt/atualizacao-pf/backups` criada.
- Comando `sqlite3` instalado (usado pelo backup) — **verificação pendente na
  Task 11**.
- Caddy: copiar `infra/Caddyfile` para `/etc/caddy/Caddyfile` e habilitar com
  `systemctl enable --now caddy` (certificado automático); DNS: registro A `pf` →
  IP do VPS (registro.br/painel Locaweb). Conferir com
  `curl -I https://pf.lsm.ia.br`.
- `infra/setup_base.sh` serve de referência para a instalação base (pacotes,
  usuário `apppf`, firewall, unit systemd).

## Criar ou trocar usuário

- **Primeiro admin (uma única vez, via SSH no VPS):**

  ```bash
  cd /opt/atualizacao-pf && venv/bin/python scripts/criar_admin.py
  ```

  O script cria o banco (se ainda não existir) e pede login, nome e senha
  (mínimo de 8 caracteres). Se o acesso de todos os admins for perdido, rode-o
  de novo: ele cria um novo admin sem apagar os existentes.

- **Novos usuários e troca de senha:** página **Administração** (visível só
  para admins), com os formulários "Criar usuário" (login, nome, senha mín. 8,
  opção Administrador) e "Trocar minha senha" (pede a senha atual).

- **Bloqueio:** após 5 tentativas de senha erradas, o usuário fica bloqueado por
  5 minutos (o bloqueio expira sozinho). A senha precisa de pelo menos 8
  caracteres.

## Baixar um backup

- **Automático:** todo dia às 02:30 o cron roda `infra/cron-backup.sh`, que gera
  `/opt/atualizacao-pf/backups/pf-<AAAA-MM-DD>.db` e mantém as **30 cópias mais
  recentes**. Para baixar, copie por SCP/SSH, por exemplo:

  ```bash
  scp apppf@<servidor>:/opt/atualizacao-pf/backups/pf-2026-09-03.db ./pf-2026-09-03.db
  ```

- **Na hora:** a página **Administração** tem o botão "Baixar backup (.db)", que
  gera um backup consistente do banco naquele momento e envia para o navegador.

## Reiniciar o app

```bash
sudo systemctl restart atualizacao-pf
```

Para acompanhar: `sudo systemctl status atualizacao-pf` e
`sudo journalctl -u atualizacao-pf -n 200 -f`. O serviço reinicia sozinho em
caso de queda (`Restart=always`).

## O que fazer se o disco encher

1. Veja o uso: `df -h /` e `sudo du -sh /opt/atualizacao-pf/*`.
2. Saídas antigas da pasta `saída/` são apagadas automaticamente pelo backup
   diário (arquivos com mais de 30 dias). Se o problema for recente e grave,
   mova manualmente os `.xlsx` antigos de `saída/` para fora do servidor.
3. Confira `backups/`: só as 30 cópias mais recentes devem existir.
4. Enxugue o log do sistema se necessário: `sudo journalctl --vacuum-size=200M`.
5. Com espaço liberado, reinicie o app (`sudo systemctl restart atualizacao-pf`)
   e o Caddy (`sudo systemctl restart caddy`) se o site estiver fora do ar.

O banco `dados/pf.db` cresce devagar (execuções e resumos diários); o volume
grande fica nas saídas Excel, por isso a limpeza automática de 30 dias.

## O pendrive continua funcionando

O app original do pendrive (Windows) e esta versão na nuvem são **independentes**:

- Os arquivos do dia (WPD-26.xls, Não_Identificado.xls e Posição Financeira
  Hias.xlsx) são enviados pelo navegador a cada execução — a nuvem não lê nada
  do pendrive, e o pendrive não lê nada da nuvem.
- O banco da nuvem (`dados/pf.db`) vive só no VPS; o pendrive tem os próprios
  arquivos.
- Se a nuvem ficar fora do ar, o fluxo no pendrive segue normal — e vice-versa.
