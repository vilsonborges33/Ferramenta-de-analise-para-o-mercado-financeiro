"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Otimizador, Proventos, Rentabilidade } from "@/componentes/carteira/Analises";
import { Lancamentos } from "@/componentes/carteira/Lancamentos";
import { Posicoes } from "@/componentes/carteira/Posicoes";
import { gravarLocal, lerLocal } from "@/lib/screening";

type Carteira = { id: number; nome: string; lancamentos: number };
const ABAS = [["posicoes", "Posições"], ["lancamentos", "Lançamentos"], ["rentabilidade", "Rentabilidade"],
  ["proventos", "Proventos"], ["otimizador", "Otimizador"]] as const;

export default function PaginaCarteira() {
  const [carteiras, setCarteiras] = useState<Carteira[] | null | undefined>(undefined); // null = sem login
  const [atual, setAtual] = useState<number | null>(null);
  const [aba, setAba] = useState<(typeof ABAS)[number][0]>("posicoes");
  const [versao, setVersao] = useState(0);

  const carregar = useCallback(async (escolher?: number) => {
    const r = await fetch("/api/carteiras");
    if (!r.ok) return setCarteiras(null);
    const lista: Carteira[] = await r.json();
    setCarteiras(lista);
    const preferida = escolher ?? lerLocal<number | null>("carteira.atual", null);
    setAtual(lista.find((c) => c.id === preferida)?.id ?? lista[0]?.id ?? null);
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);
  useEffect(() => {
    if (atual) gravarLocal("carteira.atual", atual);
  }, [atual]);

  const criar = async () => {
    const nome = window.prompt("Nome da carteira:", carteiras?.length ? "Nova carteira" : "Principal")?.trim();
    if (!nome) return;
    const r = await fetch("/api/carteiras", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nome }) });
    if (r.ok) carregar((await r.json()).id);
  };
  const renomear = async () => {
    const c = carteiras?.find((x) => x.id === atual);
    const nome = c && window.prompt("Novo nome:", c.nome)?.trim();
    if (!nome) return;
    await fetch(`/api/carteiras/${atual}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nome }) });
    carregar(atual ?? undefined);
  };
  const apagar = async () => {
    const c = carteiras?.find((x) => x.id === atual);
    if (!c || !window.confirm(`Apagar a carteira "${c.nome}" e todos os seus lançamentos?`)) return;
    await fetch(`/api/carteiras/${atual}`, { method: "DELETE" });
    carregar();
  };

  if (carteiras === undefined) return <p className="suave">Carregando…</p>;
  if (carteiras === null)
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-semibold">Carteira</h1>
        <p><Link href="/entrar" className="link">Entre na sua conta</Link> para registrar e acompanhar sua carteira.</p>
      </div>
    );
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Carteira</h1>
          <p className="suave text-sm">Consolidação, rentabilidade contra índices, proventos e otimização.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {carteiras.length > 0 && (
            <select className="campo" aria-label="Carteira" value={atual ?? ""} onChange={(e) => setAtual(Number(e.target.value))}>
              {carteiras.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
          )}
          <button type="button" className="pilula" onClick={criar}>Nova carteira</button>
          {atual && <button type="button" className="pilula" onClick={renomear}>Renomear</button>}
          {atual && <button type="button" className="pilula" onClick={apagar}>Apagar</button>}
        </div>
      </div>
      {!atual ? (
        <p className="cartao p-4 text-sm">Crie sua primeira carteira para começar.</p>
      ) : (
        <section className="cartao space-y-4 p-4">
          <div className="flex flex-wrap gap-2 text-sm" role="tablist">
            {ABAS.map(([id, nome]) => (
              <button key={id} type="button" role="tab" aria-selected={aba === id} className="pilula" onClick={() => setAba(id)}>{nome}</button>
            ))}
          </div>
          {aba === "posicoes" && <Posicoes carteira={atual} versao={versao} />}
          {aba === "lancamentos" && <Lancamentos carteira={atual} aoMudar={() => setVersao((v) => v + 1)} />}
          {aba === "rentabilidade" && <Rentabilidade carteira={atual} versao={versao} />}
          {aba === "proventos" && <Proventos carteira={atual} versao={versao} />}
          {aba === "otimizador" && <Otimizador carteira={atual} versao={versao} />}
        </section>
      )}
    </div>
  );
}
