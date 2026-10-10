"""Tipos comuns do motor de metodologias. Sem dependência de banco ou rede."""

from dataclasses import dataclass, field
from typing import Any

Numero = float | int | None


@dataclass(frozen=True)
class Resultado:
    """Saída de toda métrica.

    `valor` é None quando a métrica não pode ser calculada; nesse caso `motivo_indisponivel`
    explica o porquê. Nunca devolvemos estimativas sem aviso.
    """

    valor: float | None
    motivo_indisponivel: str | None = None
    detalhes: dict[str, Any] = field(default_factory=dict)

    @property
    def disponivel(self) -> bool:
        return self.valor is not None


def ok(valor: float, **detalhes: Any) -> Resultado:
    return Resultado(valor=float(valor), detalhes=detalhes)


def indisponivel(motivo: str, **detalhes: Any) -> Resultado:
    return Resultado(valor=None, motivo_indisponivel=motivo, detalhes=detalhes)


def faltando(**insumos: Numero) -> Resultado | None:
    """Devolve um Resultado indisponível se algum insumo for None; senão None."""
    nomes = [nome for nome, valor in insumos.items() if valor is None]
    if nomes:
        return indisponivel("dado indisponível: " + ", ".join(nomes))
    return None
