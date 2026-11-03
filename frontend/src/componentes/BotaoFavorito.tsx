"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

/** Estrela de favorito na página do ativo. Sem login, mostra o convite para entrar. */
export function BotaoFavorito({ ticker }: { ticker: string }) {
  const [estado, setEstado] = useState<"carregando" | "sem-login" | "marcado" | "desmarcado">("carregando");

  useEffect(() => {
    fetch("/api/favoritos")
      .then((r) => (r.ok ? r.json() : null))
      .then((lista: string[] | null) => setEstado(lista === null ? "sem-login" : lista.includes(ticker) ? "marcado" : "desmarcado"))
      .catch(() => setEstado("sem-login"));
  }, [ticker]);

  if (estado === "carregando") return null;
  if (estado === "sem-login")
    return (
      <Link href="/entrar" className="link text-xs" title="Entre para guardar favoritos">
        ☆ Favoritar
      </Link>
    );
  const marcado = estado === "marcado";
  return (
    <button type="button" className="pilula text-sm" aria-pressed={marcado}
      onClick={async () => {
        const r = await fetch(`/api/favoritos/${ticker}`, { method: marcado ? "DELETE" : "PUT" });
        if (r.ok) setEstado(marcado ? "desmarcado" : "marcado");
      }}>
      {marcado ? "★ Favorito" : "☆ Favoritar"}
    </button>
  );
}
