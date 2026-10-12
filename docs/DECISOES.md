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

## Fase 2

**D-021 — Motor de metodologias completo, calculado sob demanda** · 10/10/2026 · aprovada
As métricas dos 10 livros são funções puras em `backend/app/metodologias/` (um arquivo por livro/tema), todas no registro único com fórmula, premissas, parâmetros e limitações. Os métodos novos têm `exibir_no_ativo = False`: aparecem em "Como é calculado", mas só viram números na tela nas fases que os usam (screening na 3, valuation na 4, FIIs na 5, carteira na 6, longo prazo na 8). A pasta `docs/livros/` não existe; textos e parâmetros seguem as metodologias publicamente conhecidas, sem trechos dos livros.

**D-022 — Regras objetivas onde o livro deixa espaço para julgamento** · 10/10/2026 · aprovada (padrões editáveis)
- **Greenblatt:** capital de giro = (AC − caixa) − (PC − empréstimos de CP); quando negativo, conta como zero no capital empregado. EV ≤ 0 deixa o earnings yield indisponível e tira a empresa do ranking. Empate na soma: maior earnings yield primeiro.
- **Lynch, categorias, em ordem de precedência:**
  1. recuperação (último lucro ≤ 0 ou prejuízo nos 3 anos anteriores);
  2. cíclica (setor da lista ou coeficiente de variação dos lucros > 0,5);
  3. ativos ocultos (P/VP < 1);
  4. crescimento rápido (≥ 20% a.a.);
  5. robusta (10–20% a.a.);
  6. crescimento lento (< 10% a.a.).
- **Lynch, aviso de crescimento atípico:** também dispara quando o lucro-base é menor que 20% do lucro atual (efeito de base).
- **Graham, checklist defensivo:** receita mínima de R$ 2 bi (adaptação de porte ao Brasil), liquidez corrente ≥ 2, dívida LP ≤ capital de giro, 10 anos de lucro, 20 anos de dividendos, LPA +33% em 10 anos (médias de 3 anos), P/L ≤ 15 sobre o LPA médio de 3 anos, P/VP ≤ 1,5 ou P/L × P/VP ≤ 22,5. Critério sem dados conta como não atendido e é marcado como indisponível.
- **Bazin, critérios:** DL/PL ≤ 1 e proventos em todos os últimos 5 anos.
- **FII, Gordon ajustado:** usa por padrão a taxa do Tesouro líquida de 15% de IR (rendimentos de FII são isentos para a pessoa física), com opção da taxa bruta.
- **All Weather:** pesos de referência por classe (30/40/15/7,5/7,5), editáveis.

## Primeira carga com dados reais (11/10/2026)

**D-023 — Correções após a primeira carga real no computador do usuário** · 11/10/2026 · aprovada
Funcionou de primeira: cadastro CVM, FCA, DFP/ITR 2020–2026, informes de FII e Tesouro (formatos e URLs confirmados). Problemas encontrados e corrigidos:
- **Padronização:** empresas que mudaram a data de encerramento do exercício entregam dois DFP no mesmo ano. Fica o de data final mais recente. Uma empresa com falha não interrompe mais as demais.
- **COTAHIST:** dois cadastros de FII com o mesmo ISIN (fundo e classe, Resolução CVM 175) quebravam a ligação cota → fundo e, com isso, a gravação de todas as cotações. Agora cada cota liga a um único fundo (o cadastro mais recente).
- **Arquivo diário da B3:** não existe em fins de semana/feriados nem antes da publicação. Vira lote "sem_arquivo", não erro.
- **Banco Central (SGS):** respondeu algo que não era JSON para uma janela da série 432. Agora tenta 3 vezes, registra o trecho da resposta e segue para as demais janelas e séries.
- **brapi sem token:** só alguns tickers de teste respondem; os demais dão 401. O ticker é pulado sem abortar os outros, e o log sugere cadastrar o token gratuito.
- **Duas cargas simultâneas** (worker automático + comando manual): uma trava no PostgreSQL deixa só uma rodar por vez.

**D-024 — Busca sob demanda e ranking "Mais baratas"** · 11/10/2026 · aprovada (pedido do usuário)
- As páginas Ações e FIIs não listam mais tudo ao abrir. Mostram resultados só depois de 2 letras digitadas (ticker ou nome, até 20 resultados).
- A listagem geral fica na página **Mais baratas**: rankings de Greenblatt, Graham, Bazin e Lynch com parâmetros editáveis, liquidez mínima (padrão R$ 1 mi/dia), aviso de não recomendação, motivos de exclusão e link para "Como é calculado". Isso adianta o núcleo da Fase 3 (o screening com filtros completos, os favoritos e a exportação seguem pendentes).
- Valor intrínseco de Graham, preço teto de Bazin, PEG e preço justo de Lynch, e EY e ROC de Greenblatt passam a ser materializados por ação com os parâmetros padrão e aparecem na página do ativo, com o aviso.
- Página **Status dos dados**: último lote de cada fonte e contagens (ações com cotação, empresas com balanço etc.), para diagnosticar a carga sem usar o terminal.

**D-025 — Proventos pela B3 (ações) e pelo FNET (FIIs)** · 11/10/2026 · aprovada (usuário escolheu as opções 1 e 2)
- Fontes gratuitas e oficiais, para uso pessoal, em vez da brapi paga. Sites de terceiros (Status Invest, Investidor10, Fundamentus) continuam descartados por proibirem coleta automática.
- O vínculo do provento com o ticker é feito pelo ISIN (ações) ou pelo código de negociação/CNPJ do XML (FIIs).
- A data de pagamento divulgada depois do anúncio é atualizada no reprocessamento.
- Carga inicial: proventos B3 de todas as companhias e 13 meses de avisos do FNET. Atualização diária às 21h.
- Quando a fonte já carregou com sucesso, um ativo sem provento na janela tem DY = 0 (e não "dado indisponível").
- A brapi paga continua como plano B, caso a B3 mude as consultas.

**D-026 — Segunda rodada de testes reais (12/10/2026)** · aprovada
- Nenhuma cotação gravada no computador do usuário: proventos e indicadores de preço ficaram indisponíveis. O worker agora **completa uma carga parcial sozinho** ao reiniciar: se há balanços mas não há cotações (ou proventos), baixa o COTAHIST do ano atual e do anterior, os proventos e recalcula.
- A ligação cota → FII roda numa transação à parte: se falhar, as cotações são gravadas mesmo assim.
- O FCA trazia códigos que não são tickers da B3 (ex.: "8192"). Agora só entram códigos no padrão 4 letras + 1–2 dígitos, e os antigos são desativados.
- Busca: mostra "Buscando…" durante a pausa de digitação, em vez de "nenhum ativo encontrado".

**D-027 — Yahoo Finance para cotações e dividendos** · 12/10/2026 · aprovada (pedido do usuário)
- O usuário pediu para trocar a busca de dados pelo Yahoo Finance. Com `FONTE_MERCADO=yahoo` (padrão), cotações e dividendos de ações e FIIs vêm do Yahoo; COTAHIST, B3 e FNET ficam como alternativa (`FONTE_MERCADO=b3`). Isso substitui a recomendação de D-010 (não usar Yahoo), por decisão do usuário, para uso pessoal; os termos do Yahoo restringem uso automatizado.
- Balanços, cadastro, informes de FII, Selic/IPCA e Tesouro continuam nas fontes oficiais (CVM, BCB, Tesouro).
- FIIs passam a ter ticker criado a partir do ISIN do informe mensal da CVM (BRxxxxCTF… → xxxx11), sem depender do COTAHIST.
- Consequências nas regras de proventos (D-019/D-020) enquanto a fonte for o Yahoo:
  - o DY conta pela **data-ex**, porque o Yahoo não informa a data de pagamento;
  - JCP e dividendo não são separados, então entram pelo valor bruto;
  - ambas as limitações aparecem em "Como é calculado".
- Só a fonte de proventos configurada entra no DY, para não somar o mesmo provento duas vezes.
- Atualização diária às 19h, com os últimos 5 dias. Carga inicial: 6 anos de histórico.

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
