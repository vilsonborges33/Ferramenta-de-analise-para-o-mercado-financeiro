/** Estado e regras do Stock Screening (filtros, colunas, ordenação), sem dependência de React. */

export type Metodo = "graham" | "bazin" | "lynch" | "greenblatt";

export type ItemScreening = {
  posicao: number;
  ticker: string;
  nome: string | null;
  setor: string | null;
  besst: boolean;
  preco: number;
  data_preco: string;
  dy: number | null;
  p_l: number | null;
  p_vp: number | null;
  roe: number | null;
  margem_liquida: number | null;
  dl_ebitda: number | null;
  liquidez: number | null;
  valor_mercado: number | null;
  graham_valor: number | null;
  graham_margem: number | null;
  bazin_teto: number | null;
  bazin_margem: number | null;
  lynch_valor: number | null;
  lynch_margem: number | null;
  lynch_peg: number | null;
  lynch_aviso: string | null;
  earnings_yield: number | null;
  retorno_capital: number | null;
  greenblatt_posicao: number | null;
};

export type RespostaScreening = {
  aviso: string;
  ordenar_por: Metodo;
  atualizado_em: string | null;
  total_avaliados: number;
  sem_cotacao: number;
  setores: string[];
  itens: ItemScreening[];
};

/** Filtros de faixa. `escala` converte o que o usuário digita (ex.: 6 %) para a unidade da API (0,06). */
export const FAIXAS = [
  { id: "dy", titulo: "Dividend yield", sufixo: "%", escala: 0.01 },
  { id: "p_l", titulo: "P/L", sufixo: "x", escala: 1 },
  { id: "p_vp", titulo: "P/VP", sufixo: "x", escala: 1 },
  { id: "roe", titulo: "ROE", sufixo: "%", escala: 0.01 },
  { id: "margem_liquida", titulo: "Margem líquida", sufixo: "%", escala: 0.01 },
  { id: "dl_ebitda", titulo: "Dív. líquida/EBITDA", sufixo: "x", escala: 1 },
  { id: "liquidez", titulo: "Liquidez diária", sufixo: "R$ mi", escala: 1_000_000 },
] as const;

export type IdFaixa = (typeof FAIXAS)[number]["id"];
export type Faixa = { min: string; max: string };

export type EstadoFiltros = {
  faixas: Record<IdFaixa, Faixa>;
  setores: string[];
  besst: boolean;
  favoritos: boolean;
  ordenarPor: Metodo;
  yieldBazin: number; // %
  fatorGraham: number;
  fatorLynch: number;
};

const vazia = (): Faixa => ({ min: "", max: "" });

export function filtrosPadrao(): EstadoFiltros {
  const faixas = Object.fromEntries(FAIXAS.map((f) => [f.id, vazia()])) as Record<IdFaixa, Faixa>;
  faixas.liquidez = { min: "1", max: "" };
  return { faixas, setores: [], besst: false, favoritos: false, ordenarPor: "graham", yieldBazin: 6, fatorGraham: 22.5,
    fatorLynch: 1 };
}

/** Número digitado ("6,5", "1.234,5" ou "6.5") → número; vazio ou inválido → null. */
export function lerNumero(texto: string): number | null {
  const t = texto.trim();
  const limpo = t.includes(",") ? t.replace(/\./g, "").replace(",", ".") : t;
  if (limpo === "") return null;
  const n = Number(limpo);
  return Number.isFinite(n) ? n : null;
}

export function paraConsulta(e: EstadoFiltros): URLSearchParams {
  const q = new URLSearchParams({
    ordenar_por: e.ordenarPor,
    yield_bazin: String(e.yieldBazin / 100),
    fator_graham: String(e.fatorGraham),
    fator_lynch: String(e.fatorLynch),
  });
  for (const f of FAIXAS) {
    for (const lado of ["min", "max"] as const) {
      const n = lerNumero(e.faixas[f.id][lado]);
      if (n !== null) q.set(`${f.id}_${lado}`, String(Number((n * f.escala).toPrecision(12))));
    }
  }
  for (const s of e.setores) q.append("setores", s);
  if (e.besst) q.set("besst", "true");
  if (e.favoritos) q.set("somente_favoritos", "true");
  return q;
}

export type Unidade = "R$/ação" | "%" | "x" | "R$" | "un" | "texto";

export const COLUNAS: { id: keyof ItemScreening; titulo: string; unidade: Unidade; metodo?: Metodo; padrao: boolean }[] = [
  { id: "preco", titulo: "Cotação", unidade: "R$/ação", padrao: true },
  { id: "setor", titulo: "Setor", unidade: "texto", padrao: false },
  { id: "dy", titulo: "DY 12m", unidade: "%", padrao: true },
  { id: "p_l", titulo: "P/L", unidade: "x", padrao: true },
  { id: "p_vp", titulo: "P/VP", unidade: "x", padrao: true },
  { id: "roe", titulo: "ROE", unidade: "%", padrao: true },
  { id: "margem_liquida", titulo: "Margem líq.", unidade: "%", padrao: false },
  { id: "dl_ebitda", titulo: "DL/EBITDA", unidade: "x", padrao: true },
  { id: "liquidez", titulo: "Liquidez", unidade: "R$", padrao: true },
  { id: "valor_mercado", titulo: "Valor de mercado", unidade: "R$", padrao: false },
  { id: "graham_valor", titulo: "Valor Graham", unidade: "R$/ação", metodo: "graham", padrao: true },
  { id: "graham_margem", titulo: "Margem Graham", unidade: "%", metodo: "graham", padrao: true },
  { id: "bazin_teto", titulo: "Teto Bazin", unidade: "R$/ação", metodo: "bazin", padrao: true },
  { id: "bazin_margem", titulo: "Margem Bazin", unidade: "%", metodo: "bazin", padrao: true },
  { id: "lynch_valor", titulo: "Preço justo Lynch", unidade: "R$/ação", metodo: "lynch", padrao: false },
  { id: "lynch_margem", titulo: "Margem Lynch", unidade: "%", metodo: "lynch", padrao: true },
  { id: "lynch_peg", titulo: "PEG", unidade: "x", metodo: "lynch", padrao: false },
  { id: "earnings_yield", titulo: "Earnings yield", unidade: "%", metodo: "greenblatt", padrao: false },
  { id: "retorno_capital", titulo: "Retorno s/ capital", unidade: "%", metodo: "greenblatt", padrao: false },
  { id: "greenblatt_posicao", titulo: "Pos. Fórmula Mágica", unidade: "un", metodo: "greenblatt", padrao: true },
];

export const METODOS: { id: Metodo; nome: string; livro: string; metodologia: string }[] = [
  { id: "graham", nome: "Graham", livro: "Benjamin Graham", metodologia: "graham.valor_intrinseco" },
  { id: "bazin", nome: "Bazin", livro: "Décio Bazin", metodologia: "bazin.preco_teto" },
  { id: "lynch", nome: "Peter Lynch", livro: "Peter Lynch", metodologia: "lynch.preco_justo" },
  { id: "greenblatt", nome: "Fórmula Mágica", livro: "Joel Greenblatt", metodologia: "greenblatt.ranking" },
];

export type Ordem = { coluna: keyof ItemScreening; crescente: boolean } | null;

/** Ordena uma cópia; valores ausentes vão sempre para o fim. Sem ordem, mantém a posição do ranking. */
export function ordenar(itens: ItemScreening[], ordem: Ordem): ItemScreening[] {
  if (!ordem) return [...itens].sort((a, b) => a.posicao - b.posicao);
  const { coluna, crescente } = ordem;
  return [...itens].sort((a, b) => {
    const va = a[coluna];
    const vb = b[coluna];
    if (va === null || va === undefined) return vb === null || vb === undefined ? 0 : 1;
    if (vb === null || vb === undefined) return -1;
    const c = typeof va === "string" ? va.localeCompare(String(vb), "pt-BR") : Number(va) - Number(vb);
    return crescente ? c : -c;
  });
}

export function buscar(itens: ItemScreening[], texto: string): ItemScreening[] {
  const t = texto.trim().toLowerCase();
  if (!t) return itens;
  return itens.filter((i) => i.ticker.toLowerCase().includes(t) || (i.nome ?? "").toLowerCase().includes(t));
}

// Preferências guardadas no navegador (podem falhar em janela anônima: tudo funciona sem elas).
export function lerLocal<T>(chave: string, padrao: T): T {
  try {
    const texto = window.localStorage.getItem(chave);
    return texto ? (JSON.parse(texto) as T) : padrao;
  } catch {
    return padrao;
  }
}

export function gravarLocal(chave: string, valor: unknown): void {
  try {
    window.localStorage.setItem(chave, JSON.stringify(valor));
  } catch {
    /* sem armazenamento disponível */
  }
}
