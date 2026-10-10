export type Procedencia = {
  insumo: string;
  valor: number | null;
  fonte: string;
  data_referencia: string;
  coletado_em: string;
  periodo?: string;
  tipo_periodo?: string;
  contas?: { conta: string; descricao: string; documento: string; data_fim: string }[];
  [chave: string]: unknown;
};

export type Numero = {
  metrica: string;
  nome: string;
  unidade: "x" | "%" | "R$" | "R$/ação" | "un";
  valor: number | null;
  motivo_indisponivel: string | null;
  aviso: string | null;
  data_referencia: string | null;
  procedencia: Procedencia[];
};

export type Cotacao = { valor: number; data: string; fonte: string; coletado_em: string } | null;

export type ItemLista = {
  ticker: string;
  nome: string | null;
  setor: string | null;
  cotacao: Cotacao;
  indicadores: Record<string, Numero>;
};

export type Detalhe = {
  ticker: string;
  classe: string;
  nome?: string;
  cnpj?: string;
  setor?: string;
  segmento?: string;
  segmento_listagem?: string;
  mandato?: string;
  tipo_gestao?: string;
  administrador?: string;
  outros_tickers?: string[];
  tipo_plano_contas?: string;
  cotacao: Cotacao;
  grupos: Record<string, Numero[]>;
};

export type Metrica = {
  id: string;
  nome: string;
  grupo: string;
  unidade: string;
  formula: string;
  referencia: string;
  aplica_a: string[];
  limitacoes: string[];
  parametros: { chave: string; descricao: string; padrao: number; minimo: number; maximo: number }[];
};
