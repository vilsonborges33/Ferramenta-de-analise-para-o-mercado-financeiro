const casas = (min: number, max: number) =>
  new Intl.NumberFormat("pt-BR", { minimumFractionDigits: min, maximumFractionDigits: max });

const NOMES_FONTES: Record<string, string> = {
  CVM_DFP: "CVM — DFP",
  CVM_ITR: "CVM — ITR",
  CVM_CADASTRO: "CVM — Cadastro",
  CVM_FCA: "CVM — FCA",
  CVM_FII_MENSAL: "CVM — Informe mensal de FII",
  B3_COTAHIST: "B3 — COTAHIST",
  BRAPI: "brapi.dev",
  YAHOO_FINANCE: "Yahoo Finance",
  B3_PROVENTOS: "B3 — Proventos",
  FNET_RENDIMENTOS: "B3 FNET — Rendimentos de FII",
  BCB_SGS: "Banco Central — SGS",
  TESOURO_TD: "Tesouro Transparente",
};

export function nomeFonte(codigo: string): string {
  return NOMES_FONTES[codigo] ?? codigo;
}

/** Valor monetário abreviado: R$ 1,23 bi / R$ 456,7 mi / R$ 12,3 mil. */
export function formatarMoeda(valor: number, moeda = "R$"): string {
  const abs = Math.abs(valor);
  const sinal = valor < 0 ? "-" : "";
  if (abs >= 1e9) return `${sinal}${moeda} ${casas(2, 2).format(abs / 1e9)} bi`;
  if (abs >= 1e6) return `${sinal}${moeda} ${casas(2, 2).format(abs / 1e6)} mi`;
  if (abs >= 1e4) return `${sinal}${moeda} ${casas(1, 1).format(abs / 1e3)} mil`;
  return `${sinal}${moeda} ${casas(2, 2).format(abs)}`;
}

export function formatarValor(valor: number | null, unidade: string): string {
  if (valor === null || Number.isNaN(valor)) return "—";
  switch (unidade) {
    case "%":
      return `${casas(2, 2).format(valor * 100)}%`;
    case "x":
      return casas(2, 2).format(valor);
    case "R$":
      return formatarMoeda(valor);
    case "R$/ação":
      return `R$ ${casas(2, 2).format(valor)}`;
    case "un":
      return casas(0, 0).format(valor);
    default:
      return casas(2, 2).format(valor);
  }
}

/** '2024-12-31' → '31/12/2024'; ISO com hora → '31/12/2024 18:30'. */
export function formatarData(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [data, hora] = iso.split("T");
  const [a, m, d] = data.split("-");
  const base = `${d}/${m}/${a}`;
  if (!hora) return base;
  const instante = new Date(iso);
  return `${base} ${instante.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: "America/Sao_Paulo" })}`;
}
