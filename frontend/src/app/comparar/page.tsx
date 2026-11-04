"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArteVazio } from "@/componentes/Arte";
import { Aviso, Cabecalho } from "@/componentes/Ferramenta";
import { Grafico } from "@/componentes/Grafico";
import { Monograma } from "@/componentes/Monograma";
import { Numero } from "@/componentes/Numero";
import { MoedaProvider } from "@/lib/moeda";
import type { Detalhe, Numero as TNumero } from "@/lib/tipos";

const MAXIMO = 4;
// Direção do "melhor" para destacar a coluna vencedora em cada linha (só quando faz sentido comparar).
const MENOR_MELHOR = new Set(["basico.p_l", "basico.p_vp", "basico.ev_ebit", "basico.ev_ebitda", "basico.p_ebit", "basico.p_ebitda",
  "basico.dl_ebitda", "basico.dl_pl", "fii.p_vp", "fii.vacancia", "fii.alavancagem", "lynch.peg"]);
const MAIOR_MELHOR = new Set(["basico.dy", "basico.roe", "basico.roa", "basico.roic", "basico.margem_bruta", "basico.margem_ebit",
  "basico.margem_ebitda", "basico.margem_liquida", "basico.cagr_receita_5a", "basico.cagr_lucro_5a", "basico.liquidez_diaria",
  "basico.liquidez_corrente", "graham.margem_seguranca", "greenblatt.earnings_yield", "greenblatt.retorno_capital",
  "fii.dy_informado_12m", "fii.patrimonio_liquido", "fii.numero_cotistas"]);
const PERIODOS: [string, number][] = [["6 meses", 126], ["1 ano", 252], ["3 anos", 756], ["5 anos", 1260]];

async function detalhe(t: string): Promise<Detalhe | null> {
  for (const base of ["acoes", "fiis", "eua"]) {
    const r = await fetch(`/api/${base}/${t}`);
    if (r.ok) return r.json();
  }
  return null;
}

export default function Comparar() {
  const [tickers, setTickers] = useState<string[]>([]);
  const [novo, setNovo] = useState("");
  const [ativos, setAtivos] = useState<Record<string, Detalhe | null>>({});
  const [cotacoes, setCotacoes] = useState<Record<string, { data: string; fechamento: number }[]>>({});
  const [periodo, setPeriodo] = useState(252);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("t");
    setTickers(q ? q.split(",").map((t) => t.trim().toUpperCase()).filter(Boolean).slice(0, MAXIMO) : ["PETR4", "VALE3"]);
  }, []);

  useEffect(() => {
    if (!tickers.length) return;
    window.history.replaceState(null, "", `/comparar?t=${tickers.join(",")}`);
    for (const t of tickers) {
      if (!(t in ativos)) {
        detalhe(t).then((d) => setAtivos((a) => ({ ...a, [t]: d })));
        fetch(`/api/ativos/${t}/cotacoes`).then((r) => (r.ok ? r.json() : [])).then((c) => setCotacoes((a) => ({ ...a, [t]: c })));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickers]);

  const adicionar = () => {
    const t = novo.trim().toUpperCase();
    if (t && !tickers.includes(t) && tickers.length < MAXIMO) setTickers([...tickers, t]);
    setNovo("");
  };

  const carregados = tickers.map((t) => ativos[t]).filter((d): d is Detalhe => !!d);
  const linhas = useMemo(() => {
    const ordem: { grupo: string; id: string; nome: string }[] = [];
    const visto = new Set<string>();
    for (const d of carregados) {
      for (const [grupo, nums] of Object.entries(d.grupos)) {
        for (const n of nums) {
          if (!visto.has(n.metrica)) { visto.add(n.metrica); ordem.push({ grupo, id: n.metrica, nome: n.nome }); }
        }
      }
    }
    return ordem;
  }, [carregados]);

  const vencedor = (id: string): string | null => {
    if (!MENOR_MELHOR.has(id) && !MAIOR_MELHOR.has(id)) return null;
    const vals = carregados.map((d) => ({ t: d.ticker, v: Object.values(d.grupos).flat().find((n) => n.metrica === id)?.valor }))
      .filter((x): x is { t: string; v: number } => typeof x.v === "number");
    if (vals.length < 2) return null;
    const validos = MENOR_MELHOR.has(id) && id.includes("p_") ? vals.filter((x) => x.v > 0) : vals;
    if (!validos.length) return null;
    validos.sort((a, b) => (MENOR_MELHOR.has(id) ? a.v - b.v : b.v - a.v));
    return validos[0].t;
  };

  const opcao = useMemo(() => {
    const series = tickers.map((t) => {
      const c = (cotacoes[t] ?? []).slice(-periodo);
      if (c.length < 2) return null;
      return { name: t, type: "line", showSymbol: false, data: c.map((p) => [p.data, (100 * p.fechamento) / c[0].fechamento]) };
    }).filter(Boolean);
    if (!series.length) return null;
    return {
      tooltip: { trigger: "axis", valueFormatter: (v: unknown) => Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) },
      legend: { top: 0, textStyle: { color: "#8a97ab" } },
      grid: { left: 44, right: 16, top: 36, bottom: 30 },
      xAxis: { type: "time" }, yAxis: { type: "value", scale: true }, series,
    };
  }, [tickers, cotacoes, periodo]);

  let grupoAnterior = "";
  return (
    <div className="space-y-5">
      <Cabecalho trilha="Análise" titulo="Comparador de ativos" icone="comparador"
        subtitulo="Até 4 ações, FIIs ou ativos dos EUA lado a lado. O melhor de cada linha fica destacado." />

      <div className="cartao flex flex-wrap items-center gap-2 p-3">
        {tickers.map((t) => (
          <span key={t} className="pilula flex items-center gap-2 py-1">
            <Monograma ticker={t} classe={ativos[t]?.classe} tamanho={20} />
            <span className="ticker font-semibold">{t}</span>
            {ativos[t] === null && <span className="text-xs negativo">não encontrado</span>}
            <button type="button" aria-label={`Remover ${t}`} className="suave hover:text-[var(--negativo)]"
              onClick={() => setTickers(tickers.filter((x) => x !== t))}>✕</button>
          </span>
        ))}
        {tickers.length < MAXIMO && (
          <form onSubmit={(e) => { e.preventDefault(); adicionar(); }} className="flex gap-2">
            <input value={novo} onChange={(e) => setNovo(e.target.value)} placeholder="Adicionar ticker" className="campo ticker w-36 uppercase" />
            <button type="submit" className="botao py-1">Adicionar</button>
          </form>
        )}
      </div>

      {carregados.length === 0 ? (
        <div className="cartao grid place-items-center gap-2 p-10 text-center">
          <ArteVazio />
          <p className="suave">Adicione tickers para comparar.</p>
        </div>
      ) : (
        <>
          <div className="cartao p-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">Desempenho da cotação (base 100)</h2>
              <div className="flex gap-1.5 text-sm">
                {PERIODOS.map(([r, n]) => (
                  <button key={n} type="button" className="pilula" aria-pressed={periodo === n} onClick={() => setPeriodo(n)}>{r}</button>
                ))}
              </div>
            </div>
            {opcao && <Grafico opcao={opcao} altura="h-72" rotulo="Cotações normalizadas em base 100" />}
            <p className="text-xs suave">Só a cotação (sem dividendos). Para retorno com proventos reinvestidos e descontada a inflação, use
              {" "}<Link href={`/longo-prazo?t=${tickers.join(",")}`} className="link">Longo prazo</Link>.</p>
          </div>

          <div className="cartao overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b">
                  <th className="sticky left-0 px-4 py-3 text-left" style={{ background: "var(--superficie)" }}>Indicador</th>
                  {carregados.map((d) => (
                    <th key={d.ticker} className="px-4 py-3 text-right">
                      <Link href={`/${d.classe === "FII" ? "fiis" : d.mercado === "US" ? "eua" : "acoes"}/${d.ticker}`}
                        className="ticker inline-flex items-center gap-2 text-sm normal-case hover:underline" style={{ color: "var(--texto)" }}>
                        <Monograma ticker={d.ticker} classe={d.classe} tamanho={22} />{d.ticker}
                      </Link>
                      <div className="truncate text-[0.65rem] font-normal normal-case">{d.setor ?? d.segmento ?? ""}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b">
                  <td className="sticky left-0 px-4 py-2" style={{ background: "var(--superficie)" }}>Cotação</td>
                  {carregados.map((d) => (
                    <td key={d.ticker} className="mono px-4 py-2 text-right font-semibold">
                      {d.cotacao ? `${d.moeda === "USD" ? "US$" : "R$"} ${d.cotacao.valor.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "—"}
                    </td>
                  ))}
                </tr>
                {linhas.map((l) => {
                  const melhor = vencedor(l.id);
                  const cabecalho = l.grupo !== grupoAnterior;
                  grupoAnterior = l.grupo;
                  return [
                    cabecalho && (
                      <tr key={`g-${l.grupo}`}><td colSpan={carregados.length + 1} className="rotulo px-4 pb-1 pt-4">{l.grupo}</td></tr>
                    ),
                    <tr key={l.id} className="border-b last:border-0">
                      <td className="sticky left-0 px-4 py-2" style={{ background: "var(--superficie)" }}>{l.nome}</td>
                      {carregados.map((d) => {
                        const n: TNumero | undefined = Object.values(d.grupos).flat().find((x) => x.metrica === l.id);
                        const ganha = melhor === d.ticker;
                        return (
                          <td key={d.ticker} className="mono px-4 py-2 text-right"
                            style={ganha ? { background: "color-mix(in srgb, var(--positivo) 12%, transparent)", color: "var(--positivo)" } : undefined}>
                            {n ? <MoedaProvider moeda={d.moeda ?? "BRL"}><Numero compacto numero={n} /></MoedaProvider> : <span className="suave">—</span>}
                          </td>
                        );
                      })}
                    </tr>,
                  ];
                })}
              </tbody>
            </table>
          </div>
          <Aviso>Destaque = melhor valor da linha pelo critério usual (ex.: menor P/L, maior ROE); não é uma nota do ativo.
            Cálculos sobre dados públicos; não constituem recomendação de investimento.</Aviso>
        </>
      )}
    </div>
  );
}
