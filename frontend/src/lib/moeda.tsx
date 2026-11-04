"use client";

import { createContext, useContext } from "react";
import { formatarMoeda, formatarValor, simbolo } from "@/lib/formato";

/** Moeda da página (BRL na B3, USD nos EUA): os componentes formatam valores sem precisar recebê-la. */
const Contexto = createContext("BRL");

export function MoedaProvider({ moeda, children }: { moeda: string; children: React.ReactNode }) {
  return <Contexto.Provider value={moeda}>{children}</Contexto.Provider>;
}

export function useMoeda() {
  const moeda = useContext(Contexto);
  return {
    moeda,
    simbolo: simbolo(moeda),
    fv: (valor: number | null, unidade: string) => formatarValor(valor, unidade, moeda),
    fm: (valor: number) => formatarMoeda(valor, moeda),
  };
}
