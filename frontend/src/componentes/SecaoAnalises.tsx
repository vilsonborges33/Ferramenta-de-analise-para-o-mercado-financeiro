"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useMoeda } from "@/lib/moeda";
import { formatarData } from "@/lib/formato";

type Medida = {
  valor: number | null;
  motivo_indisponivel: string | null;
  detalhes: Record<string, unknown>;
  metrica: string;
  [extra: string]: unknown;
};
type Fator = { percentil: number | null; valor: number | null; criterio: string; universo: number;
  motivo_indisponivel: string | null };
type Analises = {
  graham: { valor_revisado: Medida; checklist: Medida };
  bazin: { preco_teto_media: Medida; endividamento_baixo: Medida; regularidade: Medida };
  lynch: { indice: Medida; categoria: Medida };
  siegel: { reversao_media: Medida };
  bogle: { decomposicao: Medida };
  portfolio: { beta: Medida; fatores: Record<string, Fator> };
  damodaran: { custo_capital_proprio: Medida };
  aviso: string;
};
type Criterio = { nome: string; atendido: boolean | null; detalhe: string };

const pct = (v: unknown, casas = 1) =>
  typeof v === "number" ? `${(v * 100).toLocaleString("pt-BR", { maximumFractionDigits: casas })}%` : "—";
const num = (v: unknown, casas = 2) =>
  typeof v === "number" ? v.toLocaleString("pt-BR", { maximumFractionDigits: casas }) : "—";

function Cartao({ titulo, metrica, children }: { titulo: string; metrica: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border p-3 text-sm" style={{ background: "var(--fundo)" }}>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="font-medium">{titulo}</span>
        <Link href={`/metodologia/${metrica}`} className="link text-xs">Como é calculado</Link>
      </div>
      {children}
    </div>
  );
}

function Valor({ m, texto }: { m: Medida; texto: string }) {
  if (m.valor === null) return <div className="suave text-xs">Indisponível: {m.motivo_indisponivel}</div>;
  return <div className="mono text-lg font-semibold">{texto}</div>;
}

function Aviso({ texto }: { texto: unknown }) {
  return typeof texto === "string" && texto
    ? <div className="mt-1 text-xs" style={{ color: "var(--alerta)" }}>⚠ {texto}</div> : null;
}

const marca = (a: boolean | null) => (a === null ? "—" : a ? "✓" : "✗");
const corMarca = (a: boolean | null) => (a === null ? "var(--texto-suave)" : a ? "var(--positivo)" : "var(--negativo)");

/** Análises dos livros calculadas sob demanda (Graham, Bazin, Lynch, Siegel, Bogle, Lo & Foerster, Damodaran). */
export function SecaoAnalises({ ticker }: { ticker: string }) {
  const [dados, setDados] = useState<Analises | null | undefined>(undefined);
  const { fv } = useMoeda();
  useEffect(() => {
    fetch(`/api/ativos/${ticker}/analises`).then((r) => (r.ok ? r.json() : null)).then(setDados)
      .catch(() => setDados(null));
  }, [ticker]);
  if (dados === undefined) return <p className="suave text-sm">Calculando…</p>;
  if (dados === null) return <p className="suave text-sm">Análises indisponíveis para este ativo.</p>;

  const { graham, bazin, lynch, siegel, bogle, portfolio, damodaran } = dados;
  const criterios = (graham.checklist.detalhes.criterios ?? []) as Criterio[];
  const z = siegel.reversao_media.valor;
  const ke = damodaran.custo_capital_proprio;
  const bg = bogle.decomposicao.detalhes as { retorno_investimento?: number; retorno_especulativo?: number };
  return (
    <div className="space-y-3">
      <p className="text-xs" style={{ color: "var(--alerta)" }}>{dados.aviso}</p>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <Cartao titulo="Graham — fórmula revisada" metrica="graham.valor_revisado">
          <Valor m={graham.valor_revisado} texto={fv(graham.valor_revisado.valor, "R$/ação")} />
          <div className="suave text-xs">
            Margem {pct(graham.valor_revisado.margem)} · g = {pct(graham.valor_revisado.crescimento)} (CAGR do lucro
            5 anos) · Y = {pct(graham.valor_revisado.taxa_y, 2)}
            {graham.valor_revisado.descricao_taxa_y ? ` (${graham.valor_revisado.descricao_taxa_y})` : ""}
          </div>
          <Aviso texto={graham.valor_revisado.aviso} />
        </Cartao>

        <Cartao titulo="Graham — investidor defensivo" metrica="graham.checklist_defensivo">
          <Valor m={graham.checklist} texto={`${num(graham.checklist.valor, 0)} de 7 critérios`} />
          <ul className="mt-1 space-y-0.5 text-xs">
            {criterios.map((c) => (
              <li key={c.nome} title={c.detalhe}>
                <span className="mono" style={{ color: corMarca(c.atendido) }}>{marca(c.atendido)}</span> {c.nome}
                <span className="suave"> — {c.detalhe}</span>
              </li>
            ))}
          </ul>
        </Cartao>

        <Cartao titulo="Bazin — média de anos e critérios" metrica="bazin.criterios">
          <Valor m={bazin.preco_teto_media} texto={fv(bazin.preco_teto_media.valor, "R$/ação")} />
          <div className="suave text-xs">
            Preço teto pela média dos proventos de {num(bazin.preco_teto_media.anos, 0)} anos completos
            ({fv(bazin.preco_teto_media.dividendo_medio as number | null, "R$/ação")}/ano) ÷ 6% · margem{" "}
            {pct(bazin.preco_teto_media.margem)}
          </div>
          <ul className="mt-1 text-xs">
            <li><span className="mono" style={{ color: corMarca(bazin.endividamento_baixo.valor === null ? null : bazin.endividamento_baixo.valor === 1) }}>
              {marca(bazin.endividamento_baixo.valor === null ? null : bazin.endividamento_baixo.valor === 1)}</span>{" "}
              Endividamento baixo (DL/PL ≤ 1){bazin.endividamento_baixo.motivo_indisponivel ? ` — ${bazin.endividamento_baixo.motivo_indisponivel}` : ""}</li>
            <li><span className="mono" style={{ color: corMarca(bazin.regularidade.valor === null ? null : bazin.regularidade.valor === 1) }}>
              {marca(bazin.regularidade.valor === null ? null : bazin.regularidade.valor === 1)}</span>{" "}
              Proventos em todos os últimos {num(bazin.regularidade.anos, 0)} anos
              {bazin.regularidade.motivo_indisponivel ? ` — ${bazin.regularidade.motivo_indisponivel}` : ""}</li>
          </ul>
        </Cartao>

        <Cartao titulo="Lynch — índice e categoria" metrica="lynch.categoria">
          <Valor m={lynch.categoria} texto={String(lynch.categoria.detalhes.nome ?? "—")} />
          {lynch.categoria.valor !== null && <div className="suave text-xs">Regra: {String(lynch.categoria.detalhes.regra)}</div>}
          <div className="mt-1 text-xs">
            Índice de Lynch (crescimento + DY) ÷ P/L: <span className="mono font-medium">{num(lynch.indice.valor)}</span>
            <span className="suave"> {lynch.indice.valor === null ? `— ${lynch.indice.motivo_indisponivel}` :
              lynch.indice.valor >= 2 ? "(≥ 2: atraente pela regra do autor)" : lynch.indice.valor <= 1 ? "(≤ 1: pouco atraente)" : ""}</span>
          </div>
          <Aviso texto={lynch.indice.aviso} />
        </Cartao>

        <Cartao titulo="Siegel — reversão à média do P/L" metrica="siegel.reversao_media">
          <Valor m={siegel.reversao_media} texto={`${num(z)} desvios-padrão`} />
          <div className="suave text-xs">
            P/L atual {num(siegel.reversao_media.p_l)} × média de {num(siegel.reversao_media.anos, 0)} fins de ano{" "}
            {num(siegel.reversao_media.media_historica)}.{" "}
            {z !== null && (z > 1 ? "Bem acima da média histórica." : z < -1 ? "Bem abaixo da média histórica." : "Perto da média.")}
          </div>
        </Cartao>

        <Cartao titulo="Bogle — retorno esperado" metrica="bogle.decomposicao">
          <Valor m={bogle.decomposicao} texto={`${pct(bogle.decomposicao.valor)} a.a.`} />
          <div className="suave text-xs">
            Investimento (DY + crescimento do lucro) {pct(bg.retorno_investimento)} + especulativo (P/L volta à média
            {" "}{num(bogle.decomposicao.p_l_final)} em {num(bogle.decomposicao.anos, 0)} anos) {pct(bg.retorno_especulativo)}
          </div>
          <Aviso texto={bogle.decomposicao.aviso} />
        </Cartao>

        <Cartao titulo="Beta e fatores (Lo & Foerster)" metrica="portfolio.fatores">
          <div className="text-xs">
            Beta contra {String(portfolio.beta.indice)}:{" "}
            <span className="mono font-medium">{portfolio.beta.valor === null ? "—" : num(portfolio.beta.valor)}</span>
            {portfolio.beta.valor === null && <span className="suave"> ({portfolio.beta.motivo_indisponivel})</span>}
          </div>
          <ul className="mt-1 space-y-0.5 text-xs">
            {Object.entries(portfolio.fatores).map(([nome, f]) => (
              <li key={nome}>
                <span className="capitalize">{nome}</span> ({f.criterio}):{" "}
                <span className="mono font-medium">{f.percentil === null ? "—" : `percentil ${num(f.percentil * 100, 0)}`}</span>
                <span className="suave"> de {f.universo}</span>
              </li>
            ))}
          </ul>
        </Cartao>

        <Cartao titulo="Damodaran — custo do capital próprio" metrica="damodaran.custo_capital_proprio">
          <Valor m={ke} texto={`${pct(ke.valor, 2)} a.a.`} />
          <div className="suave text-xs">
            rf {pct(ke.taxa_livre_risco, 2)}{ke.descricao_taxa ? ` (${String(ke.descricao_taxa)}` : ""}
            {typeof ke.spread_default === "number" ? ` − spread de default ${pct(ke.spread_default, 2)})` : ke.descricao_taxa ? ")" : ""}
            {" "}+ β {num(ke.beta)}{ke.beta_estimado ? "" : " (padrão: histórico curto)"} × ERP {pct(ke.premio_mercado, 2)}
            {typeof ke.premio_pais === "number" ? ` + risco país ${pct(ke.premio_pais, 2)}` : ""}.
            {ke.data_premios ? ` Prêmios: Damodaran, ${formatarData(String(ke.data_premios))}.` : ""}
          </div>
        </Cartao>
      </div>
    </div>
  );
}
