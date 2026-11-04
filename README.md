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

O serviço `worker` agenda as atualizações diárias (horário de Brasília). Numa instalação nova (banco
sem demonstrações da CVM), ele roda a **carga inicial sozinho** logo ao subir: cadastro CVM, DFP/ITR
dos últimos 6 anos, informes de FII, cotações COTAHIST, Selic/CDI/IPCA, Tesouro e indicadores.
Acompanhe com `docker compose logs -f worker`. Para rodar manualmente:

```bash
docker compose exec backend python -m app.jobs.cli carga-inicial --de 2020 --ate 2026
```

Outros comandos: `proventos` (B3 + FNET, depois recalcula os indicadores), `companhias`, `demonstracoes 2025 2026`, `fiis 2026`, `cotacoes-historicas 2026`,
`cotacoes-do-dia`, `macro`, `indicadores --tickers PETR4 VALE3`.

## Manter atualizado (Windows)

Clone com Git uma única vez e, a cada atualização, dê dois cliques em `atualizar.bat`: ele baixa a
versão mais recente (`git pull`) e reconstrói os containers. As migrações do banco rodam sozinhas
quando o backend sobe; os dados já carregados são preservados.

## Dados sempre em dia (Windows)

- **`iniciar.bat`** (dois cliques): abre o Docker Desktop se preciso, liga o sistema e abre o navegador.
- **`instalar-inicio-automatico.bat`** (uma vez): faz o sistema ligar sozinho ao entrar no Windows.
  Para desfazer: `instalar-inicio-automatico.bat remover`.
- Toda vez que o sistema liga, o worker confere a data dos dados e busca só o que ficou para trás
  (cotações e dividendos dos dias perdidos, Selic/Tesouro e, se estiverem com mais de um dia,
  balanços e informes da CVM); depois recalcula os indicadores. Para rodar à mão: `cli por-em-dia`.
- Computador suspenso no horário de uma tarefa: ela roda ao acordar (até 12 h de atraso).

## Desenvolvimento

```bash
# backend (precisa de um PostgreSQL local; os testes usam o banco analise_teste)
cd backend && python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
TEST_DATABASE_URL=postgresql+psycopg://analise:analise@localhost:5432/analise_teste \
  .venv/bin/pytest --cov=app/metodologias     # testes (NUNCA no banco de uso: eles recriam o schema)
.venv/bin/ruff check app tests              # lint

# frontend
cd frontend && npm ci
npm test                 # Vitest
npm run typecheck
npx playwright test      # com frontend e backend no ar (BASE_URL, PW_CHROMIUM opcionais)
```
