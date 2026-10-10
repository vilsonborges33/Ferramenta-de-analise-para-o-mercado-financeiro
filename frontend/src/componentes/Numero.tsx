"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { formatarData, formatarValor, nomeFonte } from "@/lib/formato";
import type { Numero as TNumero } from "@/lib/tipos";

/** Valor formatado + ícone ⓘ que abre fórmula, motivo de indisponibilidade e procedência dos insumos. */
export function Numero({ numero, compacto = false }: { numero: TNumero; compacto?: boolean }) {
  const [aberto, setAberto] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!aberto) return;
    const fechar = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setAberto(false);
    };
    document.addEventListener("mousedown", fechar);
    return () => document.removeEventListener("mousedown", fechar);
  }, [aberto]);

  const indisponivel = numero.valor === null;
  const fontes = Array.from(
    new Map(numero.procedencia.map((p) => [`${p.fonte}|${p.insumo}`, p])).values(),
  );

  return (
    <span ref={ref} className="relative inline-flex items-center gap-1">
      <span className={indisponivel ? "suave" : ""} title={indisponivel ? numero.motivo_indisponivel ?? "" : undefined}>
        {indisponivel ? (compacto ? "—" : "dado indisponível") : formatarValor(numero.valor, numero.unidade)}
      </span>
      {numero.aviso && !indisponivel && (
        <span title={numero.aviso} style={{ color: "var(--alerta)" }} aria-label={numero.aviso}>
          !
        </span>
      )}
      <button
        type="button"
        onClick={() => setAberto((a) => !a)}
        className="suave text-xs leading-none hover:opacity-80"
        aria-label={`Procedência de ${numero.nome}`}
        aria-expanded={aberto}
      >
        ⓘ
      </button>
      {aberto && (
        <span
          role="dialog"
          className="cartao fixed inset-x-4 bottom-4 z-20 block p-3 text-left text-xs font-normal shadow-lg sm:absolute sm:inset-x-auto sm:bottom-auto sm:right-0 sm:top-6 sm:w-72"
        >
          <span className="block font-semibold">{numero.nome}</span>
          {indisponivel && (
            <span className="mt-1 block" style={{ color: "var(--alerta)" }}>
              {numero.motivo_indisponivel}
            </span>
          )}
          {numero.aviso && <span className="mt-1 block" style={{ color: "var(--alerta)" }}>{numero.aviso}</span>}
          {fontes.length > 0 && (
            <span className="mt-2 block space-y-1">
              {fontes.map((p, i) => (
                <span key={i} className="block">
                  <span className="font-medium">{p.insumo.replaceAll("_", " ")}</span>: {nomeFonte(p.fonte)}, ref.{" "}
                  {formatarData(p.data_referencia)}
                  {p.periodo ? ` (${p.periodo}${p.tipo_periodo === "ttm" ? ", 12 meses" : ""})` : ""}
                  <span className="suave block">coletado em {formatarData(p.coletado_em)}</span>
                </span>
              ))}
            </span>
          )}
          <Link href={`/metodologia/${numero.metrica}`} className="link mt-2 block">
            Como é calculado →
          </Link>
        </span>
      )}
    </span>
  );
}
