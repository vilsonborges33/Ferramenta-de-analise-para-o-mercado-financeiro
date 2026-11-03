"use client";

import { useEffect, useRef } from "react";

/** Gráfico ECharts genérico: recebe a configuração pronta e cuida de tema, redimensionamento e limpeza. */
export function Grafico({ opcao, altura = "h-64", rotulo }: { opcao: Record<string, unknown>; altura?: string; rotulo: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let grafico: import("echarts").ECharts | undefined;
    let cancelado = false;
    const redimensionar = () => grafico?.resize();
    import("echarts").then((echarts) => {
      if (cancelado || !ref.current) return;
      const escuro = window.matchMedia("(prefers-color-scheme: dark)").matches;
      grafico = echarts.init(ref.current, escuro ? "dark" : undefined, { renderer: "canvas" });
      grafico.setOption({ backgroundColor: "transparent", ...opcao });
      window.addEventListener("resize", redimensionar);
    });
    return () => {
      cancelado = true;
      window.removeEventListener("resize", redimensionar);
      grafico?.dispose();
    };
  }, [opcao]);

  return <div ref={ref} className={`${altura} w-full`} role="img" aria-label={rotulo} />;
}

export const reais = (v: unknown) =>
  `R$ ${Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/** Eixo em R$ abreviado (mil, mi, bi). */
export const reaisCurto = (v: number) => {
  const a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} bi`;
  if (a >= 1e6) return `${(v / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`;
  if (a >= 1e3) return `${(v / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil`;
  return v.toLocaleString("pt-BR");
};

export const porcento = (v: unknown) =>
  v === null || v === undefined ? "—" : `${(Number(v) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`;
