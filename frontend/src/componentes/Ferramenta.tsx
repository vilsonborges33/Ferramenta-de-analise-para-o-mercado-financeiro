"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icone } from "@/componentes/Arte";

/** Cabeçalho padrão das páginas: trilha, ícone, título e subtítulo. */
export function Cabecalho({ trilha, titulo, subtitulo, icone, children }:
  { trilha?: string; titulo: string; subtitulo?: string; icone?: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="flex items-center gap-3">
        {icone && (
          <span className="grid h-11 w-11 place-items-center rounded-xl"
            style={{ background: "color-mix(in srgb, var(--destaque) 12%, transparent)", color: "var(--destaque)" }}>
            <Icone nome={icone} tamanho={22} />
          </span>
        )}
        <div>
          {trilha && <div className="text-xs suave"><Link href="/" className="hover:underline">Início</Link> › {trilha}</div>}
          <h1 className="text-2xl font-bold">{titulo}</h1>
          {subtitulo && <p className="text-sm suave">{subtitulo}</p>}
        </div>
      </div>
      {children}
    </div>
  );
}

/** Campo numérico com prefixo/sufixo e seletor de unidade acoplado (padrão das calculadoras). */
export function CampoNumero({ rotulo, valor, aoMudar, prefixo, sufixo, dica, passo = "any", unidade }: {
  rotulo: string; valor: number; aoMudar: (v: number) => void; prefixo?: string; sufixo?: string; dica?: string;
  passo?: string; unidade?: { valor: string; opcoes: [string, string][]; aoMudar: (v: string) => void };
}) {
  const [texto, setTexto] = useState(String(valor).replace(".", ","));
  useEffect(() => {
    const atual = Number(texto.replace(/\./g, "").replace(",", "."));
    if (atual !== valor) setTexto(String(valor).replace(".", ","));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valor]);
  return (
    <label className="block">
      <span className="rotulo">{rotulo}</span>
      <span className="campo mt-1 flex items-center gap-2 py-1.5">
        {prefixo && <span className="suave text-sm">{prefixo}</span>}
        <input inputMode="decimal" step={passo} value={texto} className="mono w-full min-w-0 bg-transparent outline-none"
          onChange={(e) => {
            setTexto(e.target.value);
            const n = Number(e.target.value.replace(/\./g, "").replace(",", "."));
            if (Number.isFinite(n)) aoMudar(n);
          }} />
        {sufixo && <span className="suave text-sm">{sufixo}</span>}
        {unidade && (
          <select value={unidade.valor} onChange={(e) => unidade.aoMudar(e.target.value)}
            className="rounded bg-transparent text-sm suave outline-none" aria-label={`Unidade de ${rotulo}`}>
            {unidade.opcoes.map(([v, r]) => <option key={v} value={v}>{r}</option>)}
          </select>
        )}
      </span>
      {dica && <span className="mt-1 block text-xs suave">{dica}</span>}
    </label>
  );
}

export function Kpi({ rotulo, valor, detalhe, cor }: { rotulo: string; valor: string; detalhe?: string; cor?: string }) {
  return (
    <div className="cartao cartao-kpi p-4">
      <div className="rotulo">{rotulo}</div>
      <div className="mono mt-1.5 whitespace-nowrap text-[clamp(1.05rem,1.6vw,1.5rem)] font-bold" style={cor ? { color: cor } : undefined}>{valor}</div>
      {detalhe && <div className="mt-0.5 text-xs suave">{detalhe}</div>}
    </div>
  );
}

/** Busca na API (pelo proxy /api) com atraso curto, cancelando a anterior. */
export function useApi<T>(caminho: string | null, atraso = 250) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);
  useEffect(() => {
    if (!caminho) { setDados(null); return; }
    const c = new AbortController();
    setCarregando(true);
    const id = setTimeout(() => {
      fetch(`/api${caminho}`, { signal: c.signal, credentials: "same-origin" })
        .then(async (r) => {
          if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `erro ${r.status}`);
          return r.json();
        })
        .then((d) => { setDados(d); setErro(null); })
        .catch((e) => { if (e.name !== "AbortError") setErro(typeof e.message === "string" ? e.message : "erro"); })
        .finally(() => setCarregando(false));
    }, atraso);
    return () => { clearTimeout(id); c.abort(); };
  }, [caminho, atraso]);
  return { dados, erro, carregando };
}

export const brl = (v: number | null | undefined, casas = 2) =>
  v === null || v === undefined || !Number.isFinite(v) ? "—"
    : `R$ ${v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas })}`;

export const pctf = (v: number | null | undefined, casas = 2) =>
  v === null || v === undefined || !Number.isFinite(v) ? "—"
    : `${(v * 100).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas })}%`;

export function Aviso({ children }: { children: React.ReactNode }) {
  return <p className="text-xs" style={{ color: "var(--alerta)" }}>{children}</p>;
}
