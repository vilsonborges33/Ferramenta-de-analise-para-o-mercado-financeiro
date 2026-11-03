import { describe, expect, it } from "vitest";
import { recortar } from "@/componentes/GraficoCotacao";

const pontos = ["2024-01-02", "2024-06-03", "2025-01-02", "2025-05-02", "2025-06-01"].map((data) => ({
  data, fechamento: 10, volume: null }));

describe("períodos do gráfico de cotação", () => {
  it("recorta a partir do último pregão", () => {
    expect(recortar(pontos, "1m").map((p) => p.data)).toEqual(["2025-05-02", "2025-06-01"]);
    expect(recortar(pontos, "1a").map((p) => p.data)).toEqual(["2024-06-03", "2025-01-02", "2025-05-02", "2025-06-01"]);
    expect(recortar(pontos, "tudo")).toHaveLength(5);
    expect(recortar(pontos, "ytd", new Date("2025-07-01T12:00:00Z")).map((p) => p.data)).toEqual(
      ["2025-01-02", "2025-05-02", "2025-06-01"]);
  });
});
