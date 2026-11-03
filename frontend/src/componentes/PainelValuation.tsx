"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { formatarValor } from "@/lib/formato";
import type { ItemScreening } from "@/lib/screening";

type Resposta = ItemScreening & { aviso: string; total_formula_magica: number };

type Ajuste = { rotulo: string; valor: number; passo: number; min: number; max: number; formato: (v: number) => string };

function Controle({ ajuste, aoMudar }: { ajuste: Ajuste; aoMudar: (v: number) => void }) {
  const mudar = (delta: number) =>
    aoMudar(Math.min(ajuste.max, Math.max(ajuste.min, Number((ajuste.valor + delta).toFixed(4)))));
  return (
    <div className="flex items-center justify-between gap-2 text-xs">
      <span className="suave">{ajuste.rotulo}</span>
      <span className="flex items-center gap-1">
        <button type="button" className="pilula px-2 py-0" aria-label={`Diminuir ${ajuste.rotulo}`} onClick={() => mudar(-ajuste.passo)}>–</button>
        <span className="w-12 text-center font-medium">{ajuste.formato(ajuste.valor)}</span>
        <button type="button" className="pilula px-2 py-0" aria-label={`Aumentar ${ajuste.rotulo}`} onClick={() => mudar(ajuste.passo)}>+</button>
      </span>
    </div>
  );
}

function Cartao({ metodo, titulo, livro, metodologia, principal, rotuloPrincipal, margem, extras, ajuste, aoAjustar }: {
  metodo: string; titulo: string; livro: string; metodologia: string; principal: string; rotuloPrincipal: string;
  margem?: number | null; extras: [string, string][]; ajuste?: Ajuste; aoAjustar?: (v: number) => void;
}) {
  return (
    <div className={`metodo-${metodo} cartao flex flex-col gap-3 overflow-hidden`}>
      <div className="fundo-metodo px-4 py-2">
        <div className="texto-metodo font-semibold">{titulo}</div>
        <div className="suave text-xs">{livro}</div>
      </div>
      <div className="flex flex-1 flex-col gap-2 px-4 pb-4">
        <div>
          <div className="suave text-xs">{rotuloPrincipal}</div>
          <div className="text-xl font-semibold">{principal}</div>
        </div>
        {margem !== undefined && (
          <div className="text-sm">
            <span className="suave">Margem de segurança: </span>
            <span style={{ color: margem === null ? undefined : margem >= 0 ? "var(--destaque)" : "var(--negativo)" }}>
              {formatarValor(margem ?? null, "%")}
            </span>
          </div>
        )}
        {extras.map(([r, v]) => (
          <div key={r} className="flex justify-between text-xs"><span className="suave">{r}</span><span>{v}</span></div>
        ))}
        <div className="mt-auto space-y-2">
          {ajuste && aoAjustar && <Controle ajuste={ajuste} aoMudar={aoAjustar} />}
          <Link href={`/metodologia/${metodologia}`} className="link text-xs">Como é calculado</Link>
        </div>
      </div>
    </div>
  );
}

/** Preço justo pelos quatro livros, com as premissas ajustáveis (recalculadas no backend). */
export function PainelValuation({ ticker }: { ticker: string }) {
  const [yieldBazin, setYieldBazin] = useState(6);
  const [fatorGraham, setFatorGraham] = useState(22.5);
  const [fatorLynch, setFatorLynch] = useState(1);
  const [dados, setDados] = useState<Resposta | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    const controle = new AbortController();
    const q = new URLSearchParams({ yield_bazin: String(yieldBazin / 100), fator_graham: String(fatorGraham),
      fator_lynch: String(fatorLynch) });
    const espera = setTimeout(() => {
      fetch(`/api/acoes/${ticker}/valuation?${q}`, { signal: controle.signal })
        .then(async (r) => {
          if (r.status === 404) throw new Error("Sem cotação carregada: o valuation aparece quando houver preço.");
          if (!r.ok) throw new Error("Não foi possível calcular o valuation.");
          setDados(await r.json());
          setErro(null);
        })
        .catch((e: Error) => e.name !== "AbortError" && setErro(e.message));
    }, 250);
    return () => {
      clearTimeout(espera);
      controle.abort();
    };
  }, [ticker, yieldBazin, fatorGraham, fatorLynch]);

  if (erro) return <p className="suave text-sm">{erro}</p>;
  if (!dados) return <p className="suave text-sm">Calculando…</p>;
  const r$ = (v: number | null) => formatarValor(v, "R$/ação");
  const pct = (v: number | null) => formatarValor(v, "%");

  return (
    <div className="space-y-3">
      <p className="text-xs" style={{ color: "var(--alerta)" }}>{dados.aviso}</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Cartao metodo="graham" titulo="Graham" livro="O Investidor Inteligente" metodologia="graham.valor_intrinseco"
          rotuloPrincipal="Valor intrínseco" principal={r$(dados.graham_valor)} margem={dados.graham_margem}
          extras={[["Cotação", r$(dados.preco)], ["P/L · P/VP", `${formatarValor(dados.p_l, "x")} · ${formatarValor(dados.p_vp, "x")}`]]}
          ajuste={{ rotulo: "Fator", valor: fatorGraham, passo: 0.5, min: 1, max: 100, formato: (v) => v.toLocaleString("pt-BR") }}
          aoAjustar={setFatorGraham} />
        <Cartao metodo="bazin" titulo="Bazin" livro="Faça Fortuna com Ações" metodologia="bazin.preco_teto"
          rotuloPrincipal="Preço teto" principal={r$(dados.bazin_teto)} margem={dados.bazin_margem}
          extras={[["DY 12 meses", pct(dados.dy)]]}
          ajuste={{ rotulo: "Yield mínimo", valor: yieldBazin, passo: 0.5, min: 1, max: 30, formato: (v) => `${v.toLocaleString("pt-BR")}%` }}
          aoAjustar={setYieldBazin} />
        <Cartao metodo="lynch" titulo="Peter Lynch" livro="Batendo o Mercado" metodologia="lynch.preco_justo"
          rotuloPrincipal="Preço justo" principal={r$(dados.lynch_valor)} margem={dados.lynch_margem}
          extras={[["PEG", formatarValor(dados.lynch_peg, "x")], ...(dados.lynch_aviso ? [["Atenção", dados.lynch_aviso] as [string, string]] : [])]}
          ajuste={{ rotulo: "Multiplicador", valor: fatorLynch, passo: 0.1, min: 0.1, max: 5, formato: (v) => v.toLocaleString("pt-BR") }}
          aoAjustar={setFatorLynch} />
        <Cartao metodo="greenblatt" titulo="Fórmula Mágica" livro="Joel Greenblatt" metodologia="greenblatt.ranking"
          rotuloPrincipal="Posição no ranking"
          principal={dados.greenblatt_posicao ? `${dados.greenblatt_posicao}º de ${dados.total_formula_magica}` : "—"}
          extras={[["Earnings yield", pct(dados.earnings_yield)], ["Retorno s/ capital", pct(dados.retorno_capital)]]} />
      </div>
    </div>
  );
}
