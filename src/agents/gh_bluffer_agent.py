"""Módulo de compatibilidade do Agente Blefador GH (GhBlufferAgent).

Reexporta a versão unificada e definitiva de BlufferAgent, garantindo
100% de retrocompatibilidade para todos os benchmarks, testes e serviços XAI.
"""

from src.agents.bluffer_agent import (
    BluffDecision,
    BlufferAgent,
    BlufferParameters,
    BluffTactic,
    GhBluffDecision,
    GhBlufferAgent,
    GhBlufferParameters,
    GhBluffMetrics,
    GhBluffTactic,
)

__all__ = [
    "BluffTactic",
    "GhBluffTactic",
    "GhBluffMetrics",
    "BluffDecision",
    "GhBluffDecision",
    "BlufferParameters",
    "GhBlufferParameters",
    "BlufferAgent",
    "GhBlufferAgent",
]
