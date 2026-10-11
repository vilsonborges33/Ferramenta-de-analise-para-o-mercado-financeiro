import { buscar } from "@/lib/api";
import { formatarData, nomeFonte } from "@/lib/formato";

export const dynamic = "force-dynamic";

type Status = {
  fontes: { fonte: string; nome: string; status: string; quando: string | null; linhas: number; mensagem: string | null; ultimo_sucesso: string | null }[];
  contagens: Record<string, number | string | null>;
};

const ROTULOS: [string, string][] = [
  ["empresas", "Empresas no cadastro da CVM"],
  ["acoes", "Ações (tickers)"],
  ["acoes_com_cotacao", "Ações com cotação"],
  ["ultima_cotacao", "Data da cotação mais recente"],
  ["empresas_com_balanco", "Empresas com balanço organizado"],
  ["fiis", "Fundos imobiliários"],
  ["fiis_com_ticker", "Fundos ligados a um ticker"],
  ["indicadores_disponiveis", "Indicadores calculados"],
];

const COR: Record<string, string> = { concluido: "var(--destaque)", erro: "var(--alerta)" };
const TEXTO: Record<string, string> = {
  concluido: "ok", erro: "erro", sem_arquivo: "arquivo ainda não publicado", em_andamento: "em andamento",
};

export default async function StatusDados() {
  const s = await buscar<Status>("/status");
  if (!s) return <p>Status indisponível.</p>;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Status dos dados</h1>
        <p className="suave text-sm">O que já foi carregado de cada fonte e se a última atualização deu certo.</p>
      </div>
      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {ROTULOS.map(([chave, rotulo]) => (
          <div key={chave} className="cartao p-3">
            <div className="text-xs suave">{rotulo}</div>
            <div className="mt-1 text-lg font-medium">
              {chave === "ultima_cotacao"
                ? formatarData(s.contagens[chave] as string | null)
                : Number(s.contagens[chave] ?? 0).toLocaleString("pt-BR")}
            </div>
          </div>
        ))}
      </section>
      <section className="cartao overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="suave">
            <tr className="text-left">
              <th className="px-3 py-2">Fonte</th>
              <th className="px-3 py-2">Última execução</th>
              <th className="px-3 py-2">Situação</th>
              <th className="px-3 py-2 text-right">Linhas</th>
              <th className="px-3 py-2">Último sucesso</th>
              <th className="px-3 py-2">Mensagem</th>
            </tr>
          </thead>
          <tbody>
            {s.fontes.map((f) => (
              <tr key={f.fonte} className="border-t align-top">
                <td className="px-3 py-2 whitespace-nowrap">{nomeFonte(f.fonte)}</td>
                <td className="px-3 py-2 whitespace-nowrap">{formatarData(f.quando)}</td>
                <td className="px-3 py-2 whitespace-nowrap" style={{ color: COR[f.status] }}>
                  {TEXTO[f.status] ?? f.status}
                </td>
                <td className="px-3 py-2 text-right">{f.linhas.toLocaleString("pt-BR")}</td>
                <td className="px-3 py-2 whitespace-nowrap">{formatarData(f.ultimo_sucesso)}</td>
                <td className="px-3 py-2 text-xs suave max-w-80 break-words">{f.mensagem}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
