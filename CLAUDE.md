# CLAUDE.md — Atualização PF · Hospital Israelita Albert Sabin

## Identidade visual: claro minimalista

Direção estética aprovada: **minimalismo claro**, atmosfera clínica e profissional — ordem, clareza, nada decorativo. Fundo branco, um único acento azul-institucional, sem gradientes berrantes, sem sombras pesadas.

## Tokens

| Token | Valor |
|---|---|
| Fundo da página | `#FFFFFF` |
| Superfície / fundo secundário | `#F8FAFC` |
| Texto principal | `#0F172A` |
| Texto secundário | `#64748B` |
| Acento único (primário) | `#1C5A8A` — hover `#0F3B5C` |
| Borda | `#E2E8F0` |
| Sucesso | `#15803D` |
| Erro | `#DC2626` |
| Aviso | `#B45309` |
| Cabeçalho | Barra branca com borda `#E2E8F0` de 1px |
| Raio | `10px` (botões e cards) |

## Tipografia

- Texto: **Segoe UI** (fonte local do Windows — não usar Google Fonts; o app pode rodar sem internet)
- Código/log: **Consolas** (local)
- Títulos 700, corpo 400, tamanho base 14–16px

## Regras para qualquer agente

1. Não usar gradientes em botões ou superfícies; o acento é sempre cor sólida.
2. Máximo **1 cor de acento**; estados de status usam os tons semânticos da tabela.
3. Contraste de texto mínimo **4.5:1** (WCAG AA).
4. Sem emojis como ícones estruturais — usar SVG (Lucide) ou Material Symbols (`:material/...`).
5. Sombras só quando necessárias para elevação, nunca decorativas; **borda de 1px é o padrão** de separação.
6. Espaçamento em ritmo de 4/8px; respiro generoso entre seções.
7. Cabeçalho: barra branca com borda de 1px, logo do hospital (PNG transparente `Logo_Hias.png`) à esquerda e título centralizado; o restante da página é claro.
8. Tema Streamlit via `.streamlit/config.toml`; CSS injetado apenas para o que o config.toml não cobre (chrome do Streamlit, faixa do cabeçalho, cards customizados).
9. Lógica de processamento (`core.py`, fases 0–4) é **intocável** ao mexer na interface.
10. Este arquivo é lido pelo VS Code (Copilot) e pelo Claude Code — as regras valem para ambos.
