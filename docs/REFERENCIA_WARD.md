# Referência de produto: Ward (ward.app.br)

Observação feita em 03/11/2026, com conta assinante (plano PRO), apenas navegando
— nada foi alterado, salvo, votado ou exportado. As descrições são resumos próprios;
números citados servem só para ilustrar o formato, não como dados.

## 1. Visão geral e mapa do produto

A Ward é uma plataforma de análise fundamentalista focada em **ações e FIIs
pagadores de dividendos**, com forte ênfase em **preço teto / margem de segurança**
(métodos Bazin, Graham, Peter Lynch, Gordon e fluxo de caixa). É menos um "portal de
dados" e mais um conjunto de ferramentas de decisão.

Menu lateral (agrupado por seção):

| Seção | Itens | Rota |
|---|---|---|
| — | Página Inicial | `/dashboard` |
| Ferramentas | Calculadora de Juros, Conversor de Taxas, Plano de Aposentadoria, Valuation pelo Fluxo de Caixa | `/calculadora-juros-compostos`, `/conversor-taxas`, `/plano-aposentadoria`, `/valuation-fluxo-caixa` |
| Ações | Ranking de Ações, Análise Avançada de Ações | `/screening-acoes`, `/acoes`, `/acoes/{TICKER}` |
| Fundos | Ranking de Fundos, Análise Avançada de Fundos | `/fund-screening`, `/fiis`, `/fiis/{TICKER}` |
| Suporte | Chamados (abrir / meus chamados), FAQ | `/open-ticket`, `/user-tickets`, `/faq` |

Menu do usuário (avatar no topo): Configurações (`/settings`), Minha Assinatura,
Notificações (`/minhas-notificacoes`), Sair.

**O que não existe (ou ainda não):**
- **Carteira**: só um aviso na home dizendo que a consolidação de carteira está em testes.
- **Comparador dedicado** entre ativos: não há tela "A vs B". A comparação é feita
  (a) no ranking/lista, lado a lado em tabela, e (b) na página do ativo contra
  índices de referência (CDI, IPCA, IBOV, IFIX etc.).
- **Rankings prontos** separados: o "ranking" é o próprio screening, ordenado por um
  critério de valuation escolhido.

## 2. Identidade visual e layout geral

- **Framework**: Bootstrap 5 (classes `btn-light`, `accordion-button`, cards, tabelas).
- **Fonte**: Inter (fallback IBM Plex Sans / system-ui), corpo ~14,4px — denso mas legível.
- **Cores**: fundo cinza-claro (`#F7F8FA`), cards brancos com sombra suave e cantos
  arredondados; cor primária azul-ciano (`#40ABDA`); verde para variação positiva e
  margem de segurança positiva, vermelho para negativa (variação em "pílula" colorida).
- **Cores semânticas por método de valuation**, reaproveitadas em todo o site:
  Bazin = amarelo-claro, Graham = azul, Peter Lynch = lilás/roxo, "Joel" = vermelho/salmão.
  Aparecem tanto nos campos de filtro quanto nos cabeçalhos/colunas da tabela.
- **Modo claro/escuro**: botão de sol no topo alterna o tema (há regras CSS de tema
  escuro); não foi alternado durante a observação.
- **Estrutura de página**: sidebar estreita só com ícones (expande com o ☰ para mostrar
  rótulos e grupos), topbar com tema / ajuda / sino / avatar, e um **cabeçalho em faixa
  cinza** com breadcrumb + título + subtítulo curto. Conteúdo centralizado em largura máxima.
- Gráficos com marca d'água "ward" ao fundo.
- Botões "Como usar" no cabeçalho de várias ferramentas (ajuda contextual).

## 3. Página inicial (`/dashboard`)

- Faixa de aviso (alerta azul) sobre a carteira em testes.
- **Ferramentas em Destaque**: 4 cards grandes (Fund Screening, Stock Screening,
  Análise Avançada de FIIs, Análise Avançada de Ações) — ícone, título, uma linha de
  descrição, seta ↗ e barra colorida no rodapé do card.
- **Outras Ferramentas**: cards das calculadoras.
- **Atividades Recentes**: lista (vazia na conta observada).
- Não mostra cotações, índices nem notícias — é um hub de navegação, não um painel de mercado.

## 4. Ranking de Ações / Stock Screening (`/screening-acoes`)

**Filtros avançados** (card recolhível, grade em duas colunas, faixas mín./máx.):
- Coluna esquerda: Dividend Yield, P/L, DL/EBITDA, ROE, Liquidez.
- Coluna direita: Margem Líquida, Segmentos (multisseleção), e três **parâmetros de
  valuation** com fundo colorido: taxa Bazin (DY desejado), fator Graham (o 22,5 clássico),
  limite Peter Lynch.
- Vem com valores-padrão pré-preenchidos (uma "estratégia de dividendos" pronta).

**Filtros rápidos** (checkbox em pílula): Favoritos, BESST (setores perenes).

**Ações**: Filtrar, Salvar filtro, Filtros salvos, Limpar filtros, Ocultar filtros.

**Tabela de ranking**:
- Busca por texto, seletor "Rankear por": Rank GD (padrão), Rank Bazin, Graham,
  Peter Lynch, Joel.
- Colunas: estrela (favoritar), Rank (#), Ticker com logo, Cotação, Segmento (etiqueta
  colorida por segmento), DY, P/L, Margem Líquida, DL/EBITDA, e as colunas de
  valuation coloridas (preço teto Bazin com toggle de período "12M", preço teto Graham,
  indicador Peter Lynch, % Joel).
- **Personalizar colunas**: dropdown com checkboxes (as de valuation mantêm a cor).
- Ordenação clicando nos cabeçalhos (setas ⇅); paginação; "Mostrar 10/20/50/100";
  contador "de N ações"; rodapé "Atualizado em dd/mm/aaaa" com tooltip.
- Sem exportação visível (CSV/Excel).

## 5. Lista de Ações (`/acoes`)

Tabela geral de ~400 ações: ticker + razão social, preço, variação do dia (pílula
verde/vermelha), DY, P/L, Margem Líquida, P/VP; busca, personalizar colunas,
paginação. Serve de porta de entrada para a análise individual.

## 6. Página de ação — ex.: PETR4 (`/acoes/PETR4`)

Cabeçalho: logo + ticker grande + **busca de outro ativo** inline. Abaixo, barra de
botões que rolam até seções: Dividendos, Indicadores, Empresa, Comparar, Contábil,
Relatórios (destacado em azul).

Seções, na ordem:
1. **Faixa de identificação**: razão social, segmento, tipo (ON/PN), tag along ON/PN,
   segmento de listagem, índices em que participa (lista truncada com "+").
2. **Cards de destaque** (6): ROE, P/L, DY 12m, liquidez média 2m, volatilidade 12m,
   **Índice Sharpe 12m**.
3. **Cotação**: toggle *sem ajuste / ajustada*; períodos (hoje, 7d, 1m, YTD, 12m, 5a,
   10a, desde o início); coluna lateral com preço atual, cotação no início do período,
   variação R$ e %, mín./máx.; gráfico linha (preço) + barras (volume) com dois eixos e
   seleção de área (zoom).
4. **Valuation** em três cards lado a lado — Bazin (DY desejado ajustável com –/+),
   Graham (LPA, VPA), Peter Lynch (crescimento projetado) — cada um com preço teto e
   margem de segurança em verde/azul.
5. **Preço Teto projetivo**: o usuário mexe em DY desejado, payout e projeção de lucro
   e vê cards com preço teto, DPA projetivo, yield projetivo e margem; botões Salvar /
   Reiniciar; botão "Influenciadores" para ver premissas de terceiros.
6. **Valuation pelo Fluxo de Caixa**: atalho para calcular/salvar um DCF próprio.
7. **Dividendos**: período 3/5/10 anos; DY atual, total 12m, total 10a, DY médio/mín./máx.;
   gráfico barras (R$) + linha (DY%); "Exibir pagamentos" (tabela de proventos).
8. **Indicadores** em acordeão por grupo: Básicos (cotação, VPA, LPA, payout),
   Valuation (market cap, EV, P/L, P/VP, P/EBIT, P/EBITDA, EV/EBIT, EV/EBITDA),
   Rentabilidade (ROE, ROA, ROIC, margens), Endividamento (dívida líquida/bruta,
   caixa, DL/EBITDA); botão "Exibir histórico".
9. **Sobre o ativo**: ficha cadastral (CNPJ, setor/subsetor/segmento, outros papéis
   da mesma empresa, fundação, IPO, free float, nº de ações).
10. **Lucro x Cotação** (gráfico comparativo).
11. **Balanço Patrimonial** (anual/trimestral, 5/10a): ativo, passivo, PL, endividamento
    geral, **CAGR do PL**; gráfico + "Exibir resultados".
12. **DRE**: receita, lucro, margem atuais e médias; gráfico.
13. **Rentabilidade comparada** (é o que o botão "Comparar" abre): retorno do ativo vs
    IPCA, CDI, 85% CDI, IBOV, IFIX, S&P500, IDIV, IMA-B5, IMA-B5+; toggle R$ / %;
    campo "valor inicial" para simular quanto R$ X viraria; legenda clicável.
14. **Investidores**: nº de cotistas PF/PJ/institucionais e tabela de acionistas
    relevantes com marcação de controlador.
15. **Comunidade**: enquete "tem em carteira?", nota 1–5 (resultado só após votar) e
    comentários com respostas e curtidas.

## 7. Ranking de FIIs / Fund Screening (`/fund-screening`)

Mesmo padrão do screening de ações, com filtros próprios de FII:
- DY, P/VP, Patrimônio Líquido, Tipo de Fundo (tijolo/papel/híbrido/FIAgro…),
  Vacância, Liquidez, Alavancagem Bruta, Segmento.
- **Filtros rápidos por estratégia**: Ancoragem, Crescimento, Risco, Método 2em1, Favoritos.
- Tabela: Rank, Fundo, Cotação, Segmento, Tipo, DY, P/VP, Liquidez média, nº de imóveis,
  vacância; botão "Como usar".

## 8. Página de FII — ex.: HGLG11 (`/fiis/HGLG11`)

Botões de seção: Dividendos, Indicadores, Sobre, Contábil, Comparar, **Relatório**
(botão preto) e **Documentos** (azul — documentos oficiais do fundo).

- **Identificação**: razão social, segmento (tijolo) e sub-segmento (logística), tipo de
  gestão, taxa de adm. com link "ver regra", **IRA** (indicador próprio), índices.
- **Cards**: P/VP, DY 12m, vacância, alavancagem bruta, liquidez média 2m, volatilidade 12m.
- **Cotação**: igual à de ações.
- **Valuation — Método Gordon Ajustado**: dividendos 12m, crescimento esperado (–/+),
  dividendos projetados, taxa base (Tesouro prefixado, alterável para IFIX nas
  configurações) + prêmio desejado → preço teto e margem de segurança.
- **Volatilidade** atual em card separado.
- **Dividendos**: mensal/anual, 3/5/10 anos, mesmas métricas de ações.
- **Indicadores** em grupos: Básicos (volume, nº cotas, nº cotistas), Valuation (ativos,
  passivos, PL, valor de mercado, VP/cota, P/VP), Endividamento, Operacionais (vacância
  física), Rentabilidade (último dividendo, data-com, data de pagamento, yield mensal).
- **Estatística de retornos mensais**: meses positivos x negativos (com %), maior e
  menor retorno mensal.
- **Retorno do investimento**: rentabilidade nominal e **real** em 1m/3m/6m/1a/2a/5a.
- **Distribuição**: yield e valor em R$ em 1/3/6/12 meses.
- **Composição de ativos**: tabela caixa / imóveis / FII / CRI / ações com valor e %,
  linhas expansíveis (›) e "Exibir portfólio".
- **Sobre**: gestora, administrador, taxas, data e valor do IPO, benchmark,
  representação no IFIX.
- Rentabilidade comparada com índices e Comunidade, iguais às de ações.

## 9. Valuation pelo Fluxo de Caixa (`/valuation-fluxo-caixa`)

- "Meus valuations" (estado vazio com ícone + texto + busca para começar).
- **Valuations de influenciadores**: tabela de ativos com preço teto médio calculado por
  analistas/influenciadores, upside em %, avatares dos influenciadores e linha expansível
  com detalhes. Busca por influenciador.

## 10. Alertas / Notificações (`/minhas-notificacoes`)

- Estado vazio com botão "Criar primeira notificação".
- Alertas por ativo entregues por **e-mail ou WhatsApp** (WhatsApp exige verificar o
  número em Configurações). O sino da topbar abre o dropdown de notificações recebidas.

## 11. Ferramentas (calculadoras)

- **Juros compostos**, **Conversor de taxas**, **Plano de aposentadoria**.
- Padrão de formulário: inputs grandes com ícone à esquerda ($, %, calendário),
  rótulo flutuante, dica curta abaixo (ex.: "equivale a X% ao ano"), seletor de unidade
  acoplado ao campo (meses/anos, mensal/anual), botão Calcular e card de resultado com
  texto motivacional. O plano de aposentadoria tem assistente de despesas que pode ser salvo.

## 12. Interações transversais

- **Favoritos** (estrela) em rankings, usados como filtro rápido.
- **Filtros salvos** por usuário.
- **Personalizar colunas** em todas as tabelas.
- **Tooltips** (ícone ⓘ / ?) em métricas e no "Atualizado em".
- Parâmetros ajustáveis com botões –/+ e "Salvar / Reiniciar".
- Rolagem por seção a partir da barra de botões do ativo.
- **Exportação**: não encontrada (nenhum botão CSV/Excel/PDF nas telas vistas;
  "Relatório"/"Documentos" são conteúdo, não exportação de dados).
- Suporte por chamados dentro do app.

## 13. Diferenciais em relação a um site como o Investidor 10

1. **Valuation como protagonista**: preço teto por vários métodos aparece no ranking,
   na página do ativo e tem calculadora interativa — no Investidor 10 o foco é a
   exibição de indicadores.
2. **Ranking por método** (Bazin/Graham/Lynch/Joel/GD) em vez de só ordenar por coluna.
3. **Premissas ajustáveis na própria página** (DY desejado, crescimento, prêmio de risco)
   com resultado instantâneo e possibilidade de salvar.
4. **Filtros rápidos por estratégia** (BESST, Ancoragem, Crescimento, Risco, 2em1) que
   codificam uma filosofia de investimento.
5. **Métricas de risco** em destaque: volatilidade, Índice Sharpe, meses
   positivos/negativos, rentabilidade real.
6. **Comparação com cesta ampla de benchmarks** com simulação de valor inicial.
7. **Valuations de influenciadores** agregados (preço teto médio e upside).
8. **Alertas via WhatsApp**.
9. **Codificação por cor** consistente de cada método de valuation.
10. Pontos fracos: sem carteira consolidada (em testes), sem exportação, sem comparador
    direto entre dois ativos, home sem dados de mercado.

## 14. Ideias aplicáveis ao nosso projeto

- Coluna de **preço teto + margem de segurança** por método no ranking, com cor por método.
- Seletor "**ranquear por**" método de valuation.
- **Filtros pré-configurados** por estratégia e filtros salvos pelo usuário.
- Página do ativo com **barra de seções** e acordeões de indicadores agrupados
  (básicos / valuation / rentabilidade / endividamento).
- Cards de destaque no topo (6 métricas-chave) e estatísticas de risco (volatilidade,
  Sharpe, meses positivos).
- Gráfico de **rentabilidade vs benchmarks** com valor inicial simulado.
- Para FIIs: Gordon com taxa base configurável, composição de ativos, rentabilidade real.
- Sempre mostrar "**Atualizado em**" nas tabelas.
- Lacunas que podemos cobrir: comparador lado a lado, exportação CSV e carteira.
