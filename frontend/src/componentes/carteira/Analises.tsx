"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Grafico, porcento } from "@/componentes/Grafico";
import { formatarData, formatarMoeda, formatarValor } from "@/lib/formato";

type Rentab = { dias: string[]; carteira: number[]; indices: Record<string, (number | null)[]>;
  periodos: Record<string, Record<string, number | null>>; criterio?: string; motivo?: string };
const CORES: Record<string, string> = { Carteira: "#2463b8", CDI: "#6b7280", IPCA: "#a86400", IBOV: "#0f6b5c", IFIX: "#7a3fc4" };

export function Rentabilidade({ carteira, versao }: { carteira: number; versao: number }) {
  const [dados, setDados] = useState<Rentab | null>(null);
  useEffect(() => {
    fetch(`/api/carteiras/${carteira}/rentabilidade`).then((r) => (r.ok ? r.json() : null)).then(setDados);
  }, [carteira, versao]);
  const opcao = useMemo(() => {
    if (!dados) return {};
    const series = [["Carteira", dados.carteira] as const, ...Object.entries(dados.indices)];
    return {
      grid: { left: 52, right: 16, top: 32, bottom: 28 }, legend: { top: 0 },
      tooltip: { trigger: "axis", valueFormatter: porcento },
      xAxis: { type: "category", data: dados.dias.map((d) => formatarData(d)) },
      yAxis: { type: "value", axisLabel: { formatter: porcento } },
      dataZoom: [{ type: "inside" }],
      series: series.map(([nome, valores]) => ({ name: nome, type: "line", showSymbol: false, data: valores,
        lineStyle: { width: nome === "Carteira" ? 2.5 : 1.2 }, itemStyle: { color: CORES[nome] } })),
    };
  }, [dados]);
  if (!dados) return <p className="suave text-sm">Calculando…</p>;
  if (dados.motivo) return <p className="suave text-sm">Sem rentabilidade: {dados.motivo}.</p>;
  const colunas = ["carteira", ...Object.keys(dados.indices)];
  return (
    <div className="space-y-3">
      <Grafico opcao={opcao} altura="h-80" rotulo="Rentabilidade acumulada da carteira e dos índices" />
      <div className="overflow-x-auto">
        <table className="text-sm">
          <thead className="suave"><tr className="text-right"><th className="py-1 pr-4 text-left">Período</th>
            {colunas.map((c) => <th key={c} className="px-3">{c === "carteira" ? "Carteira" : c}</th>)}</tr></thead>
          <tbody>
            {Object.entries(dados.periodos).map(([nome, valores]) => (
              <tr key={nome} className="border-t text-right">
                <td className="py-1 pr-4 text-left">{nome}</td>
                {colunas.map((c) => <td key={c} className="px-3" style={{ fontWeight: c === "carteira" ? 600 : undefined }}>{formatarValor(valores[c] ?? null, "%")}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="suave text-xs">{dados.criterio}</p>
    </div>
  );
}

type Provs = { itens: { ticker: string; tipo: string; data_com: string; credito: string; valor_por_cota: number;
  quantidade: number; total: number }[]; por_mes: Record<string, number>; total: number; criterio: string };

export function Proventos({ carteira, versao }: { carteira: number; versao: number }) {
  const [dados, setDados] = useState<Provs | null>(null);
  useEffect(() => {
    fetch(`/api/carteiras/${carteira}/proventos`).then((r) => (r.ok ? r.json() : null)).then(setDados);
  }, [carteira, versao]);
  const opcao = useMemo(() => {
    const meses = Object.entries(dados?.por_mes ?? {});
    return {
      grid: { left: 64, right: 16, top: 12, bottom: 28 }, tooltip: { trigger: "axis", valueFormatter: (v: unknown) => formatarMoeda(Number(v)) },
      xAxis: { type: "category", data: meses.map(([m]) => m.split("-").reverse().join("/")) },
      yAxis: { type: "value", axisLabel: { formatter: (v: number) => `R$ ${v.toLocaleString("pt-BR")}` } },
      series: [{ type: "bar", data: meses.map(([, v]) => v), itemStyle: { color: "#a86400" } }],
    };
  }, [dados]);
  if (!dados) return <p className="suave text-sm">Carregando…</p>;
  if (dados.itens.length === 0) return <p className="suave text-sm">Nenhum provento recebido pelas posições registradas.</p>;
  return (
    <div className="space-y-3">
      <p className="text-sm">Total recebido: <span className="font-semibold">{formatarMoeda(dados.total)}</span></p>
      <Grafico opcao={opcao} altura="h-60" rotulo="Proventos recebidos por mês" />
      <div className="max-h-96 overflow-auto">
        <table className="w-full text-sm">
          <thead className="suave"><tr className="text-right"><th className="py-1 text-left">Crédito</th><th className="text-left">Ativo</th>
            <th className="text-left">Tipo</th><th>Data-com</th><th>Por cota (líq.)</th><th>Qtd.</th><th>Total</th></tr></thead>
          <tbody>
            {dados.itens.map((p, i) => (
              <tr key={i} className="border-t text-right">
                <td className="py-1 text-left">{formatarData(p.credito)}</td><td className="text-left">{p.ticker}</td>
                <td className="suave text-left">{p.tipo.toLowerCase().replace("_fii", "")}</td><td>{formatarData(p.data_com)}</td>
                <td>{formatarValor(p.valor_por_cota, "R$/ação")}</td><td>{p.quantidade.toLocaleString("pt-BR")}</td>
                <td className="font-medium">{formatarMoeda(p.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="suave text-xs">{dados.criterio}</p>
    </div>
  );
}

type Otim = { aviso: string; motivo?: string; tickers: string[]; periodo: { inicio: string; fim: string; pregoes: number };
  taxa_livre_risco: number; correlacao: number[][]; correlacao_media: number | null; contribuicao_risco: Record<string, number>;
  carteiras: { nome: string; pesos: Record<string, number>; retorno: number; volatilidade: number; sharpe: number | null }[];
  fronteira: { retorno: number; volatilidade: number }[]; numero_efetivo: number | null; metodologias: string[];
  all_weather?: { classes: { classe: string; nome: string; peso: number; alvo: number; atual: number; diferenca: number }[];
    observacao: string } };

export function Otimizador({ carteira, versao }: { carteira: number; versao: number }) {
  const [anos, setAnos] = useState(2);
  const [dados, setDados] = useState<Otim | null>(null);
  useEffect(() => {
    setDados(null);
    fetch(`/api/carteiras/${carteira}/otimizador?anos=${anos}`).then((r) => (r.ok ? r.json() : null)).then(setDados);
  }, [carteira, versao, anos]);
  const calor = useMemo(() => {
    if (!dados?.correlacao) return {};
    const t = dados.tickers;
    return {
      grid: { left: 64, right: 16, top: 8, bottom: 56 }, tooltip: { formatter: (p: { value: number[] }) => `${t[p.value[0]]} × ${t[p.value[1]]}: ${p.value[2].toLocaleString("pt-BR", { maximumFractionDigits: 2 })}` },
      xAxis: { type: "category", data: t, axisLabel: { rotate: 45 } }, yAxis: { type: "category", data: t },
      visualMap: { show: false, min: -1, max: 1,
        inRange: { color: ["#2463b8", "#f7f8fa", "#c2410c"] } },
      series: [{ type: "heatmap", data: dados.correlacao.flatMap((linha, i) => linha.map((v, j) => [i, j, Number(v.toFixed(2))])),
        label: { show: t.length <= 8 } }],
    };
  }, [dados]);
  const dispersao = useMemo(() => {
    if (!dados?.carteiras) return {};
    return {
      grid: { left: 56, right: 16, top: 28, bottom: 40 }, legend: { top: 0 },
      tooltip: { trigger: "item", formatter: (p: { seriesName: string; value: number[] }) => `${p.seriesName}: retorno ${porcento(p.value[1])}, volatilidade ${porcento(p.value[0])}` },
      xAxis: { type: "value", name: "Volatilidade", nameLocation: "middle", nameGap: 26, axisLabel: { formatter: porcento } },
      yAxis: { type: "value", axisLabel: { formatter: porcento } },
      series: [{ name: "Fronteira eficiente", type: "line", smooth: true, showSymbol: false, data: dados.fronteira.map((p) => [p.volatilidade, p.retorno]) },
        ...dados.carteiras.map((c) => ({ name: c.nome, type: "scatter", symbolSize: 12, data: [[c.volatilidade, c.retorno]] }))],
    };
  }, [dados]);
  if (!dados) return <p className="suave text-sm">Otimizando…</p>;
  if (dados.motivo) return <p className="suave text-sm">{dados.motivo}.</p>;
  return (
    <div className="space-y-4">
      <p className="cartao p-3 text-sm" style={{ color: "var(--alerta)" }}>{dados.aviso}</p>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="suave">Histórico usado:</span>
        {[1, 2, 3, 5].map((n) => <button key={n} type="button" className="pilula" aria-pressed={anos === n} onClick={() => setAnos(n)}>{n} {n === 1 ? "ano" : "anos"}</button>)}
        <span className="suave text-xs">{formatarData(dados.periodo.inicio)} a {formatarData(dados.periodo.fim)} · {dados.periodo.pregoes} pregões · taxa livre de risco (CDI 12m) {formatarValor(dados.taxa_livre_risco, "%")}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="suave"><tr className="text-right"><th className="py-1 text-left">Carteira</th>
            {dados.tickers.map((t) => <th key={t} className="px-2">{t}</th>)}<th className="px-2">Retorno a.a.</th><th className="px-2">Volatilidade</th><th className="px-2">Sharpe</th></tr></thead>
          <tbody>
            {dados.carteiras.map((c) => (
              <tr key={c.nome} className="border-t text-right" style={{ fontWeight: c.nome === "Atual" ? 600 : undefined }}>
                <td className="whitespace-nowrap py-1 text-left">{c.nome}</td>
                {dados.tickers.map((t) => <td key={t} className="px-2">{formatarValor(c.pesos[t], "%")}</td>)}
                <td className="px-2">{formatarValor(c.retorno, "%")}</td><td className="px-2">{formatarValor(c.volatilidade, "%")}</td>
                <td className="px-2">{formatarValor(c.sharpe, "x")}</td>
              </tr>
            ))}
            <tr className="border-t text-right suave"><td className="py-1 text-left">Contribuição para o risco (atual)</td>
              {dados.tickers.map((t) => <td key={t} className="px-2">{formatarValor(dados.contribuicao_risco[t] ?? null, "%")}</td>)}<td colSpan={3} /></tr>
          </tbody>
        </table>
      </div>
      <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
        <div><h3 className="text-sm font-medium">Fronteira eficiente (Markowitz)</h3><Grafico opcao={dispersao} altura="h-72" rotulo="Fronteira eficiente" /></div>
        <div><h3 className="text-sm font-medium">Correlação dos retornos diários (Dalio)</h3><Grafico opcao={calor} altura="h-72" rotulo="Matriz de correlação" />
          <p className="suave text-xs">Correlação média: {formatarValor(dados.correlacao_media, "x")} · número efetivo de ativos: {formatarValor(dados.numero_efetivo, "x")}</p></div>
      </div>
      {dados.all_weather && (
        <div className="overflow-x-auto">
          <h3 className="text-sm font-medium">All Weather (Dalio) — referência para o patrimônio atual</h3>
          <table className="mt-1 w-full text-sm">
            <thead><tr className="suave text-xs"><th className="text-left">Classe</th><th className="text-right">Peso</th>
              <th className="text-right">Alvo</th><th className="text-right">Na carteira</th><th className="text-right">Diferença</th></tr></thead>
            <tbody>
              {dados.all_weather.classes.map((c) => (
                <tr key={c.classe} className="border-t">
                  <td className="py-1">{c.nome}</td><td className="mono text-right">{formatarValor(c.peso, "%")}</td>
                  <td className="mono text-right">{formatarValor(c.alvo, "R$")}</td>
                  <td className="mono text-right">{formatarValor(c.atual, "R$")}</td>
                  <td className="mono text-right">{formatarValor(c.diferenca, "R$")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="suave text-xs">{dados.all_weather.observacao}</p>
        </div>
      )}
      <p className="suave flex flex-wrap gap-x-3 text-xs">Como é calculado:
        {dados.metodologias.map((m) => <Link key={m} href={`/metodologia/${m}`} className="link break-all">{m}</Link>)}</p>
    </div>
  );
}
