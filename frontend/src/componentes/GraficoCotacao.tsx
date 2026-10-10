"use client";

import { useEffect, useRef, useState } from "react";

type Ponto = { data: string; fechamento: number };

/** Gráfico de cotações de fechamento (ECharts), carregado do backend via /api. */
export function GraficoCotacao({ ticker }: { ticker: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [vazio, setVazio] = useState(false);

  useEffect(() => {
    let grafico: import("echarts").ECharts | undefined;
    let cancelado = false;
    const redimensionar = () => grafico?.resize();
    (async () => {
      const [echarts, resposta] = await Promise.all([import("echarts"), fetch(`/api/ativos/${ticker}/cotacoes`)]);
      const pontos: Ponto[] = resposta.ok ? await resposta.json() : [];
      if (cancelado || !ref.current) return;
      if (pontos.length < 2) {
        setVazio(true);
        return;
      }
      const escuro = window.matchMedia("(prefers-color-scheme: dark)").matches;
      grafico = echarts.init(ref.current, escuro ? "dark" : undefined, { renderer: "canvas" });
      grafico.setOption({
        backgroundColor: "transparent",
        grid: { left: 48, right: 12, top: 16, bottom: 32 },
        tooltip: {
          trigger: "axis",
          valueFormatter: (v: unknown) =>
            `R$ ${Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
        },
        xAxis: {
          type: "category",
          data: pontos.map((p) => p.data.split("-").reverse().join("/")),
          boundaryGap: false,
        },
        yAxis: { type: "value", scale: true, axisLabel: { formatter: (v: number) => v.toLocaleString("pt-BR") } },
        series: [{ type: "line", data: pontos.map((p) => p.fechamento), showSymbol: false, lineStyle: { width: 1.5 } }],
      });
      window.addEventListener("resize", redimensionar);
    })();
    return () => {
      cancelado = true;
      window.removeEventListener("resize", redimensionar);
      grafico?.dispose();
    };
  }, [ticker]);

  if (vazio) return <p className="suave text-sm">Histórico de cotações indisponível.</p>;
  return <div ref={ref} className="h-64 w-full" aria-label={`Cotações de ${ticker}`} />;
}
