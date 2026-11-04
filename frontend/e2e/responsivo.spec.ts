import { expect, test } from "@playwright/test";

const PAGINAS = ["/", "/acoes", "/fiis", "/fiis/ranking", "/mais-baratas", "/valuations", "/carteira", "/diario", "/metodologia", "/status", "/entrar"];

for (const caminho of PAGINAS) {
  test(`sem rolagem horizontal da página em ${caminho}`, async ({ page }) => {
    await page.goto(caminho);
    const larguras = await page.evaluate(() => ({
      documento: document.documentElement.scrollWidth,
      janela: window.innerWidth,
    }));
    expect(larguras.documento).toBeLessThanOrEqual(larguras.janela);
  });
}

test("página do ativo mostra procedência ao tocar no ⓘ", async ({ page }, info) => {
  await page.goto("/acoes");
  await expect(page.locator("tbody")).toHaveCount(0); // nada listado antes de digitar
  await page.getByLabel("Buscar ativo").fill(process.env.TICKER_TESTE ?? "EXMP");
  const primeiro = page.locator("tbody a").first();
  await primeiro.waitFor({ timeout: 5000 }).catch(() => undefined);
  test.skip((await primeiro.count()) === 0, "base sem ações carregadas");
  await primeiro.click();
  await page.waitForURL(/\/acoes\/.+/);
  const larguras = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(larguras[0]).toBeLessThanOrEqual(larguras[1]);
  await page.getByRole("button", { name: /Procedência de P\/L/ }).first().click();
  const painel = page.getByRole("dialog");
  await expect(painel).toContainText("Como é calculado");
  const caixa = await painel.boundingBox();
  const janela = page.viewportSize();
  expect(caixa && janela && caixa.x >= 0 && caixa.x + caixa.width <= janela.width).toBeTruthy();
  if (process.env.CAPTURAS) await page.screenshot({ path: `${process.env.CAPTURAS}/ativo-${info.project.name}.png`, fullPage: true });
});

test("ranking de ações: filtros, ordenação, colunas e exportação", async ({ page }, info) => {
  await page.goto("/mais-baratas");
  await expect(page.getByRole("note")).toContainText("Não constituem recomendação");
  const linhas = page.locator("tbody tr");
  await expect(linhas.first()).toBeVisible();
  test.skip((await page.locator("tbody a").count()) === 0, "base sem ações com cotação");
  await page.getByLabel("Ranquear por").selectOption("greenblatt");
  await page.getByRole("button", { name: /^P\/L/ }).click();
  await expect(page.locator("th[aria-sort=descending]")).toContainText("P/L");
  await page.locator("summary", { hasText: "Colunas" }).click();
  await page.getByRole("checkbox", { name: "Setor" }).check();
  await expect(page.locator("thead")).toContainText("Setor");
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: ".csv" }).click()]);
  expect(download.suggestedFilename()).toMatch(/^screening-acoes-.*\.csv$/);
  const mostrar = page.getByRole("button", { name: "Mostrar filtros" });
  if (await mostrar.isVisible()) await mostrar.click(); // no celular os filtros começam recolhidos
  await page.getByLabel("P/L máximo").fill("0,01");
  await expect(page.locator("tbody")).toContainText("Nenhuma ação passa nos filtros");
  const larguras = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(larguras[0]).toBeLessThanOrEqual(larguras[1]);
  if (process.env.CAPTURAS) await page.screenshot({ path: `${process.env.CAPTURAS}/ranking-${info.project.name}.png`, fullPage: true });
});

test("favoritos: entrar, marcar a estrela e filtrar", async ({ page }) => {
  await page.goto("/mais-baratas");
  await expect(page.locator("tbody tr").first()).toBeVisible();
  test.skip((await page.locator("tbody a").count()) === 0, "base sem ações com cotação");
  const email = `teste${Date.now()}${Math.floor(Math.random() * 1000)}@exemplo.com`;
  const r = await page.request.post("/api/auth/registrar", { data: { email, senha: "senha-forte-123" } });
  expect(r.ok()).toBeTruthy();
  await page.reload();
  const estrela = page.getByRole("button", { name: /Adicionar .* dos favoritos/ }).first();
  await estrela.click();
  await expect(page.getByRole("button", { name: /Remover .* dos favoritos/ }).first()).toBeVisible();
  await page.getByRole("button", { name: "★ Favoritos" }).click();
  await expect(page.locator("tbody a")).toHaveCount(1);
});

test("página da ação: seções, valuation ajustável, dividendos e histórico", async ({ page }) => {
  await page.goto(`/acoes/${process.env.TICKER_TESTE ?? "EXMP3"}`);
  test.skip((await page.locator("h1").count()) === 0, "base sem a ação de teste");
  for (const secao of ["Cotação", "Dividendos", "Indicadores", "Empresa"])
    await expect(page.getByRole("navigation", { name: "Seções" }).getByRole("link", { name: secao })).toBeVisible();
  const valuation = page.locator("#valuation");
  await expect(valuation).toContainText("Não constituem recomendação");
  await expect(valuation).toContainText("Margem de segurança");
  const fator = valuation.getByText("22,5", { exact: true });
  if (await fator.isVisible()) {
    await valuation.getByRole("button", { name: "Aumentar Fator" }).click();
    await expect(valuation.getByText("23", { exact: true })).toBeVisible();
  }
  await page.locator("#historico").getByRole("tab", { name: "Balanço" }).click();
  const larguras = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(larguras[0]).toBeLessThanOrEqual(larguras[1]);
});

test("valuation: comparativo, premissas editáveis e sensibilidade", async ({ page }) => {
  await page.goto(`/valuation/${process.env.TICKER_TESTE ?? "EXMP3"}`);
  await expect(page.getByRole("note")).toContainText("Não constituem recomendação");
  test.skip(await page.getByText("Valuation disponível só para ações").isVisible(), "base sem a ação de teste");
  await expect(page.getByText("Valor por ação: taxa")).toBeVisible();
  const antes = await page.locator(".text-3xl").first().textContent();
  await page.getByLabel("WACC").fill("30");
  await expect(page.locator(".text-3xl").first()).not.toHaveText(antes ?? "");
  await page.getByRole("tab", { name: "Modelo de Gordon" }).click();
  await expect(page.getByLabel("Custo do capital próprio")).toBeVisible();
  const larguras = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(larguras[0]).toBeLessThanOrEqual(larguras[1]);
});

test("FII: Gordon ajustado, composição, imóveis e documentos", async ({ page }) => {
  await page.goto(`/fiis/${process.env.FII_TESTE ?? "HGLG11"}`);
  test.skip((await page.locator("h1").count()) === 0, "base sem o FII de teste");
  await expect(page.locator("#valuation")).toContainText("Gordon ajustado");
  await expect(page.locator("#valuation")).toContainText("Não constituem recomendação");
  await page.getByRole("button", { name: "Aumentar Prêmio sobre a taxa" }).click();
  await expect(page.locator("#valuation")).toContainText("2,5%");
  for (const id of ["composicao", "endividamento", "imoveis", "historico", "documentos"])
    await expect(page.locator(`#${id}`)).toBeVisible();
  const larguras = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(larguras[0]).toBeLessThanOrEqual(larguras[1]);
});

test("ranking de FIIs: filtros e exportação", async ({ page }) => {
  await page.goto("/fiis/ranking");
  await expect(page.getByRole("note")).toContainText("Não constituem recomendação");
  await expect(page.locator("tbody tr").first()).toBeVisible();
  test.skip((await page.locator("tbody a").count()) === 0, "base sem FIIs com cotação");
  await page.getByRole("button", { name: "Papel" }).click();
  await page.getByLabel("P/VP máximo").fill("0,01");
  await expect(page.locator("tbody")).toContainText("Nenhum fundo passa nos filtros");
  await page.getByRole("button", { name: "Limpar filtros" }).click();
  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: ".csv" }).click()]);
  expect(download.suggestedFilename()).toMatch(/^screening-fiis-.*\.csv$/);
  const larguras = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(larguras[0]).toBeLessThanOrEqual(larguras[1]);
});

test("carteira: criar, lançar, ver posições, rentabilidade, otimizador e diário", async ({ page }) => {
  await page.goto("/carteira");
  const email = `cart${Date.now()}${Math.floor(Math.random() * 1000)}@exemplo.com`;
  expect((await page.request.post("/api/auth/registrar", { data: { email, senha: "senha-forte-123" } })).ok()).toBeTruthy();
  const criada = await page.request.post("/api/carteiras", { data: { nome: "Teste" } });
  const id = (await criada.json()).id;
  for (const [ticker, qtd, preco] of [["EXMP3", 100, 10], ["EXMP4", 50, 12]] as const) {
    const r = await page.request.post(`/api/carteiras/${id}/lancamentos`,
      { data: { ticker, tipo: "COMPRA", data: "2025-01-02", quantidade: qtd, preco } });
    test.skip(!r.ok(), "base sem as ações de teste");
  }
  await page.reload();
  await expect(page.locator("tbody")).toContainText("EXMP3");
  await page.getByRole("tab", { name: "Lançamentos" }).click();
  await expect(page.getByText("Importar extrato da B3")).toBeVisible();
  await page.getByRole("tab", { name: "Rentabilidade" }).click();
  await expect(page.getByText("Desde o início")).toBeVisible();
  await page.getByRole("tab", { name: "Otimizador" }).click();
  await expect(page.getByText("não constitui recomendação", { exact: false }).first()).toBeVisible();
  const larguras = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(larguras[0]).toBeLessThanOrEqual(larguras[1]);
  await page.goto("/diario");
  await page.getByLabel("Decisão").fill("Comprar EXMP3");
  await page.getByLabel("Tese").fill("Desconto sobre o valor de Graham.");
  await page.getByRole("button", { name: "Registrar decisão" }).click();
  await expect(page.locator("article")).toContainText("Comprar EXMP3");
});
