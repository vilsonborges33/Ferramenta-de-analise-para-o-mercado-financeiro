import { expect, test } from "@playwright/test";

const PAGINAS = ["/", "/acoes", "/fiis", "/metodologia", "/entrar"];

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
  const exemplo = page.locator("tbody a", { hasText: "EXMP3" });
  const primeiro = (await exemplo.count()) ? exemplo : page.locator("tbody a").first();
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
