# Validação da Fase 1 com dados reais — pendente

A rede do ambiente onde a Fase 1 foi construída bloqueia os domínios das fontes (dados.cvm.gov.br,
bvmf.bmfbovespa.com.br, api.bcb.gov.br, brapi.dev, tesouroTransparente). Os conectores foram testados
com arquivos de amostra no formato documentado, com valores fictícios. Antes de dar a Fase 1 por
encerrada, é preciso rodar a carga real e conferir os itens abaixo.

## Como rodar

```bash
docker compose up -d --build
docker compose exec backend python -m app.jobs.cli carga-inicial --de 2019 --ate 2026
docker compose exec db psql -U analise -c "select f.codigo, l.status, l.linhas_gravadas, left(l.erro, 80) from lote_ingestao l join fonte f on f.id = l.fonte_id order by l.id"
```

## O que conferir (formatos de memória, não confirmados nas páginas oficiais)

- [ ] **CVM DFP/ITR:** nomes dos CSVs no ZIP e colunas (`ESCALA_MOEDA`, `ORDEM_EXERC`, `ST_CONTA_FIXA`). Se o esquema mudar, o conector falha com `EsquemaInesperado`, sem gravar nada.
- [ ] **Composição do capital:** quantidades em unidades (não em milhares).
- [ ] **Códigos de conta** do plano geral (3.05 = EBIT, 3.11.01 = controladores, 2.03.09 = não controladores) e regras por descrição para bancos.
- [ ] **FCA valores mobiliários:** colunas `Codigo_Negociacao`, `Mercado`, `Segmento`.
- [ ] **FII informe mensal:** nomes das colunas após a Resolução CVM 175 e se os "Percentual_*" vêm em fração (0,008) ou em pontos percentuais (0,8).
- [ ] **COTAHIST:** URL dos arquivos anual/diário e CODBDI dos ETFs.
- [ ] **Tesouro:** URL do recurso CSV no CKAN.
- [ ] **brapi:** formato de `regularMarketTime` e de `dividendsData`.
- [ ] **Indicadores de 10 ações e 10 FIIs** (`TICKERS_ACOMPANHADOS`) conferidos contra as demonstrações da CVM, com tolerância de 1% (critério de aceitação).
