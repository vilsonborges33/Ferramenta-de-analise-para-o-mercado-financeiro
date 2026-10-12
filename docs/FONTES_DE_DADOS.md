# Fontes de dados — termos de uso, formatos e custos

> Situação em 10/10/2026 (Fase 0). **Limitação:** o proxy deste ambiente bloqueou o acesso direto aos sites oficiais (dados.cvm.gov.br, api.bcb.gov.br, sec.gov, brapi.dev etc.). Por isso, as conclusões abaixo vêm de resultados de busca, não da leitura integral dos termos. Antes de integrar cada fonte (Fase 1 em diante), o texto dos termos será conferido na página oficial e esta tabela será atualizada. Tudo que ainda não foi confirmado está marcado como **a confirmar**.

## Resumo

| Fonte | Uso | Custo | Licença / termos | Situação |
|---|---|---|---|---|
| CVM Dados Abertos | DFP, ITR, FRE, cadastro, informes de FII | Grátis | ODbL; exige atribuição | ✅ Aprovável (conferir texto) |
| B3 FNET | Documentos de FII (metadados + link) | Grátis | Sem termos específicos para acesso automatizado encontrados | ⚠️ A confirmar; uso parcimonioso, só link |
| B3 COTAHIST | Histórico de preços de fechamento | Grátis | Política de Market Data da B3 rege exibição comercial | ⚠️ Área cinzenta para app pago |
| BCB SGS | Selic, CDI, IPCA, câmbio | Grátis | ODbL; exige atribuição | ✅ Aprovável |
| Tesouro Transparente | Taxas e PUs do Tesouro Direto | Grátis | Dados abertos "para livre utilização" | ✅ Aprovável (licença exata a confirmar) |
| brapi.dev | Cotações BR e proventos | Grátis (sem proventos) a ~R$ 140/mês | Exibir no próprio app: sim; revender/redistribuir: não | ⚠️ Recomendado; depende da sua aprovação (pago) |
| SEC EDGAR | Fundamentos dos EUA (XBRL) | Grátis | Dados do governo dos EUA; 10 req/s e User-Agent com contato obrigatórios | ✅ Aprovável (domínio público a confirmar) |
| Cotações EUA | Preços EOD, dividendos, splits | US$ 20–50/mês (uso pessoal/interno) | Exibição a usuários finais costuma exigir licença comercial cara | ⚠️ Decisão sua |
| Damodaran Online | ERP, risco país, betas setoriais | Grátis | Sem licença explícita; uso com citação é comum | ⚠️ Citar sempre; pedir permissão se for comercial |

## 1. CVM — Dados Abertos

- **Dados:** DFP, ITR (inclui arquivos de composição do capital), FRE, FCA, cadastro de companhias abertas; FII: informe mensal, trimestral, anual e demonstrações financeiras.
- **Formato:** um ZIP de CSVs (separador `;`, codificação latin-1) por ano, por exemplo `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_AAAA.zip`. Os metadados ficam em `.../META/`. Para FII mensal, o caminho é `https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/`. Os ZIPs do ano corrente são regravados periodicamente; a frequência exata está a confirmar.
- **Custo:** gratuito.
- **Termos:** os datasets indicam licença ODbL, que permite uso comercial, armazenamento e exibição com atribuição. O share-alike só vale se redistribuirmos a base derivada em si; telas e gráficos não entram nisso. Os dados são fornecidos "tal como estão" e o portal pode limitar robôs ([termos](https://dados.cvm.gov.br/about)).
- **Conclusão:** usar. Exibir no rodapé e nos tooltips: "Fonte: CVM – Dados Abertos (ODbL)". Usar download condicional (ETag/Last-Modified) para não sobrecarregar o portal.

## 2. B3 — FNET e dados de mercado

- **FNET:** a consulta pública de documentos de fundos estruturados dispensa login. O download por ID existe (`/fnet/publico/downloadDocumento?id=`). A listagem em JSON usada pelo próprio site **não é documentada**. Não foram encontrados termos que tratem de acesso automatizado.
  - **Conclusão:** guardar só os metadados e o link para o documento original, sem copiar PDFs. Fazer poucas requisições (1 por fundo por dia). Pendente: confirmar com a B3 ou ler os termos do site.
- **COTAHIST:** arquivos históricos diários desde 1986, gratuitos e sem ajuste por proventos. A exibição comercial de dados de mercado é regida pela [Política de Consumo de Market Data da B3](https://www.b3.com.br/data/files/66/82/D8/17/973699100A29E189AC094EA8/Politica%20de%20Consumo%20Market%20Data%20B3.pdf), revisada em 2026 (OC 036-2026).
  - **Conclusão:** área cinzenta para um app pago. Adequado para desenvolvimento e validação; antes de monetizar, consultar a B3.
- **Proventos:** não foi encontrada fonte oficial aberta e estruturada da B3 (a confirmar). Por isso, os proventos dependem do provedor de cotações.

### Yahoo Finance — cotações e dividendos (fonte padrão desde 12/10/2026 — DECISOES.md D-027)

- **O que traz:** endpoint `query1.finance.yahoo.com/v8/finance/chart/{TICKER}.SA` com cotações diárias (abertura, máxima, mínima, fechamento ajustado por desdobramentos, quantidade negociada) e dividendos com data-ex.
- **Termos:** não é uma API oficial nem tem contrato, e os termos do Yahoo restringem uso automatizado. Escolha do usuário para **uso pessoal**. Não usar num produto público ou pago sem rever essa decisão.
- **Limitações:**
  - sem data de pagamento (o DY passa a contar pela data-ex);
  - sem separar JCP de dividendo (valores brutos);
  - volume financeiro estimado como fechamento × quantidade;
  - limite de requisições (HTTP 429), tratado com novas tentativas e pausa entre tickers.
- **Balanços continuam na CVM:** os dados contábeis do Yahoo para empresas brasileiras são resumidos e não indicam a conta de origem, o que quebraria a rastreabilidade das fórmulas.

### Proventos B3/FNET (alternativa com `FONTE_MERCADO=b3` — DECISOES.md D-025)

- **Ações — B3, "Empresas listadas → Eventos corporativos".** Consulta pública usada pelo próprio site da B3 (`GetListedSupplementCompany`, parâmetro em base64 com o código de 4 letras da companhia). Traz, por ISIN, os proventos em dinheiro (dividendos, JCP, rendimentos), com data de aprovação, data-com e data de pagamento. Não é documentada: pode mudar sem aviso. Uso pessoal; uso comercial exigiria licença da B3.
- **FIIs — FNET, "Aviso aos Cotistas – Estruturado / Rendimentos e Amortizações".** XML estruturado entregue pelo administrador do fundo, com valor por cota, data-base e data de pagamento. A listagem é a consulta pública do site do FNET (não documentada). Cada documento é baixado uma única vez.
- Ambas: uma requisição por companhia ou documento, com pausa entre elas; falhas isoladas não interrompem a carga e ficam registradas em "Status dos dados".

## 3. Banco Central — API SGS

- **Endpoint:** `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial=dd/MM/aaaa&dataFinal=dd/MM/aaaa`.
- **Séries:**
  - 432: meta Selic
  - 11: Selic diária
  - 12: CDI diário
  - 433: IPCA mensal
  - 1: dólar (venda); para PTAX compra/venda, avaliar a API Olinda/PTAX.
- **Limite:** desde 26/03/2025, filtro de datas obrigatório e janela máxima de 10 anos por consulta em séries diárias. O backfill será paginado por décadas.
- **Custo e termos:** gratuito, ODbL, com atribuição.

## 4. Tesouro Direto

- **Dataset oficial:** "Taxas dos Títulos Ofertados pelo Tesouro Direto" (Tesouro Transparente, CKAN). CSV diário com vírgula decimal, arquivo grande (centenas de MB), valores sujeitos a revisão. A URL exata do recurso será fixada na Fase 1.
- **JSON de taxas atuais do site do TD:** não é API oficial. **Não será usado.**
- **Termos:** dados abertos "para livre utilização"; a licença exata está a confirmar.

## 5. Cotações e proventos — Brasil (alternativas)

| Opção | Custo | Proventos | Uso no app | Observação |
|---|---|---|---|---|
| **brapi.dev — Startup** | ~R$ 100–120/mês (150 mil req., até 10 tickers/chamada) | Sim | Exibir no próprio app: sim; redistribuir: não | **Recomendada.** Preços divergem entre páginas do site; confirmar em brapi.dev/pricing |
| brapi.dev — Pro | ~R$ 117–140/mês (500 mil req., histórico completo, endpoints de FII) | Sim | idem | Se o histórico longo for necessário |
| brapi.dev — Gratuito | R$ 0 (15 mil req./mês, 1 ticker/chamada) | **Não** | idem | Suficiente para a Fase 1 só para preços |
| B3 COTAHIST | Grátis | Não | Área cinzenta (ver item 2) | Bom para histórico e validação |
| HG Brasil Finance | Grátis (cota diária) a R$ 1.179,90/mês | Sim | A confirmar | Alternativa/backup |
| Dados de Mercado (API) | A confirmar | Sim | A confirmar | Avaliar se a brapi não servir |
| Alpha Vantage | Grátis (25 req./dia) a US$ 250/mês | Parcial | Plano grátis possivelmente não comercial | Cobertura B3 fraca; não recomendada |
| Yahoo / yfinance | Grátis | Sim | **Não**: o próprio projeto diz "uso pessoal" | Descartada |
| Status Invest, Ward e similares | — | — | **Proibido** (scraping) | Descartados |

**Proposta:** Fase 1 com brapi gratuito + COTAHIST para preços. Proventos exigem brapi pago (ou outra fonte), o que depende da sua aprovação.

## 6. SEC EDGAR

- **Dados:** `submissions`, `companyfacts`, `companyconcept` e `frames` em JSON (sem chave de API), mais os Financial Statement Data Sets trimestrais (ZIP, desde 2009) ([documentação](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)).
- **Termos:** até 10 requisições/s e User-Agent com nome e e-mail de contato obrigatórios ([acesso](https://www.sec.gov/os/accessing-edgar-data)). Obras do governo federal dos EUA não têm copyright (17 USC 105); confirmar na política do site.
- **Ressalvas:**
  - As tags XBRL variam entre empresas e há reapresentações.
  - ETFs não têm demonstrações us-gaap.
  - **FFO/AFFO** de REITs não têm tag padrão. O FFO será calculado pela definição Nareit (lucro líquido + depreciação/amortização de imóveis − ganhos na venda de imóveis + impairment de imóveis). O AFFO será rotulado como "estimado", ou ficará indisponível quando faltar insumo.
- **Taxa de administração (expense ratio) de ETFs:** a melhor fonte gratuita estruturada parece ser o XBRL dos prospectos (Risk/Return Summary Data Sets) e dos relatórios aos cotistas (`ExpenseRatioPct`). A cobertura está a confirmar na Fase 7.

## 7. Cotações — EUA (alternativas)

| Provedor | Grátis | Plano pago mais barato | Exibir a usuários do app |
|---|---|---|---|
| EODHD | 20 req./dia | US$ 19,99/mês | Comercial só em plano sob consulta |
| Tiingo | 1.000 req./dia | US$ 30–50/mês | Uso interno; exibição a confirmar |
| Massive (ex-Polygon) | EOD, 2 anos de histórico | US$ 29/mês (individual) | Comercial no Business (~US$ 2.499/mês, a confirmar) |
| Financial Modeling Prep | 250 req./dia | ~US$ 22/mês | Licença pessoal; display exige acordo |
| Twelve Data | 800 créditos/dia | ~US$ 79/mês (pessoal) | Comercial a partir de ~US$ 149/mês (a confirmar) |
| Finnhub | 60 req./min (não comercial) | ~US$ 50/mês | Redistribuição só no Enterprise |
| Alpha Vantage | 25 req./dia | US$ 49,99/mês | Termos a confirmar |
| Stooq | Grátis (CSV) | — | Termos não encontrados |
| Yahoo / yfinance | — | — | **Não** (uso pessoal) |

**Proposta:** decidir só na Fase 7. Para desenvolvimento e beta privado, EODHD ou Tiingo. Antes de abrir ao público, pedir por escrito a cotação de uma licença de exibição.

## 8. Damodaran Online

- **Dados:**
  - ERP implícito mensal e anual (desde 1960);
  - `ctryprem.xlsx` (risco país, atualizado em janeiro e julho);
  - betas e custos de capital por setor (EUA, emergentes, global; atualização anual em janeiro).
- **Formato:** XLS/XLSX, sem API. Os nomes de arquivo e os layouts mudam entre versões, então o parser deve validar colunas e falhar de forma explícita quando algo mudar.
- **Termos:** não foi encontrada licença explícita. Terceiros usam os dados citando o autor ("with his permission").
  - **Conclusão:** citar autor, arquivo e data de referência em toda tela que use esses parâmetros. Se o produto for comercial, pedir permissão por e-mail.

## Regras transversais

- Toda linha gravada guarda `fonte_id`, `data_referencia`, `coletado_em` e `lote_ingestao_id`.
- Chaves de API só no `.env`; o `.env.example` fica sem valores reais.
- O User-Agent das requisições identifica o projeto e um e-mail de contato (exigência da SEC; boa prática nas demais fontes).
- Nenhum site com proibição de scraping será acessado.
