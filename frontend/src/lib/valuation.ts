/** Campos editáveis de cada método de valuation e conversão entre a tela (%) e a API (fração). */

export type TipoCampo = "pct" | "reais" | "por_acao" | "inteiro" | "lista_pct";
export type Campo = { chave: string; rotulo: string; tipo: TipoCampo; dica?: string };

export const CAMPOS: Record<string, Campo[]> = {
  preco_teto_projetivo: [
    { chave: "lucro_projetado", rotulo: "Lucro projetado (12 meses)", tipo: "reais" },
    { chave: "payout", rotulo: "Payout", tipo: "pct", dica: "Parte do lucro distribuída" },
    { chave: "yield_minimo", rotulo: "Yield mínimo", tipo: "pct" },
  ],
  gordon: [
    { chave: "dividendo_atual", rotulo: "Dividendo por ação (12 meses)", tipo: "por_acao" },
    { chave: "custo_capital", rotulo: "Custo do capital próprio", tipo: "pct" },
    { chave: "crescimento", rotulo: "Crescimento perpétuo", tipo: "pct" },
  ],
  ddm_dois_estagios: [
    { chave: "dividendo_atual", rotulo: "Dividendo por ação (12 meses)", tipo: "por_acao" },
    { chave: "custo_capital", rotulo: "Custo do capital próprio", tipo: "pct" },
    { chave: "crescimento_alto", rotulo: "Crescimento no 1º estágio", tipo: "pct" },
    { chave: "anos_alto", rotulo: "Anos do 1º estágio", tipo: "inteiro" },
    { chave: "crescimento_estavel", rotulo: "Crescimento perpétuo", tipo: "pct" },
  ],
  dcf_fcff: [
    { chave: "receita_base", rotulo: "Receita base (12 meses)", tipo: "reais" },
    { chave: "crescimento_receita", rotulo: "Crescimento da receita por ano", tipo: "lista_pct" },
    { chave: "margem_ebit", rotulo: "Margem EBIT", tipo: "pct" },
    { chave: "aliquota", rotulo: "Alíquota de IR/CSLL", tipo: "pct" },
    { chave: "da_pct_receita", rotulo: "D&A (% da receita)", tipo: "pct" },
    { chave: "capex_pct_receita", rotulo: "Capex (% da receita)", tipo: "pct" },
    { chave: "capital_giro_pct_variacao_receita", rotulo: "Capital de giro (% do aumento da receita)", tipo: "pct" },
    { chave: "taxa_desconto", rotulo: "WACC", tipo: "pct" },
    { chave: "crescimento_perpetuo", rotulo: "Crescimento perpétuo", tipo: "pct" },
    { chave: "divida_liquida", rotulo: "Dívida líquida", tipo: "reais" },
  ],
  dcf_fcfe: [
    { chave: "receita_base", rotulo: "Receita base (12 meses)", tipo: "reais" },
    { chave: "crescimento_receita", rotulo: "Crescimento da receita por ano", tipo: "lista_pct" },
    { chave: "margem_ebit", rotulo: "Margem EBIT", tipo: "pct" },
    { chave: "aliquota", rotulo: "Alíquota de IR/CSLL", tipo: "pct" },
    { chave: "da_pct_receita", rotulo: "D&A (% da receita)", tipo: "pct" },
    { chave: "capex_pct_receita", rotulo: "Capex (% da receita)", tipo: "pct" },
    { chave: "capital_giro_pct_variacao_receita", rotulo: "Capital de giro (% do aumento da receita)", tipo: "pct" },
    { chave: "juros_anuais", rotulo: "Juros por ano", tipo: "reais" },
    { chave: "nova_divida_anual", rotulo: "Nova dívida líquida por ano", tipo: "reais" },
    { chave: "taxa_desconto", rotulo: "Custo do capital próprio", tipo: "pct" },
    { chave: "crescimento_perpetuo", rotulo: "Crescimento perpétuo", tipo: "pct" },
  ],
  multiplos: [],
};

export const DCFS = ["dcf_fcff", "dcf_fcfe"];

/** Valor da API → texto do campo (percentuais em %, com vírgula). */
export function paraTela(valor: unknown, tipo: TipoCampo): string {
  if (valor === null || valor === undefined) return "";
  if (tipo === "lista_pct") return (valor as number[]).map((v) => paraTela(v, "pct")).join("; ");
  const n = Number(valor);
  const v = tipo === "pct" ? n * 100 : n;
  return v.toLocaleString("pt-BR", { maximumFractionDigits: tipo === "reais" ? 0 : tipo === "pct" ? 2 : 4, useGrouping: false });
}

const numero = (texto: string): number | null => {
  const t = texto.trim();
  if (!t) return null;
  const n = Number(t.includes(",") ? t.replace(/\./g, "").replace(",", ".") : t);
  return Number.isFinite(n) ? n : null;
};

/** Texto do campo → valor da API; null quando vazio ou inválido. */
export function paraApi(texto: string, tipo: TipoCampo): number | number[] | null {
  if (tipo === "lista_pct") {
    const partes = texto.split(";").map((p) => numero(p));
    return partes.length && partes.every((p) => p !== null) ? partes.map((p) => (p as number) / 100) : null;
  }
  const n = numero(texto);
  if (n === null) return null;
  if (tipo === "pct") return n / 100;
  if (tipo === "inteiro") return Math.round(n);
  return n;
}
