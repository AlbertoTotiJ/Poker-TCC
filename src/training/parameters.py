"""Mapeamento, restrições e operadores genéticos para hiperparâmetros de agentes.

Fornece o contrato de hiperparâmetros treináveis para cada perfil de agente
(Bluffer, Mathematical, GhMath), incluindo geração estocástica, validação por clamping,
mutação gaussiana adaptativa e cruzamento (crossover) aritmético.
"""

from dataclasses import dataclass
import random
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.agents.bluffer_agent import BlufferAgent
from src.agents.gh_bluffer_agent import GhBlufferAgent
from src.agents.gh_math_agent import GhMathAgent
from src.agents.hybrid_agent import HybridAgent
from src.agents.mathematical_agent import MathematicalAgent


@dataclass(frozen=True)
class ParamSpec:
    """Especificação e limites operacionais de um hiperparâmetro treinável."""

    name: str
    min_val: float
    max_val: float
    default_val: float
    is_int: bool = False
    description: str = ""


BLUFFER_SPECS: List[ParamSpec] = [
    ParamSpec(
        name="fold_equity_threshold",
        min_val=0.10,
        max_val=0.90,
        default_val=0.40,
        description="Probabilidade mínima de fold dos oponentes para blefar",
    ),
    ParamSpec(
        name="bluff_frequency",
        min_val=0.05,
        max_val=0.95,
        default_val=0.40,
        description="Frequência base de blefe puro em rodadas finais",
    ),
    ParamSpec(
        name="semi_bluff_frequency",
        min_val=0.10,
        max_val=1.00,
        default_val=0.70,
        description="Frequência de transformação de draws em apostas agressivas",
    ),
    ParamSpec(
        name="cbet_frequency",
        min_val=0.10,
        max_val=1.00,
        default_val=0.65,
        description="Frequência de Continuation Bet no Flop",
    ),
    ParamSpec(
        name="bluff_raise_frequency",
        min_val=0.05,
        max_val=0.90,
        default_val=0.35,
        description="Frequência de re-aumento contra apostas fracas de sondagem",
    ),
    ParamSpec(
        name="aggression_multiplier",
        min_val=0.50,
        max_val=2.50,
        default_val=1.00,
        description="Multiplicador geral de agressividade sobre apostas e raises",
    ),
    ParamSpec(
        name="scare_card_weight",
        min_val=0.00,
        max_val=0.40,
        default_val=0.15,
        description="Peso de oportunidade ao surgir cartas assustadoras (Aces/Kings)",
    ),
    ParamSpec(
        name="dry_board_bonus",
        min_val=0.00,
        max_val=0.30,
        default_val=0.10,
        description="Bônus de fold equity em bordos desconectados/secos",
    ),
    ParamSpec(
        name="bet_sizing_factor",
        min_val=0.25,
        max_val=1.20,
        default_val=0.40,
        description="Fração do pote utilizada para precificar apostas de blefe",
    ),
]

MATHEMATICAL_SPECS: List[ParamSpec] = [
    ParamSpec(
        name="raise_equity_threshold",
        min_val=0.45,
        max_val=0.85,
        default_val=0.65,
        description="Equidade mínima calculada para realizar raise por valor",
    ),
    ParamSpec(
        name="call_ev_margin",
        min_val=-0.05,
        max_val=0.15,
        default_val=0.04,
        description="Margem de segurança de EV para pagar apostas",
    ),
    ParamSpec(
        name="draw_weight",
        min_val=0.20,
        max_val=2.00,
        default_val=1.00,
        description="Peso atribuído a outs de evolução no Flop e Turn",
    ),
    ParamSpec(
        name="bet_sizing_factor",
        min_val=0.25,
        max_val=1.20,
        default_val=0.50,
        description="Fração padrão do pote utilizada em apostas de valor",
    ),
    ParamSpec(
        name="num_simulations",
        min_val=40.0,
        max_val=300.0,
        default_val=120.0,
        is_int=True,
        description="Quantidade de iterações de Monte Carlo para estimar equidade",
    ),
]

GH_MATH_SPECS: List[ParamSpec] = [
    ParamSpec(
        name="base_threshold",
        min_val=0.50,
        max_val=0.80,
        default_val=0.58,
        description="Limiar base de equidade ajustada para decisões agressivas",
    ),
    ParamSpec(
        name="kelly_fraction_limit",
        min_val=0.10,
        max_val=0.50,
        default_val=0.25,
        description="Teto do Critério de Kelly Fracionário para dimensionar apostas",
    ),
    ParamSpec(
        name="num_simulations",
        min_val=100.0,
        max_val=300.0,
        default_val=150.0,
        is_int=True,
        description="Simulações de Monte Carlo com amostragem representativa",
    ),
]

GH_BLUFFER_SPECS: List[ParamSpec] = [
    ParamSpec(
        name="bluff_aggression",
        min_val=0.50,
        max_val=2.50,
        default_val=1.10,
        description="Multiplicador sobre a razão GTO de blefe ótimo",
    ),
    ParamSpec(
        name="gto_balance_factor",
        min_val=0.50,
        max_val=1.80,
        default_val=1.00,
        description="Fator de calibração do equilíbrio de Nash B/(P+2B)",
    ),
    ParamSpec(
        name="min_blocker_threshold",
        min_val=0.10,
        max_val=0.60,
        default_val=0.30,
        description="Pontuação mínima de bloqueador necessária para blefe puro",
    ),
    ParamSpec(
        name="num_simulations",
        min_val=50.0,
        max_val=250.0,
        default_val=100.0,
        is_int=True,
        description="Simulações de Monte Carlo para equidade e semi-blefes",
    ),
]

HYBRID_SPECS: List[ParamSpec] = [
    ParamSpec(
        name="math_weight",
        min_val=0.10,
        max_val=0.90,
        default_val=0.50,
        description="Peso de decisão matemática vs oportunismo de blefe",
    ),
    ParamSpec(
        name="raise_equity_threshold",
        min_val=0.45,
        max_val=0.85,
        default_val=0.60,
        description="Limiar de equidade para realizar apostas ou aumentos por valor",
    ),
    ParamSpec(
        name="call_ev_margin",
        min_val=-0.05,
        max_val=0.15,
        default_val=0.02,
        description="Margem de segurança de EV para aceitar calls",
    ),
    ParamSpec(
        name="bluff_frequency",
        min_val=0.05,
        max_val=0.60,
        default_val=0.25,
        description="Frequência de blefe oportuno em potes abandonados",
    ),
    ParamSpec(
        name="semi_bluff_frequency",
        min_val=0.10,
        max_val=0.85,
        default_val=0.50,
        description="Frequência de semi-blefe com draws no Flop e Turn",
    ),
    ParamSpec(
        name="fold_equity_threshold",
        min_val=0.15,
        max_val=0.80,
        default_val=0.35,
        description="Fold equity mínima estimada para validar jogadas de blefe",
    ),
    ParamSpec(
        name="slowplay_prob",
        min_val=0.05,
        max_val=0.50,
        default_val=0.20,
        description="Probabilidade de armadilha (slow-play) com mãos monstro",
    ),
    ParamSpec(
        name="bet_sizing_factor",
        min_val=0.25,
        max_val=1.20,
        default_val=0.55,
        description="Fração do pote utilizada em dimensionamento de apostas",
    ),
    ParamSpec(
        name="num_simulations",
        min_val=50.0,
        max_val=300.0,
        default_val=150.0,
        is_int=True,
        description="Simulações de Monte Carlo para cálculo de equidade",
    ),
]

AGENT_PARAM_SPECS: Dict[str, List[ParamSpec]] = {
    "bluffer": BLUFFER_SPECS,
    "mathematical": MATHEMATICAL_SPECS,
    "gh_math": GH_MATH_SPECS,
    "gh_bluffer": GH_BLUFFER_SPECS,
    "hybrid": HYBRID_SPECS,
}


def get_specs_for_agent(agent_type: str) -> List[ParamSpec]:
    """Retorna a lista de especificações de parâmetros para o tipo de agente."""
    normalized = agent_type.strip().lower()
    if normalized not in AGENT_PARAM_SPECS:
        raise ValueError(
            f"Tipo de agente '{agent_type}' não suportado. "
            f"Opções disponíveis: {list(AGENT_PARAM_SPECS.keys())}"
        )
    return AGENT_PARAM_SPECS[normalized]


def get_default_parameters(agent_type: str) -> Dict[str, Any]:
    """Retorna os hiperparâmetros padrão do agente."""
    specs = get_specs_for_agent(agent_type)
    return {
        s.name: (int(s.default_val) if s.is_int else float(s.default_val))
        for s in specs
    }


def generate_random_parameters(
    agent_type: str, rng: Optional[random.Random] = None
) -> Dict[str, Any]:
    """Gera parâmetros aleatórios válidos respeitando as faixas permitidas."""
    r = rng if rng is not None else random.Random()
    specs = get_specs_for_agent(agent_type)
    params: Dict[str, Any] = {}
    for s in specs:
        val = r.uniform(s.min_val, s.max_val)
        if s.is_int:
            params[s.name] = int(round(val))
        else:
            params[s.name] = round(val, 4)
    return params


def clamp_parameters(
    agent_type: str, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Garante que todos os hiperparâmetros estejam restritos aos limites válidos."""
    specs = get_specs_for_agent(agent_type)
    spec_map = {s.name: s for s in specs}
    clamped: Dict[str, Any] = {}

    for k, v in params.items():
        if k in spec_map:
            s = spec_map[k]
            clamped_val = max(s.min_val, min(s.max_val, float(v)))
            if s.is_int:
                clamped[k] = int(round(clamped_val))
            else:
                clamped[k] = round(clamped_val, 4)
        else:
            clamped[k] = v

    # Garante que parâmetros ausentes recebam o valor default
    for s in specs:
        if s.name not in clamped:
            clamped[s.name] = (
                int(s.default_val) if s.is_int else float(s.default_val)
            )

    return clamped


def mutate_parameters(
    agent_type: str,
    params: Dict[str, Any],
    mutation_rate: float = 0.25,
    mutation_scale: float = 0.15,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """Aplica mutação gaussiana estocástica sobre os hiperparâmetros."""
    r = rng if rng is not None else random.Random()
    specs = get_specs_for_agent(agent_type)
    mutated = dict(params)

    for s in specs:
        if r.random() < mutation_rate:
            span = s.max_val - s.min_val
            current = float(mutated.get(s.name, s.default_val))
            delta = r.gauss(0.0, span * mutation_scale)
            new_val = max(s.min_val, min(s.max_val, current + delta))
            if s.is_int:
                mutated[s.name] = int(round(new_val))
            else:
                mutated[s.name] = round(new_val, 4)

    return clamp_parameters(agent_type, mutated)


def crossover_parameters(
    agent_type: str,
    parent1: Dict[str, Any],
    parent2: Dict[str, Any],
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """Combina dois genomas de parâmetros via interpolação aritmética estocástica."""
    r = rng if rng is not None else random.Random()
    specs = get_specs_for_agent(agent_type)
    child: Dict[str, Any] = {}

    for s in specs:
        val1 = float(parent1.get(s.name, s.default_val))
        val2 = float(parent2.get(s.name, s.default_val))
        alpha = r.uniform(0.15, 0.85)
        combined = (alpha * val1) + ((1.0 - alpha) * val2)
        if s.is_int:
            child[s.name] = int(round(combined))
        else:
            child[s.name] = round(combined, 4)

    return clamp_parameters(agent_type, child)


def instantiate_agent(
    agent_type: str,
    player_id: str,
    name: str,
    params: Optional[Dict[str, Any]] = None,
    rng: Optional[random.Random] = None,
) -> BaseAgent:
    """Instancia um agente com os hiperparâmetros fornecidos."""
    normalized = agent_type.strip().lower()
    specs = get_specs_for_agent(normalized)
    spec_names = {s.name for s in specs}

    effective_params = (
        clamp_parameters(normalized, params)
        if params is not None
        else get_default_parameters(normalized)
    )

    clean_kwargs = {
        k: v for k, v in effective_params.items() if k in spec_names
    }

    if normalized == "bluffer":
        return BlufferAgent(
            player_id=player_id,
            name=name,
            rng=rng,
            **clean_kwargs,
        )
    elif normalized == "mathematical":
        return MathematicalAgent(
            player_id=player_id,
            name=name,
            rng=rng,
            **clean_kwargs,
        )
    elif normalized == "gh_bluffer":
        return GhBlufferAgent(
            player_id=player_id,
            name=name,
            rng=rng,
            **clean_kwargs,
        )
    elif normalized == "gh_math":
        return GhMathAgent(
            player_id=player_id,
            name=name,
            rng=rng,
            **clean_kwargs,
        )
    elif normalized == "hybrid":
        return HybridAgent(
            player_id=player_id,
            name=name,
            rng=rng,
            **clean_kwargs,
        )
    else:
        raise ValueError(f"Agente não reconhecido para instanciação: {agent_type}")
