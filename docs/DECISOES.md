# Registro de decisões

Formato: **D-nnn — título** · data · status (`proposta` = aguarda sua aprovação; `aprovada`; `substituída`) · decisão · motivo.

## Fase 0

**D-001 — Manter a stack padrão da especificação** · 10/10/2026 · proposta
Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pandas, PostgreSQL 16, Next.js + TypeScript + Tailwind, pytest, Vitest/Playwright e Docker Compose.
Motivo: nenhuma necessidade técnica do escopo exige trocar a stack.

**D-002 — APScheduler em container `worker` separado, sem Celery/Redis** · 10/10/2026 · proposta
Usar o APScheduler com job store no PostgreSQL, rodando na mesma imagem do backend, mas em processo separado.
Motivo: são poucas dezenas de jobs diários, então o Redis seria mais um serviço sem ganho real. Separar o worker da API evita que a ingestão pese nas requisições. A troca para Celery fica isolada em `app/jobs/`.

**D-003 — ECharts como biblioteca de gráficos** · 10/10/2026 · proposta
Usar o ECharts em vez do Recharts.
Motivo: o projeto precisa de mapas de calor (matriz de correlação e tabela de sensibilidade), séries longas de cotações (desempenho com milhares de pontos) e fronteira eficiente (dispersão). O ECharts cobre tudo isso nativamente; com o Recharts, o mapa de calor teria de ser feito à mão.

**D-004 — Dados em dois níveis: origem + padronizado** · 10/10/2026 · proposta
Guardar as linhas das demonstrações como vieram (`demonstracao_linha`, com todas as versões) e uma visão padronizada (`demonstracao_padronizada`) gerada por uma tabela de mapeamento de contas.
Motivo: a rastreabilidade exige mostrar a conta de origem. Além disso, o mapeamento pode ser corrigido e os dados reprocessados sem baixar tudo de novo.

**D-005 — Indicadores materializados com os parâmetros padrão; parâmetros do usuário calculados na hora** · 10/10/2026 · proposta
Motivo: a lista e o screening padrão ficam rápidos, e os parâmetros personalizados não multiplicam o armazenamento. A tabela `indicador_calculado` guarda os insumos e a procedência de cada número, que alimentam o tooltip.

**D-006 — Registro único de metodologias** · 10/10/2026 · proposta
Cada métrica declara fórmula, livro, parâmetros padrão e limitações num registro em Python. Esse registro gera a página "Como é calculado", a validação de parâmetros da API e o recálculo.
Motivo: uma fonte única evita que o texto da página e o código divirjam.

**D-007 — Demonstração consolidada por padrão, com recurso à individual** · 10/10/2026 · proposta
Quando a empresa não publica a consolidada, usar a individual e marcar isso no registro.

**D-008 — Bancos e seguradoras: indicadores não aplicáveis ficam "indisponíveis"** · 10/10/2026 · proposta
EV/EBIT, EV/EBITDA, DL/EBITDA, ROIC e margem bruta não se aplicam a esses setores. Eles aparecem como indisponíveis, com motivo, e essas empresas ficam excluídas do ranking de Greenblatt por padrão, como prevê o próprio livro.

**D-009 — FNET: só metadados e link** · 10/10/2026 · proposta
Não copiar os PDFs do FNET; guardar metadados e o link para o original.
Motivo: termos de acesso automatizado não confirmados, além de economia de armazenamento.

**D-010 — Não usar yfinance, Status Invest, Ward ou endpoints não oficiais do Tesouro** · 10/10/2026 · aprovada (exigência da especificação/termos de uso)

**D-011 — Arquivos brutos guardados em volume para auditoria** · 10/10/2026 · proposta
Cada arquivo baixado fica em `dados_brutos/<fonte>/<data>/`, com o hash registrado em `lote_ingestao`.

## Fase 1

**D-012 — Respostas da Fase 0 incorporadas** · 10/10/2026 · aprovada
- Uso **pessoal** por enquanto: brapi gratuita + COTAHIST para preços. Licença de exibição comercial não é necessária agora.
- Dependências aprovadas: httpx, openpyxl, pydantic-settings, psycopg, argon2-cffi, PyJWT, scipy, ruff, echarts. APScheduler e @playwright/test já estavam na stack.
- Os 20 ativos de validação propostos foram aceitos (`TICKERS_ACOMPANHADOS` no `.env`).
- Definições ambíguas: ver D-019 (respondidas pelo usuário).

**D-013 — Indicadores básicos já na Fase 1** · 10/10/2026 · aprovada (pedido do usuário)
A Fase 1 calcula e exibe os principais indicadores do tipo dos sites de análise (P/L, P/VP, PSR, EV/EBIT, EV/EBITDA, ROE, ROIC, ROA, margens, endividamento, liquidez, CAGR de 5 anos e, para FIIs, P/VP, VP/cota, patrimônio, cotistas e DY informado). Eles vêm de funções puras em `app/metodologias/` com testes. Nenhum dado é obtido de sites de terceiros: tudo sai das fontes oficiais.

**D-014 — Múltiplos por ticker** · 10/10/2026 · aprovada
P/L, P/VP e demais múltiplos de preço usam a cotação do próprio ticker × o total de ações em circulação (equivale a preço ÷ LPA). O valor de mercado e o EV usam a soma de cada classe × a sua cotação. Classe sem negociação é valorada pela cotação da outra classe, com aviso no número.

**D-015 — COTAHIST prevalece sobre a brapi no mesmo pregão** · 10/10/2026 · aprovada
O COTAHIST (B3) é a fonte oficial e sobrescreve a cotação da brapi para o mesmo dia. A brapi só preenche o pregão mais recente, enquanto o arquivo diário da B3 não chega.

**D-016 — Precisão numérica e unicidade** · 10/10/2026 · aprovada
Valores em `NUMERIC(30,10)`: com 6 casas, os índices eram arredondados de forma visível. A unicidade das linhas de demonstração usa `NULLS NOT DISTINCT`, porque linhas de balanço não têm data de início; sem isso a reingestão duplicava linhas (bug achado nos testes).

**D-017 — Lote de ingestão aberto antes do download** · 10/10/2026 · aprovada
Falhas de rede ficam registradas em `lote_ingestao` com status `erro`. Dados anteriores nunca são apagados.

**D-018 — Indicadores de FII com base nos informes da CVM** · 10/10/2026 · aprovada
Enquanto não há proventos (brapi paga), o DY por proventos do FII aparece como indisponível. O "DY informado" (soma dos percentuais mensais que o administrador declara à CVM) é mostrado à parte, com rótulo e limitação explícitos.

**D-019 — Definições de métricas respondidas pelo usuário** · 10/10/2026 · aprovada
- **JCP:** os cálculos (DY, payout e, na Fase 2, Bazin) usam o valor **líquido** de IR na fonte, com alíquota como parâmetro (padrão 15%). O banco guarda o valor bruto declarado. Onde o JCP for exibido, mostrar líquido em destaque e bruto ao lado. Dividendos e rendimentos de FII entram pelo valor declarado.
- **Graham:** a fórmula original √(22,5 × LPA × VPA) não usa taxa de juros (22,5 = P/L 15 × P/VP 1,5). Na **fórmula revisada** V = LPA × (8,5 + 2g) × 4,4 ÷ Y, a taxa Y é a **Selic meta** vigente (série SGS 432), editável pelo usuário (D-020).
- **Peter Lynch:** preço justo **sem teto** no crescimento. Quando o crescimento passar de **25% a.a.** (parâmetro) ou vier de lucro-base muito baixo ou negativo, o número aparece com o aviso "crescimento atípico: verifique a origem (efeito de base, evento não recorrente)".
- **Data do provento no DY:** ver D-020.

**D-020 — DY pela data de pagamento; Selic no Graham revisado; limite de 25% no Lynch** · 10/10/2026 · aprovada
- A janela de 12 meses do DY, do payout e (Fase 2) do Bazin conta os proventos pela **data de pagamento**. Provento anunciado e ainda sem data de pagamento não entra. Substitui a recomendação inicial (data-com).
- Graham revisado: Y = Selic meta vigente.
- Lynch: aviso de "crescimento atípico" acima de 25% a.a. ou com lucro-base muito baixo/negativo.

---

## Perguntas em aberto

> Itens 1 a 11 e 15 respondidos (D-012, D-019, D-020). Os demais seguem abertos.

### Fontes e custos
1. **Cotações e proventos BR.** A recomendação é a brapi.dev, plano Startup (~R$ 100–120/mês), porque o plano gratuito não traz proventos.
   - Posso começar a Fase 1 com o plano gratuito da brapi + COTAHIST para preços e deixar os proventos para quando você contratar o plano pago?
   - Ou você prefere outra fonte?
2. **Cotações EUA.** Proponho decidir só na Fase 7. Uma licença para exibir dados a usuários finais costuma custar muito mais que os planos pessoais. O produto será **de uso pessoal/privado** ou **público e pago**? A resposta muda a escolha de provedores no Brasil e nos EUA, e também a consulta à B3 sobre o COTAHIST.
3. **Damodaran.** Se o produto for comercial, você quer que eu prepare um e-mail pedindo permissão de uso?

### Dependências fora da stack padrão (preciso de aprovação para cada uma)
4. Backend:
   - `httpx`: cliente HTTP da ingestão;
   - `openpyxl`: .xlsx com fórmulas abertas;
   - `pydantic-settings`: leitura do `.env`;
   - `psycopg[binary]`: driver PostgreSQL;
   - `argon2-cffi` + `PyJWT`: hash de senha e sessão;
   - `scipy`: otimizador de Markowitz e paridade de risco com restrições; a alternativa é implementar só com numpy, com mais código e menos robustez;
   - `numpy`: já vem com o pandas;
   - `ruff`: lint, só em desenvolvimento.
5. Frontend:
   - `echarts`;
   - `@playwright/test` e `vitest`, já previstos na stack.

### Definições de métricas ambíguas (condição de parada da especificação)
6. **Dividend yield — data de referência do provento.** Opções:
   - (a) por **data-com**: provento "pertence" a quem tinha a ação naquele dia;
   - (b) por **data de pagamento**.
   **Recomendo (a)**, por casar com o preço vigente no período. O critério ficaria explícito na página "Como é calculado".
7. **JCP no DY e no Bazin:** valor bruto ou líquido de IR (15%)? **Recomendo bruto**, com opção "líquido" no screening.
8. **Ações com várias classes (ON/PN/UNIT):** recomendo calcular o valor de mercado como a soma de cada classe × a sua própria cotação, e o LPA/VPA por ação total da empresa (excluídas as ações em tesouraria). P/L e P/VP de cada ticker usam a cotação desse ticker.
9. **Graham revisado — taxa Y** (AAA corporativo no original). Recomendo a taxa do **Tesouro Prefixado mais longo** como proxy nominal, configurável (alternativas: Selic ou NTN-B + IPCA esperado).
10. **"Taxa Peter Lynch" do screening.** Proposta: preço justo = LPA × P/L justo, com P/L justo = crescimento do lucro (% a.a.) limitado ao teto definido pelo usuário (padrão 25). Isso corresponde à regra de Lynch PEG = 1. Concorda, ou você tem outra definição em mente?
11. **Crescimento usado no PEG/Lynch e no Graham revisado:** CAGR do LPA em 5 anos (recomendado) ou crescimento projetado digitado pelo usuário? Proponho o CAGR de 5 anos como padrão, editável.

### Escopo
12. Assinatura/planos, FAQ, chamados, blog e WhatsApp aparecem na especificação, mas em nenhuma fase. Confirma que ficam **fora** das Fases 0–8?
13. **Login:** as páginas públicas (lista, página do ativo, metodologias, ferramentas) ficam acessíveis sem login, e carteira, favoritos, valuations, diário e alertas exigem login? Recomendo que sim.
14. **Importação B3:** apenas pelo arquivo exportado da Área do Investidor (Excel de "Movimentação" e "Negociação")? A API da B3 para investidores exige parceria comercial.
15. **Universo de ativos:** todas as ações e todos os FIIs listados na B3, com validação inicial em 10 + 10? Você quer escolher os 20 ativos de validação, ou posso propor (ex.: PETR4, VALE3, ITUB4, WEGE3, ABEV3, EGIE3, MGLU3, RADL3, TAEE11, SUZB3; HGLG11, KNRI11, MXRF11, XPML11, VISC11, HGRU11, KNCR11, BTLG11, HSML11, RBRF11)?
16. **Pasta `docs/livros/`:** não existe no repositório. Vai adicionar anotações antes da Fase 2?
17. **Ambiente de produção:** por ora só local, via `docker compose`? Para os alertas por e-mail (Fase 8), será preciso um provedor SMTP, o que pode ter custo.
