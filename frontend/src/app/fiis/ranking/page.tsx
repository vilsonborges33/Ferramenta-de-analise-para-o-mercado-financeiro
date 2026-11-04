"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { formatarData, formatarMoeda, formatarValor } from "@/lib/formato";
import { gravarLocal, lerLocal, lerNumero } from "@/lib/screening";

type Item = { posicao: number; ticker: string; nome: string | null; segmento: string | null; tipo: string | null;
  preco: number; data_preco: string; dy: number | null; p_vp: number | null; patrimonio: number | null;
  liquidez: number | null; vacancia: number | null; alavancagem: number | null; cotistas: number | null;
  gordon_teto: number | null; gordon_margem: number | null };
type Resposta = { aviso: string; atualizado_em: string | null; total_avaliados: number; sem_cotacao: number;
  segmentos: string[]; tipos: string[]; descricao_taxa: string | null; taxa_base: number | null; itens: Item[] };

const FAIXAS = [
  { id: "dy", titulo: "Dividend yield", sufixo: "%", escala: 0.01 },
  { id: "p_vp", titulo: "P/VP", sufixo: "x", escala: 1 },
  { id: "patrimonio", titulo: "Patrimônio líquido", sufixo: "R$ mi", escala: 1e6 },
  { id: "liquidez", titulo: "Liquidez diária", sufixo: "R$ mi", escala: 1e6 },
  { id: "vacancia", titulo: "Vacância", sufixo: "%", escala: 0.01 },
  { id: "alavancagem", titulo: "Alavancagem", sufixo: "%", escala: 0.01 },
] as const;
type Faixas = Record<(typeof FAIXAS)[number]["id"], { min: string; max: string }>;
type Estado = { faixas: Faixas; segmentos: string[]; tipos: string[]; favoritos: boolean; ordenarPor: string;
  base: string; premio: number; crescimento: number };

const padrao = (): Estado => ({
  faixas: Object.fromEntries(FAIXAS.map((f) => [f.id, { min: f.id === "liquidez" ? "0,5" : "", max: "" }])) as Faixas,
  segmentos: [], tipos: [], favoritos: false, ordenarPor: "gordon", base: "prefixado", premio: 2, crescimento: 0,
});

const COLUNAS: { id: keyof Item; titulo: string; unidade: string; cor?: boolean }[] = [
  { id: "preco", titulo: "Cotação", unidade: "R$/ação" }, { id: "dy", titulo: "DY 12m", unidade: "%" },
  { id: "p_vp", titulo: "P/VP", unidade: "x" },
  { id: "gordon_teto", titulo: "Teto Gordon", unidade: "R$/ação", cor: true },
  { id: "gordon_margem", titulo: "Margem Gordon", unidade: "%", cor: true },
  { id: "tipo", titulo: "Tipo", unidade: "texto" }, { id: "segmento", titulo: "Segmento", unidade: "texto" },
  { id: "liquidez", titulo: "Liquidez", unidade: "R$" }, { id: "vacancia", titulo: "Vacância", unidade: "%" },
  { id: "alavancagem", titulo: "Alavancagem", unidade: "%" }, { id: "patrimonio", titulo: "Patrimônio", unidade: "R$" },
];

function consulta(e: Estado): string {
  const q = new URLSearchParams({ ordenar_por: e.ordenarPor, base: e.base, premio: String(e.premio / 100),
    crescimento: String(e.crescimento / 100) });
  for (const f of FAIXAS)
    for (const lado of ["min", "max"] as const) {
      const n = lerNumero(e.faixas[f.id][lado]);
      if (n !== null) q.set(`${f.id}_${lado}`, String(Number((n * f.escala).toPrecision(12))));
    }
  e.segmentos.forEach((s) => q.append("segmentos", s));
  e.tipos.forEach((t) => q.append("tipos", t));
  if (e.favoritos) q.set("somente_favoritos", "true");
  return q.toString();
}

export default function RankingFiis() {
  const [estado, setEstado] = useState<Estado>(padrao);
  const [dados, setDados] = useState<Resposta | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ordem, setOrdem] = useState<{ coluna: keyof Item; crescente: boolean } | null>(null);
  const [pagina, setPagina] = useState(0);
  const [logado, setLogado] = useState(false);
  const q = useMemo(() => consulta(estado), [estado]);

  useEffect(() => {
    setEstado((atual) => ({ ...atual, ...lerLocal<Partial<Estado>>("fiis.filtros", {}) }));
    fetch("/api/favoritos").then((r) => setLogado(r.ok)).catch(() => undefined);
  }, []);

  useEffect(() => {
    gravarLocal("fiis.filtros", estado);
    const controle = new AbortController();
    const espera = setTimeout(() => {
      fetch(`/api/screening/fiis?${q}`, { signal: controle.signal })
        .then(async (r) => {
          if (!r.ok) throw new Error(r.status === 401 ? "Entre na sua conta para usar favoritos." : "Falha ao calcular.");
          setDados(await r.json());
          setErro(null);
          setPagina(0);
        })
        .catch((e: Error) => e.name !== "AbortError" && setErro(e.message));
    }, 350);
    return () => {
      clearTimeout(espera);
      controle.abort();
    };
  }, [q, estado]);

  const itens = useMemo(() => {
    const lista = [...(dados?.itens ?? [])];
    if (!ordem) return lista;
    return lista.sort((a, b) => {
      const va = a[ordem.coluna], vb = b[ordem.coluna];
      if (va === null) return vb === null ? 0 : 1;
      if (vb === null) return -1;
      const c = typeof va === "string" ? va.localeCompare(String(vb), "pt-BR") : Number(va) - Number(vb);
      return ordem.crescente ? c : -c;
    });
  }, [dados, ordem]);
  const porPagina = 25;
  const trecho = itens.slice(pagina * porPagina, (pagina + 1) * porPagina);
  const paginas = Math.max(1, Math.ceil(itens.length / porPagina));
  const alternar = (lista: string[], v: string) => (lista.includes(v) ? lista.filter((x) => x !== v) : [...lista, v]);

  return (
    <div className="space-y-5">
      <div>
        <div className="suave text-xs"><Link href="/fiis" className="hover:underline">FIIs</Link> › Ranking</div>
        <h1 className="text-2xl font-semibold">Ranking de fundos imobiliários</h1>
        <p className="suave text-sm">Filtre por indicadores e compare o preço teto pelo Gordon ajustado.</p>
      </div>
      <p className="cartao p-3 text-sm" style={{ color: "var(--alerta)" }} role="note">
        {dados?.aviso ?? "Resultados calculados a partir de dados públicos e dos parâmetros escolhidos. Não constituem recomendação de investimento."}
      </p>

      <section className="cartao space-y-4 p-4 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="suave">Tipo:</span>
          {(dados?.tipos ?? ["Tijolo", "Papel", "Fundo de fundos", "Híbrido"]).map((t) => (
            <button key={t} type="button" className="pilula" aria-pressed={estado.tipos.includes(t)}
              onClick={() => setEstado({ ...estado, tipos: alternar(estado.tipos, t) })}>{t}</button>
          ))}
          <button type="button" className="pilula" aria-pressed={estado.favoritos} disabled={!logado}
            title={logado ? "" : "Entre na sua conta para usar favoritos"} onClick={() => setEstado({ ...estado, favoritos: !estado.favoritos })}>★ Favoritos</button>
          <button type="button" className="pilula ml-auto" onClick={() => { setEstado(padrao()); setOrdem(null); }}>Limpar filtros</button>
        </div>
        <div className="grid gap-x-8 gap-y-4 md:grid-cols-2">
          <fieldset className="space-y-2">
            <legend className="mb-1 font-medium">Faixas</legend>
            {FAIXAS.map((f) => (
              <div key={f.id} className="grid grid-cols-[1fr_auto_auto] items-center gap-2">
                <span>{f.titulo} <span className="suave text-xs">({f.sufixo})</span></span>
                {(["min", "max"] as const).map((lado) => (
                  <input key={lado} aria-label={`${f.titulo} ${lado === "min" ? "mínimo" : "máximo"}`} inputMode="decimal"
                    placeholder={lado === "min" ? "mín." : "máx."} className="campo w-20 text-right" value={estado.faixas[f.id][lado]}
                    onChange={(e) => setEstado({ ...estado, faixas: { ...estado.faixas, [f.id]: { ...estado.faixas[f.id], [lado]: e.target.value } } })} />
                ))}
              </div>
            ))}
          </fieldset>
          <div className="space-y-3">
            <fieldset className="metodo-bazin fundo-metodo space-y-2 rounded-lg p-3">
              <legend className="texto-metodo font-medium">Gordon ajustado</legend>
              <label className="flex items-center justify-between gap-2">Taxa base
                <select className="campo" value={estado.base} onChange={(e) => setEstado({ ...estado, base: e.target.value })}>
                  <option value="prefixado">Tesouro Prefixado</option><option value="ipca">Tesouro IPCA+</option><option value="selic">Selic</option>
                </select>
              </label>
              <label className="flex items-center justify-between gap-2">Prêmio (%)
                <input type="number" step={0.5} className="campo w-20 text-right" value={estado.premio} onChange={(e) => setEstado({ ...estado, premio: Number(e.target.value) })} />
              </label>
              <label className="flex items-center justify-between gap-2">Crescimento (%)
                <input type="number" step={0.5} className="campo w-20 text-right" value={estado.crescimento} onChange={(e) => setEstado({ ...estado, crescimento: Number(e.target.value) })} />
              </label>
              <p className="suave text-xs">{dados?.descricao_taxa ?? "taxa base indisponível"} · líquida de 15% de IR</p>
            </fieldset>
            <details className="rounded-lg border px-3 py-2">
              <summary className="cursor-pointer">Segmentos {estado.segmentos.length ? `(${estado.segmentos.length})` : "(todos)"}</summary>
              <div className="mt-2 max-h-48 space-y-1 overflow-y-auto">
                {(dados?.segmentos ?? []).map((s) => (
                  <label key={s} className="flex items-center gap-2">
                    <input type="checkbox" checked={estado.segmentos.includes(s)} onChange={() => setEstado({ ...estado, segmentos: alternar(estado.segmentos, s) })} />{s}
                  </label>
                ))}
              </div>
            </details>
          </div>
        </div>
      </section>

      {erro && <p style={{ color: "var(--alerta)" }}>{erro}</p>}

      <section className="cartao">
        <div className="flex flex-wrap items-center gap-3 border-b p-3 text-sm">
          <label className="flex items-center gap-2">Ranquear por
            <select className="campo" value={estado.ordenarPor} onChange={(e) => { setEstado({ ...estado, ordenarPor: e.target.value }); setOrdem(null); }}>
              <option value="gordon">Margem do Gordon ajustado</option><option value="dy">Maior DY</option><option value="p_vp">Menor P/VP</option>
            </select>
          </label>
          <span className="ml-auto flex gap-2">
            <a className="pilula" href={`/api/screening/fiis/exportar?${q}&formato=xlsx`}>Exportar .xlsx</a>
            <a className="pilula" href={`/api/screening/fiis/exportar?${q}&formato=csv`}>.csv</a>
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="suave">
              <tr className="text-right">
                <th className="px-2 py-2 text-left">#</th><th className="px-3 py-2 text-left">Fundo</th>
                {COLUNAS.map((c) => (
                  <th key={c.id} className={`whitespace-nowrap px-3 py-2 ${c.cor ? "metodo-bazin fundo-metodo texto-metodo" : ""}`}
                    aria-sort={ordem?.coluna === c.id ? (ordem.crescente ? "ascending" : "descending") : "none"}>
                    <button type="button" onClick={() => setOrdem((o) => (o?.coluna !== c.id ? { coluna: c.id, crescente: false } : o.crescente ? null : { coluna: c.id, crescente: true }))}>
                      {c.titulo} {ordem?.coluna === c.id ? (ordem.crescente ? "↑" : "↓") : "⇅"}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trecho.map((i) => (
                <tr key={i.ticker} className="border-t text-right">
                  <td className="suave px-2 py-2 text-left">{i.posicao}</td>
                  <td className="px-3 py-2 text-left"><Link href={`/fiis/${i.ticker}`} className="link font-medium">{i.ticker}</Link>
                    <div className="suave max-w-44 truncate text-xs">{i.nome}</div></td>
                  {COLUNAS.map((c) => {
                    const v = i[c.id];
                    const texto = c.unidade === "texto" ? (v ?? "—") : c.unidade === "R$" ? (v === null ? "—" : formatarMoeda(Number(v))) : formatarValor(v as number | null, c.unidade);
                    return (
                      <td key={c.id} className={`whitespace-nowrap px-3 py-2 ${c.cor ? "metodo-bazin fundo-metodo" : ""} ${c.unidade === "texto" ? "max-w-40 truncate text-left" : ""}`}
                        style={c.id === "gordon_margem" && typeof v === "number" ? { color: v >= 0 ? "var(--destaque)" : "var(--negativo)" } : undefined}>
                        {texto}
                      </td>
                    );
                  })}
                </tr>
              ))}
              {dados && trecho.length === 0 && (
                <tr><td colSpan={COLUNAS.length + 2} className="suave px-3 py-6 text-center">Nenhum fundo passa nos filtros escolhidos.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="suave flex flex-wrap items-center gap-3 border-t p-3 text-xs">
          <span>{itens.length} de {dados?.total_avaliados ?? 0} fundos{dados?.sem_cotacao ? ` (${dados.sem_cotacao} sem cotação)` : ""}</span>
          <span className="flex items-center gap-2">
            <button type="button" className="pilula" disabled={pagina === 0} onClick={() => setPagina(pagina - 1)}>‹</button>
            {pagina + 1} / {paginas}
            <button type="button" className="pilula" disabled={pagina + 1 >= paginas} onClick={() => setPagina(pagina + 1)}>›</button>
          </span>
          <span className="ml-auto">Atualizado em {formatarData(dados?.atualizado_em)}</span>
        </div>
      </section>
    </div>
  );
}
