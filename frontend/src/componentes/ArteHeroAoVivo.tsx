"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Ilustração do painel "ao vivo": uma ação fictícia oscilando em candles em torno do valor intrínseco.
 *
 * O candle da direita se forma tique a tique; quando fecha, o gráfico desliza e nasce outro. O preço segue um
 * passeio aleatório que volta para perto do valor intrínseco (linha dourada), com ciclos de otimismo e pessimismo:
 * abaixo dela aparece a margem de segurança. Nada aqui é dado de mercado — é só a ideia do produto em movimento.
 * Pausa com a aba oculta, fora da tela ou com o mouse em cima.
 */

type Candle = { t: number; abre: number; fecha: number; max: number; min: number; volume: number };

const L = 560, A = 230, N = 36, PASSO = (L - 92) / N;
const TOPO = 22, BASE_GRAFICO = A - 46, BASE_VOLUME = A - 20;
const TIQUE_MS = 260, TIQUES_POR_CANDLE = 5;

/** Valor intrínseco subindo devagar, com uma leve ondulação (lucros crescendo com o tempo). */
const justo = (t: number) => 150 + t * 0.12 + 3 * Math.sin(t / 23);
/** Humor do mercado: ciclos longos em que o preço fica acima ou abaixo do valor. */
const humor = (t: number) => 0.17 * Math.sin(t / 9) + 0.07 * Math.sin(t / 3.7) - 0.02;

function gerador(semente: number) {
  let s = semente;
  return () => ((s = (s * 9301 + 49297) % 233280) / 233280);
}

/** Próximo preço: puxado para o "alvo" do humor do mercado, com ruído. */
function passo(preco: number, t: number, aleatorio: () => number, escala = 1) {
  const alvo = justo(t) * (1 + humor(t));
  return preco + (alvo - preco) * 0.35 * escala + (aleatorio() - 0.5) * 7 * Math.sqrt(escala);
}

function novoCandle(t: number, abre: number, aleatorio: () => number): Candle {
  return { t, abre, fecha: abre, max: abre + aleatorio() * 0.6, min: abre - aleatorio() * 0.6, volume: 0.3 };
}

/** Série inicial fixa (com semente): o servidor e o navegador desenham o mesmo gráfico antes da animação. */
function inicial(): Candle[] {
  const r = gerador(11);
  let preco = justo(0) * (1 + humor(0));
  return Array.from({ length: N }, (_, t) => {
    const c = novoCandle(t, preco, r);
    for (let k = 0; k < TIQUES_POR_CANDLE; k++) {
      c.fecha = passo(c.fecha, t, r, 1 / TIQUES_POR_CANDLE);
      c.max = Math.max(c.max, c.fecha);
      c.min = Math.min(c.min, c.fecha);
    }
    c.max += r() * 1.6;
    c.min -= r() * 1.6;
    c.volume = 0.35 + Math.min(1, Math.abs(c.fecha - c.abre) / 5) * 0.65;
    preco = c.fecha;
    return c;
  });
}

function faixa(dados: Candle[]) {
  const valores = dados.flatMap((d) => [d.max, d.min, justo(d.t)]);
  const lo = Math.min(...valores), hi = Math.max(...valores);
  const folga = (hi - lo) * 0.12 + 1;
  return { lo: lo - folga, hi: hi + folga };
}

export function ArteHeroAoVivo({ className = "" }: { className?: string }) {
  const [dados, setDados] = useState<Candle[]>(inicial);
  const [escala, setEscala] = useState(() => faixa(inicial()));
  const [deslize, setDeslize] = useState({ x: 0, animar: false });
  const tique = useRef(0);
  const pausado = useRef(false);
  const svg = useRef<SVGSVGElement>(null);

  useEffect(() => {
    let visivel = true;
    const observador = new IntersectionObserver(([e]) => { visivel = e.isIntersecting; });
    if (svg.current) observador.observe(svg.current);
    const id = window.setInterval(() => {
      if (!visivel || document.hidden || pausado.current) return;
      tique.current += 1;
      const fechou = tique.current % TIQUES_POR_CANDLE === 0;
      setDados((atual) => {
        const ultimo = { ...atual[atual.length - 1] };
        ultimo.fecha = passo(ultimo.fecha, ultimo.t, Math.random, 1 / TIQUES_POR_CANDLE);
        ultimo.max = Math.max(ultimo.max, ultimo.fecha + Math.random() * 0.5);
        ultimo.min = Math.min(ultimo.min, ultimo.fecha - Math.random() * 0.5);
        ultimo.volume = Math.min(1, ultimo.volume + 0.08 + Math.abs(ultimo.fecha - ultimo.abre) / 40);
        const proximo = [...atual.slice(0, -1), ultimo];
        if (!fechou) return proximo;
        return [...proximo.slice(1), novoCandle(ultimo.t + 1, ultimo.fecha, Math.random)];
      });
      if (fechou) {
        // Desliza um candle para a esquerda: começa deslocado e volta ao zero com transição.
        setDeslize({ x: PASSO, animar: false });
        requestAnimationFrame(() => requestAnimationFrame(() => setDeslize({ x: 0, animar: true })));
      }
    }, TIQUE_MS);
    return () => {
      window.clearInterval(id);
      observador.disconnect();
    };
  }, []);

  // A escala vertical acompanha o gráfico devagar (sem saltos quando um candle extremo sai da tela).
  useEffect(() => {
    const alvo = faixa(dados);
    setEscala((e) => ({ lo: e.lo + (alvo.lo - e.lo) * 0.25, hi: e.hi + (alvo.hi - e.hi) * 0.25 }));
  }, [dados]);

  const y = (v: number) => TOPO + (1 - (v - escala.lo) / (escala.hi - escala.lo)) * (BASE_GRAFICO - TOPO);
  const x = (i: number) => 16 + i * PASSO + PASSO / 2;
  const caminho = (pontos: [number, number][]) =>
    pontos.map(([px, py], i) => `${i ? "L" : "M"}${px.toFixed(1)} ${py.toFixed(1)}`).join(" ");

  const media = dados.map((_, i) => {
    const j = dados.slice(Math.max(0, i - 5), i + 1);
    return j.reduce((s, d) => s + d.fecha, 0) / j.length;
  });
  const linhaJusto = caminho(dados.map((d, i) => [x(i), y(justo(d.t))]));
  const linhaMedia = caminho(media.map((m, i) => [x(i), y(m)]));

  // Margem de segurança: cada trecho contínuo em que o fechamento ficou abaixo do valor intrínseco.
  const trechos: number[][] = [];
  dados.forEach((d, i) => {
    if (d.fecha < justo(d.t)) {
      const ultimo = trechos[trechos.length - 1];
      if (ultimo && ultimo[ultimo.length - 1] === i - 1) ultimo.push(i);
      else trechos.push([i]);
    }
  });
  const areas = trechos.filter((t) => t.length > 1).map((t) => caminho([
    ...t.map((i): [number, number] => [x(i), y(justo(dados[i].t))]),
    ...[...t].reverse().map((i): [number, number] => [x(i), y(dados[i].fecha)]),
  ]) + "Z");
  const maior = trechos.reduce<number[]>((m, t) => (t.length > m.length ? t : m), []);
  const meio = maior.length >= 4 ? maior[Math.floor(maior.length / 2)] : null;

  const atual = dados[dados.length - 1];
  const anterior = dados[dados.length - 2];
  const subindo = atual.fecha >= anterior.fecha;
  const corAtual = subindo ? "var(--positivo)" : "var(--negativo)";
  const yAtual = y(atual.fecha);
  const descontado = atual.fecha < justo(atual.t);
  const margem = (justo(atual.t) - atual.fecha) / justo(atual.t);

  return (
    <svg ref={svg} viewBox={`0 0 ${L} ${A}`} className={className} role="img"
      onMouseEnter={() => { pausado.current = true; }} onMouseLeave={() => { pausado.current = false; }}
      aria-label="Ilustração animada: uma ação oscila em candles; abaixo do valor intrínseco forma-se a margem de segurança">
      <defs>
        <linearGradient id="vivo-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--ouro)" stopOpacity="0.32" />
          <stop offset="1" stopColor="var(--ouro)" stopOpacity="0.03" />
        </linearGradient>
        <linearGradient id="vivo-media" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="var(--destaque-2)" stopOpacity="0.15" />
          <stop offset="1" stopColor="var(--destaque-2)" />
        </linearGradient>
        <clipPath id="vivo-recorte"><rect x="8" y="0" width={L - 84} height={A} /></clipPath>
      </defs>

      {Array.from({ length: 6 }, (_, k) => (
        <line key={k} x1="8" x2={L - 76} y1={TOPO + k * ((BASE_GRAFICO - TOPO) / 5)}
          y2={TOPO + k * ((BASE_GRAFICO - TOPO) / 5)} stroke="var(--borda)" strokeDasharray="2 4" />
      ))}

      <g clipPath="url(#vivo-recorte)">
        <g style={{ transform: `translateX(${deslize.x}px)`,
          transition: deslize.animar ? `transform ${TIQUE_MS * 2}ms ease-out` : "none" }}>
          {areas.map((d, k) => <path key={k} d={d} fill="url(#vivo-area)" />)}
          {dados.map((d, i) => {
            const cor = d.fecha >= d.abre ? "var(--positivo)" : "var(--negativo)";
            const formando = i === dados.length - 1;
            return (
              <g key={d.t} opacity={formando ? 1 : 0.9}>
                <line x1={x(i)} x2={x(i)} y1={y(d.max)} y2={y(d.min)} stroke={cor} strokeWidth="1" />
                <rect x={x(i) - PASSO * 0.31} width={PASSO * 0.62} rx="1" y={y(Math.max(d.abre, d.fecha))}
                  height={Math.max(1.5, Math.abs(y(d.abre) - y(d.fecha)))} fill={cor} />
                <rect x={x(i) - PASSO * 0.31} width={PASSO * 0.62} y={BASE_VOLUME - 3 - d.volume * 16}
                  height={3 + d.volume * 16} fill={cor} opacity="0.22" />
              </g>
            );
          })}
          <path d={linhaMedia} fill="none" stroke="url(#vivo-media)" strokeWidth="2" strokeLinecap="round" />
          <path d={linhaJusto} fill="none" stroke="var(--ouro)" strokeWidth="1.6" strokeDasharray="6 4" />
          {meio !== null && (
            <text x={x(meio)} y={y(justo(dados[meio].t)) + 30} textAnchor="middle" fontSize="11" fill="var(--ouro)"
              opacity="0.9">margem de segurança</text>
          )}
        </g>
      </g>

      {/* Preço atual: linha até o eixo, etiqueta colorida e ponto pulsando no último fechamento. */}
      <line x1={x(dados.length - 1)} x2={L - 76} y1={yAtual} y2={yAtual} stroke={corAtual} strokeDasharray="2 3"
        opacity="0.7" />
      <circle cx={x(dados.length - 1)} cy={yAtual} r="3" fill={corAtual}>
        <animate attributeName="r" values="3;7;3" dur="1.6s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="1;0.25;1" dur="1.6s" repeatCount="indefinite" />
      </circle>
      <g fontSize="11" fontFamily="inherit">
        <rect x={L - 72} y={yAtual - 10} width="64" height="20" rx="4" fill={corAtual} />
        <text x={L - 40} y={yAtual + 4} textAnchor="middle" fill="var(--fundo)" fontWeight="600"
          className="mono">{atual.fecha.toFixed(2).replace(".", ",")}</text>
        <rect x={L - 72} y={y(justo(atual.t)) - 10} width="64" height="20" rx="4" fill="var(--superficie-2)"
          stroke="var(--ouro)" strokeOpacity="0.6" />
        <text x={L - 40} y={y(justo(atual.t)) + 4} textAnchor="middle" fill="var(--ouro)" className="mono">
          {justo(atual.t).toFixed(2).replace(".", ",")}</text>
        <text x={L - 76} y={14} textAnchor="end" fill={descontado ? "var(--ouro)" : "var(--texto-suave)"}>
          {descontado ? `margem de segurança ${(margem * 100).toFixed(1).replace(".", ",")}%`
            : `acima do valor intrínseco ${(-margem * 100).toFixed(1).replace(".", ",")}%`}
        </text>
        <text x="10" y={14} fill="var(--ouro)" opacity="0.85">— — valor intrínseco</text>
      </g>
      <line x1="8" x2={L - 76} y1={BASE_VOLUME} y2={BASE_VOLUME} stroke="var(--borda-forte)" />
    </svg>
  );
}
