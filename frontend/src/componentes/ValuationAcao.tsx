"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Grafico, reais } from "@/componentes/Grafico";
import { formatarData, formatarMoeda, formatarValor } from "@/lib/formato";
import { CAMPOS, DCFS, paraApi, paraTela, type Campo } from "@/lib/valuation";

type Comparativo = { metodo: string; nome: string; metodologia: string; valor_por_acao: number | null;
  motivo_indisponivel: string | null; margem_seguranca: number | null };
type Inicio = {
  insumos: Record<string, number | string | null>;
  premissas: Record<string, Record<string, unknown> & { origem: string }>;
  comparativo: Comparativo[];
  metodos: { id: string; nome: string; metodologia: string }[];
  aviso: string;
};
type Resultado = Comparativo & { preco: number | null; data_preco: string | null; aviso: string;
  premissas: Record<string, unknown>; detalhes: Record<string, unknown> };
type Salvo = { id: number; metodo: string; nome_metodo: string; nome: string; narrativa: string | null;
  premissas: Record<string, unknown>; resultado: Resultado; atualizado_em: string };

const textos = (campos: Campo[], valores: Record<string, unknown>) =>
  Object.fromEntries(campos.map((c) => [c.chave, paraTela(valores[c.chave], c.tipo)]));

function Projecao({ linhas, fcfe }: { linhas: Record<string, number>[]; fcfe: boolean }) {
  const rotulos: [string, string][] = [["receita", "Receita"], ["ebit", "EBIT"], ["nopat", "NOPAT"],
    ["depreciacao", "D&A"], ["capex", "Capex"], ["variacao_capital_giro", "Variação do capital de giro"],
    ["fcff", "FCFF"], ...(fcfe ? [["fluxo", "FCFE"] as [string, string]] : [])];
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="suave"><tr className="text-right"><th className="px-2 py-1 text-left">Ano</th>
          {linhas.map((l) => <th key={l.ano} className="px-2 py-1">{l.ano}</th>)}</tr></thead>
        <tbody>
          {rotulos.map(([chave, nome]) => (
            <tr key={chave} className="border-t text-right">
              <td className="whitespace-nowrap px-2 py-1 text-left">{nome}</td>
              {linhas.map((l) => <td key={l.ano} className="whitespace-nowrap px-2 py-1">{formatarMoeda(l[chave])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Sensibilidade({ s, preco }: { s: { taxas: number[]; crescimentos: number[]; valores: (number | null)[][] };
  preco: number | null }) {
  return (
    <div className="overflow-x-auto">
      <p className="suave mb-1 text-xs">Valor por ação: taxa de desconto (linhas) × crescimento perpétuo (colunas).</p>
      <table className="text-sm">
        <thead className="suave"><tr className="text-right"><th className="px-2 py-1" />
          {s.crescimentos.map((g) => <th key={g} className="px-2 py-1">g {formatarValor(g, "%")}</th>)}</tr></thead>
        <tbody>
          {s.taxas.map((t, i) => (
            <tr key={t} className="border-t text-right">
              <th className="suave px-2 py-1">r {formatarValor(t, "%")}</th>
              {s.valores[i].map((v, j) => (
                <td key={j} className="px-2 py-1"
                  style={{ fontWeight: i === 2 && j === 2 ? 700 : undefined,
                    color: v === null || preco === null ? undefined : v >= preco ? "var(--destaque)" : "var(--negativo)" }}>
                  {formatarValor(v, "R$/ação")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Valuation completo de uma ação: comparativo dos métodos, premissas editáveis, salvar e exportar. */
export function ValuationAcao({ ticker }: { ticker: string }) {
  const [inicio, setInicio] = useState<Inicio | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [metodo, setMetodo] = useState("dcf_fcff");
  const [campos, setCampos] = useState<Record<string, string>>({});
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [salvos, setSalvos] = useState<Salvo[] | null>(null); // null = sem login
  const [mensagem, setMensagem] = useState<string | null>(null);

  const carregarSalvos = useCallback(() => {
    fetch(`/api/valuations?ticker=${ticker}`).then((r) => (r.ok ? r.json() : null)).then(setSalvos)
      .catch(() => setSalvos(null));
  }, [ticker]);

  useEffect(() => {
    fetch(`/api/valuation/${ticker}`)
      .then(async (r) => {
        if (!r.ok) throw new Error(r.status === 404 ? "Valuation disponível só para ações." : "Falha ao carregar.");
        const dados: Inicio = await r.json();
        setInicio(dados);
        setCampos(textos(CAMPOS.dcf_fcff, dados.premissas.dcf_fcff));
      })
      .catch((e: Error) => setErro(e.message));
    carregarSalvos();
  }, [ticker, carregarSalvos]);

  const premissas = useMemo(() => {
    const p: Record<string, unknown> = {};
    for (const c of CAMPOS[metodo] ?? []) p[c.chave] = paraApi(campos[c.chave] ?? "", c.tipo);
    return p;
  }, [campos, metodo]);

  useEffect(() => {
    if (!inicio) return;
    const controle = new AbortController();
    const espera = setTimeout(() => {
      fetch(`/api/valuation/${ticker}/calcular`, {
        method: "POST", headers: { "Content-Type": "application/json" }, signal: controle.signal,
        body: JSON.stringify({ metodo, premissas }),
      })
        .then(async (r) => {
          if (!r.ok) throw new Error((await r.json()).detail ?? "Não foi possível calcular.");
          setResultado(await r.json());
          setMensagem(null);
        })
        .catch((e: Error) => e.name !== "AbortError" && setMensagem(String(e.message)));
    }, 300);
    return () => {
      clearTimeout(espera);
      controle.abort();
    };
  }, [inicio, ticker, metodo, premissas]);

  const escolher = (m: string, valores?: Record<string, unknown>) => {
    if (!inicio) return;
    setMetodo(m);
    setResultado(null);
    setCampos(textos(CAMPOS[m] ?? [], valores ?? inicio.premissas[m]));
  };

  const salvar = async () => {
    const nome = window.prompt("Nome deste valuation (ex.: Cenário base):")?.trim();
    if (!nome) return;
    const narrativa = window.prompt("Narrativa (opcional): a história que justifica estes números") ?? null;
    const r = await fetch("/api/valuations", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, metodo, nome, premissas, narrativa: narrativa || null }) });
    setMensagem(r.ok ? "Valuation salvo." : r.status === 401 ? "Entre na sua conta para salvar." : "Não foi possível salvar.");
    if (r.ok) carregarSalvos();
  };

  const exportar = async () => {
    const r = await fetch(`/api/valuation/${ticker}/exportar`, { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ metodo, premissas }) });
    if (!r.ok) return setMensagem("Não foi possível exportar.");
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = `dcf-${ticker.toLowerCase()}-${metodo.replace("dcf_", "")}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const apagar = async (id: number) => {
    if (!window.confirm("Apagar este valuation?")) return;
    await fetch(`/api/valuations/${id}`, { method: "DELETE" });
    carregarSalvos();
  };

  const preco = inicio ? (inicio.insumos.preco as number | null) : null;
  const grafico = useMemo(() => {
    const itens = (inicio?.comparativo ?? []).filter((c) => c.valor_por_acao !== null);
    return {
      grid: { left: 150, right: 24, top: 8, bottom: 24 },
      tooltip: { trigger: "axis", valueFormatter: reais },
      xAxis: { type: "value", axisLabel: { formatter: (v: number) => `R$ ${v.toLocaleString("pt-BR")}` } },
      yAxis: { type: "category", data: itens.map((c) => c.nome), inverse: true },
      series: [{ type: "bar", data: itens.map((c) => c.valor_por_acao), itemStyle: { color: "#2463b8" },
        markLine: preco ? { symbol: "none", label: { formatter: "Cotação" }, data: [{ xAxis: preco }] } : undefined }],
    };
  }, [inicio, preco]);

  if (erro) return <p className="suave">{erro}</p>;
  if (!inicio) return <p className="suave">Carregando…</p>;
  const ins = inicio.insumos;
  const detalhes = resultado?.detalhes ?? {};

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="suave text-xs"><Link href={`/acoes/${ticker}`} className="hover:underline">{ticker}</Link> › Valuation</div>
          <h1 className="text-2xl font-semibold">Valuation de {ticker}</h1>
          <div className="suave text-sm">{ins.nome}</div>
        </div>
        <div className="text-right text-sm">
          <div className="text-2xl font-semibold">{formatarValor(preco, "R$/ação")}</div>
          <div className="suave text-xs">fechamento de {formatarData(ins.data_preco as string)}</div>
        </div>
      </div>
      <p className="cartao p-3 text-sm" style={{ color: "var(--alerta)" }} role="note">{inicio.aviso}</p>

      <section className="cartao space-y-3 p-4">
        <h2 className="font-semibold">Comparativo entre métodos (premissas padrão)</h2>
        <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
          <Grafico opcao={grafico} altura="h-60" rotulo="Valor por ação em cada método" />
          <table className="w-full text-sm">
            <thead className="suave"><tr className="text-right"><th className="py-1 text-left">Método</th><th>Valor/ação</th><th>Margem</th></tr></thead>
            <tbody>
              {inicio.comparativo.map((c) => (
                <tr key={c.metodo} className="border-t text-right">
                  <td className="py-1 text-left"><button type="button" className="link" onClick={() => escolher(c.metodo)}>{c.nome}</button></td>
                  <td title={c.motivo_indisponivel ?? ""}>{c.valor_por_acao === null ? <span className="suave">—</span> : formatarValor(c.valor_por_acao, "R$/ação")}</td>
                  <td style={{ color: c.margem_seguranca === null ? undefined : c.margem_seguranca >= 0 ? "var(--destaque)" : "var(--negativo)" }}>
                    {formatarValor(c.margem_seguranca, "%")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="suave text-xs">
          Base contábil: {ins.periodo ?? "—"} · Selic {formatarValor(ins.selic as number | null, "%")} ({formatarData(ins.data_selic as string)})
          · {formatarValor(ins.acoes as number | null, "un")} ações. Passe o mouse sobre “—” para ver o motivo.
        </p>
      </section>

      <section className="cartao space-y-4 p-4">
        <div className="flex flex-wrap gap-2 text-sm" role="tablist">
          {inicio.metodos.map((m) => (
            <button key={m.id} type="button" role="tab" aria-selected={metodo === m.id} className="pilula" onClick={() => escolher(m.id)}>
              {m.nome}
            </button>
          ))}
        </div>
        <p className="suave text-xs">{inicio.premissas[metodo]?.origem}{" "}
          <Link href={`/metodologia/${inicio.metodos.find((m) => m.id === metodo)?.metodologia}`} className="link">Como é calculado</Link>
        </p>
        <div className="grid gap-6 lg:grid-cols-[22rem_1fr]">
          <div className="space-y-2 text-sm">
            {(CAMPOS[metodo] ?? []).map((c) => (
              <label key={c.chave} className="block">
                <span className="suave text-xs">{c.rotulo}{c.tipo === "pct" || c.tipo === "lista_pct" ? " (%)" : c.tipo === "reais" ? " (R$)" : ""}</span>
                <input className="campo mt-0.5 w-full text-right" inputMode="decimal" aria-label={c.rotulo}
                  value={campos[c.chave] ?? ""} onChange={(e) => setCampos({ ...campos, [c.chave]: e.target.value })} />
                {c.tipo === "lista_pct" && <span className="suave text-xs">Um valor por ano, separados por “;”.</span>}
              </label>
            ))}
            {metodo === "multiplos" && <p className="suave">Sem premissas: usa a mediana dos pares do setor.</p>}
            <div className="flex flex-wrap gap-2 pt-2">
              <button type="button" className="pilula" onClick={() => escolher(metodo)}>Restaurar padrão</button>
              <button type="button" className="pilula" onClick={salvar} disabled={salvos === null}
                title={salvos === null ? "Entre na sua conta para salvar" : ""}>Salvar</button>
              {DCFS.includes(metodo) && <button type="button" className="pilula" onClick={exportar}>Exportar .xlsx</button>}
            </div>
            {salvos === null && <Link href="/entrar" className="link text-xs">Entre para salvar seus valuations</Link>}
          </div>

          <div className="min-w-0 space-y-4">
            <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
              <div>
                <div className="suave text-xs">Valor por ação</div>
                <div className="text-3xl font-semibold">{formatarValor(resultado?.valor_por_acao ?? null, "R$/ação")}</div>
              </div>
              <div>
                <div className="suave text-xs">Margem de segurança</div>
                <div className="text-xl" style={{ color: (resultado?.margem_seguranca ?? 0) >= 0 ? "var(--destaque)" : "var(--negativo)" }}>
                  {formatarValor(resultado?.margem_seguranca ?? null, "%")}
                </div>
              </div>
              {typeof detalhes.peso_terminal === "number" && (
                <div><div className="suave text-xs">Peso do valor terminal</div><div>{formatarValor(detalhes.peso_terminal, "%")}</div></div>
              )}
            </div>
            {resultado?.motivo_indisponivel && <p style={{ color: "var(--alerta)" }}>{resultado.motivo_indisponivel}</p>}
            {mensagem && <p className="text-sm" style={{ color: "var(--alerta)" }}>{mensagem}</p>}
            {Array.isArray(detalhes.projecao) && (
              <Projecao linhas={detalhes.projecao as Record<string, number>[]} fcfe={metodo === "dcf_fcfe"} />
            )}
            {detalhes.sensibilidade !== undefined && (
              <Sensibilidade s={detalhes.sensibilidade as never} preco={preco} />
            )}
            {detalhes.por_multiplo !== undefined && (
              <table className="text-sm">
                <thead className="suave"><tr className="text-right"><th className="px-2 text-left">Múltiplo</th><th className="px-2">Mediana do setor</th><th className="px-2">Pares</th><th className="px-2">Preço implícito</th></tr></thead>
                <tbody>
                  {Object.entries(detalhes.por_multiplo as Record<string, { valor: number | null; mediana_setor: number | null; pares: number | null; motivo_indisponivel: string | null }>).map(([nome, m]) => (
                    <tr key={nome} className="border-t text-right">
                      <td className="px-2 text-left">{nome}</td><td className="px-2">{formatarValor(m.mediana_setor, "x")}</td>
                      <td className="px-2">{m.pares ?? "—"}</td>
                      <td className="px-2" title={m.motivo_indisponivel ?? ""}>{formatarValor(m.valor, "R$/ação")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </section>

      {salvos && (
        <section className="cartao space-y-2 p-4">
          <h2 className="font-semibold">Meus valuations de {ticker}</h2>
          {salvos.length === 0 && <p className="suave text-sm">Nenhum salvo ainda. Ajuste as premissas e clique em Salvar.</p>}
          {salvos.map((v) => (
            <div key={v.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t py-2 text-sm">
              <button type="button" className="link font-medium" onClick={() => escolher(v.metodo, v.premissas)}>{v.nome}</button>
              <span className="suave">{v.nome_metodo}</span>
              <span>{formatarValor(v.resultado.valor_por_acao, "R$/ação")}</span>
              <span className="suave text-xs">salvo em {formatarData(v.atualizado_em)}</span>
              {v.narrativa && <span className="suave w-full text-xs">“{v.narrativa}”</span>}
              <span className="ml-auto flex gap-2">
                {DCFS.includes(v.metodo) && <a className="pilula" href={`/api/valuations/${v.id}/exportar.xlsx`}>.xlsx</a>}
                <button type="button" className="pilula" onClick={() => apagar(v.id)}>Apagar</button>
              </span>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
