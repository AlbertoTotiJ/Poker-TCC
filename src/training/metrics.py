"""Sistema modular de qualificação de métricas individuais de performance e fitness.

Permite que o usuário ou o otimizador qualifique cada métrica individualmente
(ex: focar 100% em Taxa de Sucesso de Blefe, ou focar em BB/100, ou ponderar métricas
combinadas), fornecendo notas, tiers de excelência (S/A/B/C/D) e pontuação de fitness.
"""

from dataclasses import asdict, dataclass
from enum import Enum
import math
from typing import Any, Dict, Optional


class EvaluationMetric(str, Enum):
    """Métricas individuais elegíveis para qualificação e calibração de agentes."""

    BB_PER_100 = "bb_per_100"
    WIN_RATE = "win_rate"
    BLUFF_SUCCESS_RATE = "bluff_success_rate"
    AGGRESSION_FACTOR = "aggression_factor"
    FOLD_EQUITY_REALIZED = "fold_equity_realized"
    VPIP = "vpip"
    PFR = "pfr"
    SHOWDOWN_WIN_RATE = "showdown_win_rate"
    NET_CHIPS = "net_chips"


@dataclass
class AgentPerformanceMetrics:
    """Métricas brutas e consolidadas coletadas durante a avaliação em mesa."""

    hands_played: int = 0
    hands_won: int = 0
    net_chips: int = 0
    bb_per_100: float = 0.0
    win_rate: float = 0.0
    vpip: float = 0.0
    pfr: float = 0.0
    aggression_factor: float = 0.0
    bluffs_attempted: int = 0
    bluffs_won: int = 0
    bluff_success_rate: float = 0.0
    fold_equity_realized: float = 0.0
    showdowns_played: int = 0
    showdowns_won: int = 0
    showdown_win_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Converte métricas para dicionário serializável."""
        return asdict(self)


@dataclass
class MetricWeights:
    """Pesos atribuídos a cada métrica individual para calcular o fitness composto."""

    weights: Dict[EvaluationMetric, float]

    def __post_init__(self) -> None:
        # Normaliza a soma dos pesos para 1.0 se houver algum peso positivo
        total = sum(v for v in self.weights.values() if v > 0)
        if total > 0:
            self.weights = {
                k: max(0.0, v / total) for k, v in self.weights.items()
            }
        else:
            self.weights = {EvaluationMetric.BB_PER_100: 1.0}

    @classmethod
    def for_single_metric(
        cls, metric: EvaluationMetric | str
    ) -> "MetricWeights":
        """Cria uma configuração com 100% de foco em uma única métrica individual."""
        target = (
            EvaluationMetric(metric)
            if isinstance(metric, str)
            else metric
        )
        return cls(weights={target: 1.0})

    @classmethod
    def preset_balanced(cls) -> "MetricWeights":
        """Preset equilibrado: valoriza rentabilidade, agressividade e blefe."""
        return cls(
            weights={
                EvaluationMetric.BB_PER_100: 0.35,
                EvaluationMetric.WIN_RATE: 0.20,
                EvaluationMetric.AGGRESSION_FACTOR: 0.15,
                EvaluationMetric.BLUFF_SUCCESS_RATE: 0.15,
                EvaluationMetric.FOLD_EQUITY_REALIZED: 0.15,
            }
        )

    @classmethod
    def preset_bluff_specialist(cls) -> "MetricWeights":
        """Preset focado em qualificar a maestria do Agente Blefador."""
        return cls(
            weights={
                EvaluationMetric.BLUFF_SUCCESS_RATE: 0.40,
                EvaluationMetric.FOLD_EQUITY_REALIZED: 0.25,
                EvaluationMetric.BB_PER_100: 0.20,
                EvaluationMetric.AGGRESSION_FACTOR: 0.15,
            }
        )

    @classmethod
    def preset_profit_max(cls) -> "MetricWeights":
        """Preset focado estritamente em rentabilidade máxima (BB/100)."""
        return cls(
            weights={
                EvaluationMetric.BB_PER_100: 0.70,
                EvaluationMetric.WIN_RATE: 0.30,
            }
        )

    @classmethod
    def preset_tight_aggressive(cls) -> "MetricWeights":
        """Preset para qualificar postura clássica TAG (Tight-Aggressive)."""
        return cls(
            weights={
                EvaluationMetric.BB_PER_100: 0.40,
                EvaluationMetric.SHOWDOWN_WIN_RATE: 0.25,
                EvaluationMetric.PFR: 0.20,
                EvaluationMetric.AGGRESSION_FACTOR: 0.15,
            }
        )


@dataclass
class MetricScore:
    """Qualificação de uma métrica individual com nota (0-100) e tier."""

    metric: EvaluationMetric
    raw_value: float
    score: float
    tier: str
    description: str


@dataclass
class MetricQualificationCard:
    """Boletim consolidado de qualificação do agente."""

    overall_fitness: float
    overall_tier: str
    target_focus: Optional[str]
    individual_scores: Dict[str, MetricScore]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_fitness": round(self.overall_fitness, 2),
            "overall_tier": self.overall_tier,
            "target_focus": self.target_focus,
            "individual_scores": {
                k: {
                    "raw_value": round(v.raw_value, 2),
                    "score": round(v.score, 2),
                    "tier": v.tier,
                    "description": v.description,
                }
                for k, v in self.individual_scores.items()
            },
        }


def _tier_from_score(score: float) -> str:
    """Converte pontuação normalizada de 0 a 100 em tier acadêmico."""
    if score >= 90.0:
        return "S (Elite)"
    elif score >= 75.0:
        return "A (Mestre)"
    elif score >= 60.0:
        return "B (Competitivo)"
    elif score >= 45.0:
        return "C (Intermediário)"
    else:
        return "D (Iniciante)"


def score_bb_per_100(val: float) -> float:
    """Normaliza BB/100 em escala 0 a 100 via sigmoide centrada."""
    # Breakeven (0 BB/100) = 50 pts; +35 BB/100 ~ 85 pts; -35 BB/100 ~ 15 pts
    sig = 1.0 / (1.0 + math.exp(-0.06 * val))
    return max(0.0, min(100.0, sig * 100.0))


def score_win_rate(val: float, num_players: int = 6) -> float:
    """Normaliza Win Rate (%) em relação à expectativa teórica da mesa."""
    expected = 100.0 / max(2, num_players)
    if val <= 0:
        return 0.0
    ratio = val / expected
    score = ratio * 50.0
    return max(0.0, min(100.0, score))


def score_bluff_success_rate(val: float) -> float:
    """Normaliza a Taxa de Sucesso dos Blefes (0 a 100%)."""
    # 0% = 10 pts; 35% (breakeven teórico) = 50 pts; 60% = 85 pts; 75%+ = 100 pts
    if val <= 0:
        return 10.0
    sig = 1.0 / (1.0 + math.exp(-0.08 * (val - 35.0)))
    return max(0.0, min(100.0, sig * 100.0))


def score_aggression_factor(val: float) -> float:
    """Normaliza Fator de Agressão. O ponto ótimo situa-se entre 2.2 e 3.4."""
    if val <= 0.2:
        return 15.0
    # Distribuição em sino centrada em 2.8 com desvio padrão 1.0
    optimal = 2.8
    dist = abs(val - optimal)
    score = 100.0 * math.exp(-0.5 * (dist / 1.1) ** 2)
    return max(0.0, min(100.0, score))


def score_fold_equity(val: float) -> float:
    """Normaliza percentual de Fold Equity realizado na prática (0 a 100%)."""
    # 0% = 10 pts; 45% = 65 pts; 65%+ = 95+ pts
    sig = 1.0 / (1.0 + math.exp(-0.07 * (val - 35.0)))
    return max(0.0, min(100.0, sig * 100.0))


def score_vpip(val: float) -> float:
    """Normaliza VPIP (Voluntarily Put in Pot). Faixa ideal: 18% a 28%."""
    optimal = 23.0
    dist = abs(val - optimal)
    score = 100.0 * math.exp(-0.5 * (dist / 8.0) ** 2)
    return max(0.0, min(100.0, score))


def score_pfr(val: float) -> float:
    """Normaliza PFR (Pre-Flop Raise). Faixa ideal: 14% a 22%."""
    optimal = 18.0
    dist = abs(val - optimal)
    score = 100.0 * math.exp(-0.5 * (dist / 6.0) ** 2)
    return max(0.0, min(100.0, score))


def score_showdown_win_rate(val: float) -> float:
    """Normaliza Showdown Win Rate (%). 50% = 50 pts; 65%+ = 85+ pts."""
    sig = 1.0 / (1.0 + math.exp(-0.08 * (val - 50.0)))
    return max(0.0, min(100.0, sig * 100.0))


def score_net_chips(val: int, starting_stack: int = 1000) -> float:
    """Normaliza o saldo líquido de fichas."""
    bb_equiv = val / 20.0
    return score_bb_per_100(bb_equiv)


class FitnessEvaluator:
    """Motor de avaliação analítica que qualifica métricas individuais."""

    def __init__(
        self,
        weights: Optional[MetricWeights] = None,
        num_players: int = 6,
    ) -> None:
        self.weights: MetricWeights = (
            weights if weights is not None else MetricWeights.preset_balanced()
        )
        self.num_players: int = num_players

    def evaluate(
        self, metrics: AgentPerformanceMetrics
    ) -> MetricQualificationCard:
        """Gera o boletim completo qualificando cada métrica individualmente."""
        ind_scores: Dict[str, MetricScore] = {}

        # 1. BB/100
        s_bb = score_bb_per_100(metrics.bb_per_100)
        ind_scores[EvaluationMetric.BB_PER_100.value] = MetricScore(
            metric=EvaluationMetric.BB_PER_100,
            raw_value=metrics.bb_per_100,
            score=s_bb,
            tier=_tier_from_score(s_bb),
            description=(
                "Lucratividade líquida padronizada em Big Blinds a cada 100 mãos."
            ),
        )

        # 2. Win Rate
        s_wr = score_win_rate(metrics.win_rate, self.num_players)
        ind_scores[EvaluationMetric.WIN_RATE.value] = MetricScore(
            metric=EvaluationMetric.WIN_RATE,
            raw_value=metrics.win_rate,
            score=s_wr,
            tier=_tier_from_score(s_wr),
            description="Taxa percentual de mãos vencidas na mesa.",
        )

        # 3. Bluff Success Rate
        s_bluff = score_bluff_success_rate(metrics.bluff_success_rate)
        ind_scores[EvaluationMetric.BLUFF_SUCCESS_RATE.value] = MetricScore(
            metric=EvaluationMetric.BLUFF_SUCCESS_RATE,
            raw_value=metrics.bluff_success_rate,
            score=s_bluff,
            tier=_tier_from_score(s_bluff),
            description=(
                "Percentual de blefes que forçaram fold e venceram sem showdown."
            ),
        )

        # 4. Aggression Factor
        s_af = score_aggression_factor(metrics.aggression_factor)
        ind_scores[EvaluationMetric.AGGRESSION_FACTOR.value] = MetricScore(
            metric=EvaluationMetric.AGGRESSION_FACTOR,
            raw_value=metrics.aggression_factor,
            score=s_af,
            tier=_tier_from_score(s_af),
            description=(
                "Razão de equilíbrio entre apostas/raises ofensivos e calls passivos."
            ),
        )

        # 5. Fold Equity Realized
        s_fe = score_fold_equity(metrics.fold_equity_realized)
        ind_scores[EvaluationMetric.FOLD_EQUITY_REALIZED.value] = MetricScore(
            metric=EvaluationMetric.FOLD_EQUITY_REALIZED,
            raw_value=metrics.fold_equity_realized,
            score=s_fe,
            tier=_tier_from_score(s_fe),
            description="Eficácia prática em induzir desistência imediata dos rivais.",
        )

        # 6. VPIP
        s_vpip = score_vpip(metrics.vpip)
        ind_scores[EvaluationMetric.VPIP.value] = MetricScore(
            metric=EvaluationMetric.VPIP,
            raw_value=metrics.vpip,
            score=s_vpip,
            tier=_tier_from_score(s_vpip),
            description="Percentual de potes disputados voluntariamente pré-flop.",
        )

        # 7. PFR
        s_pfr = score_pfr(metrics.pfr)
        ind_scores[EvaluationMetric.PFR.value] = MetricScore(
            metric=EvaluationMetric.PFR,
            raw_value=metrics.pfr,
            score=s_pfr,
            tier=_tier_from_score(s_pfr),
            description="Frequência de aumento agressivo pré-flop (Pre-Flop Raise).",
        )

        # 8. Showdown Win Rate
        s_sd = score_showdown_win_rate(metrics.showdown_win_rate)
        ind_scores[EvaluationMetric.SHOWDOWN_WIN_RATE.value] = MetricScore(
            metric=EvaluationMetric.SHOWDOWN_WIN_RATE,
            raw_value=metrics.showdown_win_rate,
            score=s_sd,
            tier=_tier_from_score(s_sd),
            description=(
                "Taxa de vitória quando a mão atinge a abertura final das cartas."
            ),
        )

        # 9. Net Chips
        s_nc = score_net_chips(metrics.net_chips)
        ind_scores[EvaluationMetric.NET_CHIPS.value] = MetricScore(
            metric=EvaluationMetric.NET_CHIPS,
            raw_value=float(metrics.net_chips),
            score=s_nc,
            tier=_tier_from_score(s_nc),
            description="Variação líquida absoluta do stack em fichas.",
        )

        # Calcula o fitness composto ponderado
        total_score = 0.0
        active_weight = 0.0
        single_focus: Optional[str] = None

        for metric, weight in self.weights.weights.items():
            if weight > 0:
                m_score = ind_scores.get(metric.value)
                if m_score:
                    total_score += m_score.score * weight
                    active_weight += weight
                if weight >= 0.99:
                    single_focus = metric.value

        composite_fitness = (
            total_score / active_weight if active_weight > 0 else 50.0
        )

        return MetricQualificationCard(
            overall_fitness=round(composite_fitness, 2),
            overall_tier=_tier_from_score(composite_fitness),
            target_focus=single_focus,
            individual_scores=ind_scores,
        )
