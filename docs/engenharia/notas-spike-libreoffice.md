# Notas do spike — LibreOffice/UNO no arquivo Hias (Task 3)

**Status: BLOQUEADO NO PORTÃO DE ACEITE (Step 3) — nas DUAS versões testadas (24.2.7.2 e 26.2.5.2).** O round-trip LibreOffice **NÃO preserva** o arquivo Hias em nenhuma delas. Resta 1 caminho não testado (LibreOffice 26.8.0, pendente de instalação manual pelo usuário — ver fase 2). O plano precisa ser revisto pelo controlador com o usuário (opções do próprio plano: container Windows pago para o COM, reescrever as abas de pivô como estáticas, ou outra via).

## O que foi feito

- Arquivo real `Posição Financeira Hias.xlsx` (6.240.678 bytes, pen drive) copiado para o VPS em `/home/apppf/spike/` via SFTP/paramiko — **nunca no git** (R22).
- `spike/spike_roundtrip.py` (verbatim do brief): sobe um soffice headless dedicado (UserInstallation `/tmp/lo_spike`, socket 127.0.0.1:2002), abre o Hias real e salva como xlsx com `FilterName = "Calc MS Excel 2007 XML"`.
- Executado no VPS com o python3 do sistema (3.12.3), como usuário `apppf` (R24).
- openpyxl instalado no python3 do sistema para a comparação (R23): `pip3 install openpyxl` falhou por PEP 668 → `pip3 install --break-system-packages openpyxl` → openpyxl 3.1.5. Ferramenta de spike; não é dependência do app.

## Resultados reais

### Step 2 — round-trip (rodou OK, 1ª tentativa)

```
Warning: failed to launch javaldx - java may not function correctly
ROUNDTRIP OK -> /home/apppf/spike/spike_roundtrip.xlsx
```

O aviso `javaldx` é inofensivo (sem JRE no VPS — desnecessário para Calc/UNO). Saída: 5.470.750 bytes (original: 6.240.678).

### Step 3 — comparação (PORTÃO DE ACEITE FALHOU)

Comando verbatim do brief (openpyxl read-only/data_only + zipfile), saída integral:

```
DIF valores na aba Data Entrega
DIF valores na aba Data Vencimento
DIF valores na aba Data Recebimento
DIF valores na aba À Quitar
DIF valores na aba BD1
abas iguais: ['Data Entrega', 'Data Vencimento', 'Data Recebimento', 'À Quitar', 'BD1', 'BD2', 'Camp calculado'] | abas com dif: 5
pivotCacheParts: ['xl/pivotCache/pivotCacheRecords1.xml', 'xl/pivotCache/pivotCacheDefinition2.xml', 'xl/pivotCache/pivotCacheRecords2.xml', 'xl/pivotCache/_rels/pivotCacheDefinition1.xml.rels', 'xl/pivotCache/_rels/pivotCacheDefinition2.xml.rels', 'xl/pivotCache/pivotCacheDefinition1.xml'] -> ['xl/pivotCache/pivotCacheDefinition1.xml', 'xl/pivotCache/_rels/pivotCacheDefinition2.xml.rels', 'xl/pivotCache/_rels/pivotCacheDefinition1.xml.rels', 'xl/pivotCache/pivotCacheRecords1.xml', 'xl/pivotCache/pivotCacheDefinition2.xml', 'xl/pivotCache/pivotCacheRecords2.xml']
slicers: ['xl/slicerCaches/slicerCache5.xml', 'xl/slicerCaches/slicerCache1.xml', 'xl/slicerCaches/slicerCache2.xml', 'xl/slicerCaches/slicerCache3.xml', 'xl/slicerCaches/slicerCache4.xml', 'xl/slicerCaches/slicerCache6.xml', 'xl/slicerCaches/slicerCache7.xml', 'xl/slicers/slicer1.xml', 'xl/slicers/slicer2.xml', 'xl/slicers/slicer3.xml', 'xl/slicers/slicer4.xml'] -> []
```

Diagnóstico complementar (somente leitura, nenhum arquivo alterado) — contagem de células com dif e primeira célula divergente por aba:

```
Data Entrega      | linhas: 20205 -> 49   | células com dif: 539  | primeira: (10, 1, 'Convênio', None)
Data Vencimento   | linhas: 3169  -> 49   | células com dif: 539  | primeira: (10, 1, 'Convênio', None)
Data Recebimento  | linhas: 3169  -> 49   | células com dif: 496  | primeira: (10, 1, 'Convênio', None)
À Quitar          | linhas: 421   -> 421  | células com dif: 190  | primeira: (4, 1, 'CONVÊNIO', 'Convênio')
BD1               | linhas: 34111 -> 34111| células com dif: 3785 | primeira: (5378, 15, 5.3922001471670296, 5.39220014716703)
BD2               | linhas: 1020  -> 1020 | células com dif: 0    | primeira: None
Camp calculado    | linhas: 21    -> 21   | células com dif: 0    | primeira: None
```

## Interpretação (fatos registrados)

1. **Slicers PERDIDOS.** Os 7 `slicerCaches` e 4 `slicers` do original não existem na saída — o LibreOffice 24.2 não suporta slicers e os descarta ao salvar xlsx. É a mesma destruição que a Global Constraint proíbe no openpyxl; o LO desta versão faz o mesmo. (Suporte a slicers no Calc só foi introduzido no LibreOffice 25.2.)
2. **Pivôs re-renderizados e encolhidos.** As abas de pivô caíram de 20.205/3.169/3.169 linhas para 49 — o LO re-renderizou os pivôs e a maior parte do resultado cacheado pelo Excel desapareceu da saída.
3. **Fórmulas recalculadas na BD1.** 3.785 células com dif, todas de valores cacheados de fórmula levemente diferentes (ex.: `5.3922001471670296` → `5.39220014716703`) — o LO recalcula e grava resultados distintos dos cacheados pelo Excel.
4. **pivotCache* preservados.** A lista de partes `pivotCache*` é idêntica na saída (mesmos 6 nomes).
5. **BD2 e "Camp calculado" intactos.** 0 difs — abas de dados puros sobreviveram ao round-trip.

## O que funcionou (nomes de API confirmados nesta etapa)

- Subir soffice headless dedicado e conectar via UNO, como `apppf`, com o python3 do sistema:
  `subprocess.Popen(["soffice", "--headless", "--invisible", "--norestore", "--nologo", "-env:UserInstallation=file:///tmp/lo_spike", "--accept=socket,host=127.0.0.1,port=2002;urp;StarOffice.ServiceManager"])` + `uno.getComponentContext()` + `UnoUrlResolver.resolve(...)` + `Desktop.loadComponentFromURL(...)` — conectaram de primeira, sem retry.
- `doc.storeToURL("file://" + caminho, (_prop("FilterName", "Calc MS Excel 2007 XML"),))` — salva xlsx sem erro.
- `doc.close(False)` — OK.
- `loadComponentFromURL` aceitou a URL com espaços e acentos no nome do arquivo (`file:///home/apppf/spike/Posição Financeira Hias.xlsx`).
- Leitura do arquivo real com openpyxl read-only/data_only + zipfile — OK (avisos "Slicer List extension is not supported" são esperados: openpyxl só LÊ; jamais gravar).

## O que NÃO foi testado

Os Steps 4–5 (`spike/spike_uno_ops.py`) **não foram executados**: o portão de aceite do Step 3 determinou parada imediata, sem adaptações (decisão do controlador). Ficam sem confirmação as APIs de pivô (`DataPilotTables`, `refresh()`, `RowFields`, `Items`, `ShowDetails`), `DatabaseRanges` (tabelas estruturadas) e escrita de células/fórmulas — embora a falha do round-trip já torne a decisão de engine independente delas.

## Decisão do spike

- **Engine = UNO com LibreOffice 24.2.7.2 e 26.2.5.2: REPROVADO nas duas.** O round-trip viola a Global Constraint (slicers destruídos) e altera valores cacheados de pivôs e fórmulas — exatamente o que a integração não pode fazer. Subir a versão dentro da mesma família (26.2) não mudou NADA: mesmas 5 abas com dif e mesmos slicers perdidos.
- Caminho restante: **LibreOffice 26.8.0** (o suporte a slicers no Calc chegou no 25.2, mas o 26.2 ainda perde os slicers deste arquivo — o 26.8 pode se comportar diferente; sem garantia).
- Revisão do plano pendente com o controlador/usuário (fallbacks já previstos no plano: container Windows pago, abas de pivô estáticas — decisão do controlador).

## Fase 2 — LibreOffice 26.2.5.2 (Fresh, via PPA oficial)

Instalado **pessoalmente pelo usuário** (a instalação via SSH era negada pelo sistema de permissões do Claude Code; o usuário fez por PuTTY). Verificação: `soffice --version` → `LibreOffice 26.2.5.2 620(Build:2)`; `python3 -c 'import uno'` → `uno OK`; pacote `libreoffice-calc 4:26.2.5.2-0ubuntu0.24.04.1~lo1` (PPA registrado).

### Gate (round-trip a partir do arquivo ORIGINAL + comparação do Step 3) — FALHOU de novo

Round-trip: `ROUNDTRIP OK -> /home/apppf/spike/spike_roundtrip.xlsx` (sem o aviso javaldx desta vez). Saída: 5.472.941 bytes.

```
DIF valores na aba Data Entrega
DIF valores na aba Data Vencimento
DIF valores na aba Data Recebimento
DIF valores na aba À Quitar
DIF valores na aba BD1
abas iguais: ['Data Entrega', 'Data Vencimento', 'Data Recebimento', 'À Quitar', 'BD1', 'BD2', 'Camp calculado'] | abas com dif: 5
pivotCacheParts: [mesmas 6 partes do original] -> [mesmas 6 partes na saída]
slicers: ['xl/slicerCaches/slicerCache1..7.xml', 'xl/slicers/slicer1..4.xml'] -> []
```

Diagnóstico read-only:

```
Data Entrega      | linhas: 20205 -> 48   | células com dif: 493  | primeira: (10, 1, 'Convênio', 'Row Labels')
Data Vencimento   | linhas: 3169  -> 48   | células com dif: 493  | primeira: (10, 1, 'Convênio', 'Row Labels')
Data Recebimento  | linhas: 3169  -> 48   | células com dif: 451  | primeira: (10, 1, 'Convênio', 'Row Labels')
À Quitar          | linhas: 421   -> 421  | células com dif: 191  | primeira: (3, 1, None, 'Convênio')
BD1               | linhas: 34111 -> 34111| células com dif: 3785 | primeira: (5378, 15, 5.3922001471670296, 5.39220014716703)
BD2               | linhas: 1020  -> 1020 | células com dif: 0    | primeira: None
Camp calculado    | linhas: 21    -> 21   | células com dif: 0    | primeira: None
```

**Conclusão do 26.2.5:** mesmo padrão do 24.2 — pivôs re-renderizados (cabeçalho "Row Labels" e encolhimento de 20.205/3.169/3.169 para 48 linhas), 3.785 células de fórmula da BD1 recalculadas com dif de float, **11 partes de slicer (7 slicerCaches + 4 slicers) eliminadas**. pivotCache* preservados; BD2 e Camp calculado intactos.

### Fallback LibreOffice 26.8.0 — não testado nesta sessão

A instalação dessa versão é mudança de sistema via SSH como root e não foi autorizada pelo sistema de permissões (o critério exige mensagem direta do usuário nomeando o host e a mudança; repasses do controlador não contam). Não insisti, conforme orientação do controlador. Se o usuário quiser testar o 26.8.0, ele instala pessoalmente (como fez com o PPA) e o gate está pronto para rodar em seguida — com dois ajustes a verificar: binário em `/opt/libreoffice26.8/program/soffice` (os scripts do spike apontariam esse caminho absoluto) e compatibilidade do `python3-uno` dessa versão com o python3 3.12 do sistema (se não servir, reportar).

## Estado do VPS (deixado para a revisão do plano)

- **LibreOffice 26.2.5.2** (PPA, instalado pelo usuário) — substituiu o 24.2.7.2; `uno OK`.
- `/home/apppf/spike/`: arquivo original (intacto, 6.240.678 bytes) + `spike_roundtrip.py` + `spike_uno_ops.py` + `entrada_minima.py` + `spike_roundtrip.xlsx` (round-trip do 26.2.5), tudo de `apppf:apppf`.
- openpyxl 3.1.5 instalado no python3 do sistema (`--break-system-packages`).
- `spike/entrada_minima.py` (gerador da fixture mínima) validado localmente: gera BD2 com tabela `Tabela1` + BD1 com tabela `BD_1` (espelha o helper `_fazer_hias_minimo` dos testes da Task 4) — não chegou a ser usado no spike por causa do bloqueio.
- Aviso do VPS sobre kernel pendente (6.8.0-134 → 138): ignorado por enquanto; reboot fica para a Task 10.
