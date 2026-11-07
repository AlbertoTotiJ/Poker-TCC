"""Módulo de compatibilidade do Agente Matemático GH (GhMathAgent).

Reexporta a versão unificada e definitiva de MathematicalAgent, garantindo
100% de compatibilidade retroativa para todos os benchmarks, testes e serviços XAI.
"""

from src.agents.mathematical_agent import (
    GhCognitiveMetrics,
    GhMathAgent,
    GhMathDecision,
    GhMathParameters,
    GhPosition,
    MathematicalAgent,
    MathematicalDecision,
    MathematicalParameters,
)

__all__ = [
    "GhPosition",
    "GhCognitiveMetrics",
    "GhMathDecision",
    "GhMathAgent",
    "GhMathParameters",
    "MathematicalAgent",
    "MathematicalDecision",
    "MathematicalParameters",
]
