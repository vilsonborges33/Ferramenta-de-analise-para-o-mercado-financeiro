# Conferência dos indicadores com a Ward

A Ward serve só como referência de conferência, consultada na conta do usuário em modo somente leitura.
Nenhum dado dela entra no sistema.

## Segunda conferência (10/11/2026)

### Como foi feita

- **Amostra:** 14 ações (PETR4, VALE3, ITUB4, BBAS3, WEGE3, BBSE3, TAEE11, CMIG4, ABEV3, ITSA4, KLBN11, BRBI11,
  SANB11, ENGI11) e 6 FIIs (HGLG11, MXRF11, KNRI11, XPML11, KNCR11, BTLG11), com cerca de 30 números por ação e
  13 por FII.
- **Também comparados:**
  - o ranking padrão de ações da Ward (52 ativos) contra o nosso screening com os mesmos filtros;
  - as calculadoras de juros compostos e de conversão de taxas;
  - o preço teto de Gordon dos FIIs, com os parâmetros da Ward.
- **Script:** `comparar.py` (no scratchpad da sessão) lê a nossa API e coloca as métricas que dependem do preço
  na mesma cotação da Ward antes de comparar. Tolerância: 2%.
- **Testes automáticos, antes e depois:**
  - backend: 190 → 202 testes (+12 novos);
  - frontend: 9 testes Vitest e `tsc` sem erros;
  - `ruff` limpo.

### Resultado depois das correções

| Grupo | Igual à Ward (até 2%) | Diferenças restantes |
|---|---|---|
| P/L, P/VP, LPA, VPA, Graham | 12 de 14 ações | VALE3 (quantidade de ações, critério) e ITSA4 (balanço mais novo na Ward) |
| ROE · margem bruta · margem EBITDA · DL/EBITDA · dívida bruta | 100% das ações em que se aplicam | — |
| Valor de mercado · EV · EV/EBIT · EV/EBITDA | iguais, exceto VALE3 | VALE3 (mesma causa) |
| DY 12m · dividendos 12m · payout | 8 de 10 | ITUB4 −2%, BBAS3 −5% (Yahoo traz um provento a menos que a B3) |
| Volatilidade 12m | 9 de 10 (TAEE11 −2,8%) | — |
| FIIs: P/VP, DY, VP/cota, PL, ativo, passivo, cotas, dividendos 12m, volatilidade | 6 de 6 | — |
| FIIs: alavancagem | 5 de 6 (KNCR11: 0,10% × 0,07%) | — |
| FIIs: retorno 12m | diferença ≤ 1 p.p. | — |
| Units (TAEE11, SANB11, ENGI11, KLBN11, BRBI11) | P/L, LPA, VPA, ROE, EV/EBITDA iguais | — |
| Juros compostos | idêntico (R$ 8.089,99) | — |
| Conversor de taxas | idêntico ao ano (0,9% a.m. = 11,35% a.a.) | taxa diária: Ward usa 30 dias/mês, nós 365 dias/ano |
| Screening com os filtros padrão da Ward | 47 de 52 em comum (antes 41) | ver abaixo |

### Erros nossos encontrados e corrigidos

1. **Recálculo de indicadores parado.**
   - O que acontecia: um FII com rendimento mas sem cotação (SNLG11, RMLE11, ASMT11, PMOV11) derrubava o
     recálculo inteiro.
   - Efeito: todos os números ficaram presos na cotação de 06/11. Os informes trimestrais de FII de 30/09
     também não entravam.
   - Correção: o insumo vazio é descartado, e uma falha num ativo é registrada sem interromper os outros.
2. **Risco (volatilidade, retorno 12m e Sharpe) sem proventos e sem filtro de cotação errada.**
   - O que acontecia: o retorno de 12 meses usava só o preço, sem os dividendos.
   - Efeito no retorno: FIIs apareciam com −9% quando o retorno total era +3%.
   - Cotação errada do Yahoo: três pregões do XPML11 a R$ 1,06 (em vez de ~R$ 110) davam volatilidade de 10.340%.
   - Correção: risco calculado sobre o retorno total, com proventos reinvestidos na data-ex. Picos isolados
     (até 5 pregões fora de 2× da mediana vizinha) saem; desdobramentos ficam.
   - Resultado: PETR4 tem Sharpe 1,24 (Ward 1,20) e XPML11 tem volatilidade de 13,8% (Ward 13,6%).
3. **Units sem nenhum indicador.**
   - O que acontecia: a classe UNIT (TAEE11, KLBN11, SANB11, ENGI11…) ficava fora do recálculo, da lista e do
     ranking.
   - Correção: indicadores por unit, com LPA = lucro ÷ (ações ÷ ações por unit). A composição de cada unit fica
     numa tabela no código, conferida pelas cotações (ENGI11 = ON + 4 PN; SANB11 = ON + PN; TAEE11 = ON + 2 PN).
   - Empresas negociadas quase só pela unit: a classe sem cotação vale preço da unit ÷ ações por unit.
4. **Lucro dos controladores zerado.**
   - O que acontecia: em 101 empresas e 488 trimestres desde 2024, a empresa entrega 3.11.01 e 3.11.02
     zeradas (Klabin, BR Partners…).
   - Efeito: o lucro de 12 meses ficava errado. A KLBN11 aparecia com prejuízo e LPA −0,43, quando a Ward
     mostra +0,33.
   - Correção: com a divisão zerada, vale o lucro consolidado.
5. **DRE consolidada toda zerada.**
   - O que acontecia: a TIM (DFP 2025) entrega a DRE consolidada toda zerada e os números só na individual.
   - Efeito: o lucro anual saía zero e o 4º trimestre −R$ 2,98 bi. A TIMS3 aparecia com P/L 3.666; agora 11,6.
   - Correção: o consolidado só é usado quando tem algum valor (4 empresas, 13 documentos).
6. **Holdings tratadas como banco.**
   - O que acontecia: o tipo de plano vinha só do setor da CVM. Itaúsa, BR Partners, Porto Seguro, Caixa
     Seguridade, Wiz, Qualicorp, Alfa Holdings e Arandu entregam a DRE de empresa comum.
   - Efeito: ficavam sem receita, margens, dívida e EV.
   - Correção: o plano agora segue o formato da DRE entregue.
   - Resultado: ITSA4 tem margem 214% (Ward 217%) e EV/EBITDA 7,61 (Ward 7,39).
7. **Alavancagem de FII com rendimentos a distribuir.**
   - Correção: rendimentos a distribuir e taxas a pagar saem do passivo, porque não são dívida.
   - Resultado: HGLG11 tem 13,95% (Ward 13,95%; antes 14,60%) e MXRF11 tem 2,43% (Ward 2,42%; antes 3,37%).
8. **Vale com ações em tesouraria descontadas duas vezes.**
   - O que acontecia: desde o ITR de 31/03/2026 a Vale informa o capital integralizado já sem a tesouraria.
   - Efeito: contávamos 4,07 bi de ações; o certo são 4,256 bi. A B3 (via Ward) mostra 4,439 bi emitidas,
     que é 4,256 bi + 0,183 bi em tesouraria.
   - Correção: exceção explícita por CNPJ (D-043).
9. **Empresas sem ticker.**
   - O padrão de ticker recusava raiz com dígito (B3SA3).
   - Só o FCA do ano corrente era lido, então quem ainda não entregou o de 2026 ficava sem ticker (CMIN3).
   - Correção: 25 tickers a mais, com balanços reprocessados a partir dos arquivos da CVM já baixados.
10. **Screening reprovava bancos e seguradoras.**
    - O que acontecia: no filtro de DL/EBITDA ou de margem líquida, essas métricas "não se aplicam" a bancos e
      seguradoras, e o vazio contava como reprovação.
    - Correção: agora passam, como na Ward. Com isso entraram ITUB4, ITUB3, ABCB4, PINE4 e BBSE3.

### Diferenças de critério (sem mudança; nossa escolha está documentada)

| Item | Nós | Ward |
|---|---|---|
| P/EBIT, P/EBITDA de empresa com ON e PN (PETR4, CMIG4) | cotação do ticker × total de ações (D-008) | valor de mercado da empresa |
| Quantidade de ações | em circulação (sem tesouraria) | emitidas (VALE3: 4,44 bi) |
| ROIC | EBIT × (1 − 34%) ÷ (PL + dívida líquida) | outra base de capital (sempre maior) |
| Margem líquida e "lucro atual" | lucro dos controladores | lucro consolidado ou do último ano (WEGE3, ABEV3, BBAS3) |
| Gordon (FII) | crescimento 0% e Tesouro Prefixado mais longo, líquido de IR | crescimento 4% e Tesouro Prefixado 2029, bruto. Com os parâmetros da Ward, nosso cálculo dá o mesmo valor: HGLG11 132,13 × 132,08; MXRF11 11,66 × 11,66; KNCR11 134,12 × 134,14 |
| Bazin na página do ativo | dividendos dos últimos 12 meses (igual ao "12M" do ranking da Ward) | média de dividendos por ação de vários anos |
| Peter Lynch | PEG = P/L ÷ crescimento do lucro em 5 anos | (crescimento 3% + DY) ÷ P/L |
| Sharpe 12m | (retorno total 12m − CDI 12m) ÷ volatilidade | conta não informada; diverge mesmo com retorno e volatilidade iguais. Exemplo: BBSE3 conferida à mão, preço +18,5% e R$ 4,59 de dividendos dão retorno total de ~35% |

### Diferenças de fonte ou de data

- **Vacância de FII:** o informe trimestral da CVM mais recente para HGLG11, KNRI11 e BTLG11 é de 30/06; a Ward
  parece usar dado mais novo ou do relatório gerencial. Os informes de 30/09 já carregados (92 fundos) entraram
  depois da correção 1.
- **Proventos (ITUB4, BBAS3):** o Yahoo não traz um ou dois proventos que a B3 traz, e não distingue JCP de
  dividendo.
- **Screening:** os 5 ativos que ainda faltam em relação à Ward se explicam por:
  - PSSA3: margem de 8,5% abaixo do filtro; a Ward não calcula margem para ela;
  - BRBI11: DL/EBITDA 66; a Ward mostra "-" no ranking e 66 na página;
  - CXSE3: margem não calculada;
  - B3SA3: já tem balanço e indicadores (P/L 13,58 × Ward 13,71; DY 6,23% nos dois);
  - CMIN3: a CSN Mineração ainda está sem ticker no FCA da CVM.
- **Reprocessamento:** 21 empresas que estavam sem balanço passaram a ter (B3, JBS, Natura, GOL, Banco PAN, Wilson
  Sons…). A JBSS3 fica sem valor de mercado porque a JBS migrou para a bolsa de Nova York.

### Pendências encontradas, fora desta correção

- O banco de uso tem os tickers de teste EXMP3, EXMP4 e BEXM3 (restos do incidente D-042). EXMP3 e EXMP4 estão
  ligados ao Banco do Brasil, porque o CNPJ de exemplo dos testes (`tests/amostras.py`) é o CNPJ real do BB.
  Não alteram números (não têm cotação), mas aparecem como "outros tickers" do BBAS3.
- A SEC (EUA) não atualiza porque falta `CONTATO_USER_AGENT` no `.env`.
- A tabela `unit_composicao` do esquema continua sem uso; a composição das units está em `COMPOSICAO_UNITS`.

## Primeira conferência (04/11/2026)

Feita com cotações de fechamento de 03/11/2026.

### Ações

| Ticker | Indicador | Nosso | Ward | Situação |
|---|---|---|---|---|
| PETR4 | P/L · P/VP · ROE | 4,90 · 1,36 · 27,73% | 4,90 · 1,36 · 27,73% | igual |
| PETR4 | DY 12m · payout | 7,23% · 35,4% | 7,25% · 35,5% | igual (arredondamento) |
| PETR4 | EV/EBIT · EV/EBITDA · DL/EBITDA | 5,49 · 3,73 · 1,14 | 5,49 · 3,73 · 1,14 | igual |
| PETR4 | P/EBIT · P/EBITDA | 3,52 · 2,39 | 3,80 · 2,59 | **critério**: usamos a cotação da PETR4 × ações totais (D-008); a Ward usa o valor de mercado (PETR3 + PETR4) |
| PETR4 | ROIC | 15,5% | 17,3% | definição diferente de capital investido (ver 2ª conferência) |
| WEGE3 | P/L · P/VP · ROE · DY | 32,91 · 10,34 · 31,41% · 4,07% | 32,92 · 10,34 · 31,41% · 4,07% | igual |
| WEGE3 | Margem líquida | 15,4% | 16,4% | critério: lucro dos controladores × consolidado (ver 2ª conferência) |
| ITUB4 | P/L · ROE · P/VP | 9,06 · 21,50% · 1,95 | 9,06 · 21,50% · 1,95 | igual |
| ITUB4 | DY 12m | 8,06% | 8,23% | proventos do Yahoo × B3 (próximo) |
| VALE3 | ROE · DY · EV/EBITDA* | 1,12% · 9,32% · 7,18 | 1,12% · 9,32% · 7,68 | ROE e DY iguais |
| VALE3 | Ações / valor de mercado | 4,07 bi · R$ 245 bi | 4,44 bi · R$ 267 bi | corrigido na 2ª conferência (4,256 bi) |
| BBAS3 | ROE · P/L · LPA | ~~9,94% · 5,00 · 3,24~~ → **6,60% · 7,53 · 2,15** | 6,60% · 7,56 · 2,14 | **erro nosso, corrigido** (ver abaixo) |

\* Diferença do EV/EBITDA da VALE3 vem do mesmo valor de mercado.

### Fundos imobiliários

| Ticker | Indicador | Nosso | Ward | Situação |
|---|---|---|---|---|
| MXRF11 | P/VP · VP/cota · PL | 0,91 · R$ 9,35 · R$ 5,30 bi | 0,91 · R$ 9,35 · R$ 5,30 bi | igual |
| MXRF11 | DY 12m | 12,92% | 14,05% | o rendimento com data-com 30/10/2026 ainda não estava no Yahoo; entra na próxima atualização |
| MXRF11 | Alavancagem | 3,37% | 2,42% | corrigido na 2ª conferência (2,43%) |

### Erro corrigido: Banco do Brasil

No ITR do 3º trimestre de 2025, o BB entregou à CVM a conta "Atribuído aos Sócios da Empresa Controladora"
duas vezes: 3.09.01 com valor zero e 3.11.01 com R$ 2,24 bi. A padronização pegava a primeira (zerada).

O 4º trimestre de 2025 (anual − 9 meses) também saía errado, e o lucro de 12 meses subia de R$ 12,3 bi para
R$ 18,5 bi.

Correção em `backend/app/ingestao/padronizacao.py` (uma conta zerada não esconde outra com valor), com o teste
`test_conta_duplicada_zerada_nao_esconde_a_que_tem_valor` e o reprocessamento de todas as empresas.
