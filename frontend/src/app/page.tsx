import Link from "next/link";

export default function Inicio() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Análise fundamentalista de ações e FIIs</h1>
      <p className="suave max-w-2xl">
        Cada número exibido mostra a fórmula usada, o livro ou autor que a fundamenta e a fonte e a data do
        dado bruto. Toque no ícone ⓘ ao lado de qualquer indicador para ver a procedência.
      </p>
      <div className="grid gap-4 sm:grid-cols-3">
        <Link href="/acoes" className="cartao p-4 hover:shadow">
          <div className="font-medium">Ações</div>
          <div className="text-sm suave">P/L, P/VP, ROE, margens, endividamento e mais.</div>
        </Link>
        <Link href="/fiis" className="cartao p-4 hover:shadow">
          <div className="font-medium">Fundos imobiliários</div>
          <div className="text-sm suave">P/VP, patrimônio, cotistas e liquidez.</div>
        </Link>
        <Link href="/metodologia" className="cartao p-4 hover:shadow">
          <div className="font-medium">Como é calculado</div>
          <div className="text-sm suave">Fórmulas, referências e limitações de cada métrica.</div>
        </Link>
      </div>
    </div>
  );
}
