"use client";

import { useEffect, useState } from "react";
import { formatarData, formatarValor } from "@/lib/formato";

type Lancamento = { id: number; ticker: string; tipo: string; data: string; quantidade: number; preco: number;
  taxas: number; origem: string };
const TIPOS = [["COMPRA", "Compra"], ["VENDA", "Venda"], ["DESDOBRAMENTO", "Desdobramento (ações recebidas)"],
  ["BONIFICACAO", "Bonificação (ações recebidas)"], ["GRUPAMENTO", "Grupamento (ações que saem)"]];

export function Lancamentos({ carteira, aoMudar }: { carteira: number; aoMudar: () => void }) {
  const [lista, setLista] = useState<Lancamento[]>([]);
  const [form, setForm] = useState({ ticker: "", tipo: "COMPRA", data: new Date().toISOString().slice(0, 10),
    quantidade: "", preco: "", taxas: "" });
  const [mensagem, setMensagem] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    fetch(`/api/carteiras/${carteira}/lancamentos`).then((r) => (r.ok ? r.json() : [])).then(setLista);
  }, [carteira, versao]);

  const num = (t: string) => (t.trim() ? Number(t.replace(/\./g, "").replace(",", ".")) : 0);
  const mudou = () => {
    setVersao((v) => v + 1);
    aoMudar();
  };

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    const r = await fetch(`/api/carteiras/${carteira}/lancamentos`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...form, quantidade: num(form.quantidade), preco: num(form.preco), taxas: num(form.taxas) }) });
    if (r.ok) {
      setMensagem("Lançamento registrado.");
      setForm({ ...form, quantidade: "", preco: "", taxas: "" });
      mudou();
    } else {
      const corpo = await r.json().catch(() => ({}));
      setMensagem(typeof corpo.detail === "string" ? corpo.detail : "Confira os campos (quantidade e preço positivos).");
    }
  };

  const importar = async (arquivo: File | undefined) => {
    if (!arquivo) return;
    setMensagem("Importando…");
    const r = await fetch(`/api/carteiras/${carteira}/importar?nome_arquivo=${encodeURIComponent(arquivo.name)}`, {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: arquivo });
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) return setMensagem(corpo.detail ?? "Não foi possível importar.");
    setMensagem(`${corpo.importados} lançamento(s) importado(s); ${corpo.repetidos} já existiam; ${corpo.ignorados} linha(s) ignorada(s) (proventos e outros).` +
      (corpo.erros.length ? ` Problemas: ${corpo.erros.slice(0, 5).join("; ")}.` : ""));
    mudou();
  };

  const apagar = async (id: number) => {
    if (!window.confirm("Apagar este lançamento?")) return;
    const r = await fetch(`/api/carteiras/${carteira}/lancamentos/${id}`, { method: "DELETE" });
    if (!r.ok) setMensagem((await r.json().catch(() => ({}))).detail ?? "Não foi possível apagar.");
    else mudou();
  };

  return (
    <div className="space-y-4 text-sm">
      <form onSubmit={enviar} className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7 lg:items-end">
        <label className="block"><span className="suave text-xs">Ticker</span>
          <input required className="campo w-full uppercase" aria-label="Ticker" value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value })} /></label>
        <label className="block"><span className="suave text-xs">Tipo</span>
          <select className="campo w-full" aria-label="Tipo" value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
            {TIPOS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}</select></label>
        <label className="block"><span className="suave text-xs">Data</span>
          <input required type="date" className="campo w-full" aria-label="Data" value={form.data} onChange={(e) => setForm({ ...form, data: e.target.value })} /></label>
        <label className="block"><span className="suave text-xs">Quantidade</span>
          <input required inputMode="decimal" className="campo w-full text-right" aria-label="Quantidade" value={form.quantidade} onChange={(e) => setForm({ ...form, quantidade: e.target.value })} /></label>
        <label className="block"><span className="suave text-xs">Preço (R$)</span>
          <input inputMode="decimal" className="campo w-full text-right" aria-label="Preço" value={form.preco} disabled={!["COMPRA", "VENDA"].includes(form.tipo)} onChange={(e) => setForm({ ...form, preco: e.target.value })} /></label>
        <label className="block"><span className="suave text-xs">Taxas (R$)</span>
          <input inputMode="decimal" className="campo w-full text-right" aria-label="Taxas" value={form.taxas} onChange={(e) => setForm({ ...form, taxas: e.target.value })} /></label>
        <button type="submit" className="pilula">Registrar</button>
      </form>
      <div className="flex flex-wrap items-center gap-3 rounded-lg border p-3">
        <label className="pilula cursor-pointer">Importar extrato da B3 (.xlsx)
          <input type="file" accept=".xlsx" className="hidden" aria-label="Arquivo da B3" onChange={(e) => importar(e.target.files?.[0])} />
        </label>
        <span className="suave text-xs">Na Área do Investidor (investidor.b3.com.br): Extratos → Negociação (ou Movimentação) → Baixar Excel.
          Use um dos dois para o mesmo período. Lançamentos repetidos são ignorados.</span>
      </div>
      {mensagem && <p style={{ color: "var(--alerta)" }}>{mensagem}</p>}
      <div className="max-h-[32rem] overflow-auto">
        <table className="w-full">
          <thead className="suave sticky top-0" style={{ background: "var(--superficie)" }}><tr className="text-right">
            <th className="py-1 text-left">Data</th><th className="text-left">Ativo</th><th className="text-left">Tipo</th>
            <th>Qtd.</th><th>Preço</th><th>Taxas</th><th className="text-left">Origem</th><th /></tr></thead>
          <tbody>
            {lista.map((l) => (
              <tr key={l.id} className="border-t text-right">
                <td className="py-1 text-left">{formatarData(l.data)}</td><td className="text-left">{l.ticker}</td>
                <td className="text-left">{l.tipo.toLowerCase()}</td><td>{l.quantidade.toLocaleString("pt-BR")}</td>
                <td>{l.preco ? formatarValor(l.preco, "R$/ação") : "—"}</td><td>{l.taxas ? formatarValor(l.taxas, "R$/ação") : "—"}</td>
                <td className="suave text-left">{l.origem === "b3" ? "B3" : "manual"}</td>
                <td><button type="button" className="suave hover:underline" aria-label={`Apagar lançamento ${l.id}`} onClick={() => apagar(l.id)}>apagar</button></td>
              </tr>
            ))}
            {lista.length === 0 && <tr><td colSpan={8} className="suave py-4 text-center">Nenhum lançamento.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
