"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Grafico, porcento, reaisCurto } from "@/componentes/Grafico";
import { formatarData, formatarMoeda, formatarValor } from "@/lib/formato";

type Grupo = { grupo: string; valor: number; percentual: number };
type Fundo = {
  ligado_ao_informe: boolean;
  tipo: string | null;
  competencia: string | null;
  composicao: { grupos: Grupo[]; cobertura: number | null; motivo_indisponivel: string | null };
  endividamento: { ativo_total: number | null; passivo_total: number | null; alavancagem: number | null;
    obrigacoes: { grupo: string; valor: number }[] };
  imoveis: { nome: string; classe: string | null; endereco: string | null; area_m2: number | null; vacancia: number | null;
    inadimplencia: number | null; receitas: number | null }[];
  competencia_imoveis: string | null;
  historico: { competencia: string; patrimonio_liquido: number | null; vp_cota: number | null; cotistas: number | null;
    dy_mes: number | null }[];
  retornos_mensais: { mes: string; retorno: number }[];
  estatistica_retornos: { valor: number | null; motivo_indisponivel: string | null; positivos?: number; negativos?: number;
    meses?: number; maior?: number; menor?: number };
};
type Gordon = { preco: number | null; dividendo_12m: number | null; taxa_base: number | null; descricao_taxa: string | null;
  taxa_exigida: number | null; preco_teto: number | null; motivo_indisponivel: string | null;
  margem_seguranca: number | null; aviso: string };
type Documentos = { documentos: { id: number; categoria: string; tipo: string; referencia: string; entrega: string;
  url: string }[]; erro: string | null; busca: string };

const CORES = ["#2463b8", "#a86400", "#7a3fc4", "#c2410c", "#0f6b5c", "#6b7280", "#b42318", "#4fc3a9"];

function Secao({ id, titulo, children }: { id: string; titulo: string; children: React.ReactNode }) {
  return (
    <section id={id} className="cartao scroll-mt-16 space-y-3 p-4">
      <h2 className="font-semibold">{titulo}</h2>
      {children}
    </section>
  );
}

/** Preço teto do FII pelo Gordon ajustado (Damodaran), com taxa base do Tesouro e prêmio ajustáveis. */
export function PainelGordonFii({ ticker }: { ticker: string }) {
  const [base, setBase] = useState("prefixado");
  const [premio, setPremio] = useState(2);
  const [crescimento, setCrescimento] = useState(0);
  const [liquida, setLiquida] = useState(true);
  const [dados, setDados] = useState<Gordon | null>(null);

  useEffect(() => {
    const q = new URLSearchParams({ base, premio: String(premio / 100), crescimento: String(crescimento / 100),
      liquida: String(liquida) });
    const controle = new AbortController();
    const espera = setTimeout(() => {
      fetch(`/api/fiis/${ticker}/gordon?${q}`, { signal: controle.signal }).then((r) => (r.ok ? r.json() : null))
        .then(setDados).catch(() => undefined);
    }, 250);
    return () => {
      clearTimeout(espera);
      controle.abort();
    };
  }, [ticker, base, premio, crescimento, liquida]);

  const passo = (v: number, d: number, set: (n: number) => void) => set(Math.round((v + d) * 10) / 10);
  return (
    <div className="space-y-3">
      {dados && <p className="text-xs" style={{ color: "var(--alerta)" }}>{dados.aviso}</p>}
      <div className="grid gap-4 md:grid-cols-[1fr_1fr]">
        <div className="space-y-2 text-sm">
          <label className="flex items-center justify-between gap-2">
            <span className="suave">Taxa base</span>
            <select className="campo" value={base} onChange={(e) => setBase(e.target.value)}>
              <option value="prefixado">Tesouro Prefixado (mais longo)</option>
              <option value="ipca">Tesouro IPCA+ (juro real)</option>
              <option value="selic">Selic meta</option>
            </select>
          </label>
          {([["Prêmio sobre a taxa", premio, setPremio], ["Crescimento dos rendimentos", crescimento, setCrescimento]] as const).map(
            ([rotulo, valor, set]) => (
              <div key={rotulo} className="flex items-center justify-between gap-2">
                <span className="suave">{rotulo}</span>
                <span className="flex items-center gap-1">
                  <button type="button" className="pilula px-2 py-0" aria-label={`Diminuir ${rotulo}`} onClick={() => passo(valor, -0.5, set)}>–</button>
                  <span className="w-14 text-center font-medium">{valor.toLocaleString("pt-BR")}%</span>
                  <button type="button" className="pilula px-2 py-0" aria-label={`Aumentar ${rotulo}`} onClick={() => passo(valor, 0.5, set)}>+</button>
                </span>
              </div>
            ))}
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={liquida} onChange={(e) => setLiquida(e.target.checked)} />
            Descontar 15% de IR da taxa do Tesouro (rendimentos de FII são isentos para pessoa física)
          </label>
          <p className="suave text-xs">Taxa usada: {dados?.descricao_taxa ?? "—"} ({formatarValor(dados?.taxa_base ?? null, "%")})</p>
        </div>
        <div className="metodo-bazin fundo-metodo space-y-1 rounded-lg p-4">
          <div className="texto-metodo font-semibold">Gordon ajustado</div>
          <div className="suave text-xs">Preço teto</div>
          <div className="text-2xl font-semibold">{formatarValor(dados?.preco_teto ?? null, "R$/ação")}</div>
          {dados?.motivo_indisponivel && <p className="text-xs" style={{ color: "var(--alerta)" }}>{dados.motivo_indisponivel}</p>}
          <div className="text-sm">
            <span className="suave">Margem de segurança: </span>
            <span style={{ color: (dados?.margem_seguranca ?? 0) >= 0 ? "var(--destaque)" : "var(--negativo)" }}>
              {formatarValor(dados?.margem_seguranca ?? null, "%")}
            </span>
          </div>
          <div className="flex justify-between text-xs"><span className="suave">Rendimentos 12 meses</span><span>{formatarValor(dados?.dividendo_12m ?? null, "R$/ação")}</span></div>
          <div className="flex justify-between text-xs"><span className="suave">Taxa exigida</span><span>{formatarValor(dados?.taxa_exigida ?? null, "%")}</span></div>
          <Link href="/metodologia/fii.gordon_ajustado" className="link text-xs">Como é calculado</Link>
        </div>
      </div>
    </div>
  );
}

function Documentos({ ticker }: { ticker: string }) {
  const [dados, setDados] = useState<Documentos | null>(null);
  const [aberto, setAberto] = useState(false);
  useEffect(() => {
    if (!aberto || dados) return;
    fetch(`/api/fiis/${ticker}/documentos`).then((r) => (r.ok ? r.json() : null)).then(setDados).catch(() => undefined);
  }, [aberto, dados, ticker]);
  if (!aberto)
    return <button type="button" className="pilula text-sm" onClick={() => setAberto(true)}>Carregar documentos do FNET</button>;
  if (!dados) return <p className="suave text-sm">Consultando o FNET…</p>;
  return (
    <div className="space-y-2 text-sm">
      {dados.erro && <p style={{ color: "var(--alerta)" }}>{dados.erro}. <a className="link" href={dados.busca} target="_blank" rel="noreferrer">Abrir o FNET</a></p>}
      {dados.documentos.length > 0 && (
        <div className="max-h-96 overflow-auto">
          <table className="w-full">
            <thead className="suave"><tr><th className="py-1 text-left">Documento</th><th className="text-left">Referência</th><th className="text-left">Entrega</th></tr></thead>
            <tbody>
              {dados.documentos.map((d) => (
                <tr key={d.id} className="border-t">
                  <td className="py-1"><a className="link" href={d.url} target="_blank" rel="noreferrer">{d.tipo || d.categoria}</a>
                    <span className="suave block text-xs">{d.categoria}</span></td>
                  <td>{d.referencia}</td><td>{d.entrega}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="suave text-xs">Fonte: B3 — FNET (consulta pública). Os documentos abrem no site do FNET.</p>
    </div>
  );
}

/** Seções específicas da página de um FII: composição, endividamento, imóveis, histórico e documentos. */
export function SecoesFundo({ ticker }: { ticker: string }) {
  const [fundo, setFundo] = useState<Fundo | null>(null);
  useEffect(() => {
    fetch(`/api/fiis/${ticker}/fundo`).then((r) => (r.ok ? r.json() : null)).then(setFundo).catch(() => undefined);
  }, [ticker]);

  const pizza = useMemo(() => ({
    tooltip: { trigger: "item", valueFormatter: (v: unknown) => formatarMoeda(Number(v)) },
    legend: { bottom: 0, type: "scroll" },
    series: [{ type: "pie", radius: ["45%", "70%"], top: -20, label: { show: false },
      data: (fundo?.composicao.grupos ?? []).map((g, i) => ({ name: g.grupo, value: g.valor, itemStyle: { color: CORES[i % CORES.length] } })) }],
  }), [fundo]);
  const historico = useMemo(() => {
    const h = fundo?.historico ?? [];
    return {
      grid: { left: 56, right: 52, top: 28, bottom: 28 }, legend: { top: 0 }, tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: h.map((x) => x.competencia.slice(0, 7).split("-").reverse().join("/")) },
      yAxis: [{ type: "value", scale: true, axisLabel: { formatter: (v: number) => `R$ ${v.toLocaleString("pt-BR")}` } },
        { type: "value", axisLabel: { formatter: porcento }, splitLine: { show: false } }],
      series: [
        { name: "Valor patrimonial por cota", type: "line", data: h.map((x) => x.vp_cota) },
        { name: "DY do mês (informado)", type: "bar", yAxisIndex: 1, data: h.map((x) => x.dy_mes),
          tooltip: { valueFormatter: porcento } },
      ],
    };
  }, [fundo]);

  if (!fundo) return <p className="suave text-sm">Carregando dados do fundo…</p>;
  if (!fundo.ligado_ao_informe)
    return <p className="cartao p-3 text-sm suave">Este ticker ainda não está ligado a um informe da CVM (pelo código ISIN).</p>;
  const e = fundo.endividamento;
  const est = fundo.estatistica_retornos;
  return (
    <>
      <Secao id="composicao" titulo={`Composição do ativo${fundo.tipo ? ` — fundo de ${fundo.tipo.toLowerCase()}` : ""}`}>
        {fundo.composicao.grupos.length === 0 ? (
          <p className="suave text-sm">{fundo.composicao.motivo_indisponivel}</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 [&>*]:min-w-0">
            <Grafico opcao={pizza} altura="h-64" rotulo="Composição do ativo" />
            <table className="text-sm">
              <tbody>
                {fundo.composicao.grupos.map((g, i) => (
                  <tr key={g.grupo} className="border-t text-right">
                    <td className="py-1 text-left"><span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ background: CORES[i % CORES.length] }} />{g.grupo}</td>
                    <td>{formatarMoeda(g.valor)}</td><td className="w-20">{formatarValor(g.percentual, "%")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="suave text-xs">
          Informe mensal da CVM de {formatarData(fundo.competencia)}. Tipo: Tijolo, Papel ou Fundo de fundos quando um grupo passa de 60% do ativo; senão Híbrido.
          {fundo.composicao.cobertura !== null && ` Classificado: ${formatarValor(fundo.composicao.cobertura, "%")} do ativo total.`}
        </p>
      </Secao>

      <Secao id="endividamento" titulo="Endividamento">
        <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
          <div><dt className="suave text-xs">Ativo total</dt><dd>{e.ativo_total === null ? "—" : formatarMoeda(e.ativo_total)}</dd></div>
          <div><dt className="suave text-xs">Passivo total</dt><dd>{e.passivo_total === null ? "—" : formatarMoeda(e.passivo_total)}</dd></div>
          <div><dt className="suave text-xs">Alavancagem bruta (passivo ÷ ativo)</dt><dd className="font-medium">{formatarValor(e.alavancagem, "%")}</dd></div>
        </dl>
        {e.obrigacoes.length > 0 && (
          <table className="text-sm">
            <tbody>
              {e.obrigacoes.map((o) => (
                <tr key={o.grupo} className="border-t"><td className="py-1 pr-6">{o.grupo}</td><td className="text-right">{formatarMoeda(o.valor)}</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </Secao>

      <Secao id="imoveis" titulo="Imóveis">
        {fundo.imoveis.length === 0 ? (
          <p className="suave text-sm">Sem imóveis no informe trimestral (fundos de papel e de fundos não têm imóveis).</p>
        ) : (
          <div className="max-h-96 overflow-auto">
            <table className="w-full text-sm">
              <thead className="suave"><tr className="text-right"><th className="py-1 text-left">Imóvel</th><th>Área (m²)</th><th>Vacância</th><th>Inadimplência</th><th>% da receita</th></tr></thead>
              <tbody>
                {fundo.imoveis.map((i, n) => (
                  <tr key={`${i.nome}-${n}`} className="border-t text-right">
                    <td className="py-1 text-left">{i.nome}<span className="suave block text-xs">{i.endereco}</span></td>
                    <td>{i.area_m2 === null ? "—" : i.area_m2.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}</td>
                    <td>{formatarValor(i.vacancia, "%")}</td><td>{formatarValor(i.inadimplencia, "%")}</td><td>{formatarValor(i.receitas, "%")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {fundo.competencia_imoveis && <p className="suave text-xs">Informe trimestral da CVM de {formatarData(fundo.competencia_imoveis)}.</p>}
      </Secao>

      <Secao id="historico" titulo="Histórico mensal">
        {fundo.historico.length > 1 && <Grafico opcao={historico} rotulo="Histórico mensal do fundo" />}
        <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div><dt className="suave text-xs">Meses com cotação em alta</dt><dd>{est.valor === null ? "—" : `${est.positivos} de ${est.meses} (${formatarValor(est.valor, "%")})`}</dd></div>
          <div><dt className="suave text-xs">Meses em queda</dt><dd>{est.negativos ?? "—"}</dd></div>
          <div><dt className="suave text-xs">Melhor mês</dt><dd>{formatarValor(est.maior ?? null, "%")}</dd></div>
          <div><dt className="suave text-xs">Pior mês</dt><dd>{formatarValor(est.menor ?? null, "%")}</dd></div>
        </dl>
        <p className="suave text-xs">Retornos mensais da cotação, sem rendimentos, nos últimos 24 meses. Valor patrimonial e DY mensal informados pelo administrador à CVM.
          {fundo.historico.length > 0 && ` Cotistas no último informe: ${(fundo.historico[fundo.historico.length - 1].cotistas ?? 0).toLocaleString("pt-BR")}.`}</p>
      </Secao>

      <Secao id="documentos" titulo="Documentos e relatórios">
        <Documentos ticker={ticker} />
      </Secao>
    </>
  );
}
