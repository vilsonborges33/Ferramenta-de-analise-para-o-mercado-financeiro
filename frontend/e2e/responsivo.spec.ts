import { expect, test } from "@playwright/test";

const PAGINAS = ["/", "/acoes", "/fiis", "/mais-baratas", "/metodologia", "/status", "/entrar"];

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
  await page.getByRole("button", { name: /Procedência de P\/L/ }).click();
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
