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

**D-028 — Complemento de carga mais robusto (diagnóstico de 12/10/2026)** · aprovada
O diagnóstico no computador do usuário mostrou:
- o Yahoo nunca tinha rodado: as 3 cotações da brapi faziam o sistema achar que já havia cotações;
- a Petrobras tinha 15.704 linhas de balanço e nenhum período organizado;
- os FIIs não tinham ticker.

Correções:
- **Cotações faltando:** passa a valer "menos da metade das ações ativas tem cotação".
- **Complemento por passos:** organiza os balanços pendentes, cria os tickers de FII pelo ISIN, busca cotações e dividendos e recalcula. Cada passo é independente: a falha de um não impede os seguintes.
- **Organização dos balanços visível:** grava um lote ("Organização dos balanços") em Status, com quantas empresas foram organizadas e exemplos de falha.
- **Diagnóstico:** se o ticker tem balanço mas nenhum período organizado, roda a organização em memória e mostra o erro exato.
- **Comando `completar`:** força o complemento inteiro pelo terminal.

**D-029 — Ações informadas em milhares e FIIs sem ticker** · 12/10/2026 · aprovada
O teste no computador do usuário mostrou números absurdos no ranking, por exemplo:
- ABEV3 com preço justo de Lynch de R$ 6.708 e PEG 0,00;
- EMBJ3 com earnings yield de 238%.

Causa: algumas empresas informam na CVM a quantidade de ações em milhares.

Correções:
- **Escala das ações:** se o P/VP (ou o P/Receita, sem PL positivo) fica implausivelmente baixo e, multiplicando a quantidade por 1.000, cai numa faixa normal, o cálculo usa a quantidade × 1.000. O ajuste aparece como aviso no detalhamento do número (ⓘ).
- **ISIN dos FIIs:** a leitura passa a aceitar qualquer coluna do informe mensal cujo nome contenha "ISIN".
- **Complemento:** o comando `completar` reprocessa os informes de FII quando há fundos sem ticker e busca no Yahoo as cotações dos tickers que ainda não têm nenhuma.
- **Diagnóstico:** mostra quantos FIIs existem, quantos têm ISIN e quantos têm ticker.

**D-030 — Atualização ao ligar a aplicação** · 03/11/2026 · aprovada (pedido do usuário)
Problema: o sistema roda no computador pessoal. Com o computador desligado no horário, a tarefa do dia se perdia.

Solução:
- **Ao subir, o worker põe os dados em dia** (`por_em_dia`):
  - cotações paradas antes do último dia útil → Yahoo com a menor janela que cobre o atraso (5d, 1mo, 3mo, 6mo, 1y, Ny);
  - Selic/Tesouro e, no modo b3, proventos → se a última atualização tem mais de 20 h;
  - recálculo dos indicadores;
  - só depois, os downloads demorados da CVM (cadastro, balanços e informes do ano), se estiverem com mais de 20 h, e novo recálculo.
- **Tarefas perdidas por suspensão** rodam ao acordar (até 12 h de atraso, uma vez só).
- **`restart: unless-stopped`** nos containers: voltam junto com o Docker Desktop.
- **`iniciar.bat`** (liga tudo e abre o navegador) e **`instalar-inicio-automatico.bat`** (põe o início na pasta Inicializar do Windows).

## Fase 3 — Ranking completo (03/11/2026)

**D-031 — Stock screening inspirado na Ward** · aprovada (usuário pediu para seguir com a recomendação)
Referência de produto em `docs/REFERENCIA_WARD.md`. Só a organização foi aproveitada; textos, marca, paleta e dados são nossos.

A página "Mais baratas" vira **Ranking de ações** (`/screening/acoes`):
- **Filtros por faixa** (mín./máx.): DY, P/L, P/VP, ROE, margem líquida, dívida líquida/EBITDA e liquidez. Também filtra por setor da CVM.
- **Parâmetros dos métodos** editáveis: yield de Bazin, fator de Graham e multiplicador de Lynch.
- **Todos os métodos lado a lado**: valor de Graham, teto de Bazin, preço justo de Lynch, PEG, EY/ROC e posição na Fórmula Mágica.
  - Cada método tem uma cor fixa no site: Graham azul, Bazin âmbar, Lynch roxo, Greenblatt laranja.
  - "Ranquear por" escolhe o método. Ações sem dado para esse método vão para o fim, em vez de sumir.
- **Fórmula Mágica dentro do conjunto filtrado**, sem exclusões automáticas: quem decide o universo são os filtros do usuário.
- **BESST** como filtro rápido: bancos, energia elétrica, saneamento, seguros e telecomunicações (Luiz Barsi). O setor é identificado pelo nome do setor da CVM.
- **"Rank GD" da Ward não foi incluído:** é um método próprio da plataforma e não está nos 10 livros.
- **Tabela:**
  - personalizar colunas;
  - ordenar clicando no cabeçalho (valores ausentes sempre no fim);
  - busca;
  - paginação (10/20/50/100);
  - "Atualizado em" (último fechamento entre as ações listadas).
- **Exportação** .xlsx (formatos de % e R$) e .csv (padrão do Excel em português: `;` e vírgula decimal). As duas incluem fontes, data e aviso de não recomendação.
- **Favoritos:**
  - estrela na tabela e na página do ativo;
  - exigem login e usam a tabela `favorito`, que já existia (sem mudança de esquema).
- **Filtros salvos e colunas escolhidas** ficam no navegador (`localStorage`). Guardar no banco exigiria uma tabela nova, ou seja, mudança de esquema após a Fase 1.
- **Login que sobrevive ao reinício:** sem `JWT_SEGREDO` no `.env`, o segredo gerado é guardado em `dados_brutos/.segredo_jwt`. Antes, cada reinício do computador desconectava o usuário.
- O endpoint antigo `/ranking/acoes` continua existindo.

**D-032 — Página da ação reorganizada** · 03/11/2026 · aprovada (usuário pediu para seguir)
- **Barra de seções fixa:** Cotação, Valuation, Dividendos, Indicadores, Histórico e Empresa.
- **6 cards de destaque:** ROE, P/L, DY 12m, liquidez, volatilidade 12m e Sharpe 12m.
  - Volatilidade = desvio-padrão dos retornos diários × √252.
  - Sharpe = (retorno de 12 meses − CDI de 12 meses) ÷ volatilidade. O CDI vem do SGS, acumulado dia a dia.
  - As duas são calculadas sob demanda (`/ativos/{t}/risco`), com página em "Como é calculado". O Sharpe passa a valer também para ações e FIIs.
- **Cotação:** períodos de 1 mês a tudo, volume financeiro, zoom e resumo (início, variação, mínima e máxima). Os fechamentos não são ajustados por proventos, e o gráfico avisa isso.
- **Valuation pelos livros:** Graham, Bazin, Lynch e Fórmula Mágica em quatro cartões coloridos.
  - O usuário ajusta fator, yield mínimo e multiplicador com –/+.
  - O recálculo é feito no backend (`/acoes/{t}/valuation`), com as mesmas contas do ranking.
  - A posição na Fórmula Mágica é entre todas as ações com cotação.
- **Dividendos** (`/ativos/{t}/dividendos`):
  - total líquido por ano e DY do ano = total ÷ último fechamento do ano;
  - DY médio, mínimo e máximo só de anos completos (o ano corrente aparece como parcial);
  - tabela de pagamentos com valor bruto e líquido.
- **Indicadores:** grupos recolhíveis. Nas ações, os grupos dos métodos saem daqui e vão para o painel de valuation.
- **Histórico anual** (`/acoes/{t}/historico`): DRE e balanço de 5 ou 10 anos, a partir das DFP padronizadas, em gráfico e tabela. Inclui lucro × cotação no fim do exercício e o CAGR do patrimônio.
- **Não incluído agora:**
  - cotação ajustada por proventos (exige guardar o fechamento ajustado do Yahoo, uma coluna nova);
  - rentabilidade comparada com índices (fica na Fase 6);
  - acionistas e comunidade (fora do escopo).

**D-033 — Cotações paradas desde 09/10 (relato de 03/11/2026)** · aprovada
Sintoma: a página do SAPR4 mostrava o fechamento de 09/10/2026 em 03/11. Este ambiente não acessa o Yahoo nem a CVM, então a causa exata depende do diagnóstico no computador do usuário. Correções para as causas prováveis:
- **"Em dia" pela mediana:** a atualização ao ligar decide se as cotações estão atrasadas pela mediana da última cotação de cada ação. Antes usava a data mais recente entre todas, e uma única ação atualizada escondia as demais paradas.
- **Cotações antes do complemento:** ao ligar, primeiro vêm as cotações; depois o complemento (informes de FII, tickers sem preço), que pode demorar.
- **Yahoo grava em blocos de 25 ativos:** uma interrupção (computador desligado, Docker fechado) não perde a rodada inteira.
- **Yahoo para após 25 falhas seguidas** (bloqueio 429 ou sem internet), registra "interrompido" em Status e deixa o restante para a próxima rodada, em vez de insistir em centenas de consultas.
- **Diagnóstico ampliado:** mostra até que data as cotações estão em dia, as 5 últimas rodadas do Yahoo e os resultados por período do ticker (trimestres, 12 meses e anos), para conferir números de 12 meses que destoam do anual.

**D-034 — Causa das cotações paradas: fuso da tarefa de inicialização** · 04/11/2026 · aprovada
Diagnóstico do usuário em 04/11: nenhuma fonte rodou depois de 13/10, e o worker tinha acabado de subir sem executar nada.
- **Causa:** a tarefa "ao ligar" era agendada com `datetime.now()` sem fuso. O container roda em UTC, e o agendador lê horários sem fuso como horário de Brasília. Resultado: a tarefa ficava para 3 horas depois, e o computador costumava ser desligado antes disso.
- **As tarefas fixas (19h, 2h–5h) também não rodavam:** o computador não estava ligado nesses horários.
- **Correção:** horário com fuso (`datetime.now(ZoneInfo("America/Sao_Paulo"))`), com teste que garante a execução imediata.
- **Verificação a cada hora** (pedido do usuário: "que ocorra de modo automático sempre"): com a aplicação ligada, confere de hora em hora se algo ficou para trás e busca só o que faltar.
  - Cotações: o pregão esperado é o de hoje depois das 19h em dia útil; senão, o dia útil anterior.
  - Em feriado o pregão esperado nunca chega: o sistema tenta no máximo a cada 3 h.
  - Cobre computador que dormiu, tarefa das 19h perdida e documento novo da CVM (balanços com mais de 20 h são rebaixados).
- **Lucro de 12 meses do SAPR4 conferido:** o 2º trimestre de 2026 teve prejuízo de R$ 505 mi com EBIT positivo de R$ 365 mi. A queda do patrimônio no trimestre (R$ 12,70 bi → R$ 12,10 bi) confirma que o prejuízo está no balanço da CVM; não é erro de cálculo. Por isso o ROE de 12 meses (3,8%) fica bem abaixo do ROE de 2025 (16,8%).

---

## Fase 4 — Valuation (04/11/2026)

**D-035 — Valuation por ação, "Meus valuations" e DCF exportável** · aprovada (usuário pediu para seguir à Fase 4)
A conferência da Fase 3 contra o Investidor 10 ficou pendente: este ambiente não acessa `investidor10.com.br`, `dados.cvm.gov.br` nem `query1.finance.yahoo.com`. Será feita quando o acesso for liberado.

- **Página `/valuation/{ticker}`:** comparativo dos métodos com as premissas padrão (gráfico com a cotação marcada) e uma aba por método com premissas editáveis, recalculadas no backend.
  - **Preço teto projetivo (Bazin):** lucro projetado × payout ÷ ações ÷ yield mínimo.
  - **Gordon e dividendos em dois estágios (Damodaran):** a partir dos dividendos líquidos de 12 meses.
  - **DCF FCFF e FCFE (McKinsey/Damodaran):**
    - projeção de 5 anos e valor terminal de Gordon;
    - tabela de sensibilidade de taxa de desconto (±2 p.p.) × crescimento perpétuo (±1 p.p.);
    - peso do valor terminal.
  - **Múltiplos do setor:** mediana de P/L, P/VP e EV/EBITDA das outras empresas do mesmo setor da CVM (mínimo de 3 pares). O resultado é a mediana dos preços implícitos.
- **Premissas padrão** (editáveis e explicadas na tela):
  - custo do capital próprio = Selic meta + 5%;
  - custo da dívida = Selic + 2%;
  - WACC com pesos a valor de mercado e IR de 34%;
  - crescimento da receita = CAGR de 5 anos limitado a 0–10%;
  - crescimento perpétuo de 4%;
  - margem EBIT, D&A e capex dos últimos 12 meses;
  - capital de giro = 10% do aumento da receita.
- **Meus valuations** (login): salva método, premissas, narrativa, resultado e um retrato dos insumos, para reproduzir o cálculo mesmo depois de novos dados. Usa a tabela `valuation_salvo`, que já existia (sem mudança de esquema). Lista em `/valuations`; apagar e exportar.
- **Exportação do DCF para .xlsx com fórmulas abertas:** aba Premissas (células amarelas editáveis) e aba DCF com fórmulas. O teste recalcula a planilha no LibreOffice e confere o valor por ação com o do sistema, para FCFF e FCFE.
- **Todo resultado** traz o aviso de não recomendação e o link para "Como é calculado".

## Fase 5 — Fundos imobiliários (04/11/2026)

**D-036 — Página do fundo, Gordon ajustado, FNET e Fund Screening** · aprovada (usuário pediu para seguir à Fase 5)
- **Composição do ativo:** vem do detalhamento "ativo_passivo" do informe mensal da CVM, que já era guardado em `extras` (sem mudança de esquema).
  - Grupos: Imóveis, CRI/CRA, LCI/LCA/LH/LIG, Cotas de FII, Ações e sociedades, Caixa e renda fixa, Outros valores mobiliários, Valores a receber.
  - Os subtotais (`Total_*`, `Direitos_Bens_Imoveis`) não entram, para não contar duas vezes.
- **Tipo do fundo:** Tijolo, Papel (CRI/CRA + LCI etc.) ou Fundo de fundos quando um grupo passa de 60% do ativo classificado; senão Híbrido.
- **Endividamento:** alavancagem bruta = passivo total ÷ ativo total, com as obrigações separadas (aquisição de imóveis, securitização, adiantamentos, rendimentos a distribuir, taxas, outros).
- **Imóveis e vacância:** nova fonte `CVM_FII_TRIMESTRAL` (informe trimestral, ODbL), gravada na tabela `fii_imovel`, que já existia.
  - Vacância física = média ponderada pela área (média simples se faltar a área).
  - As colunas são achadas pelo nome, e percentuais em 0–100 viram fração.
  - ⚠️ A leitura foi testada com arquivo simulado; o arquivo real da CVM não pôde ser baixado neste ambiente. Se o leiaute for outro, o erro aparece em Status ("CVM — Informe trimestral de FII") e os demais dados seguem normais.
- **Novos indicadores do FII:** `fii.vacancia` e `fii.alavancagem`, com página em "Como é calculado".
- **Gordon ajustado na página do fundo:**
  - taxa base = Tesouro Prefixado de vencimento mais longo (padrão), Tesouro IPCA+ ou Selic, todos com a data da taxa;
  - 15% de IR descontados da taxa do Tesouro, porque os rendimentos de FII são isentos (opcional);
  - prêmio de 2% e crescimento de 0% como padrão, ajustáveis com –/+.
- **Histórico mensal:** valor patrimonial por cota, DY mensal informado e cotistas. Estatística dos retornos mensais da cotação (meses em alta e em queda, melhor e pior mês, 24 meses).
- **Documentos do FNET:** consulta pública sob demanda, só quando o usuário clica em "Carregar documentos". Mostra apenas metadados e link para o FNET, em linha com o uso parcimonioso registrado em FONTES_DE_DADOS.md.
- **Ranking de FIIs** (`/fiis/ranking`):
  - faixas de DY, P/VP, patrimônio, liquidez, vacância e alavancagem;
  - tipo, segmento e favoritos;
  - parâmetros do Gordon ajustado;
  - ordenar pela margem do Gordon, maior DY ou menor P/VP;
  - exportação .xlsx/.csv com fontes e aviso.
  - Os filtros ficam guardados no navegador.

## Fase 6 — Carteira (04/11/2026)

**D-037 — Consolidador, rentabilidade, otimizador e diário** · aprovada (usuário pediu para seguir à Fase 6)
Usa as tabelas `carteira`, `lancamento`, `arquivo_importacao`, `preco_medio_ajuste` e `diario_decisao`, que já existiam (sem mudança de esquema). Tudo exige login, e cada usuário vê só o que é seu.

- **Lançamentos:** compra, venda, desdobramento, bonificação e grupamento.
  - Preço médio com taxas pelo método da Receita: a venda não altera o preço médio, e o resultado realizado = quantidade × (preço − preço médio) − taxas.
  - Lançamentos que deixariam uma venda sem posição são recusados, inclusive ao apagar uma compra.
  - O preço médio pode ser informado à mão (posições antigas sem histórico).
- **Importação da Área do Investidor B3** (.xlsx exportado pelo usuário; a API da B3 exige parceria):
  - extrato de **Negociação**: compras e vendas;
  - extrato de **Movimentação**: liquidações, desdobro, bonificação e grupamento;
  - mercado fracionário (PETR4F → PETR4);
  - linhas repetidas são ignoradas, então reimportar não duplica;
  - proventos do extrato são ignorados, porque vêm da fonte de mercado.
  - O arquivo vai no corpo da requisição, sem `python-multipart` (sem dependência nova).
- **Proventos recebidos:** quantidade detida na data-com × valor líquido (JCP com 15% de IR), creditados na data de pagamento (ou data-ex no Yahoo). Yield on cost = proventos por cota de 12 meses ÷ preço médio.
- **Rentabilidade pelo método das cotas** (time-weighted): o retorno de cada dia desconta aportes e resgates e soma os proventos creditados. Comparada com:
  - CDI e IPCA (Banco Central);
  - **Ibovespa e IFIX**, nova coleta no Yahoo (`^BVSP`, `IFIX.SA`) gravada como série.
  - Se um índice estiver indisponível, os outros seguem normais.
  - Períodos: 1 mês, no ano, 12 meses e desde o início.
- **Otimizador** (Lo & Foerster e Dalio), com retornos diários de 1 a 5 anos:
  - pesos atuais × mínima variância × máximo Sharpe (taxa livre de risco = CDI de 12 meses) × paridade de risco;
  - fronteira eficiente;
  - matriz de correlação;
  - contribuição de cada ativo para o risco;
  - número efetivo de ativos.
  - Aviso fixo: pesos históricos, ferramenta de estudo, não é recomendação.
- **Diário de decisões:** decisão, tese, premissas e data de revisão. Registros com a revisão vencida aparecem como "revisão pendente"; depois o usuário registra a revisão e o resultado observado.
- **Menu:** mostra o e-mail da conta e "Sair" quando há login.
- **Fica para depois:** compartilhar a carteira por link (`token_compartilhamento` já existe na tabela).

## Fase 7 — Mercado dos EUA (04/11/2026)

**D-038 — Ações, REITs e ETFs dos EUA com as mesmas metodologias** · aprovada (usuário pediu para seguir à Fase 7)
- **Sem mudança de esquema:** usa `empresa.cik/pais` e `ativo.classe/mercado/moeda`.
  - Classes novas: `STOCK` (ações), `REIT` e `ETF`, com `mercado = "US"` e `moeda = "USD"`.
  - O que filtra `classe == "ACAO"` continua sendo só B3: rankings, buscas e indicadores não misturam reais com dólares.
- **Balanços: SEC EDGAR (XBRL, `companyfacts`).**
  - Os conceitos US-GAAP são levados aos mesmos campos padronizados da CVM, por isso P/L, ROE, Graham, Bazin, Lynch, Greenblatt, DCF etc. funcionam sem mudança.
  - Anual = fatos de ~12 meses do 10-K (o último arquivado vence, para pegar reapresentações).
  - 12 meses = último anual + acumulado do ano − acumulado do mesmo período do ano anterior.
  - Ações em circulação = capa do último relatório (soma das classes); sem a capa, média diluída.
  - Setor e tipo (REIT, banco, seguradora) pelo código SIC.
  - A SEC exige um contato no User-Agent: sem e-mail real em `CONTATO_USER_AGENT`, a ingestão para com aviso. **O e-mail não foi preenchido pelo sistema.**
- **Lista acompanhada:** `TICKERS_EUA` e `ETFS_EUA` no `.env`; vazias = lista padrão de 39 empresas/REITs grandes e 8 ETFs. Não baixamos as ~7 mil empresas da SEC, para manter a carga leve num computador pessoal.
- **Cotações e dividendos: Yahoo Finance** (mesma fonte da B3, sem custo, D-027). Na primeira vez, 7 anos de histórico.
- **REITs (Damodaran; definição de FFO da NAREIT):**
  - FFO = lucro + D&A − ganho na venda de imóveis;
  - AFFO simplificado = FFO − investimentos de manutenção (`PaymentsForCapitalImprovements`; indisponível sem esse dado);
  - também FFO por ação, P/FFO e dividendos ÷ FFO.
  - Limitação registrada: D&A total, sem impairment.
- **ETFs:** cotação, dividendos, liquidez e risco. **Custos de Bogle:** o usuário informa a taxa de administração (não há fonte oficial gratuita integrada), e o sistema mostra quanto ela consome do patrimônio final e compara com um fundo de 0,03%.
- **Valuation em dólar:**
  - taxa livre de risco = Treasury de 10 anos (nova fonte `US_TREASURY`);
  - crescimento perpétuo de 2,5%;
  - IR de 21%;
  - múltiplos do setor só entre pares dos EUA.
- **Ranking:** seletor Brasil (B3) / EUA (US$) na mesma página; exportação com "US$" e fontes da SEC.
- **Moeda na tela:** valores dos EUA aparecem em US$ (contexto de moeda nos componentes).
- **Carteira:** por enquanto só aceita ativos da B3, porque consolidar reais e dólares exige câmbio. Fica para depois.
- **Dividendos dos EUA (métrica a confirmar com o usuário):** DY pelo valor **bruto**; o texto avisa que os EUA retêm 30% na fonte para residentes no Brasil. A alternativa é mostrar o DY líquido de 30%, como fazemos com o JCP (15%).

## Comparação com a Ward e Fase 8 (04/11/2026)

**D-039 — Conferência com a Ward e correção de conta duplicada** · aprovada (usuário pediu a comparação)
- Comparamos 5 ações e 1 FII com a Ward (detalhes em `docs/VALIDACAO_WARD.md`). PETR4, WEGE3 e ITUB4 batem (P/L, ROE, DY, margens, DL/EBITDA, EV).
- **Erro encontrado e corrigido:** no ITR do 3T25 o Banco do Brasil entregou a conta "Atribuído aos Sócios da Controladora" duas vezes (3.09.01 zerada e 3.11.01 com o valor). A padronização pegava a zerada e o lucro de 12 meses ficava inflado (ROE 9,9% em vez de 6,6%). Agora uma conta zerada não esconde outra com valor (teste novo). Todas as empresas foram reprocessadas.
- **Diferenças explicadas, sem mudança:** P/EBIT de empresas com ON e PN (usamos a cotação do próprio ticker, D-008; a Ward usa o valor de mercado); ações da VALE3 (usamos capital integralizado − tesouraria do ITR da CVM: 4,07 bi; a Ward usa 4,44 bi); DY de FII logo após o anúncio do rendimento (o Yahoo ainda não trazia o de 30/10). ROIC da PETR4, margem líquida da WEGE3 e alavancagem do MXRF11 diferem e ainda não foram investigados.

**D-040 — Visual de terminal financeiro e artes próprias** · aprovada (pedido do usuário)
- Tema escuro por padrão (azul-noite, números em fonte tabular/mono, verde e vermelho só para variação), com tema claro no botão do topo (fica salvo no navegador).
- Menu lateral agrupado, busca rápida de qualquer ativo (atalho "/"), faixa rolante com Selic, CDI, IPCA, dólar, Tesouro e maiores variações do pregão.
- Painel inicial com indicadores de mercado, maiores altas e baixas (só ativos com liquidez relevante), os 5 primeiros de cada método e atalhos das ferramentas. Endpoint novo `/painel`.
- Artes em SVG feitas para o projeto: marca "Prumo" (candles + fio de prumo = margem de segurança), ilustração do painel (preço × valor intrínseco), emblemas de Graham, Bazin, Lynch e Greenblatt, monograma por ticker (não usamos logotipos de empresas) e estado vazio. O nome "Prumo" é provisório e muda em uma linha (`NOME_PRODUTO`).

**D-041 — Fase 8: ferramentas, comparador, longo prazo e alertas** · aprovada (usuário pediu para seguir às próximas fases)
- Calculadoras com fórmulas no módulo de metodologias (`ferramentas.py`, testes à mão): juros compostos (aporte no fim do mês; taxa anual vira mensal equivalente), conversor de taxas (dia útil = 252) com taxa real de Fisher, plano de aposentadoria (renda = patrimônio × DY ÷ 12; aporte necessário pelo PMT).
- Comparador: até 4 ativos (ações, FIIs, EUA), todas as métricas lado a lado com procedência, melhor valor da linha destacado e cotações em base 100.
- Longo prazo (Siegel): R$ 100 com proventos reinvestidos na data-ex, contra CDI, dólar e IPCA, nominal e real; CAPE = valor de mercado ÷ lucro real médio de N anos. Como temos DFP desde 2020, o CAPE de 10 anos fica indisponível; o usuário pode escolher 5 a 8 anos, com aviso.
- Alertas: usa a tabela `alerta` que já existia (sem mudar o esquema). Condições de preço, DY, P/L, P/VP, margem de Graham e preço teto de Bazin; avaliados após cada recálculo; repetição no máximo a cada N dias. E-mail por SMTP só se `SMTP_HOST` estiver no `.env` (biblioteca padrão do Python, sem dependência nova); sem SMTP, o disparo aparece na tela.
- **Simulador de opções não foi feito**: a especificação pede confirmação nesta fase.

**D-042 — Incidente: banco apagado pelos testes (04/11/2026)** · registro
- Ao rodar a suíte completa com `docker exec backend pytest`, o `DATABASE_URL` do container apontava para o banco de uso; o `conftest.py` recria o schema (`DROP SCHEMA public CASCADE`) a cada teste e apagou tudo.
- Perdidos, sem backup: conta de usuário, carteiras, lançamentos, preços médios ajustados, favoritos, valuations salvos, diário e alertas. Os dados de mercado foram recarregados pelo worker (carga inicial automática).
- Correções: trava no `conftest.py` (só aceita banco cujo nome termine em `_teste`; use `TEST_DATABASE_URL`), banco `analise_teste` criado, `alembic stamp head` depois de conferir que o esquema era idêntico ao das migrações.

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
