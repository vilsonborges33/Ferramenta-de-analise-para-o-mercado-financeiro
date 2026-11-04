"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { formatarData } from "@/lib/formato";

type Registro = { id: number; ticker: string | null; data: string; decisao: string; tese: string;
  premissas: Record<string, string>; data_revisao_prevista: string | null; revisao: string | null;
  resultado_observado: string | null; revisao_pendente: boolean };
const VAZIO = { ticker: "", data: new Date().toISOString().slice(0, 10), decisao: "", tese: "", premissas: "",
  data_revisao_prevista: "", revisao: "", resultado_observado: "" };

/** Diário de decisões: o que foi decidido, por quê, com quais premissas — e a revisão depois (Dalio). */
export default function Diario() {
  const [lista, setLista] = useState<Registro[] | null | undefined>(undefined);
  const [form, setForm] = useState(VAZIO);
  const [editando, setEditando] = useState<number | null>(null);
  const [mensagem, setMensagem] = useState<string | null>(null);

  const carregar = useCallback(() => {
    fetch("/api/diario").then((r) => (r.ok ? r.json() : null)).then(setLista).catch(() => setLista(null));
  }, []);
  useEffect(carregar, [carregar]);

  const salvar = async (e: React.FormEvent) => {
    e.preventDefault();
    const premissas = Object.fromEntries(form.premissas.split("\n").map((l) => l.split(":")).filter((p) => p[0]?.trim())
      .map(([k, ...v]) => [k.trim(), v.join(":").trim()]));
    const corpo = { ...form, ticker: form.ticker.trim() || null, premissas, data_revisao_prevista: form.data_revisao_prevista || null,
      revisao: form.revisao || null, resultado_observado: form.resultado_observado || null };
    const r = await fetch(editando ? `/api/diario/${editando}` : "/api/diario", { method: editando ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
    if (!r.ok) return setMensagem((await r.json().catch(() => ({}))).detail?.toString() ?? "Confira os campos.");
    setMensagem(null);
    setForm(VAZIO);
    setEditando(null);
    carregar();
  };
  const editar = (r: Registro) => {
    setEditando(r.id);
    setForm({ ticker: r.ticker ?? "", data: r.data, decisao: r.decisao, tese: r.tese,
      premissas: Object.entries(r.premissas).map(([k, v]) => `${k}: ${v}`).join("\n"),
      data_revisao_prevista: r.data_revisao_prevista ?? "", revisao: r.revisao ?? "", resultado_observado: r.resultado_observado ?? "" });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const apagar = async (id: number) => {
    if (!window.confirm("Apagar este registro?")) return;
    await fetch(`/api/diario/${id}`, { method: "DELETE" });
    carregar();
  };

  if (lista === undefined) return <p className="suave">Carregando…</p>;
  if (lista === null)
    return <p><Link href="/entrar" className="link">Entre na sua conta</Link> para usar o diário de decisões.</p>;
  const campo = "campo w-full";
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Diário de decisões</h1>
        <p className="suave text-sm">Registre a decisão, a tese e as premissas no momento em que decide; revise depois e compare com o que aconteceu.</p>
      </div>
      <form onSubmit={salvar} className="cartao grid gap-3 p-4 text-sm md:grid-cols-2">
        <label><span className="suave text-xs">Ativo (opcional)</span><input className={`${campo} uppercase`} aria-label="Ativo" value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value })} /></label>
        <label><span className="suave text-xs">Data</span><input required type="date" className={campo} aria-label="Data" value={form.data} onChange={(e) => setForm({ ...form, data: e.target.value })} /></label>
        <label className="md:col-span-2"><span className="suave text-xs">Decisão</span><input required className={campo} aria-label="Decisão" placeholder="Ex.: Comprar 100 ações" value={form.decisao} onChange={(e) => setForm({ ...form, decisao: e.target.value })} /></label>
        <label className="md:col-span-2"><span className="suave text-xs">Tese (por quê)</span><textarea required rows={3} className={campo} aria-label="Tese" value={form.tese} onChange={(e) => setForm({ ...form, tese: e.target.value })} /></label>
        <label><span className="suave text-xs">Premissas (uma por linha, “nome: valor”)</span><textarea rows={3} className={campo} aria-label="Premissas" placeholder={"crescimento: 5% a.a.\nmargem: 20%"} value={form.premissas} onChange={(e) => setForm({ ...form, premissas: e.target.value })} /></label>
        <label><span className="suave text-xs">Revisar em</span><input type="date" className={campo} aria-label="Revisar em" value={form.data_revisao_prevista} onChange={(e) => setForm({ ...form, data_revisao_prevista: e.target.value })} /></label>
        {editando && <>
          <label><span className="suave text-xs">Revisão</span><textarea rows={2} className={campo} aria-label="Revisão" value={form.revisao} onChange={(e) => setForm({ ...form, revisao: e.target.value })} /></label>
          <label><span className="suave text-xs">Resultado observado</span><textarea rows={2} className={campo} aria-label="Resultado observado" value={form.resultado_observado} onChange={(e) => setForm({ ...form, resultado_observado: e.target.value })} /></label>
        </>}
        <div className="flex gap-2 md:col-span-2">
          <button type="submit" className="pilula">{editando ? "Salvar revisão" : "Registrar decisão"}</button>
          {editando && <button type="button" className="pilula" onClick={() => { setEditando(null); setForm(VAZIO); }}>Cancelar</button>}
          {mensagem && <span style={{ color: "var(--alerta)" }}>{mensagem}</span>}
        </div>
      </form>
      <div className="space-y-3">
        {lista.length === 0 && <p className="suave text-sm">Nenhuma decisão registrada.</p>}
        {lista.map((r) => (
          <article key={r.id} className="cartao space-y-1 p-4 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{r.decisao}</span>
              {r.ticker && <Link href={`/acoes/${r.ticker}`} className="link">{r.ticker}</Link>}
              <span className="suave">{formatarData(r.data)}</span>
              {r.revisao_pendente && <span className="pilula text-xs" style={{ color: "var(--alerta)" }}>revisão pendente</span>}
              <span className="ml-auto flex gap-3 text-xs">
                <button type="button" className="link" onClick={() => editar(r)}>{r.revisao ? "Editar" : "Revisar"}</button>
                <button type="button" className="suave hover:underline" onClick={() => apagar(r.id)}>Apagar</button>
              </span>
            </div>
            <p className="whitespace-pre-line">{r.tese}</p>
            {Object.keys(r.premissas).length > 0 && (
              <p className="suave text-xs">Premissas: {Object.entries(r.premissas).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
            )}
            {r.data_revisao_prevista && <p className="suave text-xs">Revisar em {formatarData(r.data_revisao_prevista)}</p>}
            {r.revisao && <p><span className="font-medium">Revisão:</span> {r.revisao}</p>}
            {r.resultado_observado && <p><span className="font-medium">Resultado:</span> {r.resultado_observado}</p>}
          </article>
        ))}
      </div>
    </div>
  );
}
