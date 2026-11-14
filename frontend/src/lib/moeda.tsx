"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { formatarData, formatarMoeda, formatarValor, simbolo } from "@/lib/formato";

type Cambio = { valor: number; data: string } | null;
type Estado = { moeda: string; emReais: boolean; cambio: Cambio; alternar: () => void };

/** Moeda da página (BRL na B3, USD nos EUA): os componentes formatam valores sem precisar recebê-la.
 * Nos ativos dos EUA, o usuário pode ver os valores em R$ pelo dólar comercial de venda (PTAX, Banco Central). */
const Contexto = createContext<Estado>({ moeda: "BRL", emReais: false, cambio: null, alternar: () => {} });
const CHAVE = "converter-usd-brl";
const MONETARIAS = new Set(["R$", "R$/ação"]);

export function MoedaProvider({ moeda, children }: { moeda: string; children: React.ReactNode }) {
  const [emReais, setEmReais] = useState(false);
  const [cambio, setCambio] = useState<Cambio>(null);

  useEffect(() => {
    if (moeda !== "USD") return;
    try {
      setEmReais(localStorage.getItem(CHAVE) === "1");
    } catch {
      /* sem armazenamento local: começa em US$ */
    }
    const desde = new Date(Date.now() - 20 * 864e5).toISOString().slice(0, 10);
    fetch(`/api/series/DOLAR_VENDA?desde=${desde}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => {
        const ultimo = s?.pontos?.at(-1);
        if (ultimo) setCambio({ valor: Number(ultimo.valor), data: ultimo.data });
      })
      .catch(() => setCambio(null));
  }, [moeda]);

  const alternar = () => {
    setEmReais((atual) => {
      try {
        localStorage.setItem(CHAVE, atual ? "0" : "1");
      } catch {
        /* preferência só nesta visita */
      }
      return !atual;
    });
  };
  return <Contexto.Provider value={{ moeda, emReais, cambio, alternar }}>{children}</Contexto.Provider>;
}

export function useMoeda() {
  const { moeda, emReais, cambio } = useContext(Contexto);
  const converter = moeda === "USD" && emReais && cambio !== null;
  const exibida = converter ? "BRL" : moeda;
  const taxa = converter ? cambio.valor : 1;
  return {
    moeda: exibida,
    simbolo: simbolo(exibida),
    fv: (valor: number | null, unidade: string) =>
      formatarValor(valor !== null && MONETARIAS.has(unidade) ? valor * taxa : valor, unidade, exibida),
    fm: (valor: number) => formatarMoeda(valor * taxa, exibida),
  };
}

/** Botão "ver em R$" dos ativos dos EUA, com o câmbio usado e a data. */
export function SeletorMoeda() {
  const { moeda, emReais, cambio, alternar } = useContext(Contexto);
  if (moeda !== "USD") return null;
  return (
    <div className="flex items-center gap-2 text-xs">
      <button type="button" onClick={alternar} disabled={!cambio} className="pilula" aria-pressed={emReais}>
        {emReais ? "Ver em US$" : "Ver em R$"}
      </button>
      {cambio && (
        <span className="suave">
          US$ 1 = R$ {cambio.valor.toLocaleString("pt-BR", { minimumFractionDigits: 4 })} (PTAX venda,{" "}
          {formatarData(cambio.data)})
        </span>
      )}
    </div>
  );
}

/** Valor formatado na moeda da página (acompanha o "ver em R$"). */
export function ValorMoeda({ valor, unidade }: { valor: number | null; unidade: string }) {
  const { fv } = useMoeda();
  return <>{fv(valor, unidade)}</>;
}
