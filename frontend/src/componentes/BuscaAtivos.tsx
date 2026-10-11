"use client";

import { useEffect, useState } from "react";
import { TabelaAtivos } from "@/componentes/TabelaAtivos";
import type { ItemLista } from "@/lib/tipos";

type Props = { base: "acoes" | "fiis"; colunas: { id: string; rotulo: string }[]; exemplo: string };

/** Busca por ticker ou nome: só consulta e mostra resultados depois de 2 letras digitadas. */
export function BuscaAtivos({ base, colunas, exemplo }: Props) {
  const [termo, setTermo] = useState("");
  const [itens, setItens] = useState<ItemLista[]>([]);
  const [carregando, setCarregando] = useState(false);
  const ativo = termo.trim().length >= 2;

  useEffect(() => {
    if (!ativo) {
      setItens([]);
      return;
    }
    const controle = new AbortController();
    const espera = setTimeout(async () => {
      setCarregando(true);
      try {
        const r = await fetch(`/api/${base}?busca=${encodeURIComponent(termo.trim())}`, { signal: controle.signal });
        setItens(r.ok ? await r.json() : []);
      } catch {
        /* busca cancelada pela digitação seguinte */
      } finally {
        setCarregando(false);
      }
    }, 300);
    return () => {
      clearTimeout(espera);
      controle.abort();
    };
  }, [termo, ativo, base]);

  return (
    <div className="space-y-3">
      <input
        type="search"
        value={termo}
        onChange={(e) => setTermo(e.target.value)}
        placeholder={`Digite o ticker ou o nome (ex.: ${exemplo})`}
        className="cartao w-full px-3 py-2 text-sm sm:w-96"
        aria-label="Buscar ativo"
        autoFocus
      />
      {ativo && (
        <TabelaAtivos
          itens={itens}
          colunas={colunas}
          base={base}
          vazio={carregando ? "Buscando…" : "Nenhum ativo encontrado com esse ticker ou nome."}
        />
      )}
    </div>
  );
}
