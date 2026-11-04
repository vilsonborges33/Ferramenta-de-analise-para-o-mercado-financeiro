"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArteVazio } from "@/componentes/Arte";
import { Aviso, Cabecalho, CampoNumero, pctf } from "@/componentes/Ferramenta";
import { Monograma } from "@/componentes/Monograma";
import { formatarData } from "@/lib/formato";

type Condicao = { tipo: string; rotulo: string; percentual: boolean; precisa_valor: boolean };
type Alerta = { id: number; ticker: string; classe: string; tipo: string; valor: number | null; repetir_dias: number;
  canal: string; descricao: string; ultimo_disparo: string | null; atual: number | null; preco: number | null;
  condicao_verdadeira: boolean | null };

export default function Alertas() {
  const [alertas, setAlertas] = useState<Alerta[] | null | undefined>(undefined); // null = sem login
  const [condicoes, setCondicoes] = useState<Condicao[]>([]);
  const [emailConfigurado, setEmailConfigurado] = useState(false);
  const [ticker, setTicker] = useState("");
  const [tipo, setTipo] = useState("preco_abaixo");
  const [valor, setValor] = useState(0);
  const [repetir, setRepetir] = useState(7);
  const [canal, setCanal] = useState("email");
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    const r = await fetch("/api/alertas");
    setAlertas(r.ok ? await r.json() : null);
  }, []);
  useEffect(() => {
    carregar();
    fetch("/api/alertas/condicoes").then((r) => r.json()).then((d) => {
      setCondicoes(d.condicoes);
      setEmailConfigurado(d.email_configurado);
    }).catch(() => undefined);
  }, [carregar]);

  const cond = condicoes.find((c) => c.tipo === tipo);
  const criar = async (e: React.FormEvent) => {
    e.preventDefault();
    setErro(null);
    const r = await fetch("/api/alertas", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker, tipo, valor: cond?.precisa_valor ? (cond.percentual ? valor / 100 : valor) : null,
        repetir_dias: repetir, canal }),
    });
    if (!r.ok) return setErro((await r.json().catch(() => null))?.detail ?? "não foi possível criar o alerta");
    setTicker("");
    carregar();
  };
  const apagar = async (id: number) => {
    await fetch(`/api/alertas/${id}`, { method: "DELETE" });
    carregar();
  };

  if (alertas === null) {
    return (
      <div className="space-y-5">
        <Cabecalho trilha="Minha conta" titulo="Alertas" icone="alertas" />
        <div className="cartao grid place-items-center gap-3 p-10 text-center">
          <ArteVazio />
          <p className="suave">Entre na sua conta para criar alertas de preço e de indicadores.</p>
          <Link href="/entrar" className="botao">Entrar</Link>
        </div>
      </div>
    );
  }

  const formatarAtual = (a: Alerta) => {
    if (a.atual === null) return "dado indisponível";
    const c = condicoes.find((x) => x.tipo === a.tipo);
    return c?.percentual ? pctf(a.atual) : a.atual.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  return (
    <div className="space-y-5">
      <Cabecalho trilha="Minha conta" titulo="Alertas" icone="alertas"
        subtitulo="Avisos quando um ativo atingir o preço ou o indicador que você definiu. Verificados após cada atualização dos dados." />
      {!emailConfigurado && (
        <p className="cartao p-3 text-sm" style={{ color: "var(--alerta)" }}>
          E-mail ainda não configurado: os alertas disparam e ficam marcados aqui. Para receber por e-mail, preencha
          SMTP_HOST, SMTP_USUARIO e SMTP_SENHA no arquivo .env (veja .env.example) e reinicie o sistema.
        </p>
      )}
      <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
        <form onSubmit={criar} className="cartao space-y-4 p-5">
          <h2 className="font-semibold">Novo alerta</h2>
          <label className="block">
            <span className="rotulo">Ativo</span>
            <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} required placeholder="PETR4"
              className="campo ticker mt-1 w-full py-1.5" />
          </label>
          <label className="block">
            <span className="rotulo">Condição</span>
            <select value={tipo} onChange={(e) => setTipo(e.target.value)} className="campo mt-1 w-full py-1.5">
              {condicoes.map((c) => <option key={c.tipo} value={c.tipo}>{c.rotulo}</option>)}
            </select>
          </label>
          {cond?.precisa_valor && (
            <CampoNumero rotulo="Valor" valor={valor} aoMudar={setValor} prefixo={cond.percentual ? undefined : tipo.startsWith("preco") ? "R$" : undefined}
              sufixo={cond.percentual ? "%" : undefined} />
          )}
          <CampoNumero rotulo="Repetir no máximo a cada" sufixo="dias" valor={repetir} aoMudar={setRepetir} />
          <label className="block">
            <span className="rotulo">Aviso</span>
            <select value={canal} onChange={(e) => setCanal(e.target.value)} className="campo mt-1 w-full py-1.5">
              <option value="email">E-mail e tela</option>
              <option value="tela">Só nesta tela</option>
            </select>
          </label>
          {erro && <p className="text-sm negativo">{erro}</p>}
          <button type="submit" className="botao w-full justify-center">Criar alerta</button>
        </form>

        <div className="cartao overflow-x-auto">
          {alertas === undefined ? <p className="p-4 suave">Carregando…</p> : alertas.length === 0 ? (
            <div className="grid place-items-center gap-2 p-10 text-center">
              <ArteVazio />
              <p className="suave">Nenhum alerta ainda.</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="px-4 py-2 text-left">Ativo</th><th className="px-4 py-2 text-left">Condição</th>
                  <th className="px-4 py-2 text-right">Agora</th><th className="px-4 py-2 text-left">Situação</th><th />
                </tr>
              </thead>
              <tbody>
                {alertas.map((a) => (
                  <tr key={a.id} className="border-b last:border-0">
                    <td className="px-4 py-2">
                      <Link href={`/${a.classe === "FII" ? "fiis" : "acoes"}/${a.ticker}`} className="flex items-center gap-2 hover:underline">
                        <Monograma ticker={a.ticker} classe={a.classe} tamanho={22} /><span className="ticker font-semibold">{a.ticker}</span>
                      </Link>
                    </td>
                    <td className="px-4 py-2">{a.descricao}<div className="text-xs suave">{a.canal === "email" ? "e-mail" : "tela"} · a cada {a.repetir_dias} d</div></td>
                    <td className="mono px-4 py-2 text-right">{formatarAtual(a)}</td>
                    <td className="px-4 py-2">
                      {a.condicao_verdadeira ? <span className="variacao positivo">condição atendida</span>
                        : a.condicao_verdadeira === false ? <span className="suave">aguardando</span> : <span className="suave">sem dado</span>}
                      {a.ultimo_disparo && <div className="text-xs suave">disparou em {formatarData(a.ultimo_disparo)}</div>}
                    </td>
                    <td className="px-2 py-2 text-right">
                      <button type="button" onClick={() => apagar(a.id)} className="text-xs suave hover:text-[var(--negativo)]">Excluir</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
      <Aviso>Alertas são cálculos automáticos sobre dados públicos; não constituem recomendação de investimento.</Aviso>
    </div>
  );
}
