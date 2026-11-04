# Conferência dos indicadores com a Ward (04/11/2026)

Comparação feita navegando na conta do usuário na Ward (somente leitura), com cotações de fechamento de
03/11/2026. A Ward serve só como referência de conferência; nenhum dado dela entra no sistema.

## Ações

| Ticker | Indicador | Nosso | Ward | Situação |
|---|---|---|---|---|
| PETR4 | P/L · P/VP · ROE | 4,90 · 1,36 · 27,73% | 4,90 · 1,36 · 27,73% | igual |
| PETR4 | DY 12m · payout | 7,23% · 35,4% | 7,25% · 35,5% | igual (arredondamento) |
| PETR4 | EV/EBIT · EV/EBITDA · DL/EBITDA | 5,49 · 3,73 · 1,14 | 5,49 · 3,73 · 1,14 | igual |
| PETR4 | P/EBIT · P/EBITDA | 3,52 · 2,39 | 3,80 · 2,59 | **critério**: usamos a cotação da PETR4 × ações totais (D-008); a Ward usa o valor de mercado (PETR3 + PETR4) |
| PETR4 | ROIC | 15,5% | 17,3% | não investigada (provável definição diferente de capital investido) |
| WEGE3 | P/L · P/VP · ROE · DY | 32,91 · 10,34 · 31,41% · 4,07% | 32,92 · 10,34 · 31,41% · 4,07% | igual |
| WEGE3 | Margem líquida | 15,4% | 16,4% | não investigada (provável diferença de receita ou de lucro usado) |
| ITUB4 | P/L · ROE · P/VP | 9,06 · 21,50% · 1,95 | 9,06 · 21,50% · 1,95 | igual |
| ITUB4 | DY 12m | 8,06% | 8,23% | proventos do Yahoo × B3 (próximo) |
| VALE3 | ROE · DY · EV/EBITDA* | 1,12% · 9,32% · 7,18 | 1,12% · 9,32% · 7,68 | ROE e DY iguais |
| VALE3 | Ações / valor de mercado | 4,07 bi · R$ 245 bi | 4,44 bi · R$ 267 bi | **critério**: usamos capital integralizado − tesouraria do ITR 3T26 (CVM); a diferença muda P/L e VPA |
| BBAS3 | ROE · P/L · LPA | ~~9,94% · 5,00 · 3,24~~ → **6,60% · 7,53 · 2,15** | 6,60% · 7,56 · 2,14 | **erro nosso, corrigido** (ver abaixo) |

\* Diferença do EV/EBITDA da VALE3 vem do mesmo valor de mercado.

## Fundos imobiliários

| Ticker | Indicador | Nosso | Ward | Situação |
|---|---|---|---|---|
| MXRF11 | P/VP · VP/cota · PL | 0,91 · R$ 9,35 · R$ 5,30 bi | 0,91 · R$ 9,35 · R$ 5,30 bi | igual |
| MXRF11 | DY 12m | 12,92% | 14,05% | o rendimento com data-com 30/10/2026 ainda não estava no Yahoo; entra na próxima atualização |
| MXRF11 | Alavancagem | 3,37% | 2,42% | não investigada (provável definição diferente) |

## Erro corrigido: Banco do Brasil

No ITR do 3º trimestre de 2025, o BB entregou à CVM a conta "Atribuído aos Sócios da Empresa Controladora"
duas vezes: 3.09.01 com valor zero e 3.11.01 com R$ 2,24 bi. A padronização pegava a primeira (zerada) e o
4º trimestre de 2025 (anual − 9 meses) também saía errado, inflando o lucro de 12 meses de R$ 12,3 bi para
R$ 18,5 bi. Correção em `backend/app/ingestao/padronizacao.py` (uma conta zerada não esconde outra com valor),
teste `test_conta_duplicada_zerada_nao_esconde_a_que_tem_valor` e reprocessamento de todas as empresas.
