"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { formatarData, formatarValor } from "@/lib/formato";

type Salvo = { id: number; ticker: string; metodo: string; nome_metodo: string; nome: string; narrativa: string | null;
  resultado: { valor_por_acao: number | null; preco: number | null; margem_seguranca: number | null }; atualizado_em: string };

/** "Meus valuations": todos os valuations salvos, com o preço da época e a margem calculada no dia. */
export default function MeusValuations() {
  const [salvos, setSalvos] = useState<Salvo[] | null | undefined>(undefined); // null = sem login
  const [ticker, setTicker] = useState("");
  const router = useRouter();

  useEffect(() => {
    fetch("/api/valuations").then((r) => (r.ok ? r.json() : null)).then(setSalvos).catch(() => setSalvos(null));
  }, []);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Valuation</h1>
        <p className="suave text-sm">DCF, Gordon, dividendos em dois estágios, preço teto projetivo e múltiplos do setor.</p>
      </div>
      <section className="cartao space-y-2 p-4">
        <h2 className="font-semibold">Fazer o valuation de uma ação</h2>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (ticker.trim()) router.push(`/valuation/${ticker.trim().toUpperCase()}`); }}>
          <input aria-label="Ticker da ação" placeholder="Ex.: WEGE3" className="campo w-40 uppercase" value={ticker}
            onChange={(e) => setTicker(e.target.value)} />
          <button type="submit" className="pilula">Abrir</button>
        </form>
      </section>
      <section className="cartao space-y-2 p-4">
        <h2 className="font-semibold">Meus valuations</h2>
        {salvos === undefined && <p className="suave text-sm">Carregando…</p>}
        {salvos === null && (
          <p className="text-sm"><Link href="/entrar" className="link">Entre na sua conta</Link> para ver e salvar valuations.</p>
        )}
        {salvos && salvos.length === 0 && <p className="suave text-sm">Nenhum valuation salvo ainda.</p>}
        {salvos && salvos.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="suave"><tr className="text-right">
                <th className="px-2 py-1 text-left">Ação</th><th className="px-2 py-1 text-left">Nome</th>
                <th className="px-2 py-1 text-left">Método</th><th className="px-2 py-1">Valor/ação</th>
                <th className="px-2 py-1">Cotação na época</th><th className="px-2 py-1">Margem na época</th><th className="px-2 py-1">Salvo em</th>
              </tr></thead>
              <tbody>
                {salvos.map((v) => (
                  <tr key={v.id} className="border-t text-right">
                    <td className="px-2 py-1 text-left"><Link href={`/valuation/${v.ticker}`} className="link font-medium">{v.ticker}</Link></td>
                    <td className="px-2 py-1 text-left">{v.nome}</td>
                    <td className="suave px-2 py-1 text-left">{v.nome_metodo}</td>
                    <td className="px-2 py-1">{formatarValor(v.resultado.valor_por_acao, "R$/ação")}</td>
                    <td className="px-2 py-1">{formatarValor(v.resultado.preco, "R$/ação")}</td>
                    <td className="px-2 py-1">{formatarValor(v.resultado.margem_seguranca, "%")}</td>
                    <td className="suave px-2 py-1">{formatarData(v.atualizado_em)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
