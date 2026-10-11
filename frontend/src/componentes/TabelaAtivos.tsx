"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Numero } from "@/componentes/Numero";
import { formatarValor } from "@/lib/formato";
import type { ItemLista } from "@/lib/tipos";

type Props = {
  itens: ItemLista[];
  colunas: { id: string; rotulo: string }[];
  base: "acoes" | "fiis";
  vazio: string;
};

export function TabelaAtivos({ itens, colunas, base, vazio }: Props) {
  const [ordem, setOrdem] = useState<{ coluna: string; asc: boolean }>({ coluna: "ticker", asc: true });

  const linhas = useMemo(() => {
    const filtradas = itens;
    const valor = (i: ItemLista): number | string | null => {
      if (ordem.coluna === "ticker") return i.ticker;
      if (ordem.coluna === "cotacao") return i.cotacao?.valor ?? null;
      return i.indicadores[ordem.coluna]?.valor ?? null;
    };
    return [...filtradas].sort((a, b) => {
      const va = valor(a);
      const vb = valor(b);
      if (va === null) return 1; // indisponíveis sempre no fim
      if (vb === null) return -1;
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return ordem.asc ? cmp : -cmp;
    });
  }, [itens, ordem]);

  const cabecalho = (id: string, rotulo: string) => (
    <th key={id} className="whitespace-nowrap px-3 py-2 text-right font-medium first:text-left">
      <button
        type="button"
        onClick={() => setOrdem((o) => ({ coluna: id, asc: o.coluna === id ? !o.asc : true }))}
        className="hover:underline"
      >
        {rotulo}
        {ordem.coluna === id ? (ordem.asc ? " ▲" : " ▼") : ""}
      </button>
    </th>
  );

  return (
    <div className="space-y-3">
      <div className="cartao overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="suave">
            <tr>
              {cabecalho("ticker", "Ativo")}
              {cabecalho("cotacao", "Cotação")}
              {colunas.map((c) => cabecalho(c.id, c.rotulo))}
            </tr>
          </thead>
          <tbody>
            {linhas.map((i) => (
              <tr key={i.ticker} className="border-t" style={{ borderColor: "var(--borda)" }}>
                <td className="px-3 py-2">
                  <Link href={`/${base}/${i.ticker}`} className="link font-medium">
                    {i.ticker}
                  </Link>
                  <div className="suave max-w-48 truncate text-xs">{i.nome}</div>
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-right">
                  {i.cotacao ? formatarValor(i.cotacao.valor, "R$/ação") : "—"}
                </td>
                {colunas.map((c) => (
                  <td key={c.id} className="whitespace-nowrap px-3 py-2 text-right">
                    {i.indicadores[c.id] ? <Numero numero={i.indicadores[c.id]} compacto /> : "—"}
                  </td>
                ))}
              </tr>
            ))}
            {linhas.length === 0 && (
              <tr>
                <td colSpan={colunas.length + 2} className="suave px-3 py-6 text-center">
                  {vazio}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
