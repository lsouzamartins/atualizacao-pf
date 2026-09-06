# Dashboard de Glosas (DACM) — Spec de Design

**Data:** 06/09/2026 · **Autor:** Claude Code + Leonardo Martins (ABIRJ / Hospital Israelita Albert Sabin)
**Estado:** Aprovado em seções (05-06/09/2026) — aguardando revisão final do Leonardo.

## 1. Objetivo

Sistema web dentro do app **Atualização PF** (pf.lsm.ia.br) para acompanhar **glosas de convênios a partir do DACM** (Demonstrativo de Análise de Conta) e gerir os **recursos de glosa**, com dashboard para tomada de decisões.

Primeiro convênio: **Porto Saúde** (DACM em Excel, formato ANS). PDF será suportado depois (outros convênios não exportam Excel).

## 2. Decisões aprovadas (registro)

| Decisão | Escolha |
|---|---|
| Arquitetura | Portal no app atual — um login só; após o login, cards "Escolha o sistema" |
| Banco | SQLite SEPARADO: `dados/dacm_glosas.db` (o banco do PF não é tocado além da flag de acesso) |
| Fonte de dados | Upload do DACM em Excel (agora) e PDF (depois); parser por formato |
| Convênio | Detectado automaticamente pela operadora do arquivo; nome editável na prévia |
| Substituição (reenvio) | Chave: `(convenio, guia_prestador)`. Reenviar o DACM atualiza as guias existentes e insere as novas — nunca duplica |
| Status do recurso | **5 status** (06/09): `A iniciar recurso` · `Em análise` · `Glosa Recebida` · `Recurso Negado` · `Livre de Glosa` |
| Glosa zerada no reenvio | **Aviso + 1 clique** (06/09): nada muda sozinho; o painel destaca e o usuário confirma com 1 clique |
| Dashboard | Para tomada de decisões: % glosa, taxa de recuperação, aging, tendência mensal |
| Interatividade | Plotly + filtros cruzados (convênio, período, status, busca) |
| Histórico | Banco acumula todos os uploads; nada é apagado; status tem histórico por guia |
| Envio e-mail/WhatsApp | Feature FUTURA (fora desta spec) |
| Visual | Padrão do app PF (azul #1C5A8A, cartões brancos) + referência dos modelos HTML em `G:\Dashboard - Contas a Receber\Modelos\` (KPI cards, badges coloridos, linhas com glosa em destaque) |

## 3. Fonte de dados — DACM formato ANS (Porto Saúde)

Inspecionado (somente leitura) em `G:\Dashboard - Contas a Receber\Convênios\Porto Saúde\DACM _PORTO_SAÚDE_15.07.26.xls`:

- **66 abas** — cada aba = 1 guia (com cabeçalho do protocolo repetido); **9 protocolos**, **~57 guias**.
- **Guias grandes são quebradas em várias abas consecutivas** (mesma guia, itens continuados; ex.: guia 73685102 em 5 abas com 17+17+17+17+14 itens). O parser CONCATENA as abas consecutivas da mesma guia em uma única guia (totais vêm do bloco `TOTAL DA GUIA`, repetido em cada aba).
- Formato ANS numerado (campos 1-48), posições estáveis por rótulo de linha:
  - `2-Nº` → número do DACM (ex.: 14880859)
  - `1 - REGISTRO ANS` / `3 - NOME DA OPERADORA` / `4 - CNPJ` / `5 - DATA DE EMISSÃO`
  - `6 - CÓDIGO NA OPERADORA` / `7 - NOME DO CONTRATADO` / `8 - CÓDIGO CNES`
  - `9 - NÚMERO DO LOTE` / `10 - NÚMERO DO PROTOCOLO` / `11 - DATA DO PROTOCOLO` / `13 - CÓDIGO DA SITUAÇÃO DO PROTOCOLO`
  - `14 - NÚMERO DA GUIA DO PRESTADOR` / `15 - NÚMERO DA GUIA ATRIBUÍDO PELA OPERADORA` / `16 - SENHA`
  - `48 - NOME SOCIAL` / `17 - NOME DO BENEFICIÁRIO` / `18 - NÚMERO DA CARTEIRA`
  - `19/21 - DATA INÍCIO/FIM DO FATURAMENTO` / `24 - CÓDIGO DA SITUAÇÃO DA GUIA`
  - **Itens** (bloco `25 - DATA DE REALIZAÇÃO` em diante): `26 - TABELA`, `27 - CÓDIGO DO PROCEDIMENTO`, `28 - DESCRIÇÃO`, `29 - GRAU DE PARTICIPAÇÃO`, `30 - VALOR INFORMADO`, `31 - QUANT. EXECUTADA`, `32 - VALOR PROCESSADO`, `33 - VALOR LIBERADO`, `34 - VALOR GLOSA`, `35 - CÓDIGO DA GLOSA` (numérico, ex.: 1714, 1705)
  - `TOTAL DA GUIA` (36-39) · `TOTAL DO PROTOCOLO` (40-43) · `TOTAL GERAL` (44-47)
- **Robustez**: há 1 aba anômala no arquivo (cabeçalho deslocado). O parser localiza valores PELO RÓTULO da linha (não por linha fixa) e pula abas sem guia, registrando aviso.
- **Sem status de recurso no DACM** — status vive só no sistema (registro na tela).
- Totais do arquivo de exemplo: informado/processado R$ 25.276,60 · liberado R$ 24.613,40 · **glosado R$ 663,20**.

**Motivo de glosa** exibido = descrição do item glosado + código da glosa (ex.: "GLICOSE - PESQUISA E/OU DOSAGEM [1714]").

## 4. Arquitetura

```
app_streamlit.py (gate de login existente)
  └─ usuário com acesso_glosas=1 → página Portal (default) + páginas de glosas no nav
parser_dacm.py   → lê DACM ANS (.xls via xlrd; .xlsx via openpyxl) → dict estruturado
banco_glosas.py  → dados/dacm_glosas.db (schema + CRUD + regras de importação)
app_pages/
  portal.py           → 2 cards: Atualização PF · Dashboard de Glosas
  upload_dacm.py      → upload com prévia, confirmação e resultado
  dashboard_glosas.py → filtros + KPIs + 4 blocos (Plotly)
  recursos_glosa.py   → painel de recursos: status, em lote, avisos, histórico
banco.py (PF)     → + coluna usuarios.acesso_glosas (migração) e helpers
administracao.py  → checkbox "Acesso ao Dashboard de Glosas" por usuário (admin)
```

**Arquivos novos:** `parser_dacm.py`, `banco_glosas.py`, `app_pages/portal.py`, `app_pages/upload_dacm.py`, `app_pages/dashboard_glosas.py`, `app_pages/recursos_glosa.py`, `tests/test_parser_dacm.py`, `tests/test_banco_glosas.py`.
**Modificados:** `app_streamlit.py`, `banco.py`, `app_pages/administracao.py`, `ui_comum.py` (CSS do portal/cards/badges), `requirements.txt` (+ `plotly>=6.0`; `xlrd` já existe).

## 5. Banco de dados (`dados/dacm_glosas.db`)

```
convenios     (id PK, nome UNIQUE, registro_ans, cnpj, criado_em)
uploads       (id PK, convenio_id FK, nome_arquivo, num_dacm, data_emissao,
               guias_novas, guias_atualizadas, usuario, criado_em)
guias         (id PK, convenio_id FK, upload_id FK,
               guia_prestador, guia_operadora, senha, lote, protocolo,
               data_protocolo, beneficiario, nome_social, carteira,
               data_inicio, data_fim, cod_situacao_guia,
               vl_informado, vl_processado, vl_liberado, vl_glosa,
               status_recurso, vl_recuperado, observacao,
               aviso_glosa_zerada INTEGER DEFAULT 0,
               atualizado_em,
               UNIQUE(convenio_id, guia_prestador))
itens_guia    (id PK, guia_id FK, data_realizacao, tabela, cod_procedimento,
               descricao, grau_participacao, quantidade,
               vl_informado, vl_processado, vl_liberado, vl_glosa, cod_glosa)
recursos_hist (id PK, guia_id FK, status_de, status_para, vl_recuperado,
               observacao, usuario, atualizado_em)   -- append-only
```

- Datas em **ISO** (`aaaa-mm-dd`) no banco; exibição em `dd-mm-aaaa` (reusa `formatar_data_br` do `ui_comum.py`).
- `data_inicio` da guia = menor `data_realizacao` dos itens (eixo da evolução mensal).
- A coluna `status_recurso` em `guias` é o estado ATUAL; `recursos_hist` guarda todas as mudanças (quem/quando/de/para).

## 6. Parser (`parser_dacm.py`)

```python
parse_dacm_ans(caminho) -> {
    "metadados": {num_dacm, operadora, registro_ans, cnpj, data_emissao,
                  codigo_na_operadora, contratado, cnes,
                  tot_geral_informado, tot_geral_processado,
                  tot_geral_liberado, tot_geral_glosa},
    "guias": [  # já concatenadas (abas consecutivas da mesma guia = 1 guia)
        {lote, protocolo, data_protocolo, cod_situacao_protocolo,
         guia_prestador, guia_operadora, senha,
         beneficiario, nome_social, carteira,
         data_inicio_fat, data_fim_fat, cod_situacao_guia,
         vl_informado, vl_processado, vl_liberado, vl_glosa,  # total da guia
         itens: [{data_realizacao, tabela, cod_procedimento, descricao,
                  grau_participacao, quantidade,
                  vl_informado, vl_processado, vl_liberado, vl_glosa, cod_glosa}]}],
    "avisos": ["SheetX ignorada: sem guia", ...]
}
```

Regras do parser:
- Localiza cada campo pelo **rótulo** da linha (tolera linhas deslocadas), nunca por posição fixa absoluta.
- Concatena abas consecutivas com a mesma `(lote, protocolo, guia_prestador)`; totais da guia vêm do bloco `TOTAL DA GUIA` (repetido, idêntico).
- Datas `dd/mm/aaaa` → ISO. Números com vírgula são tratados (xlrd já devolve float para célula numérica).
- Aba sem guia → pula e registra aviso. Arquivo ilegível/sem guias → erro claro (`ValueError` com mensagem amigável em Pt-br).
- **Somente leitura** (xlrd/openpyxl nunca salvam o arquivo de entrada).

## 7. Importação (`upload_dacm.py` + `banco_glosas.py`)

Fluxo: escolher arquivo (.xls/.xlsx) → parser roda → **prévia** (convênio detectado com nome editável, nº DACM, data de emissão, nº de guias, guias com glosa, totais, avisos do parser, conferência: soma das guias × totais gerais) → usuário confirma → importação → resultado.

Regras de importação (`banco_glosas.importar_dacm(conn, parsed, convenio_nome, usuario)`):
1. Convênio: procura por `nome`; se não existe, cria (registro_ans/cnpj do arquivo).
2. Para cada guia:
   - **Nova** (`(convenio, guia_prestador)` não existe): insere guia + itens; `status_recurso` inicial = `A iniciar recurso` se `vl_glosa > 0`, senão `Livre de Glosa`; registra `recursos_hist` (— → inicial).
   - **Existente**: atualiza valores/totais/itens (itens são substituídos), `upload_id` passa a ser o novo; **mantém** `status_recurso`, `vl_recuperado`, `observacao`. Se `vl_glosa` anterior > 0 e novo == 0 → `aviso_glosa_zerada = 1`. Se mudar o status manualmente ou confirmar o aviso → zera o flag.
3. Grava `uploads` (nome do arquivo original sanitizado, nº DACM, data de emissão, contagem novas/atualizadas, usuário) e **copia o arquivo original** para `dados/uploads_dacm/<nome seguro>` (histórico; nada é apagado).
4. Retorna `{novas, atualizadas, avisos_glosa_zerada}` exibido na tela.

## 8. Páginas

### 8.1 Portal (`portal.py`) — default após o login quando o usuário tem acesso
2 cards grandes clicáveis (ícone + título + descrição), visual do app: **Atualização PF** e **Dashboard de Glosas**. Nav superior lista todas as páginas (grupos por sistema no título: "PF · …" e "Glosas · …").

### 8.2 Dashboard (`dashboard_glosas.py`)
- **Filtros**: convênio (todos/um), período (data_inicio de/até), status do recurso.
- **KPI cards** (visual dos modelos HTML): Total Processado · Total Liberado · Total Glosado · Taxa de Glosa (glosa/processado) · Em Recurso (a iniciar + em análise) · Taxa de Recuperação (vl_recuperado das "Glosa Recebida" / glosa total) · Perda Real (glosa das "Recurso Negado").
- **Bloco 1 — Glosa por convênio**: barras por convênio (processado × liberado × glosado) + % de glosa.
- **Bloco 2 — Evolução mensal**: linhas glosado × recuperado por mês (data_inicio).
- **Bloco 3 — Painel de recursos por guia**: tabela resumo (guia, beneficiário, protocolo, glosa, status, dias em aberto desde `data_protocolo`, valor recuperado) + atalho para a página Recursos.
- **Bloco 4 — Motivos de glosa**: ranking (barras horizontais) de descrição + código de glosa, por valor.
- **Alertas de decisão** (cards no topo): guias "A iniciar recurso" há > 30 dias e > 60 dias (aging), guias com aviso de glosa zerada.
- Gráficos: Plotly (`st.plotly_chart`), cores dos status (azul #3b82f6 / verde #22c55e / amarelo #eab308 / vermelho #ef4444), rodapé `VERSAO`.

### 8.3 Recursos de glosa (`recursos_glosa.py`)
- Filtros: convênio, status, busca (guia/beneficiário), checkbox "somente avisos (glosa zerada)".
- Tabela por guia: guia, beneficiário, protocolo, data protocolo, glosa, **status (edição na linha)**, **vl_recuperado**, observação.
- **Edição em lote**: selecionar várias (checkbox) → definir status (+ vl_recuperado) → Aplicar. Toda mudança grava em `recursos_hist` (usuário + data).
- **Aviso de glosa zerada**: badge na linha + botão "Confirmar como Glosa Recebida" (individual) e "Confirmar todas" (lote) — 1 clique.
- Expander por guia: histórico de mudanças (`recursos_hist`).
- Quando o status vira `Glosa Recebida`, `vl_recuperado` default = `vl_glosa` da guia (editável).

### 8.4 Administração (modificação)
Seção "Acesso ao Dashboard de Glosas": checkbox por usuário (só admin enxerga/edita). Grava em `usuarios.acesso_glosas` (banco do PF).

## 9. Integração com o app PF

- `banco.py`: `inicializar_banco` garante a coluna `usuarios.acesso_glosas` (ALTER TABLE tolerante a já-existir); `usuario_atual()` de `auth.py` passa a incluir `acesso_glosas` na sessão.
- `app_streamlit.py`: páginas de glosas + portal entram no `st.navigation` **somente** quando o usuário logado tem `acesso_glosas`; sem a flag, comportamento idêntico ao atual.
- `ui_comum.py`: CSS dos cards do portal, badges de status e KPI cards; `VERSAO` nova.
- Login, "Manter conectado", bloqueio de tentativas: inalterados.

## 10. Segurança e restrições

- Upload aceito: `.xls` / `.xlsx` (type do file_uploader); parser somente leitura (nunca reescreve o arquivo enviado).
- Nome de arquivo salvo sanitizado (`os.path.basename` + regex como em `fotos.py`), nunca escapa de `dados/uploads_dacm/`.
- Nenhum segredo versionado; deploy só com autorização explícita do Leonardo (R17 em vigor).
- Acesso às páginas de glosas controlado pela flag por usuário.

## 11. Testes (TDD)

- `tests/test_parser_dacm.py`: fixture .xls pequena gerada em teste (xlwt ou xlsx→xls via xlwt) com 2 abas (1 guia quebrada em 2 abas + 1 guia simples) → concatenação, totais, datas ISO, código de glosa, aba sem guia ignorada; arquivo ilegível → erro claro.
- `tests/test_banco_glosas.py`: importar 2× o mesmo DACM → 2ª vez atualiza (0 novas, N atualizadas, sem duplicar); guia nova com glosa → "A iniciar recurso"; sem glosa → "Livre de Glosa"; reenvio com glosa zerada → `aviso_glosa_zerada=1` e status mantido; confirmar aviso → status "Glosa Recebida" e flag zerado; `recursos_hist` registra mudanças.

## 12. Deploy

- `requirements.txt` + `plotly>=6.0` (xlrd já presente). Instalar no VPS (ambiente do serviço `atualizacao-pf`) antes/na hora do deploy.
- Deploy dos arquivos com backup, py_compile, restart e verificação (mesmo procedimento padrão; autorização do Leonardo por mensagem).

## 13. Fora de escopo (futuro)

- Parser de **PDF** (DACM ANS em PDF, pdfplumber) — mesmo formato de campos.
- Planilha "Detalhamento de Guias" (.xlsx com colunas montadas pelo Leonardo, ex.: Petrobras) — parser próprio por colunas (mapeamento case-insensitive).
- Envio do relatório por **e-mail/WhatsApp** (SMTP lsm.ia.br; WhatsApp exige provedor — confirmar depois).
- Versionamento do repositório no GitHub com deploy por Actions (pendência T11).
