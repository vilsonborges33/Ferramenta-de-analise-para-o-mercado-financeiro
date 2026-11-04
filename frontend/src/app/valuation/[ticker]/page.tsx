import { ValuationAcao } from "@/componentes/ValuationAcao";

export default async function Valuation({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  return <ValuationAcao ticker={ticker.toUpperCase()} />;
}
