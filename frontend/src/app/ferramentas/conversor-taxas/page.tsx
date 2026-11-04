"use client";

import { useState } from "react";
import { Cabecalho, CampoNumero, Kpi, pctf, useApi } from "@/componentes/Ferramenta";

const PERIODOS: [string, string][] = [
  ["dia_util", "ao dia útil (252/ano)"], ["dia_corrido", "ao dia corrido (365/ano)"], ["mes", "ao mês"],
  ["trimestre", "ao trimestre"], ["semestre", "ao semestre"], ["ano", "ao ano"],
];

type Resposta = { valor: number | null; motivo_indisponivel: string | null; todas: Record<string, number>; real_anual?: number | null };

export default function ConversorTaxas() {
  const [taxa, setTaxa] = useState(1);
  const [origem, setOrigem] = useState("mes");
  const [destino, setDestino] = useState("ano");
  const [inflacao, setInflacao] = useState(4.5);
  const { dados, erro } = useApi<Resposta>(
    `/ferramentas/taxa-equivalente?taxa=${taxa / 100}&origem=${origem}&destino=${destino}&inflacao=${inflacao / 100}`);
  const nome = (p: string) => PERIODOS.find(([v]) => v === p)?.[1] ?? p;
  return (
    <div className="space-y-5">
      <Cabecalho trilha="Ferramentas" titulo="Conversor de taxas equivalentes" icone="conversor"
        subtitulo="Converte uma taxa entre períodos por capitalização composta e calcula a taxa real (Fisher)." />
      <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
        <div className="cartao space-y-4 p-5">
          <CampoNumero rotulo="Taxa de entrada" sufixo="%" valor={taxa} aoMudar={setTaxa}
            unidade={{ valor: origem, aoMudar: setOrigem, opcoes: PERIODOS }} />
          <label className="block">
            <span className="rotulo">Converter para</span>
            <select value={destino} onChange={(e) => setDestino(e.target.value)} className="campo mt-1 w-full py-1.5">
              {PERIODOS.map(([v, r]) => <option key={v} value={v}>{r}</option>)}
            </select>
          </label>
          <CampoNumero rotulo="Inflação esperada" sufixo="% ao ano" valor={inflacao} aoMudar={setInflacao}
            dica="Para a taxa real: (1 + nominal) ÷ (1 + inflação) − 1." />
          <p className="text-xs suave">(1 + i<sub>destino</sub>) = (1 + i<sub>origem</sub>)<sup>n<sub>origem</sub> ÷ n<sub>destino</sub></sup>,
            com n = períodos por ano.</p>
        </div>
        <div className="space-y-4">
          {(erro || dados?.motivo_indisponivel) && <p className="cartao p-3 text-sm negativo">{erro ?? dados?.motivo_indisponivel}</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            <Kpi rotulo={`Taxa ${nome(destino)}`} valor={pctf(dados?.valor, 4)} cor="var(--destaque)"
              detalhe={`${pctf(taxa / 100, 4)} ${nome(origem)}`} />
            <Kpi rotulo="Taxa real ao ano" valor={pctf(dados?.real_anual, 2)} detalhe={`descontada inflação de ${pctf(inflacao / 100)}`} />
          </div>
          <div className="cartao overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="border-b"><th className="px-4 py-2 text-left">Período</th><th className="px-4 py-2 text-right">Taxa equivalente</th></tr></thead>
              <tbody>
                {PERIODOS.map(([p, r]) => (
                  <tr key={p} className="border-b last:border-0" style={p === destino ? { background: "color-mix(in srgb, var(--destaque) 8%, transparent)" } : undefined}>
                    <td className="px-4 py-2">{r}</td>
                    <td className="mono px-4 py-2 text-right">{pctf(dados?.todas?.[p], 6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
