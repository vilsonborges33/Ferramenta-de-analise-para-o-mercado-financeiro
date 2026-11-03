"use client";

import { FAIXAS, type EstadoFiltros, type IdFaixa, type Metodo } from "@/lib/screening";

type Props = {
  estado: EstadoFiltros;
  setores: string[];
  aoMudar: (e: EstadoFiltros) => void;
};

const PARAMETROS: { metodo: Metodo; rotulo: string; chave: "yieldBazin" | "fatorGraham" | "fatorLynch";
  min: number; max: number; passo: number; dica: string }[] = [
  { metodo: "bazin", rotulo: "Yield mínimo de Bazin (%)", chave: "yieldBazin", min: 1, max: 30, passo: 0.5,
    dica: "Preço teto = dividendos de 12 meses ÷ este yield." },
  { metodo: "graham", rotulo: "Fator de Graham", chave: "fatorGraham", min: 1, max: 100, passo: 0.5,
    dica: "22,5 = P/L 15 × P/VP 1,5 (original)." },
  { metodo: "lynch", rotulo: "Multiplicador de Lynch", chave: "fatorLynch", min: 0.1, max: 5, passo: 0.1,
    dica: "P/L justo = multiplicador × crescimento do lucro (1 = PEG 1)." },
];

export function FiltrosScreening({ estado, setores, aoMudar }: Props) {
  const faixa = (id: IdFaixa, lado: "min" | "max", valor: string) =>
    aoMudar({ ...estado, faixas: { ...estado.faixas, [id]: { ...estado.faixas[id], [lado]: valor } } });
  const alternarSetor = (setor: string) =>
    aoMudar({
      ...estado,
      setores: estado.setores.includes(setor) ? estado.setores.filter((s) => s !== setor) : [...estado.setores, setor],
    });

  return (
    <div className="grid gap-x-8 gap-y-4 text-sm md:grid-cols-2">
      <fieldset className="space-y-2">
        <legend className="mb-1 font-medium">Faixas (deixe em branco para não filtrar)</legend>
        {FAIXAS.map((f) => (
          <div key={f.id} className="grid grid-cols-[1fr_auto_auto] items-center gap-2">
            <span>
              {f.titulo} <span className="suave text-xs">({f.sufixo})</span>
            </span>
            <input aria-label={`${f.titulo} mínimo`} inputMode="decimal" placeholder="mín." className="campo w-20 text-right"
              value={estado.faixas[f.id].min} onChange={(e) => faixa(f.id, "min", e.target.value)} />
            <input aria-label={`${f.titulo} máximo`} inputMode="decimal" placeholder="máx." className="campo w-20 text-right"
              value={estado.faixas[f.id].max} onChange={(e) => faixa(f.id, "max", e.target.value)} />
          </div>
        ))}
      </fieldset>

      <div className="space-y-4">
        <fieldset className="space-y-2">
          <legend className="mb-1 font-medium">Parâmetros dos métodos</legend>
          {PARAMETROS.map((p) => (
            <label key={p.chave} className={`metodo-${p.metodo} fundo-metodo flex items-center justify-between gap-2 rounded-lg px-3 py-2`}>
              <span>
                <span className="texto-metodo font-medium">{p.rotulo}</span>
                <span className="suave block text-xs">{p.dica}</span>
              </span>
              <input type="number" min={p.min} max={p.max} step={p.passo} className="campo w-20 text-right"
                value={estado[p.chave]} onChange={(e) => aoMudar({ ...estado, [p.chave]: Number(e.target.value) })} />
            </label>
          ))}
        </fieldset>

        <details className="rounded-lg border px-3 py-2">
          <summary className="cursor-pointer">
            Setores {estado.setores.length > 0 ? `(${estado.setores.length} selecionados)` : "(todos)"}
          </summary>
          <div className="mt-2 max-h-56 space-y-1 overflow-y-auto">
            {setores.length === 0 && <p className="suave">Nenhum setor carregado.</p>}
            {setores.map((s) => (
              <label key={s} className="flex items-center gap-2">
                <input type="checkbox" checked={estado.setores.includes(s)} onChange={() => alternarSetor(s)} />
                {s}
              </label>
            ))}
          </div>
          {estado.setores.length > 0 && (
            <button type="button" className="link mt-2 text-xs" onClick={() => aoMudar({ ...estado, setores: [] })}>
              Limpar setores
            </button>
          )}
        </details>
      </div>
    </div>
  );
}
