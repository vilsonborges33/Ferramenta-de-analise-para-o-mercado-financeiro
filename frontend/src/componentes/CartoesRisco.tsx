"use client";

import { useEffect, useState } from "react";
import { Numero } from "@/componentes/Numero";
import type { Numero as TNumero } from "@/lib/tipos";

type Medida = { valor: number | null; motivo_indisponivel: string | null; metrica: string };

const comoNumero = (m: Medida | undefined, nome: string, unidade: TNumero["unidade"], aviso: string | null): TNumero => ({
  metrica: m?.metrica ?? "", nome, unidade, valor: m?.valor ?? null,
  motivo_indisponivel: m ? m.motivo_indisponivel : "carregando", aviso, data_referencia: null, procedencia: [],
});

/** Volatilidade e Sharpe dos últimos 12 meses (calculados sob demanda a partir das cotações e do CDI). */
export function CartoesRisco({ ticker }: { ticker: string }) {
  const [dados, setDados] = useState<{ volatilidade_12m: Medida; sharpe_12m: Medida; cdi_12m: number | null } | null>(null);

  useEffect(() => {
    fetch(`/api/ativos/${ticker}/risco`).then((r) => (r.ok ? r.json() : null)).then(setDados).catch(() => setDados(null));
  }, [ticker]);

  const cdi = dados?.cdi_12m;
  return (
    <>
      <div className="cartao cartao-kpi p-3">
        <div className="rotulo">Volatilidade 12m</div>
        <div className="mono mt-1.5 text-xl font-semibold">
          <Numero compacto numero={comoNumero(dados?.volatilidade_12m, "Volatilidade (12 m)", "%", null)} />
        </div>
      </div>
      <div className="cartao cartao-kpi p-3">
        <div className="rotulo">Índice de Sharpe 12m</div>
        <div className="mono mt-1.5 text-xl font-semibold">
          <Numero compacto numero={comoNumero(dados?.sharpe_12m, "Índice de Sharpe (12 m)", "x", null)} />
        </div>
        {cdi !== null && cdi !== undefined && (
          <div className="suave text-xs">CDI 12m: {(cdi * 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%</div>
        )}
      </div>
    </>
  );
}
