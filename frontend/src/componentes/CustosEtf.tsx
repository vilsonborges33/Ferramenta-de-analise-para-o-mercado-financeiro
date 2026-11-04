"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Grafico } from "@/componentes/Grafico";
import { formatarValor } from "@/lib/formato";
import { useMoeda } from "@/lib/moeda";

type Resposta = { impacto: number | null; impacto_comparacao: number | null; aviso: string;
  serie: { ano: number; sem_custo: number; com_custo: number; comparacao: number }[] };

/** Bogle: quanto a taxa de administração do ETF consome do patrimônio no longo prazo. */
export function CustosEtf({ ticker }: { ticker: string }) {
  const { fm, simbolo } = useMoeda();
  const [taxa, setTaxa] = useState("0,50"); // valor de exemplo: troque pela taxa do ETF
  const [retorno, setRetorno] = useState("7");
  const [inicial, setInicial] = useState("10000");
  const [aporte, setAporte] = useState("0");
  const [anos, setAnos] = useState("30");
  const [dados, setDados] = useState<Resposta | null>(null);
  const num = (t: string) => Number(t.replace(/\./g, "").replace(",", "."));

  useEffect(() => {
    const q = new URLSearchParams({ custo_anual: String(num(taxa) / 100), retorno_anual: String(num(retorno) / 100),
      inicial: String(num(inicial)), aporte_anual: String(num(aporte)), anos: String(Math.round(num(anos))) });
    const controle = new AbortController();
    const espera = setTimeout(() => {
      fetch(`/api/ferramentas/impacto-custos?${q}`, { signal: controle.signal }).then((r) => (r.ok ? r.json() : null))
        .then(setDados).catch(() => undefined);
    }, 300);
    return () => {
      clearTimeout(espera);
      controle.abort();
    };
  }, [taxa, retorno, inicial, aporte, anos]);

  const opcao = useMemo(() => ({
    grid: { left: 72, right: 16, top: 32, bottom: 28 }, legend: { top: 0 },
    tooltip: { trigger: "axis", valueFormatter: (v: unknown) => fm(Number(v)) },
    xAxis: { type: "category", data: (dados?.serie ?? []).map((p) => p.ano) },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => `${simbolo} ${v.toLocaleString("pt-BR")}` } },
    series: [
      { name: "Sem custo", type: "line", showSymbol: false, data: (dados?.serie ?? []).map((p) => p.sem_custo) },
      { name: `Com taxa de ${taxa}%`, type: "line", showSymbol: false, data: (dados?.serie ?? []).map((p) => p.com_custo) },
      { name: "Fundo de 0,03%", type: "line", showSymbol: false, lineStyle: { type: "dashed" },
        data: (dados?.serie ?? []).map((p) => p.comparacao) },
    ],
  }), [dados, taxa, fm, simbolo]);

  const campo = (rotulo: string, valor: string, set: (v: string) => void) => (
    <label className="flex items-center justify-between gap-2"><span className="suave">{rotulo}</span>
      <input className="campo w-28 text-right" inputMode="decimal" aria-label={rotulo} value={valor} onChange={(e) => set(e.target.value)} /></label>
  );
  return (
    <div className="space-y-3 text-sm">
      <p className="suave text-xs">
        Informe a taxa de administração (expense ratio) do {ticker}, que está no prospecto ou na página da gestora.
        O sistema não tem essa informação de uma fonte oficial gratuita, por isso ela não é preenchida sozinha.
      </p>
      <div className="grid gap-4 md:grid-cols-[18rem_1fr] [&>*]:min-w-0">
        <div className="space-y-2">
          {campo("Taxa anual (%)", taxa, setTaxa)}
          {campo("Retorno anual esperado (%)", retorno, setRetorno)}
          {campo(`Valor inicial (${simbolo})`, inicial, setInicial)}
          {campo(`Aporte anual (${simbolo})`, aporte, setAporte)}
          {campo("Anos", anos, setAnos)}
          <div className="metodo-bazin fundo-metodo rounded-lg p-3">
            <div className="suave text-xs">A taxa consome do patrimônio final</div>
            <div className="text-2xl font-semibold">{formatarValor(dados?.impacto ?? null, "%")}</div>
            <div className="suave text-xs">Um fundo de 0,03% consumiria {formatarValor(dados?.impacto_comparacao ?? null, "%")}</div>
          </div>
          <Link href="/metodologia/bogle.impacto_custos" className="link text-xs">Como é calculado</Link>
        </div>
        <Grafico opcao={opcao} rotulo="Patrimônio com e sem custos" />
      </div>
      {dados && <p className="text-xs" style={{ color: "var(--alerta)" }}>{dados.aviso}</p>}
    </div>
  );
}
