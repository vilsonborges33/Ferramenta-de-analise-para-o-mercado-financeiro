import { describe, expect, it } from "vitest";
import { paraApi, paraTela } from "@/lib/valuation";

describe("campos do valuation", () => {
  it("converte percentuais e listas entre a tela e a API", () => {
    expect(paraTela(0.15, "pct")).toBe("15");
    expect(paraTela(0.035, "pct")).toBe("3,5");
    expect(paraTela(0.138771, "pct")).toBe("13,88");
    expect(paraTela([0.1, 0.08], "lista_pct")).toBe("10; 8");
    expect(paraTela(8000000.4, "reais")).toBe("8000000");
    expect(paraApi("15", "pct")).toBeCloseTo(0.15);
    expect(paraApi("3,5", "pct")).toBeCloseTo(0.035);
    expect(paraApi("10; 8", "lista_pct")).toEqual([0.1, 0.08]);
    expect(paraApi("10; x", "lista_pct")).toBeNull();
    expect(paraApi("5,6", "inteiro")).toBe(6);
    expect(paraApi("", "reais")).toBeNull();
  });
});
