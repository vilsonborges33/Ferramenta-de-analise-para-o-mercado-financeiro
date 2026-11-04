"use client";

import { useMoeda } from "@/lib/moeda";
import { useEffect, useMemo, useState } from "react";
import { Grafico, porcento, reais } from "@/componentes/Grafico";
import { formatarData, formatarValor, nomeFonte } from "@/lib/formato";

type Pagamento = { tipo: string; valor_bruto: number; valor_liquido: number; data_com: string; data_ex: string | null;
  data_pagamento: string | null; fonte: string };
type Ano = { ano: number; total_liquido: number; cotacao: number | null; dividend_yield: number | null; parcial: boolean };
type Resposta = { pagamentos: Pagamento[]; anos: Ano[]; dy_medio: number | null; dy_minimo: number | null;
  dy_maximo: number | null; criterio: string; fontes: string[] };

const TIPOS: Record<string, string> = { DIVIDENDO: "Dividendo", JCP: "JCP", RENDIMENTO: "Rendimento" };

export function SecaoDividendos({ ticker }: { ticker: string }) {
  const { fv, fm, simbolo } = useMoeda();
  const [dados, setDados] = useState<Resposta | null>(null);
  const [anos, setAnos] = useState(5);
  const [verPagamentos, setVerPagamentos] = useState(false);

  useEffect(() => {
    fetch(`/api/ativos/${ticker}/dividendos?anos=10`).then((r) => (r.ok ? r.json() : null)).then(setDados)
      .catch(() => setDados(null));
  }, [ticker]);

  const serie = useMemo(() => (dados?.anos ?? []).slice(-anos), [dados, anos]);
  const opcao = useMemo(() => ({
    grid: { left: 52, right: 52, top: 28, bottom: 28 },
    legend: { top: 0 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: serie.map((a) => (a.parcial ? `${a.ano}*` : String(a.ano))) },
    yAxis: [
      { type: "value", axisLabel: { formatter: (v: number) => `${simbolo} ${v.toLocaleString("pt-BR")}` } },
      { type: "value", axisLabel: { formatter: porcento }, splitLine: { show: false } },
    ],
    series: [
      { name: "Proventos líquidos por ação", type: "bar", data: serie.map((a) => a.total_liquido),
        itemStyle: { color: "#a86400" }, tooltip: { valueFormatter: (v: unknown) => fv(Number(v), "R$/ação") } },
      { name: "Dividend yield", type: "line", yAxisIndex: 1, data: serie.map((a) => a.dividend_yield),
        tooltip: { valueFormatter: porcento } },
    ],
  }), [serie]);

  if (!dados) return <p className="suave text-sm">Carregando proventos…</p>;
  if (dados.pagamentos.length === 0)
    return <p className="suave text-sm">Nenhum provento registrado nos últimos 10 anos ({dados.fontes.map(nomeFonte).join(", ")}).</p>;

  const ultimos12 = dados.anos.length ? dados.anos[dados.anos.length - 1] : null;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {[3, 5, 10].map((n) => (
          <button key={n} type="button" className="pilula" aria-pressed={anos === n} onClick={() => setAnos(n)}>{n} anos</button>
        ))}
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div className="cartao p-3"><dt className="suave text-xs">DY médio (anos completos)</dt><dd className="font-medium">{fv(dados.dy_medio, "%")}</dd></div>
        <div className="cartao p-3"><dt className="suave text-xs">DY mínimo / máximo</dt><dd className="font-medium">{fv(dados.dy_minimo, "%")} / {fv(dados.dy_maximo, "%")}</dd></div>
        <div className="cartao p-3"><dt className="suave text-xs">Pago em {ultimos12?.ano} (parcial)</dt><dd className="font-medium">{fv(ultimos12?.total_liquido ?? null, "R$/ação")}</dd></div>
        <div className="cartao p-3"><dt className="suave text-xs">Total em 10 anos</dt><dd className="font-medium">{fv(dados.anos.reduce((s, a) => s + a.total_liquido, 0), "R$/ação")}</dd></div>
      </dl>
      <Grafico opcao={opcao} rotulo={`Proventos de ${ticker} por ano`} />
      <p className="suave text-xs">{dados.criterio} Fonte: {dados.fontes.map(nomeFonte).join(", ")}.</p>
      <button type="button" className="pilula text-sm" aria-expanded={verPagamentos} onClick={() => setVerPagamentos(!verPagamentos)}>
        {verPagamentos ? "Ocultar pagamentos" : "Exibir pagamentos"}
      </button>
      {verPagamentos && (
        <div className="cartao max-h-96 overflow-auto">
          <table className="w-full text-sm">
            <thead className="suave sticky top-0" style={{ background: "var(--superficie)" }}>
              <tr className="text-right">
                <th className="px-3 py-2 text-left">Tipo</th><th className="px-3 py-2">Data-com</th>
                <th className="px-3 py-2">Pagamento</th><th className="px-3 py-2">Bruto</th><th className="px-3 py-2">Líquido</th>
              </tr>
            </thead>
            <tbody>
              {dados.pagamentos.map((p, i) => (
                <tr key={i} className="border-t text-right">
                  <td className="px-3 py-1 text-left">{TIPOS[p.tipo] ?? p.tipo}</td>
                  <td className="px-3 py-1">{formatarData(p.data_com)}</td>
                  <td className="px-3 py-1" title={p.data_pagamento ? "" : "a fonte não informa a data de pagamento; usada a data-ex"}>
                    {p.data_pagamento ? formatarData(p.data_pagamento) : `${formatarData(p.data_ex)} (ex)`}
                  </td>
                  <td className="px-3 py-1">{fv(p.valor_bruto, "R$/ação")}</td>
                  <td className="px-3 py-1 font-medium">{fv(p.valor_liquido, "R$/ação")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
