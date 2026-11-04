import { buscar } from "@/lib/api";

export type ItemMacro = {
  id: string; rotulo: string; valor: number; unidade: string; data: string; fonte: string; variacao: number | null;
};
export type Variacao = { ticker: string; classe: string; fechamento: number; variacao: number };
export type GrupoVariacoes = { altas: Variacao[]; baixas: Variacao[]; positivas: number; negativas: number; total: number };
export type Painel = {
  macro: ItemMacro[];
  variacoes: { data: string | null; fonte: string; acoes: GrupoVariacoes; fiis: GrupoVariacoes };
};

/** O painel nunca derruba a página: sem API, a faixa e os cartões simplesmente não aparecem. */
export async function buscarPainel(): Promise<Painel | null> {
  try {
    return await buscar<Painel>("/painel");
  } catch {
    return null;
  }
}

export function formatarMacro(m: ItemMacro): string {
  if (m.unidade === "R$") return `R$ ${m.valor.toLocaleString("pt-BR", { minimumFractionDigits: 4, maximumFractionDigits: 4 })}`;
  const pct = (m.valor * 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return m.id === "Tesouro IPCA+" ? `IPCA + ${pct}%` : `${pct}%`;
}

export const pct = (v: number, sinal = true) =>
  `${sinal && v > 0 ? "+" : ""}${(v * 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
