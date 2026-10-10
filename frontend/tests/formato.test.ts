import { describe, expect, it } from "vitest";
import { formatarData, formatarMoeda, formatarValor, nomeFonte } from "@/lib/formato";

describe("formatação pt-BR", () => {
  it("usa vírgula decimal e unidades", () => {
    expect(formatarValor(10.256, "x")).toBe("10,26");
    expect(formatarValor(0.1234, "%")).toBe("12,34%");
    expect(formatarValor(12.5, "R$/ação")).toBe("R$ 12,50");
    expect(formatarValor(5012, "un")).toBe("5.012");
    expect(formatarValor(null, "x")).toBe("—");
  });

  it("abrevia valores monetários", () => {
    expect(formatarMoeda(10_800_000)).toBe("R$ 10,80 mi");
    expect(formatarMoeda(2_500_000_000)).toBe("R$ 2,50 bi");
    expect(formatarMoeda(-1_400_000)).toBe("-R$ 1,40 mi");
    expect(formatarMoeda(45_000)).toBe("R$ 45,0 mil");
    expect(formatarMoeda(950)).toBe("R$ 950,00");
  });

  it("formata datas", () => {
    expect(formatarData("2024-12-31")).toBe("31/12/2024");
    expect(formatarData(null)).toBe("—");
  });

  it("traduz códigos de fonte", () => {
    expect(nomeFonte("CVM_DFP")).toBe("CVM — DFP");
    expect(nomeFonte("XYZ")).toBe("XYZ");
  });
});
