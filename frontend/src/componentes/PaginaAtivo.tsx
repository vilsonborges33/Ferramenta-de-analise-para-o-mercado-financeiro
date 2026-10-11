import Link from "next/link";
import { GraficoCotacao } from "@/componentes/GraficoCotacao";
import { Numero } from "@/componentes/Numero";
import { formatarData, formatarValor, nomeFonte } from "@/lib/formato";
import type { Detalhe } from "@/lib/tipos";

const METODOS_DE_PRECO = ["Graham", "Bazin", "Lynch", "Greenblatt"];
const ORDEM_GRUPOS = ["Valuation", "Graham", "Bazin", "Lynch", "Greenblatt", "Rentabilidade", "Endividamento",
  "Crescimento", "Mercado", "Base"];

export function PaginaAtivo({ ativo }: { ativo: Detalhe }) {
  const grupos = Object.entries(ativo.grupos).sort(
    ([a], [b]) => ORDEM_GRUPOS.indexOf(a) - ORDEM_GRUPOS.indexOf(b),
  );
  const fichas: [string, string | undefined][] = [
    ["CNPJ", ativo.cnpj],
    ["Setor (CVM)", ativo.setor],
    ["Segmento de listagem", ativo.segmento_listagem],
    ["Segmento", ativo.segmento],
    ["Mandato", ativo.mandato],
    ["Gestão", ativo.tipo_gestao],
    ["Administrador", ativo.administrador],
  ];
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{ativo.ticker}</h1>
          <div className="suave">{ativo.nome}</div>
          {ativo.outros_tickers && ativo.outros_tickers.length > 0 && (
            <div className="mt-1 text-xs suave">
              Outras classes:{" "}
              {ativo.outros_tickers.map((t) => (
                <Link key={t} href={`/acoes/${t}`} className="link mr-2">
                  {t}
                </Link>
              ))}
            </div>
          )}
        </div>
        {ativo.cotacao && (
          <div className="text-right">
            <div className="text-2xl font-semibold">{formatarValor(ativo.cotacao.valor, "R$/ação")}</div>
            <div className="text-xs suave">
              fechamento de {formatarData(ativo.cotacao.data)} · {nomeFonte(ativo.cotacao.fonte)}
            </div>
          </div>
        )}
      </div>

      {ativo.tipo_plano_contas && ativo.tipo_plano_contas !== "geral" && (
        <p className="cartao p-3 text-sm" style={{ color: "var(--alerta)" }}>
          Instituição financeira/seguradora: indicadores baseados em EBIT, dívida e capital de giro não se aplicam.
        </p>
      )}

      <section className="cartao p-4">
        <GraficoCotacao ticker={ativo.ticker} />
      </section>

      {grupos.map(([grupo, numeros]) => (
        <section key={grupo} className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide suave">{grupo}</h2>
          {METODOS_DE_PRECO.includes(grupo) && (
            <p className="text-xs" style={{ color: "var(--alerta)" }}>
              Valor calculado com os parâmetros padrão do método; não constitui recomendação de investimento.
            </p>
          )}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {numeros.map((n) => (
              <div key={n.metrica} className="cartao p-3">
                <div className="text-xs suave">{n.nome}</div>
                <div className="mt-1 text-base font-medium">
                  <Numero numero={n} />
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}

      <section className="cartao p-4 text-sm">
        <h2 className="mb-2 font-semibold">Dados cadastrais</h2>
        <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
          {fichas
            .filter(([, v]) => v)
            .map(([rotulo, valor]) => (
              <div key={rotulo} className="flex justify-between gap-3 border-b py-1" style={{ borderColor: "var(--borda)" }}>
                <dt className="suave">{rotulo}</dt>
                <dd className="text-right">{valor}</dd>
              </div>
            ))}
        </dl>
      </section>
    </div>
  );
}
