"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Aviso, brl, Cabecalho, pctf, useApi } from "@/componentes/Ferramenta";
import { Grafico } from "@/componentes/Grafico";

type Serie = { nome: string; tipo: string; classe?: string | null; fonte: string; nominal: (number | null)[]; real: (number | null)[];
  acumulado_nominal: number | null; acumulado_real: number | null; real_anualizado: number | null };
type Cape = { valor: number | null; motivo_indisponivel: string | null; anos?: number; valor_mercado?: number | null;
  lucro_real_medio?: number | null; lucros?: { ano: number; lucro_nominal: number; lucro_real: number }[];
  premio_risco?: { valor: number | null; motivo_indisponivel: string | null; earnings_yield_real: number | null;
    juro_real: number | null; descricao_juro: string | null } };
type Resposta = { meses: string[]; inicio?: string; ultimo_ipca?: string; series: Serie[]; capes: Record<string, Cape>;
  observacao?: string; motivo?: string };

const INICIOS: [string, string][] = [["2020-01-01", "Desde 2020"], ["2022-01-01", "Desde 2022"], ["2024-01-01", "Desde 2024"],
  ["2025-01-01", "Desde 2025"]];

export default function LongoPrazo() {
  const [tickers, setTickers] = useState<string[] | null>(null);
  const [texto, setTexto] = useState("");
  const [desde, setDesde] = useState("2020-01-01");
  const [real, setReal] = useState(true);
  const [anosCape, setAnosCape] = useState(10);
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("t");
    const lista = q ? q.split(",").map((t) => t.trim().toUpperCase()).filter(Boolean) : ["PETR4", "ITUB4", "HGLG11"];
    setTickers(lista.slice(0, 4));
    setTexto(lista.slice(0, 4).join(", "));
  }, []);
  const { dados, erro, carregando } = useApi<Resposta>(
    tickers ? `/longo-prazo?tickers=${tickers.join(",")}&desde=${desde}&anos_cape=${anosCape}` : null, 50);

  const opcao = useMemo(() => {
    if (!dados?.meses?.length) return null;
    return {
      tooltip: { trigger: "axis", valueFormatter: (v: unknown) => (v === null ? "—" : brl(Number(v))) },
      legend: { top: 0, textStyle: { color: "#8a97ab" } },
      grid: { left: 60, right: 16, top: 36, bottom: 30 },
      xAxis: { type: "category", data: dados.meses },
      yAxis: { type: "value", scale: true, axisLabel: { formatter: (v: number) => `R$ ${v}` } },
      series: dados.series.filter((s) => !(real && s.tipo === "inflacao")).map((s) => ({
        name: s.nome, type: "line", showSymbol: false, connectNulls: false,
        lineStyle: s.tipo === "ativo" ? { width: 2.2 } : { width: 1.5, type: "dashed" },
        data: real ? s.real : s.nominal,
      })),
    };
  }, [dados, real]);

  return (
    <div className="space-y-5">
      <Cabecalho trilha="Ferramentas" titulo="Retorno de longo prazo" icone="longoPrazo"
        subtitulo="Jeremy Siegel: o que importa é o retorno real, com dividendos reinvestidos, contra a renda fixa e a inflação." />

      <div className="cartao flex flex-wrap items-end gap-3 p-4">
        <form className="flex flex-1 flex-wrap items-end gap-2" onSubmit={(e) => {
          e.preventDefault();
          const lista = texto.split(/[,\s]+/).map((t) => t.trim().toUpperCase()).filter(Boolean).slice(0, 4);
          setTickers(lista);
          window.history.replaceState(null, "", `/longo-prazo?t=${lista.join(",")}`);
        }}>
          <label className="block min-w-60 flex-1">
            <span className="rotulo">Ativos da B3 (até 4)</span>
            <input value={texto} onChange={(e) => setTexto(e.target.value)} className="campo ticker mt-1 w-full uppercase" />
          </label>
          <button type="submit" className="botao">Atualizar</button>
        </form>
        <div className="flex flex-wrap gap-1.5 text-sm">
          {INICIOS.map(([v, r]) => <button key={v} type="button" className="pilula" aria-pressed={desde === v} onClick={() => setDesde(v)}>{r}</button>)}
        </div>
        <div className="flex gap-1.5 text-sm">
          <button type="button" className="pilula" aria-pressed={real} onClick={() => setReal(true)}>Real (− IPCA)</button>
          <button type="button" className="pilula" aria-pressed={!real} onClick={() => setReal(false)}>Nominal</button>
        </div>
      </div>

      {erro && <p className="cartao p-3 text-sm negativo">{erro}</p>}
      {dados?.motivo && <p className="cartao p-3 text-sm suave">{dados.motivo}</p>}

      <div className="cartao p-4">
        <div className="mb-1 flex items-baseline justify-between">
          <h2 className="font-semibold">R$ 100 investidos em {dados?.inicio ?? "…"}</h2>
          {carregando && <span className="text-xs suave">calculando…</span>}
        </div>
        {opcao && <Grafico opcao={opcao} altura="h-96" rotulo="Crescimento de R$ 100 por ativo, CDI, dólar e IPCA" />}
        <p className="text-xs suave">{dados?.observacao}</p>
      </div>

      {dados && dados.series.length > 0 && (
        <div className="cartao overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="px-4 py-2 text-left">Série</th><th className="px-4 py-2 text-right">Acumulado nominal</th>
                <th className="px-4 py-2 text-right">Acumulado real</th><th className="px-4 py-2 text-right">Real ao ano</th>
                <th className="hidden px-4 py-2 text-left md:table-cell">Fonte</th>
              </tr>
            </thead>
            <tbody>
              {[...dados.series].sort((a, b) => (b.acumulado_real ?? -9) - (a.acumulado_real ?? -9)).map((s) => (
                <tr key={s.nome} className="border-b last:border-0">
                  <td className="px-4 py-2 font-medium">
                    {s.tipo === "ativo" ? <Link href={`/${s.classe === "FII" ? "fiis" : "acoes"}/${s.nome}`} className="ticker link">{s.nome}</Link> : s.nome}
                  </td>
                  <td className="mono px-4 py-2 text-right">{pctf(s.acumulado_nominal, 1)}</td>
                  <td className={`mono px-4 py-2 text-right ${(s.acumulado_real ?? 0) >= 0 ? "positivo" : "negativo"}`}>{pctf(s.acumulado_real, 1)}</td>
                  <td className="mono px-4 py-2 text-right">{pctf(s.real_anualizado, 1)}</td>
                  <td className="hidden px-4 py-2 text-xs suave md:table-cell">{s.fonte}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-4 pb-3 text-xs suave">Real = (1 + nominal) ÷ (1 + IPCA) − 1 (Fisher). {dados.ultimo_ipca ? `Série real até ${dados.ultimo_ipca}, último IPCA publicado.` : "IPCA ainda não carregado."}</p>
        </div>
      )}

      {dados && Object.keys(dados.capes).length > 0 && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-lg font-semibold">CAPE — P/L de Shiller</h2>
            <label className="flex items-center gap-2 text-sm">
              <span className="suave">Anos na média</span>
              <select value={anosCape} onChange={(e) => setAnosCape(Number(e.target.value))} className="campo">
                {[10, 8, 6, 5].map((n) => <option key={n} value={n}>{n}{n === 10 ? " (Shiller/Siegel)" : ""}</option>)}
              </select>
            </label>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {Object.entries(dados.capes).map(([t, c]) => (
              <div key={t} className="cartao cartao-kpi p-4">
                <div className="rotulo">{t}</div>
                {c.valor !== null ? (
                  <>
                    <div className="mono mt-1.5 text-2xl font-bold">{c.valor.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}x</div>
                    <div className="text-xs suave">valor de mercado ÷ lucro real médio de {c.anos} anos</div>
                    {c.premio_risco && (
                      <div className="mt-2 border-t pt-2 text-xs">
                        <span className="rotulo">Prêmio de risco (Siegel)</span>{" "}
                        {c.premio_risco.valor !== null ? (
                          <><span className="mono font-semibold">{pctf(c.premio_risco.valor)}</span>
                            <span className="suave"> = 1/CAPE {pctf(c.premio_risco.earnings_yield_real)} − juro real {pctf(c.premio_risco.juro_real)}
                              {c.premio_risco.descricao_juro ? ` (${c.premio_risco.descricao_juro})` : ""}</span></>
                        ) : <span className="suave">{c.premio_risco.motivo_indisponivel}</span>}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="mt-1.5 text-sm suave">{c.motivo_indisponivel}</div>
                )}
              </div>
            ))}
          </div>
          <p className="text-xs suave">Siegel/Shiller usam 10 anos para suavizar o ciclo. As demonstrações anuais da CVM vêm desde 2011;
            empresas com menos anos de capital aberto ficam indisponíveis — escolha uma média menor sabendo que ela suaviza menos.
            O prêmio de risco compara o rendimento real implícito das ações (1/CAPE) com o juro real do Tesouro IPCA+ mais longo.</p>
        </div>
      )}
      <Aviso>Retornos passados não garantem retornos futuros. Cálculos sobre dados públicos; não constituem recomendação de investimento.</Aviso>
    </div>
  );
}
