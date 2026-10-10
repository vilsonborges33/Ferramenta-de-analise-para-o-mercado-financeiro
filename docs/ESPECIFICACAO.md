# PROMPT PARA O CLAUDE CODE — PLATAFORMA DE ANÁLISE DE AÇÕES E FUNDOS IMOBILIÁRIOS

> Cole este texto inteiro no Claude Code, numa pasta vazia que será a raiz do projeto. Se quiser, salve também uma cópia como `docs/ESPECIFICACAO.md` dentro do projeto para o Claude Code reler a cada sessão.

---

## OBJETIVO

Construir uma aplicação web completa de análise fundamentalista de **ações e fundos imobiliários do Brasil** (B3) e do **mercado internacional** (ações dos EUA, REITs e ETFs), com screening, rankings, valuation, comparador, consolidador de carteira e ferramentas financeiras.

O diferencial do produto é que **toda métrica, ranking e valuation deriva explicitamente de uma metodologia de um dos 10 livros de referência** listados abaixo. Cada número exibido na tela deve ser rastreável até: (1) a fórmula, (2) o livro/autor que a fundamenta e (3) a fonte e a data do dado bruto.

A aplicação é uma ferramenta de análise. Ela **não emite recomendação de investimento**: toda tela de ranking, preço teto ou valuation deve exibir um aviso de que os resultados são cálculos a partir de parâmetros escolhidos pelo usuário e não constituem recomendação.

---

## CONTEXTO

### Produto de referência: Ward (ward.app.br)

O Ward é uma plataforma brasileira paga que já faz grande parte do que se quer. As funcionalidades abaixo foram levantadas nas páginas públicas e na estrutura do site. **Use-as como referência funcional, nunca como fonte de dados**: é proibido fazer scraping, chamar a API ou copiar textos, layout ou marca do Ward.

**Ferramentas gratuitas**
- Calculadora de juros compostos.
- Conversor de taxas equivalentes (diária, mensal, anual; taxa de entrada → taxa de saída).
- Plano de aposentadoria: investimento inicial, aporte mensal/anual, meta de dividendos mensais, projeção de dividendos no mês e no ano, horizonte em anos.

**Ações**
- Lista de ações com ticker, preço, variação, dividend yield, P/L, margem líquida, P/VP.
- Página do ativo (`/acoes/:ticker`): setor, subsetor, segmento de listagem; P/L, P/VP, EV/EBIT, EV/EBITDA, P/EBIT, P/EBITDA; ROE, ROIC; margens bruta, EBITDA e líquida; LPA, VPA, payout; dívida bruta, dívida líquida, DL/EBITDA, endividamento geral; receita e lucro líquido (anual e média), CAGR de receita e lucro; gráfico lucro × cotação; balanço patrimonial; histórico de proventos; documentos da CVM do emissor.
- Stock Screening: parâmetros editáveis por usuário (Taxa Bazin, padrão 6%; Taxa Graham, padrão 22,5; Taxa Peter Lynch); filtros P/L mín./máx., DL/EBITDA mín./máx., dividend yield mínimo, margem líquida, ROE, liquidez mínima; colunas de Valuation Bazin, Graham, Peter Lynch e Joel Greenblatt com ranking próprio em cada método; favoritos; busca; exportação/impressão.

**Valuation**
- Preço teto projetivo: lucro projetado, payout, yield mínimo exigido, margem de segurança, preço alvo, yield projetivo.
- Valuation por fluxo de caixa descontado: taxa de crescimento esperada, taxa de desconto, crescimento perpétuo (ajuste em passos de 0,5%), payout médio, ROE original do ativo, Selic atualizada.
- "Meus Valuations": salvar, resetar, comparar preços teto entre métodos.

**Fundos imobiliários**
- Lista e página do fundo (`/fiis/:ticker`): segmento e subsegmento, gestora, taxa de administração, taxa de performance, dividend yield 1/3/6/12 meses, P/VP, valor patrimonial por cota, liquidez média diária, número de cotistas e distribuição de cotistas, vacância, número de imóveis e lista de imóveis, patrimônio líquido, peso no IFIX, rentabilidade nominal e real, volatilidade, meses negativos, política de dividendos.
- Composição do ativo (imóveis para renda acabados/em construção, imóveis para venda, direitos reais, instrumentos financeiros), indicadores de endividamento (obrigações/ativo total) e de liquidez, yield patrimonial × yield de mercado.
- Preço teto por **Gordon ajustado**: crescimento esperado dos dividendos, prêmio exigido sobre a taxa do Tesouro (bruta e líquida), comparação com o retorno médio do IFIX.
- Portal de relatórios: Informe Mensal, Trimestral e Anual Estruturado e Relatório Gerencial, vindos do FNET/B3.
- Fund Screening / Ranking de fundos: filtros por DY, P/VP, liquidez, patrimônio, vacância, número de imóveis, segmento, crescimento.

**Outras funcionalidades**
- Comparador de ativos lado a lado.
- Consolidador de carteira: várias carteiras, classes de ativos, importação de posições e proventos pela Área do Investidor da B3, preço médio automático ou editável, proventos recebidos, yield on cost, yield médio mensal e anual, rentabilidade acumulada contra índices (CDI, IPCA, Ibovespa, IFIX), evolução do patrimônio, alocação por classe, maiores quedas, consolidação de aportes, carteira compartilhada por link (somente leitura).
- Notificações e alertas (e-mail; WhatsApp como fase posterior).
- Simulador de opções: estruturas com CALL/PUT, rolagem, volatilidade histórica e implícita, preço de equilíbrio, comparativo ação × ação + opções.
- Área do usuário, assinatura (plano mensal/anual), FAQ, abertura de chamados, blog.

### Base metodológica: os 10 livros

Os livros **não estão** no projeto. Implemente as metodologias publicamente conhecidas de cada um, com parâmetros configuráveis, e **nunca reproduza trechos dos livros**. Se existir a pasta `docs/livros/` com anotações ou resumos meus, leia esses arquivos antes da fase de metodologias e use-os para ajustar parâmetros e textos explicativos.

| # | Livro | O que deve virar funcionalidade |
|---|-------|---------------------------------|
| 1 | Investindo em Ações no Longo Prazo — Jeremy Siegel | Retorno real de longo prazo (descontada a inflação), reinvestimento de dividendos, reversão à média do P/L e CAPE (P/L de Shiller de 10 anos), prêmio de risco das ações contra renda fixa; gráfico de retorno acumulado real por classe de ativo. |
| 2 | Em Busca do Portfólio Perfeito — Andrew Lo e Stephen Foerster | Teoria moderna de portfólio: fronteira eficiente de Markowitz, CAPM e beta, índice de Sharpe, fatores (valor, tamanho, momento), diversificação. Otimizador de carteira sobre a carteira do usuário. |
| 3 | O Investidor de Bom Senso — John Bogle | Impacto de custos e taxas no retorno composto (taxa de administração de FII/ETF/fundo), comparação gestão ativa × índice, decomposição do retorno esperado (dividend yield + crescimento do lucro + variação do múltiplo). |
| 4 | A Fórmula Mágica — Joel Greenblatt | Ranking por soma de posições: earnings yield (EBIT/EV) e retorno sobre capital (EBIT / (capital de giro líquido + ativo fixo líquido)); exclusões configuráveis (financeiras, utilities, liquidez mínima). |
| 5 | Faça Fortuna com Ações — Décio Bazin | Preço teto = média dos dividendos pagos (padrão: últimos 12 meses, opção de média de N anos) ÷ yield mínimo (padrão 6%); critérios de endividamento baixo e regularidade de proventos. |
| 6 | O Investidor Inteligente — Benjamin Graham | Valor intrínseco √(22,5 × LPA × VPA); fórmula revisada V = LPA × (8,5 + 2g) × 4,4 / Y; margem de segurança; checklist do investidor defensivo (porte, liquidez corrente, histórico de lucros e dividendos, crescimento do LPA, P/L e P/VP máximos) com pontuação. |
| 7 | Batendo o Mercado — Peter Lynch | PEG; índice de Lynch (crescimento do lucro + dividend yield) ÷ P/L; classificação automática nas seis categorias de Lynch (crescimento lento, robustas, crescimento rápido, cíclicas, recuperação, ativos ocultos) com regras explícitas. |
| 8 | Valuation: Guia Fundamental e Modelagem em Excel | DCF completo: projeção de receita, margens, capex, capital de giro; FCFF e FCFE; WACC; valor terminal; tabela de sensibilidade (taxa × crescimento); exportação do modelo para .xlsx com fórmulas abertas. |
| 9 | Valuation — Aswath Damodaran | Custo de capital com CAPM + prêmio de risco país para o Brasil; modelo de desconto de dividendos (Gordon e dois estágios); valuation relativa por múltiplos do setor; ligação "narrativa → números" (premissas justificadas por texto do usuário). Usar os datasets públicos do Damodaran (ERP, risco país, betas setoriais) como fonte de parâmetros, com data de referência. |
| 10 | Princípios — Ray Dalio | Diversificação entre fontes de retorno pouco correlacionadas (matriz de correlação da carteira), alocação por paridade de risco / estilo All Weather, e um diário de decisões de investimento (tese, premissas, revisão posterior). |

Cada metodologia deve ter uma página "Como é calculado" com a fórmula, as premissas, os parâmetros padrão e as limitações.

---

## FONTES DE DADOS

Use somente fontes oficiais, abertas ou com termos de uso compatíveis. Antes de integrar cada fonte, confirme os termos de uso e registre a conclusão em `docs/FONTES_DE_DADOS.md`.

- **CVM — Dados Abertos**: DFP, ITR, FRE e cadastro de companhias; informes mensais, trimestrais e anuais de FII.
- **B3 / FNET**: documentos de FII (relatórios gerenciais, informes, fatos relevantes).
- **Banco Central — API SGS**: Selic, CDI, IPCA, câmbio.
- **Tesouro Direto**: taxas dos títulos públicos (referência para Gordon e custo de capital).
- **Cotações BR**: avaliar opções gratuitas/baratas (ex.: brapi.dev) e apresentar as alternativas antes de escolher.
- **Internacional**: SEC EDGAR (fundamentos de empresas dos EUA via XBRL); cotações por provedor a escolher (apresentar alternativas e custos).
- **Damodaran Online**: prêmio de risco de mercado, risco país, betas setoriais.

Todo dado gravado no banco deve guardar fonte, data de referência e data de coleta.

---

## STACK PADRÃO

Use esta stack, salvo se houver motivo técnico forte — nesse caso, proponha a troca na Fase 0 e aguarde aprovação:

- Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic, pandas.
- Jobs de ingestão: tarefas agendadas (APScheduler ou Celery + Redis).
- Banco: PostgreSQL (SQLite aceitável apenas em testes).
- Frontend: Next.js + TypeScript + Tailwind; gráficos com uma biblioteca madura (Recharts ou ECharts).
- Testes: pytest no backend, Vitest/Playwright no frontend.
- Ambiente: Docker Compose para subir tudo com um comando.
- Idioma da interface: português do Brasil; números no padrão brasileiro (vírgula decimal, R$); ativos internacionais em US$ com conversão opcional para R$.

---

## ESCOPO E RESTRIÇÕES

- Trabalhe somente dentro da pasta do projeto.
- Não faça scraping de sites que proíbam isso nos termos de uso, inclusive o Ward e sites de análise pagos.
- Não grave chaves de API no código: use `.env` e mantenha um `.env.example` sem valores reais.
- Não invente dados. Se um indicador não puder ser calculado com os dados disponíveis, mostre "dado indisponível" e o motivo — nunca um número estimado sem aviso.
- Faça apenas o que está nesta especificação. Não acrescente funcionalidades, abstrações ou dependências não pedidas sem perguntar.
- Toda fórmula financeira fica num módulo isolado de metodologias (`backend/app/metodologias/`), uma função pura por métrica, com docstring citando o livro/autor e a fórmula.

---

## PLANO DE EXECUÇÃO POR FASES

Execute uma fase por vez. **Ao fim de cada fase, pare, apresente o resumo e aguarde minha aprovação antes de começar a próxima.**

**Fase 0 — Arquitetura (sem código de produto)**
Entregue `docs/ARQUITETURA.md` com: modelo de dados (empresas, ativos, cotações, demonstrações, proventos, FII, imóveis, carteiras, valuations do usuário), diagrama dos módulos, fontes de dados escolhidas com custos e termos de uso, estrutura de pastas e estratégia de atualização dos dados. Liste as dúvidas que dependem de mim.

**Fase 1 — Esqueleto e ingestão Brasil**
Docker Compose, banco com migrações, autenticação básica, jobs de ingestão de CVM (DFP/ITR), cotações BR, proventos, BCB (Selic, CDI, IPCA) e Tesouro. Validar com 10 ações e 10 FIIs de setores diferentes.

**Fase 2 — Motor de metodologias**
Implementar todas as métricas e métodos dos 10 livros como funções puras. Para cada uma, testes unitários com casos calculados à mão (incluindo casos de borda: lucro negativo, patrimônio negativo, sem dividendos, EV negativo).

**Fase 3 — Ações: lista, página do ativo e Stock Screening**
Todos os indicadores listados no contexto, filtros, parâmetros editáveis, rankings por Bazin, Graham, Lynch e Greenblatt, favoritos e exportação para .xlsx/.csv.

**Fase 4 — Valuation**
Preço teto projetivo, DCF (FCFF/FCFE), Gordon e dois estágios, múltiplos do setor, tabela de sensibilidade, "Meus Valuations" e comparativo entre métodos; exportação do DCF para .xlsx com fórmulas.

**Fase 5 — Fundos imobiliários**
Lista, página do fundo, composição do ativo, endividamento, Gordon ajustado, portal de relatórios FNET e Fund Screening.

**Fase 6 — Carteira**
Consolidador (lançamentos manuais e importação por arquivo da B3), rentabilidade contra índices, proventos, yield on cost, alocação, otimizador de Markowitz, matriz de correlação, paridade de risco, diário de decisões.

**Fase 7 — Mercado internacional**
Ações dos EUA, REITs e ETFs com as mesmas metodologias, adaptando o que for específico (ex.: FFO/AFFO para REITs, custos de ETF para a análise de Bogle).

**Fase 8 — Ferramentas e extras**
Juros compostos, conversor de taxas, plano de aposentadoria, comparador de ativos, alertas por e-mail, retorno de longo prazo à la Siegel (CAPE, retorno real). Simulador de opções somente se eu confirmar nesta fase.

---

## CRITÉRIOS DE ACEITAÇÃO

- [ ] `docker compose up` sobe backend, frontend e banco sem erro.
- [ ] Todos os testes passam; cobertura do módulo de metodologias ≥ 90%.
- [ ] Cada métrica tem página "Como é calculado" com fórmula, autor/livro, parâmetros e limitações.
- [ ] Cada número exibido mostra (ao passar o mouse ou num ícone) a fonte e a data do dado.
- [ ] Para 5 ações escolhidas, os indicadores básicos (P/L, P/VP, DY, ROE, margem líquida) conferem com as demonstrações da CVM dentro de 1%.
- [ ] O Stock Screening com os parâmetros padrão gera os quatro rankings sem erro para todas as ações com dados suficientes.
- [ ] A interface funciona em celular (largura de 375 px) e em desktop.
- [ ] Aviso de "não constitui recomendação de investimento" presente em rankings, preços teto e valuations.

---

## CONDIÇÕES DE PARADA

Pare e me pergunte antes de:
- Contratar ou integrar qualquer API paga.
- Adicionar uma dependência que não esteja na stack padrão.
- Alterar o esquema do banco depois da Fase 1.
- Apagar arquivos.
- Escolher entre duas abordagens válidas que mudem a arquitetura.
- Continuar após 2 tentativas sem resolver o mesmo erro.
- Encontrar uma métrica cuja definição seja ambígua entre fontes (ex.: dividend yield por data-com ou data de pagamento) — nesse caso apresente as opções e a recomendada.

---

## COMUNICAÇÃO

- Use subagentes para pesquisar termos de uso e formatos das fontes de dados, para não poluir o contexto principal.
- Após cada etapa concluída, escreva: `✅ <o que foi feito> — <arquivos afetados>`.
- No fim de cada fase, liste: arquivos criados/alterados, testes executados e resultado, pendências e perguntas.
- Mantenha `docs/DECISOES.md` atualizado com cada decisão tomada e o motivo.

Comece pela **Fase 0**.
