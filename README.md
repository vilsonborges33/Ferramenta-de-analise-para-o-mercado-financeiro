# Análise de Ações e FIIs

Ferramenta pessoal de análise fundamentalista de ações e fundos imobiliários da B3. Cada número
mostra a fórmula, a referência (livro/autor) e a fonte e a data do dado bruto. **Não constitui
recomendação de investimento.**

Documentação: `docs/ESPECIFICACAO.md` (escopo), `docs/ARQUITETURA.md`, `docs/DECISOES.md`,
`docs/FONTES_DE_DADOS.md`.

## Subir tudo

```bash
cp .env.example .env        # preencha JWT_SEGREDO e CONTATO_USER_AGENT
docker compose up -d --build
```

- Interface: http://localhost:3000
- API: http://localhost:8000 (documentação interativa em http://localhost:8000/docs)

O serviço `worker` agenda as atualizações diárias (horário de Brasília). Para a primeira carga
(cadastro CVM, DFP/ITR, informes de FII, cotações COTAHIST, Selic/CDI/IPCA, Tesouro e indicadores):

```bash
docker compose exec backend python -m app.jobs.cli carga-inicial --de 2019 --ate 2026
```

Outros comandos: `companhias`, `demonstracoes 2025 2026`, `fiis 2026`, `cotacoes-historicas 2026`,
`cotacoes-do-dia`, `macro`, `indicadores --tickers PETR4 VALE3`.

## Desenvolvimento

```bash
# backend (precisa de um PostgreSQL local; os testes usam o banco analise_teste)
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest --cov=app/metodologias     # testes
.venv/bin/ruff check app tests              # lint

# frontend
cd frontend && npm ci
npm test                 # Vitest
npm run typecheck
npx playwright test      # com frontend e backend no ar (BASE_URL, PW_CHROMIUM opcionais)
```
