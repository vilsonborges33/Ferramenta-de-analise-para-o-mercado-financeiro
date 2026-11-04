"use client";

import { useEffect, useRef, useState } from "react";

/** Paleta das séries, igual nos dois temas (validada contra os fundos claro e escuro). */
const PALETA = ["#2dd4bf", "#60a5fa", "#f5b544", "#c084fc", "#fb7c4c", "#34d399", "#f472b6", "#94a3b8"];

export const temaEscuro = () =>
  typeof document !== "undefined" && document.documentElement.dataset.tema !== "claro";

/** Gráfico ECharts genérico: recebe a configuração pronta e cuida de tema, redimensionamento e limpeza. */
export function Grafico({ opcao, altura = "h-64", rotulo }: { opcao: Record<string, unknown>; altura?: string; rotulo: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [versaoTema, setVersaoTema] = useState(0);

  useEffect(() => {
    const trocar = () => setVersaoTema((v) => v + 1);
    window.addEventListener("tema", trocar);
    return () => window.removeEventListener("tema", trocar);
  }, []);

  useEffect(() => {
    let grafico: import("echarts").ECharts | undefined;
    let cancelado = false;
    const redimensionar = () => grafico?.resize();
    import("echarts").then((echarts) => {
      if (cancelado || !ref.current) return;
      const escuro = temaEscuro();
      grafico = echarts.init(ref.current, escuro ? "dark" : undefined, { renderer: "canvas" });
      const eixo = escuro ? "#1d2940" : "#dfe4ec";
      grafico.setOption({
        backgroundColor: "transparent",
        color: PALETA,
        textStyle: { fontFamily: "Inter, system-ui, sans-serif" },
        tooltip: { backgroundColor: escuro ? "#0f1726" : "#ffffff", borderColor: eixo,
          textStyle: { color: escuro ? "#e6ebf2" : "#0f1726" } },
        ...opcao,
      });
      // Linhas de grade discretas, no padrão do tema.
      grafico.setOption({ yAxis: ([] as unknown[]).concat((opcao as { yAxis?: unknown }).yAxis ?? []).map(() => ({
        splitLine: { lineStyle: { color: eixo, type: "dashed" } } })) });
      window.addEventListener("resize", redimensionar);
    });
    return () => {
      cancelado = true;
      window.removeEventListener("resize", redimensionar);
      grafico?.dispose();
    };
  }, [opcao, versaoTema]);

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
