import { describe, expect, it } from "vitest";
import { buscar, filtrosPadrao, lerNumero, ordenar, paraConsulta, type ItemScreening } from "@/lib/screening";

const item = (ticker: string, posicao: number, p_l: number | null, nome = ""): ItemScreening =>
  ({ ticker, posicao, p_l, nome } as unknown as ItemScreening);

describe("screening", () => {
  it("lê números digitados em pt-BR", () => {
    expect(lerNumero("6,5")).toBe(6.5);
    expect(lerNumero("1.234,5")).toBe(1234.5);
    expect(lerNumero("6.5")).toBe(6.5);
    expect(lerNumero("")).toBeNull();
    expect(lerNumero("abc")).toBeNull();
  });

  it("converte os filtros para a unidade da API", () => {
    const e = filtrosPadrao();
    e.faixas.dy.min = "6";
    e.faixas.p_l.max = "12";
    e.setores = ["Bancos", "Telecomunicações"];
    e.besst = true;
    const q = paraConsulta(e);
    expect(q.get("dy_min")).toBe("0.06");
    expect(q.get("p_l_max")).toBe("12");
    expect(q.get("liquidez_min")).toBe("1000000");
    expect(q.has("dy_max")).toBe(false);
    expect(q.getAll("setores")).toEqual(["Bancos", "Telecomunicações"]);
    expect(q.get("besst")).toBe("true");
    expect(q.get("yield_bazin")).toBe("0.06");
  });

  it("ordena com valores ausentes no fim e busca por ticker ou nome", () => {
    const itens = [item("AAAA3", 2, 8), item("BBBB3", 1, null), item("CCCC3", 3, 4, "Companhia C")];
    expect(ordenar(itens, null).map((i) => i.ticker)).toEqual(["BBBB3", "AAAA3", "CCCC3"]);
    expect(ordenar(itens, { coluna: "p_l", crescente: true }).map((i) => i.ticker)).toEqual(["CCCC3", "AAAA3", "BBBB3"]);
    expect(ordenar(itens, { coluna: "p_l", crescente: false }).map((i) => i.ticker)).toEqual(["AAAA3", "CCCC3", "BBBB3"]);
    expect(buscar(itens, "companhia").map((i) => i.ticker)).toEqual(["CCCC3"]);
  });
});
