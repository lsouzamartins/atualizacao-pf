# Dashboard de Ponto — Spec de Design

**Data:** 06/11/2026 · **Autor:** Claude Code + Leonardo Martins (ABIRJ / Hospital Israelita Albert Sabin)
**Estado:** Aprovado em seções (06/11/2026) — aguardando revisão final do Leonardo.

## 1. Objetivo

Adicionar ao portal **Atualização PF** (pf.lsm.ia.br) uma página **Ponto**, para o Leonardo acompanhar o próprio banco de horas: saldo acumulado, horas trabalhadas, atrasos, faltas, férias, feriados, atestados e batidas incompletas.

A fonte pode ser a planilha **Controle de Ponto.xlsx** (upload) **ou o lançamento direto na página**. O sistema recalcula tudo a partir das batidas de entrada/saída — não importa os cálculos da planilha — e corrige três distorções identificadas: jornada de fim de semana, atraso contado em dobro e ausência de saldo acumulado. O lançamento manual existe para o Leonardo não depender do Excel (o do Lameirão é pirata e dá problema).

## 2. Decisões aprovadas (registro)

| Decisão | Escolha |
|---|---|
| Objetivo | Acompanhamento pessoal do banco de horas |
| Arquitetura | Página nova dentro do portal PF — um login só, um deploy só |
| Atualização | Upload de planilha **sem senha** ou lançamento manual na página; o site não guarda senha |
| Lançamento manual | Sim — formulário na própria página para criar/editar um dia (entrada, saída, férias, feriado, atestado, observação) |
| Precedência upload × manual | O upload **preserva** os dias editados manualmente; na confirmação há a opção de sobrescrevê-los |
| Regras | Corrigidas (fim de semana/feriado com jornada 0, atraso informativo, saldo acumulado) |
| Faltas | Dia útil passado sem registro desconta a jornada; batida incompleta fica pendente e não entra no saldo |
| Fonte da verdade | Batidas registradas no site (upload + manual); cálculos da planilha são ignorados |
| Período | Histórico começa em 08/04/2026; o formulário manual pode lançar outras datas; dias futuros não contam |
| Visual | Padrão do portal (azul #1C5A8A, fundo branco, bordas 1px, Segoe UI) |
| Publicação | Só depois de testes verdes e autorização explícita do Leonardo (push na main dispara deploy) |

## 3. Fonte de dados — Controle de Ponto.xlsx

Inspecionado em 06/11/2026 (somente leitura; o arquivo original está protegido por senha, lido localmente para análise).

- Duas abas: **2025** (formato antigo de 4 colunas: DIA/ENTRADA/SAIDA/Status; tem 41 linhas preenchidas, mas é ignorada pela regra do ano mais recente — decisão de 06/11/2026) e **2026** (formato atual).
- Aba 2026: 268 linhas, de **08/04/2026 a 31/12/2026**, colunas:
  `Data`, `Dia`, `Entrada`, `Saída`, `Jornada`, `Horas Trabalhadas`, `Atraso`, `Hora Positiva`, `Hora Negativa`, `Saldo`, `Status`.
- `Dia` é fórmula `=TEXT(Data;"ddd")`; `Jornada` é fórmula `=IF(WEEKDAY(Data;2)=5;9h;10h)`; as demais colunas calculadas usam fórmulas arrastadas até 23/10/2026 apenas.
- Entrada/Saída contêm hora (`time`) ou texto: `Férias` (32 dias), `Feriado` (4) / `feriado` (1) e `atestado` (3).
- Batidas incompletas: 5 (25/06 saída sem entrada; 22/10 saída sem entrada; 03/11 entrada sem saída; 04/11 saída sem entrada; 05/11 entrada sem saída).
- Não há faltas de dia inteiro até 05/11/2026.
- Dias futuros (06/11 a 31/12) estão sem batida.

### Diagnóstico dos cálculos da planilha

| Problema | Efeito |
|---|---|
| Cálculos param em 23/10/2026 | 7 dias com batida (26/10 a 05/11) sem horas/atraso/saldo |
| Saldo preenchido só em 11 linhas, à mão | Sem banco de horas acumulado |
| Jornada de 10h em sábado e domingo | Trabalho no fim de semana não vira hora extra |
| Atraso subtraído no saldo **e** já refletido na hora negativa | Débito em dobro |
| Textos de férias/feriado/atestado nas colunas de horário | Fórmulas não tratam; `Feriado` e `feriado` convivem |
| Status quase não usado | 1 registro em 268 linhas |

### Números de referência (recálculo corrigido, 08/04 a 05/11/2026)

| Indicador | Valor |
|---|---|
| Dias com batida completa | 117 |
| Horas trabalhadas | 1.102:37 |
| Atraso total (informativo) | 80:33 |
| Férias / feriados / atestados | 32 / 5 / 3 dias |
| Faltas | 0 |
| Pendências (batida incompleta) | 5 |
| **Saldo corrigido** | **−43:23** |
| Saldo que a planilha mostra | −123:56 |
| Diferença (atraso em dobro) | 80:33 |

Saldo mensal corrigido: abr +0:31 · jun +0:48 · jul −0:19 · ago −21:08 · set −10:53 · out −12:22 · nov 0:00.
(Maio é férias; não há dados de 2025.)

## 4. Arquitetura

```text
app_streamlit.py (login existente)
  └─ usuário com acesso_ponto=1 ou admin → Início (portal) + página Ponto no nav
ponto_core.py            → leitura da planilha + regras de cálculo (sem Streamlit)
banco.py                 → tabelas ponto_uploads/ponto_registros + acesso_ponto
app_pages/ponto.py       → upload com prévia + lançamento manual + dashboard + calendário + tabela
app_pages/portal.py      → card "Controle de Ponto"
app_pages/administracao.py → checkbox "Acesso ao Controle de Ponto"
navegacao.py             → inclui a página Ponto para quem tem acesso
ui_comum.py              → VERSAO = "V 5.2026.1106"
```

**Arquivos novos:** `ponto_core.py`, `app_pages/ponto.py`, `tests/test_ponto_core.py`, `tests/test_banco_ponto.py`.
**Arquivos modificados:** `banco.py`, `navegacao.py`, `app_streamlit.py`, `app_pages/portal.py`, `app_pages/administracao.py`, `ui_comum.py`, `tests/test_navegacao.py`, `tests/test_portal.py`.
**Dependências:** nenhuma nova — `openpyxl`, `xlrd`, `pandas` e `plotly` já estão no `requirements.txt`.

## 5. Banco de dados (pf.db)

```sql
CREATE TABLE IF NOT EXISTS ponto_uploads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  usuario TEXT NOT NULL,
  nome_arquivo TEXT NOT NULL,
  enviado_em TEXT NOT NULL,          -- ISO 8601
  periodo_de TEXT NOT NULL,          -- YYYY-MM-DD
  periodo_ate TEXT NOT NULL,         -- YYYY-MM-DD
  linhas INTEGER NOT NULL,
  avisos TEXT                        -- JSON array de strings
);

CREATE TABLE IF NOT EXISTS ponto_registros (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  upload_id INTEGER REFERENCES ponto_uploads(id),  -- NULL = lançamento manual
  data TEXT NOT NULL,                -- YYYY-MM-DD
  entrada TEXT,                      -- HH:MM ou NULL
  saida TEXT,                        -- HH:MM ou NULL
  tipo TEXT NOT NULL DEFAULT 'trabalho',  -- trabalho|ferias|feriado|atestado|outro
  observacao TEXT,                   -- coluna Status da planilha
  origem TEXT NOT NULL DEFAULT 'upload',   -- upload|manual
  atualizado_em TEXT,                -- ISO 8601 (lançamentos manuais)
  atualizado_por TEXT,               -- login (lançamentos manuais)
  UNIQUE(data)
);
CREATE INDEX IF NOT EXISTS idx_ponto_data ON ponto_registros(data);
```

- `UNIQUE(data)` impede duplicidade de dia.
- `upload_id` é `NULL` nos lançamentos manuais; `origem` distingue `upload` de `manual`.
- A importação percorre **somente as datas presentes no arquivo**, dentro de uma transação: para cada data, se existir registro com `origem='manual'` e `sobrescrever_manuais=False`, pula; senão, apaga o registro de origem upload daquela data e insere o novo. Assim os lançamentos manuais são preservados por padrão.
- `ponto_uploads` guarda o histórico de envios (quem, quando, arquivo, período e avisos). Nada é apagado do histórico.
- Migração: `usuarios.acesso_ponto INTEGER NOT NULL DEFAULT 0` via `_garantir_coluna`, como as demais permissões.

### Funções novas em banco.py

| Função | Contrato |
|---|---|
| `definir_acesso_ponto(conn, login, valor)` | Liga/desliga a permissão |
| `salvar_importacao_ponto(conn, usuario, nome_arquivo, registros, periodo_de, periodo_ate, avisos, sobrescrever_manuais=False)` | Transação: grava upload + registros e devolve `upload_id`; preserva os dias manuais, salvo `sobrescrever_manuais=True` |
| `salvar_registro_manual(conn, data, entrada, saida, tipo, observacao, usuario)` | Upsert de um dia com `origem='manual'`, `atualizado_em` e `atualizado_por` |
| `excluir_registro_ponto(conn, data)` | Remove o dia do banco (usado pelo botão "Excluir dia") |
| `ultimo_upload_ponto(conn)` | Última linha de `ponto_uploads` (ou `None`) |
| `listar_uploads_ponto(conn, limite=20)` | Uploads mais recentes primeiro |
| `registros_ponto(conn)` | Todos os registros ordenados por `data` |

`registros` é uma lista de dicts `{"data": date, "entrada": "HH:MM"|None, "saida": "HH:MM"|None, "tipo": str, "observacao": str|None}`.

## 6. Regras de cálculo

### 6.1 Classificação de cada data importada

| Situação | Condição |
|---|---|
| `positivo` | Tipo `trabalho`, entrada e saída válidas, saída > entrada, dia útil, saldo do dia > 0 |
| `trabalhado` | Mesma condição, saldo do dia = 0 |
| `negativo` | Mesma condição, saldo do dia < 0 |
| `extra` | Sábado ou domingo com batida completa (jornada 0) |
| `ferias` / `feriado` / `atestado` | Texto reconhecido em Entrada ou Saída |
| `falta` | Tipo `trabalho`, sem entrada e sem saída, dia útil, **data anterior a hoje** |
| `hoje` | Data = hoje, sem batida (não conta e não é falta) |
| `pendente` | Entrada sem saída, saída sem entrada, ou saída ≤ entrada |
| `futuro` | Data > hoje, sem batida (não entra no saldo) |
| `fim_de_semana` | Sábado/domingo sem batida |
| `outro` | Texto não reconhecido em Entrada/Saída — conta como pendência e gera aviso |

Precedência da classificação: tipo especial (férias/feriado/atestado) > pendente > falta/hoje/futuro > fim de semana > positivo/trabalhado/negativo/extra/outro.

### 6.2 Fórmulas

- **Jornada do dia:** 0 min em sábado/domingo; 9h (540 min) na sexta; 10h (600 min) nos demais dias úteis. Férias, feriado e atestado têm jornada 0.
- **Horas trabalhadas:** `saída − entrada` em minutos, sem desconto de almoço/intervalo.
- **Saldo do dia:** `horas trabalhadas − jornada`. Em falta: `−jornada`. Em férias/feriado/atestado, pendente e futuro: não computado (0 no acumulado; "—" na tabela).
- **Atraso:** `max(0, entrada − 08:00)` apenas em dias com batida completa. É informativo e **não** entra no saldo.
- **Horas positivas / negativas:** `max(0, saldo do dia)` e `max(0, −saldo do dia)`.
- **Saldo acumulado:** soma corrida dos saldos dos dias com data ≤ hoje, em ordem de data, desde o primeiro registro importado.

### 6.3 Regras de borda

- Datas **> hoje** nunca geram falta nem entram no saldo. **Hoje** entra no saldo se tiver batida completa e nunca gera falta.
- `saída ≤ entrada` não é convertida em virada de madrugada: fica pendente.
- Textos são comparados sem diferenciar maiúsculas nem acentos (`Férias`, `ferias`, `Feriado`, `feriado`, `atestado`).
- Se a mesma data aparecer duas vezes na planilha, a importação é recusada com erro.
- Linhas sem data são ignoradas com aviso.

## 7. Importação

### 7.1 Leitura

- Aceita `.xlsx` e `.xls`, até 5 MB.
- Para cada aba, o cabeçalho é localizado na primeira linha. São aceitos os nomes `Data` ou `DIA`, `Entrada`/`ENTRADA`, `Saída`/`SAIDA`/`SAÍDA` e `Status` (comparação sem caixa/acento).
- Abas sem nenhum valor em Entrada, Saída ou Status são ignoradas com aviso.
- **Vale apenas a aba do ano mais recente** (decisão de 06/11/2026): abas cujos registros param em anos anteriores são ignoradas com o aviso `Aba '<nome>' ignorada: vale a aba do ano mais recente (<ano>).` Duas abas do mesmo ano somam-se.
- Se nenhuma aba válida for encontrada, a importação é recusada com mensagem explicando o formato esperado.
- Datas aceitas: `datetime` ou texto `dd/mm/aaaa`. Horas aceitas: `time`, `datetime`, fração do dia (`float`) ou texto `HH:MM`.
- **Arquivo protegido:** se o conteúdo for OLE2 com `EncryptedPackage`, a página orienta: “Abra no Excel, salve uma cópia sem senha e envie a cópia”.

### 7.2 Avisos exibidos na prévia

- Aba ignorada (sem dados).
- Aba de ano anterior ignorada (vale a aba do ano mais recente).
- Texto não reconhecido em Entrada/Saída.
- Linhas sem data.
- Batidas incompletas encontradas.
- Divergência de jornada em dia útil (informativo; a regra do sistema prevalece). Sábado, domingo e feriado não geram aviso, pois a diferença é intencional.
- Datas duplicadas (erro, não aviso).

### 7.3 Prévia e confirmação

1. O upload é lido em memória; nada é gravado.
2. A prévia mostra: nome do arquivo, período (primeira e última data), número de linhas, contagem por tipo, número de pendências, **quantos dias editados manualmente serão preservados** e a lista de avisos.
3. O botão **Confirmar importação** grava; **Cancelar** descarta. Um checkbox **"Sobrescrever também os dias editados manualmente"** (desmarcado por padrão) controla a precedência.
4. Após gravar: mensagem de sucesso, limpeza do cache de cálculo e recarga da página.

### 7.4 Substituição e histórico

- O upload é a fonte da verdade para as datas que contém, **exceto os dias com `origem='manual'`**, que são preservados por padrão.
- Reenviar a planilha atualiza os dias de origem upload e inclui os novos, sem duplicar.
- Com o checkbox "Sobrescrever também os dias editados manualmente" marcado, o upload substitui tudo, inclusive os manuais.
- O histórico de uploads fica visível em um expansor (data/hora, usuário, arquivo, período, linhas).
- Datas fora do arquivo enviado permanecem no banco e continuam sendo recalculadas; a prévia mostra exatamente o período coberto pelo novo arquivo.
- Não há botão de desfazer; o backup diário do `pf.db` (30 cópias) é a rede de segurança.

## 8. Dashboard

### 8.1 Estrutura da página

```text
Título "Controle de Ponto" + seletor de mês/ano (opção "Tudo")
Linha "Última atualização: origem (planilha ou manual) · data/hora"
KPIs (5 cartões)
Dois gráficos lado a lado
Calendário do mês
Expander "Lançar/editar ponto" (formulário manual)
Tabela detalhada + botão "Baixar CSV"
Expander "Importar nova planilha" + histórico
```

- Período padrão: o mês da batida mais recente (assim a página abre com dados úteis); a opção **Tudo** mostra o período completo. Se ainda não houver dados, a página mostra o estado vazio de importação.
- O saldo acumulado do KPI é calculado até o último dia do período selecionado (limitado a hoje); os demais KPIs são do período.

### 8.2 KPIs

| Cartão | Conteúdo |
|---|---|
| Saldo acumulado | Soma até o fim do período; sinal e cor (verde ≥ 0, vermelho < 0); subtítulo "desde a primeira data importada" |
| Horas no período | Total trabalhado; subtítulo com a jornada do período |
| Atrasos | Total no período; subtítulo "informativo" |
| Faltas | Quantidade no período |
| Pendências | Quantidade no período; subtítulo "batidas incompletas" |

### 8.3 Gráficos (plotly)

1. **Evolução do saldo acumulado** — linha do saldo dia a dia até o fim do período selecionado (limitado a hoje), eixo Y em horas, hover com data, saldo do dia e acumulado.
2. **Saldo por mês** — barras divergentes (verde para positivo, vermelho para negativo), com linha zero.

Cores e tipografia seguem o CLAUDE.md; sem gradientes.

### 8.4 Calendário

- Grade seg→dom do mês selecionado; cada célula mostra o número do dia e, no hover, entrada, saída, horas e saldo.
- Cores de fundo suaves com texto escuro (contraste AA):
  - trabalhado: `#DBEAFE` / texto `#1C5A8A`
  - positivo: `#DCFCE7` / texto `#15803D`
  - negativo: `#FEE2E2` / texto `#DC2626`
  - pendente: `#FEF3C7` / texto `#B45309`
  - falta: `#FECACA` / texto `#991B1B`
  - férias: `#E0F2FE` / texto `#0369A1`
  - feriado: `#F1F5F9` / texto `#64748B`
  - atestado: `#F3E8FF` / texto `#6B21A8`
  - futuro: branco com borda tracejada `#E2E8F0`
  - hoje sem batida: branco com borda azul `#1C5A8A`
  - fim de semana: `#F8FAFC`
- Legenda abaixo da grade.

### 8.5 Tabela e exportação

Colunas: `Data`, `Dia`, `Entrada`, `Saída`, `Jornada`, `Horas trabalhadas`, `Atraso`, `Saldo do dia`, `Saldo acumulado`, `Situação`, `Observação`.

- Dias sem valor exibem "—".
- Situação em português: Positivo, Trabalhado, Negativo, Extra, Férias, Feriado, Atestado, Falta, Hoje, Pendente, Futuro, Fim de semana, Outro.
- **Baixar CSV**: separador `;`, UTF-8 com BOM, mesmo conjunto de colunas e o período selecionado.

### 8.6 Lançamento manual

- Formulário no expander **Lançar/editar ponto**, disponível para quem tem `acesso_ponto` (ou admin).
- Campos: data (`date_input`, padrão hoje), situação (`Trabalho`, `Férias`, `Feriado`, `Atestado`), entrada e saída (`time_input`, habilitados só para Trabalho) e observação (texto).
- Ao escolher uma data que já existe, o formulário carrega os valores atuais (venham de upload ou de edição manual).
- **Salvar** grava com `origem='manual'`, `atualizado_em` e `atualizado_por`; a dashboard recalcula na hora. Se o dia veio de upload, o valor da planilha não fica guardado — o registro passa a ser manual.
- **Excluir dia** remove o registro (com confirmação). O dia deixa de existir no banco; se for dia útil passado, passa a contar como falta.
- Validação: em dia de trabalho, a saída deve ser maior que a entrada; em férias/feriado/atestado os horários são ignorados; data fora do período importado gera aviso, mas é permitida.
- O lançamento manual nunca é sobrescrito por upload, salvo se o checkbox de sobrescrita for marcado.

### 8.7 Estados vazios e erros

- Sem nenhuma importação: cartão explicando como enviar a planilha e o botão de upload.
- Sem dados no período: mensagem e sugestão de trocar o mês.
- Erro de leitura: mensagem com o motivo (protegido, formato, colunas, duplicidade), sem gravar nada.

## 9. Permissões e navegação

- Nova permissão `acesso_ponto`; admin sempre tem acesso.
- `auth._usuario_sessao` passa a carregar `acesso_ponto`.
- `navegacao.montar_paginas` ganha o parâmetro `acesso_ponto`; a página **Ponto** entra no nav para quem tem a permissão.
- `app_streamlit.py` repassa a permissão.
- `portal.py`: card "Controle de Ponto" na segunda linha do portal (terceira coluna, ao lado de Glosa/Cobrança), visível só com a permissão.
- `tem_portal` passa a considerar também `acesso_ponto`.
- A página verifica a permissão no início; sem ela, exibe "Acesso restrito" e para (proteção extra contra acesso direto por URL).
- `administracao.py`: checkbox "Acesso ao Controle de Ponto" por usuário.

## 10. Testes

### `tests/test_ponto_core.py`

- Jornada 10h (seg–qui), 9h (sex), 0h (sáb/dom/feriado/férias/atestado).
- Sábado trabalhado gera horas positivas integrais.
- Atraso não reduz o saldo.
- Falta desconta a jornada; sábado sem batida não é falta.
- Entrada sem saída, saída sem entrada e saída ≤ entrada viram pendência e não entram no saldo.
- Datas futuras não contam e não geram falta.
- Saldo acumulado na ordem das datas.
- Textos com/sem acento e maiúsculas.
- Duplicidade de data recusada; linha sem data gera aviso.
- Aba vazia ignorada; aba de ano anterior ignorada quando há aba de ano mais recente; nenhuma aba válida gera erro.
- Arquivo protegido gera a mensagem orientativa.

### `tests/test_banco_ponto.py`

- Criação das tabelas e migração de `acesso_ponto` em banco antigo.
- Importação substitui somente as datas enviadas, sem duplicar.
- Histórico de uploads preservado.
- Lançamento manual cria/atualiza o dia com `origem='manual'` e autor.
- Upload preserva o dia manual por padrão; com `sobrescrever_manuais=True`, substitui.
- Excluir registro remove o dia.
- `definir_acesso_ponto` liga/desliga.

### Testes existentes atualizados

- `tests/test_navegacao.py`: Ponto aparece só com permissão; Início continua default.
- `tests/test_portal.py`: card condicional.

### Teste de fumaça

- Página importa e renderiza sem dados e com dados (Streamlit AppTest, se disponível no projeto).

## 11. Publicação e versão

- `ui_comum.VERSAO` passa a **V 5.2026.1106**.
- Rodar `pytest` local antes de qualquer commit.
- **Commit/push só com autorização explícita do Leonardo** — o push na `main` dispara o deploy automático no VPS.
- Rollback: `git revert` do commit; `dados/pf.db` não é apagado pelo deploy e tem backup diário.

## 12. Fora de escopo

- Múltiplos funcionários/equipe.
- Edição em lote (vários dias de uma vez) — o formulário manual é dia a dia.
- Desconto de almoço/intervalo (a planilha não registra).
- Integração com relógio de ponto.
- Notificações por e-mail/WhatsApp.
- Aprovação/espelho de ponto.
- Histórico de anos anteriores: a planilha pode ter abas antigas, mas a dashboard acompanha só o ano mais recente (06/11/2026).

## 13. Riscos e limitações

| Risco | Tratamento |
|---|---|
| Planilha protegida | Mensagem orientando salvar cópia sem senha; nada é gravado |
| Formato da planilha mudar | Validação de cabeçalho e mensagem clara; importação recusada |
| Datas duplicadas | Importação recusada |
| Upload errado | Prévia + confirmação; reenvio corrige; backup diário do banco |
| Memória do VPS (1 GB) | 268 linhas é carga trivial para pandas/openpyxl |
| Fuso horário | Datas e horas tratadas como valores locais sem fuso |

## 14. Critérios de aceite

1. Importar uma **cópia sem senha** da planilha atual e obter 268 linhas, período 08/04/2026 a 31/12/2026.
2. A dashboard exibir: 117 dias trabalhados, 1.102:37 trabalhadas, 80:33 de atraso, **saldo −43:23**, 5 pendências e 0 faltas (até 05/11/2026).
3. O saldo mensal bater com: abr +0:31 · jun +0:48 · jul −0:19 · ago −21:08 · set −10:53 · out −12:22 · nov 0:00.
4. Lançar um dia manualmente (entrada/saída) e ver o saldo mudar.
5. Marcar férias/feriado/atestado sem horários e ver o dia fora do saldo.
6. Subir a planilha e o dia manual permanecer (padrão); com a opção de sobrescrever, ele ser substituído.
7. Excluir um lançamento manual e ver o dia deixar de ter registro (e virar falta, se for dia útil passado).
8. Reenviar uma versão alterada substituir os dias do período, sem duplicar, e manter o histórico.
9. O card e a página só aparecerem com `acesso_ponto` (ou admin).
10. O CSV baixado abrir no Excel com acentos e horas corretos.
11. Todos os testes verdes.
12. Deploy autorizado explicitamente pelo Leonardo.
