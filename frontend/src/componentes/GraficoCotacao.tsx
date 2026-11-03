"use client";

import { useEffect, useMemo, useState } from "react";
import { Grafico, reais, reaisCurto } from "@/componentes/Grafico";
import { formatarData, formatarValor } from "@/lib/formato";

type Ponto = { data: string; fechamento: number; volume: number | null };

const PERIODOS = [
  { id: "1m", nome: "1 mês", dias: 31 },
  { id: "6m", nome: "6 meses", dias: 183 },
  { id: "ytd", nome: "No ano", dias: 0 },
  { id: "1a", nome: "12 meses", dias: 366 },
  { id: "5a", nome: "5 anos", dias: 5 * 366 },
  { id: "tudo", nome: "Tudo", dias: Infinity },
] as const;

/** Recorta os pontos do período escolhido (datas ISO comparadas como texto). */
export function recortar(pontos: Ponto[], periodo: (typeof PERIODOS)[number]["id"], hoje = new Date()): Ponto[] {
  if (pontos.length === 0) return pontos;
  const p = PERIODOS.find((x) => x.id === periodo)!;
  if (p.dias === Infinity) return pontos;
  const ultimo = new Date(`${pontos[pontos.length - 1].data}T12:00:00`);
  const base = periodo === "ytd" ? new Date(Date.UTC(hoje.getFullYear(), 0, 1)) : new Date(ultimo.getTime() - p.dias * 864e5);
  const corte = base.toISOString().slice(0, 10);
  return pontos.filter((x) => x.data >= corte);
}

/** Cotação de fechamento com volume, seletor de período e resumo (início, variação, mínima e máxima). */
export function GraficoCotacao({ ticker }: { ticker: string }) {
  const [pontos, setPontos] = useState<Ponto[] | null>(null);
  const [periodo, setPeriodo] = useState<(typeof PERIODOS)[number]["id"]>("1a");

  useEffect(() => {
    fetch(`/api/ativos/${ticker}/cotacoes`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setPontos)
      .catch(() => setPontos([]));
  }, [ticker]);

  const trecho = useMemo(() => recortar(pontos ?? [], periodo), [pontos, periodo]);
  const opcao = useMemo(
    () => ({
      grid: [
        { left: 52, right: 12, top: 12, height: "62%" },
        { left: 52, right: 12, top: "80%", height: "14%" },
      ],
      tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
      axisPointer: { link: [{ xAxisIndex: "all" }] },
      xAxis: [
        { type: "category", data: trecho.map((p) => formatarData(p.data)), boundaryGap: false, axisLabel: { show: false } },
        { type: "category", gridIndex: 1, data: trecho.map((p) => formatarData(p.data)), boundaryGap: false },
      ],
      yAxis: [
        { type: "value", scale: true, axisLabel: { formatter: (v: number) => v.toLocaleString("pt-BR") } },
        { type: "value", gridIndex: 1, axisLabel: { formatter: reaisCurto }, splitNumber: 2 },
      ],
      dataZoom: [{ type: "inside", xAxisIndex: [0, 1] }],
      series: [
        { name: "Fechamento", type: "line", data: trecho.map((p) => p.fechamento), showSymbol: false,
          lineStyle: { width: 1.5 }, tooltip: { valueFormatter: reais } },
        { name: "Volume", type: "bar", xAxisIndex: 1, yAxisIndex: 1, data: trecho.map((p) => p.volume),
          itemStyle: { opacity: 0.5 }, tooltip: { valueFormatter: (v: unknown) => `R$ ${reaisCurto(Number(v))}` } },
      ],
    }),
    [trecho],
  );

  if (pontos === null) return <p className="suave text-sm">Carregando cotações…</p>;
  if (pontos.length < 2) return <p className="suave text-sm">Histórico de cotações indisponível.</p>;

  const inicio = trecho[0]?.fechamento ?? null;
  const fim = trecho[trecho.length - 1]?.fechamento ?? null;
  const variacao = inicio && fim ? fim / inicio - 1 : null;
  const precos = trecho.map((p) => p.fechamento);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 text-sm" role="tablist" aria-label="Período">
        {PERIODOS.map((p) => (
          <button key={p.id} type="button" role="tab" aria-selected={periodo === p.id} className="pilula"
            onClick={() => setPeriodo(p.id)}>
            {p.nome}
          </button>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_12rem]">
        <Grafico opcao={opcao} altura="h-72" rotulo={`Cotações de ${ticker}`} />
        <dl className="grid grid-cols-2 gap-2 text-sm lg:grid-cols-1">
          <div><dt className="suave text-xs">Início do período</dt><dd>{formatarValor(inicio, "R$/ação")}</dd></div>
          <div><dt className="suave text-xs">Último fechamento</dt><dd>{formatarValor(fim, "R$/ação")}</dd></div>
          <div>
            <dt className="suave text-xs">Variação</dt>
            <dd style={{ color: (variacao ?? 0) >= 0 ? "var(--destaque)" : "var(--negativo)" }}>
              {formatarValor(variacao, "%")}
            </dd>
          </div>
          <div>
            <dt className="suave text-xs">Mínima / máxima</dt>
            <dd>{formatarValor(Math.min(...precos), "R$/ação")} / {formatarValor(Math.max(...precos), "R$/ação")}</dd>
          </div>
          <p className="suave col-span-2 text-xs lg:col-span-1">Fechamentos sem ajuste por proventos.</p>
        </dl>
      </div>
    </div>
  );
}
