"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { FiltrosScreening } from "@/componentes/FiltrosScreening";
import { formatarData, formatarValor } from "@/lib/formato";
import {
  COLUNAS,
  METODOS,
  buscar,
  filtrosPadrao,
  gravarLocal,
  lerLocal,
  ordenar,
  paraConsulta,
  type EstadoFiltros,
  type ItemScreening,
  type Ordem,
  type RespostaScreening,
} from "@/lib/screening";

type FiltroSalvo = { nome: string; estado: EstadoFiltros };

const CHAVE_COLUNAS = "screening.colunas";
const CHAVE_SALVOS = "screening.filtros-salvos";
const AVISO =
  "Resultados calculados a partir de dados públicos e dos parâmetros escolhidos. Não constituem recomendação de investimento.";

function celula(item: ItemScreening, id: keyof ItemScreening, unidade: string, moeda: string) {
  const v = item[id];
  if (unidade === "texto") return v ?? "—";
  return formatarValor(typeof v === "number" ? v : null, unidade === "un" ? "un" : unidade, moeda);
}

export default function RankingAcoes() {
  const [estado, setEstado] = useState<EstadoFiltros>(filtrosPadrao);
  const [dados, setDados] = useState<RespostaScreening | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [mostrarFiltros, setMostrarFiltros] = useState(true);
  const [colunas, setColunas] = useState<string[]>(() => COLUNAS.filter((c) => c.padrao).map((c) => c.id));
  const [salvos, setSalvos] = useState<FiltroSalvo[]>([]);
  const [ordem, setOrdem] = useState<Ordem>(null);
  const [texto, setTexto] = useState("");
  const [porPagina, setPorPagina] = useState(20);
  const [pagina, setPagina] = useState(0);
  const [favoritos, setFavoritos] = useState<Set<string> | null>(null); // null = sem login

  // Preferências do navegador (lidas depois de montar, para não divergir da renderização do servidor).
  useEffect(() => {
    setColunas((atual) => lerLocal(CHAVE_COLUNAS, atual));
    setSalvos(lerLocal(CHAVE_SALVOS, []));
    if (window.innerWidth < 640) setMostrarFiltros(false); // no celular, a tabela aparece primeiro
    if (new URLSearchParams(window.location.search).get("mercado") === "EUA")
      setEstado((e) => ({ ...e, mercado: "EUA" }));
    fetch("/api/favoritos")
      .then((r) => (r.ok ? r.json() : null))
      .then((lista: string[] | null) => setFavoritos(lista ? new Set(lista) : null))
      .catch(() => setFavoritos(null));
  }, []);

  const consulta = useMemo(() => paraConsulta(estado).toString(), [estado]);

  useEffect(() => {
    const controle = new AbortController();
    setCarregando(true);
    const espera = setTimeout(async () => {
      try {
        const r = await fetch(`/api/screening/acoes?${consulta}`, { signal: controle.signal });
        if (r.status === 401) throw new Error("Entre na sua conta para filtrar pelos favoritos.");
        if (!r.ok) throw new Error("Não foi possível calcular o ranking.");
        setDados(await r.json());
        setErro(null);
        setPagina(0);
      } catch (e) {
        if ((e as Error).name !== "AbortError") setErro((e as Error).message);
      } finally {
        if (!controle.signal.aborted) setCarregando(false);
      }
    }, 350);
    return () => {
      clearTimeout(espera);
      controle.abort();
    };
  }, [consulta]);

  const visiveis = COLUNAS.filter((c) => colunas.includes(c.id));
  const itens = useMemo(() => ordenar(buscar(dados?.itens ?? [], texto), ordem), [dados, texto, ordem]);
  const paginas = Math.max(1, Math.ceil(itens.length / porPagina));
  const trecho = itens.slice(pagina * porPagina, (pagina + 1) * porPagina);
  const metodo = METODOS.find((m) => m.id === estado.ordenarPor)!;
  const eua = estado.mercado === "EUA";
  const moeda = eua ? "USD" : "BRL";
  const trocarMercado = (mercado: "B3" | "EUA") => {
    setEstado({ ...filtrosPadrao(), ...estado, mercado, setores: [], besst: false });
    setOrdem(null);
  };

  const alternarColuna = (id: string) => {
    const novas = colunas.includes(id) ? colunas.filter((c) => c !== id) : [...colunas, id];
    setColunas(novas);
    gravarLocal(CHAVE_COLUNAS, novas);
  };

  const clicarCabecalho = (id: keyof ItemScreening) =>
    setOrdem((o) => (o?.coluna !== id ? { coluna: id, crescente: false } : o.crescente ? null : { coluna: id, crescente: true }));

  const salvarFiltro = () => {
    const nome = window.prompt("Nome do filtro:")?.trim();
    if (!nome) return;
    const novos = [...salvos.filter((s) => s.nome !== nome), { nome, estado }];
    setSalvos(novos);
    gravarLocal(CHAVE_SALVOS, novos);
  };

  const removerFiltro = (nome: string) => {
    const novos = salvos.filter((s) => s.nome !== nome);
    setSalvos(novos);
    gravarLocal(CHAVE_SALVOS, novos);
  };

  const alternarFavorito = async (ticker: string) => {
    if (!favoritos) return;
    const marcado = favoritos.has(ticker);
    const r = await fetch(`/api/favoritos/${ticker}`, { method: marcado ? "DELETE" : "PUT" });
    if (!r.ok) return;
    const novo = new Set(favoritos);
    if (marcado) novo.delete(ticker);
    else novo.add(ticker);
    setFavoritos(novo);
  };

  return (
    <div className="space-y-5">
      <div>
        <div className="suave text-xs">Ações › Ranking</div>
        <h1 className="text-2xl font-semibold">Ranking de ações{eua ? " dos EUA" : ""}</h1>
        <div className="mt-2 flex gap-2 text-sm" role="tablist" aria-label="Mercado">
          {(["B3", "EUA"] as const).map((m) => (
            <button key={m} type="button" role="tab" aria-selected={estado.mercado === m} className="pilula" onClick={() => trocarMercado(m)}>
              {m === "B3" ? "Brasil (B3)" : "EUA (US$)"}
            </button>
          ))}
        </div>
        <p className="suave text-sm">
          Filtre por indicadores e compare o preço justo de cada livro lado a lado.
        </p>
      </div>

      <p className="cartao p-3 text-sm" style={{ color: "var(--alerta)" }} role="note">
        {dados?.aviso ?? AVISO}
      </p>

      <section className="cartao p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-medium">Filtros avançados</h2>
          <div className="flex flex-wrap gap-2 text-sm">
            <button type="button" className="pilula" onClick={salvarFiltro}>Salvar filtro</button>
            <button type="button" className="pilula" onClick={() => { setEstado(filtrosPadrao()); setOrdem(null); }}>
              Limpar filtros
            </button>
            <button type="button" className="pilula" aria-expanded={mostrarFiltros} onClick={() => setMostrarFiltros(!mostrarFiltros)}>
              {mostrarFiltros ? "Ocultar filtros" : "Mostrar filtros"}
            </button>
          </div>
        </div>

        {salvos.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <span className="suave">Filtros salvos:</span>
            {salvos.map((s) => (
              <span key={s.nome} className="pilula inline-flex items-center gap-1">
                <button type="button" onClick={() => setEstado({ ...filtrosPadrao(), ...s.estado })}>{s.nome}</button>
                <button type="button" aria-label={`Remover filtro ${s.nome}`} className="suave" onClick={() => removerFiltro(s.nome)}>
                  ×
                </button>
              </span>
            ))}
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <span className="suave">Filtros rápidos:</span>
          <button type="button" className="pilula" aria-pressed={estado.favoritos} disabled={favoritos === null}
            title={favoritos === null ? "Entre na sua conta para usar favoritos" : ""}
            onClick={() => setEstado({ ...estado, favoritos: !estado.favoritos })}>
            ★ Favoritos
          </button>
          {!eua && <button type="button" className="pilula" aria-pressed={estado.besst}
            title="Setores perenes (Luiz Barsi): bancos, energia elétrica, saneamento, seguros e telecomunicações"
            onClick={() => setEstado({ ...estado, besst: !estado.besst })}>
            BESST
          </button>}
          {favoritos === null && (
            <Link href="/entrar" className="link text-xs">Entre para usar favoritos</Link>
          )}
        </div>

        {mostrarFiltros && (
          <div className="mt-4 border-t pt-4">
            <FiltrosScreening estado={estado} setores={dados?.setores ?? []} aoMudar={setEstado} moeda={moeda} />
          </div>
        )}
      </section>

      {erro && <p style={{ color: "var(--alerta)" }}>{erro}</p>}

      {dados && dados.total_avaliados > 0 && dados.sem_cotacao === dados.total_avaliados && (
        <p className="cartao p-3 text-sm" style={{ color: "var(--alerta)" }}>
          Nenhuma ação tem cotação carregada ainda. Deixe o sistema ligado: ele baixa as cotações sozinho. Acompanhe em{" "}
          <Link href="/status" className="link">Status dos dados</Link>.
        </p>
      )}

      <section className="cartao">
        <div className="flex flex-wrap items-center gap-3 border-b p-3 text-sm">
          <label className="flex items-center gap-2">
            Ranquear por
            <select className={`campo metodo-${estado.ordenarPor} texto-metodo font-medium`} value={estado.ordenarPor}
              onChange={(e) => { setEstado({ ...estado, ordenarPor: e.target.value as EstadoFiltros["ordenarPor"] }); setOrdem(null); }}>
              {METODOS.map((m) => (
                <option key={m.id} value={m.id}>{m.nome}</option>
              ))}
            </select>
          </label>
          <Link href={`/metodologia/${metodo.metodologia}`} className="link text-xs">Como é calculado</Link>
          <input aria-label="Buscar na tabela" placeholder="Buscar ticker ou empresa" className="campo w-44"
            value={texto} onChange={(e) => { setTexto(e.target.value); setPagina(0); }} />
          <details className="relative">
            <summary className="pilula cursor-pointer list-none">Colunas</summary>
            <div className="cartao absolute z-10 mt-1 max-h-72 w-56 space-y-1 overflow-y-auto p-3 shadow-lg">
              {COLUNAS.map((c) => (
                <label key={c.id} className={`flex items-center gap-2 ${c.metodo ? `metodo-${c.metodo} texto-metodo` : ""}`}>
                  <input type="checkbox" checked={colunas.includes(c.id)} onChange={() => alternarColuna(c.id)} />
                  {c.titulo}
                </label>
              ))}
            </div>
          </details>
          <span className="ml-auto flex gap-2">
            <a className="pilula" href={`/api/screening/acoes/exportar?${consulta}&formato=xlsx`}>Exportar .xlsx</a>
            <a className="pilula" href={`/api/screening/acoes/exportar?${consulta}&formato=csv`}>.csv</a>
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="suave">
              <tr className="text-right">
                <th className="w-8 px-2 py-2" aria-label="Favorito" />
                <th className="px-2 py-2 text-left">#</th>
                <th className="px-3 py-2 text-left">Ação</th>
                {visiveis.map((c) => (
                  <th key={c.id} className={`whitespace-nowrap px-3 py-2 ${c.metodo ? `metodo-${c.metodo} fundo-metodo texto-metodo` : ""}`}
                    aria-sort={ordem?.coluna === c.id ? (ordem.crescente ? "ascending" : "descending") : "none"}>
                    <button type="button" onClick={() => clicarCabecalho(c.id)}>
                      {c.titulo} {ordem?.coluna === c.id ? (ordem.crescente ? "↑" : "↓") : "⇅"}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trecho.map((i) => (
                <tr key={i.ticker} className="border-t text-right">
                  <td className="px-2 py-2 text-center">
                    {favoritos ? (
                      <button type="button" aria-label={`${favoritos.has(i.ticker) ? "Remover" : "Adicionar"} ${i.ticker} dos favoritos`}
                        aria-pressed={favoritos.has(i.ticker)} onClick={() => alternarFavorito(i.ticker)}
                        style={{ color: favoritos.has(i.ticker) ? "var(--cor-bazin)" : "var(--texto-suave)" }}>
                        {favoritos.has(i.ticker) ? "★" : "☆"}
                      </button>
                    ) : null}
                  </td>
                  <td className="px-2 py-2 text-left suave">{i.posicao}</td>
                  <td className="px-3 py-2 text-left">
                    <Link href={`/${eua ? "eua" : "acoes"}/${i.ticker}`} className="link font-medium">{i.ticker}</Link>
                    {i.classe === "REIT" && <span className="suave ml-1 text-xs">REIT</span>}
                    {i.lynch_aviso && <span title={i.lynch_aviso} className="ml-1" style={{ color: "var(--alerta)" }}>!</span>}
                    <div className="suave max-w-44 truncate text-xs">{i.nome}</div>
                  </td>
                  {visiveis.map((c) => {
                    const v = i[c.id];
                    const margem = c.id.endsWith("_margem") && typeof v === "number";
                    return (
                      <td key={c.id} title={c.id === "preco" ? `fechamento de ${formatarData(i.data_preco)}` : undefined}
                        className={`whitespace-nowrap px-3 py-2 ${c.metodo ? `metodo-${c.metodo} fundo-metodo` : ""} ${c.unidade === "texto" ? "max-w-48 truncate text-left" : ""}`}
                        style={margem ? { color: (v as number) >= 0 ? "var(--destaque)" : "var(--negativo)" } : undefined}>
                        {celula(i, c.id, c.unidade, moeda)}
                      </td>
                    );
                  })}
                </tr>
              ))}
              {dados && trecho.length === 0 && (
                <tr>
                  <td colSpan={visiveis.length + 3} className="suave px-3 py-6 text-center">
                    Nenhuma ação passa nos filtros escolhidos.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex flex-wrap items-center gap-3 border-t p-3 text-xs suave">
          <span>
            {carregando ? "Calculando…" : `${itens.length} de ${dados?.total_avaliados ?? 0} ações`}
            {dados && dados.sem_cotacao > 0 ? ` (${dados.sem_cotacao} sem cotação)` : ""}
          </span>
          <label className="flex items-center gap-1">
            Mostrar
            <select className="campo" value={porPagina} onChange={(e) => { setPorPagina(Number(e.target.value)); setPagina(0); }}>
              {[10, 20, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <span className="flex items-center gap-2">
            <button type="button" className="pilula" disabled={pagina === 0} onClick={() => setPagina(pagina - 1)}>‹</button>
            {pagina + 1} / {paginas}
            <button type="button" className="pilula" disabled={pagina + 1 >= paginas} onClick={() => setPagina(pagina + 1)}>›</button>
          </span>
          <span className="ml-auto" title="Data do último fechamento entre as ações listadas">
            Atualizado em {formatarData(dados?.atualizado_em)}
          </span>
        </div>
      </section>
    </div>
  );
}
