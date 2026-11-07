"""Agente Matemático Definitivo para Texas Hold'em.

Unifica e aprimora a versão analítica clássica (Alberto) e a versão GTO/XAI (Gustavo - GH):
1. Avaliação rigorosa de equidade Monte Carlo com detecção precisa de outs (Flop/Turn).
2. Consciência posicional real (Early, Middle, Late, Blinds) e fórmula Chen calibrada.
3. Dimensionamento ótimo de apostas e aumentos via Critério de Kelly Fracionário.
4. Cálculo exato de Pot Odds diretas e Implied Odds dinâmicas por stack efetivo.
5. Controle de pote multiway para contenção de variância no pós-flop e river.
6. Tenacidade de showdown (bluff catching) com jogos feitos contra apostas moderadas.
7. Disciplina absoluta contra overbets (-EV fold imediato, sem leaks de calling station).
8. Payload explicativo cognitivo completo (XAI) para Quartz e telemetria de pesquisa.
"""

from collections import Counter
from dataclasses import asdict, dataclass
from enum import Enum
import json
from pathlib import Path
import random
import sys
from typing import Any, Dict, Optional, Sequence, Tuple

# Garante resolução dos módulos a partir da raiz do repositório
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.agents.base import BaseAgent  # noqa: E402
from src.engine.deck import Card, Rank  # noqa: E402
from src.engine.equity import (  # noqa: E402
    calculate_pot_odds,
    estimate_hand_equity,
    has_flush_draw,
    has_overcards,
    has_straight_draw,
)
from src.engine.hand_eval import evaluate_hand  # noqa: E402
from src.engine.table import Action, ActionType, Street, Table  # noqa: E402


class GhPosition(Enum):
    """Categorias de posição relativa na mesa de poker."""

    EARLY = "Early"
    MIDDLE = "Middle"
    LATE = "Late"
    BLINDS = "Blinds"


@dataclass(frozen=True)
class GhCognitiveMetrics:
    """Métricas explicáveis para a Visão Micro da Rede Neural e Auditoria XAI."""

    raw_equity: float
    adjusted_equity: float
    direct_pot_odds: float
    implied_odds: float
    expected_value_call: float
    expected_value_raise: float
    kelly_fraction: float
    outs_count: int
    position_name: str
    tactical_rationale: str
    formula_reference: str


@dataclass(frozen=True)
class MathematicalDecision:
    """Estrutura formal e completa da decisão analítica do Agente Matemático."""

    action_type: ActionType
    amount: int
    equity: float
    pot_odds: float
    expected_value: float
    outs: int
    reason: str
    metrics: GhCognitiveMetrics


# Alias para 100% de retrocompatibilidade com o ecossistema GH
GhMathDecision = MathematicalDecision


@dataclass
class MathematicalParameters:
    """Hiperparâmetros calibráveis que regem as decisões analíticas e probabilísticas."""

    raise_equity_threshold: float = 0.60
    call_ev_margin: float = 0.03
    draw_weight: float = 1.0
    bet_sizing_factor: float = 0.50
    kelly_fraction_limit: float = 0.25
    num_simulations: int = 250

    @property
    def base_threshold(self) -> float:
        return self.raise_equity_threshold

    @base_threshold.setter
    def base_threshold(self, value: float) -> None:
        self.raise_equity_threshold = max(0.40, min(0.90, float(value)))

    def to_dict(self) -> Dict[str, Any]:
        """Converte hiperparâmetros em dicionário serializável."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MathematicalParameters":
        """Instancia hiperparâmetros a partir de dicionário com validação e clamping."""
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered: Dict[str, Any] = {}
        for k, v in data.items():
            if k == "base_threshold":
                filtered["raise_equity_threshold"] = float(v)
            elif k in valid_keys:
                filtered[k] = int(v) if k == "num_simulations" else float(v)
        return cls(**filtered)


GhMathParameters = MathematicalParameters


class MathematicalAgent(BaseAgent):
    """Agente Matemático Definitivo.

    Combina precisão de Monte Carlo, ranges posicionais RFI, teoria das Implied Odds,
    Critério de Kelly fracionário e explicabilidade XAI de ponta a ponta.
    """

    def __init__(
        self,
        player_id: str,
        name: str = "Agente Matemático Definitivo",
        raise_equity_threshold: float = 0.60,
        call_ev_margin: float = 0.03,
        draw_weight: float = 1.0,
        bet_sizing_factor: float = 0.50,
        kelly_fraction_limit: float = 0.25,
        num_simulations: int = 250,
        base_threshold: Optional[float] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        effective_threshold = base_threshold if base_threshold is not None else raise_equity_threshold
        self.params = MathematicalParameters(
            raise_equity_threshold=max(0.40, min(0.80, float(effective_threshold))),
            call_ev_margin=max(-0.10, min(0.20, float(call_ev_margin))),
            draw_weight=max(0.0, min(2.5, float(draw_weight))),
            bet_sizing_factor=max(0.20, min(1.5, float(bet_sizing_factor))),
            kelly_fraction_limit=max(0.10, min(0.50, float(kelly_fraction_limit))),
            num_simulations=max(100, min(1000, int(num_simulations))),
        )
        self.rng: random.Random = rng if rng is not None else random.Random()

        # Telemetria acumulada de partidas
        self.hands_played: int = 0
        self.vpip_actions: int = 0
        self.pfr_actions: int = 0
        self.bets_and_raises: int = 0
        self.calls: int = 0
        self.folds: int = 0
        self.checks: int = 0
        self.last_decision: Optional[MathematicalDecision] = None

    # Getters e Setters com compatibilidade total
    @property
    def raise_equity_threshold(self) -> float:
        return self.params.raise_equity_threshold

    @raise_equity_threshold.setter
    def raise_equity_threshold(self, value: float) -> None:
        self.params.raise_equity_threshold = max(0.40, min(0.90, float(value)))

    @property
    def base_threshold(self) -> float:
        return self.params.raise_equity_threshold

    @base_threshold.setter
    def base_threshold(self, value: float) -> None:
        self.params.raise_equity_threshold = max(0.50, min(0.80, float(value)))

    @property
    def call_ev_margin(self) -> float:
        return self.params.call_ev_margin

    @call_ev_margin.setter
    def call_ev_margin(self, value: float) -> None:
        self.params.call_ev_margin = max(-0.10, min(0.20, float(value)))

    @property
    def draw_weight(self) -> float:
        return self.params.draw_weight

    @draw_weight.setter
    def draw_weight(self, value: float) -> None:
        self.params.draw_weight = max(0.0, min(2.5, float(value)))

    @property
    def bet_sizing_factor(self) -> float:
        return self.params.bet_sizing_factor

    @bet_sizing_factor.setter
    def bet_sizing_factor(self, value: float) -> None:
        self.params.bet_sizing_factor = max(0.20, min(1.5, float(value)))

    @property
    def kelly_fraction_limit(self) -> float:
        return self.params.kelly_fraction_limit

    @kelly_fraction_limit.setter
    def kelly_fraction_limit(self, value: float) -> None:
        self.params.kelly_fraction_limit = max(0.10, min(0.50, float(value)))

    @property
    def num_simulations(self) -> int:
        return self.params.num_simulations

    @num_simulations.setter
    def num_simulations(self, value: int) -> None:
        self.params.num_simulations = max(100, min(1000, int(value)))

    @property
    def aggression_factor(self) -> float:
        """Razão clássica entre ações agressivas (bets/raises) e passivas (calls)."""
        if self.calls == 0:
            return float(self.bets_and_raises)
        return round(self.bets_and_raises / self.calls, 2)

    def export_parameters(self) -> Dict[str, Any]:
        """Exporta os hiperparâmetros atuais para calibração/treino."""
        return self.params.to_dict()

    def load_parameters(self, params: Dict[str, Any]) -> None:
        """Aplica novos hiperparâmetros resultantes de rotinas de treino."""
        self.params = MathematicalParameters.from_dict(params)

    def save_parameters(self, filepath: str | Path) -> None:
        """Persiste os hiperparâmetros em arquivo JSON."""
        target = Path(filepath)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.export_parameters(), f, indent=2)

    def load_parameters_file(self, filepath: str | Path) -> None:
        """Carrega hiperparâmetros pré-treinados de arquivo JSON."""
        target = Path(filepath)
        if not target.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {target}")
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load_parameters(data)

    def decide_action(self, table: Table) -> Action:
        """Determina a ação ótima na mesa com base em probabilidade, Kelly e EV."""
        legal_actions = table.get_legal_actions(self.player_id)
        if not legal_actions:
            return Action(self.player_id, ActionType.FOLD)

        player = next(p for p in table.players if p.player_id == self.player_id)
        if player.hole_cards is None:
            return Action(self.player_id, ActionType.FOLD)

        to_call = table.current_highest_bet - player.current_bet
        active_opponents = max(
            1,
            sum(
                1
                for p in table.players
                if p.is_active and p.player_id != self.player_id
            ),
        )
        position = self._determine_position(table, self.player_id)

        # Determina o stack efetivo restante dos oponentes ativos
        other_stacks = [
            p.stack
            for p in table.players
            if p.is_active and p.player_id != self.player_id
        ]
        effective_stack = min(player.stack, max(other_stacks)) if other_stacks else player.stack

        decision = self.evaluate_state(
            hole_cards=player.hole_cards,
            community_cards=table.community_cards,
            pot_size=table.pot_manager.total_pot,
            to_call=to_call,
            player_stack=player.stack,
            player_current_bet=player.current_bet,
            current_highest_bet=table.current_highest_bet,
            min_raise=table.min_raise,
            big_blind=table.big_blind,
            num_opponents=active_opponents,
            legal_actions=legal_actions,
            street=table.street,
            position=position,
            effective_stack_behind=effective_stack,
        )

        self._track_decision_telemetry(decision.action_type, table.street)
        self.last_decision = decision
        return Action(
            player_id=self.player_id,
            action_type=decision.action_type,
            amount=decision.amount,
        )

    def evaluate_cognitive_state(self, table: Table) -> MathematicalDecision:
        """Endpoint para interface visual Quartz (XAI Micro Vision)."""
        self.decide_action(table)
        assert self.last_decision is not None
        return self.last_decision

    def evaluate_state(
        self,
        hole_cards: Tuple[Card, Card],
        community_cards: Sequence[Card],
        pot_size: int,
        to_call: int,
        player_stack: int,
        player_current_bet: int,
        current_highest_bet: int,
        min_raise: int,
        big_blind: int,
        num_opponents: int,
        legal_actions: Sequence[ActionType],
        street: Optional[Street] = None,
        position: Optional[GhPosition] = None,
        effective_stack_behind: Optional[int] = None,
        **kwargs: Any,
    ) -> MathematicalDecision:
        """Calcula equidade, Kelly, EV e retorna a decisão matemática estruturada."""
        pos = position if position is not None else GhPosition.LATE
        eff_stack = effective_stack_behind if effective_stack_behind is not None else player_stack
        is_preflop = len(community_cards) == 0 or street == Street.PREFLOP

        # 1. Equidade e contagem de outs com Chen/Monte Carlo
        adjusted_equity, outs = self._calculate_equity_and_outs(
            hole_cards=hole_cards,
            community_cards=community_cards,
            num_opponents=num_opponents,
            position=pos,
        )
        raw_equity = adjusted_equity

        # 2. Pot Odds diretas e Odds implícitas
        direct_pot_odds = (
            to_call / max(1, pot_size + to_call) if to_call > 0 else 0.0
        )
        implied_odds = self._calculate_implied_odds(
            to_call=to_call,
            pot_size=pot_size,
            outs=outs,
            effective_stack=eff_stack,
            street=street,
        )

        # 3. Expectativa Matemática de Ganho (EV)
        ev_call = (adjusted_equity * (pot_size + to_call)) - to_call if to_call > 0 else 0.0
        ev_raise = (adjusted_equity * (pot_size + to_call + min_raise)) - (to_call + min_raise)

        # 4. Critério de Kelly Fracionário
        kelly_fraction = self._compute_kelly_fraction(
            equity=adjusted_equity, pot_size=pot_size, to_call=to_call
        )

        # 5. Avaliação da força da mão
        all_cards = list(hole_cards) + list(community_cards)
        score = evaluate_hand(all_cards) if len(all_cards) >= 5 else None
        hand_rank_val = score.hand_rank.value if score else 1
        comb_desc = score.description if score else ""

        # Preflop score combinatório
        preflop_score = self._evaluate_gh_preflop(hole_cards, pos) if is_preflop else 0.0

        if to_call == 0:
            return self._decide_zero_cost(
                adjusted_equity=adjusted_equity,
                raw_equity=raw_equity,
                direct_pot_odds=direct_pot_odds,
                implied_odds=implied_odds,
                ev_call=ev_call,
                ev_raise=ev_raise,
                kelly_fraction=kelly_fraction,
                outs=outs,
                pot_size=pot_size,
                player_stack=player_stack,
                big_blind=big_blind,
                min_raise=min_raise,
                position=pos,
                legal_actions=legal_actions,
                street=street,
                num_opponents=num_opponents,
                hand_rank_val=hand_rank_val,
            )

        return self._decide_facing_cost(
            adjusted_equity=adjusted_equity,
            raw_equity=raw_equity,
            direct_pot_odds=direct_pot_odds,
            implied_odds=implied_odds,
            ev_call=ev_call,
            ev_raise=ev_raise,
            kelly_fraction=kelly_fraction,
            outs=outs,
            pot_size=pot_size,
            to_call=to_call,
            player_stack=player_stack,
            player_current_bet=player_current_bet,
            current_highest_bet=current_highest_bet,
            min_raise=min_raise,
            position=pos,
            legal_actions=legal_actions,
            street=street,
            num_opponents=num_opponents,
            hand_rank_val=hand_rank_val,
            comb_desc=comb_desc,
            is_preflop=is_preflop,
            preflop_score=preflop_score,
            big_blind=big_blind,
        )

    def calculate_effective_equity(
        self,
        hole_cards: Tuple[Card, Card],
        community_cards: Sequence[Card],
        num_opponents: int = 1,
    ) -> Tuple[float, int]:
        """Calcula a equidade ajustada incluindo Monte Carlo e outs de draws."""
        return self._calculate_equity_and_outs(
            hole_cards=hole_cards,
            community_cards=community_cards,
            num_opponents=num_opponents,
            position=GhPosition.LATE,
        )

    def _decide_zero_cost(
        self,
        adjusted_equity: float,
        raw_equity: float,
        direct_pot_odds: float,
        implied_odds: float,
        ev_call: float,
        ev_raise: float,
        kelly_fraction: float,
        outs: int,
        pot_size: int,
        player_stack: int,
        big_blind: int,
        min_raise: int,
        position: GhPosition,
        legal_actions: Sequence[ActionType],
        street: Optional[Street] = None,
        num_opponents: int = 1,
        hand_rank_val: int = 1,
    ) -> MathematicalDecision:
        """Determina aposta por valor ou check gratuito com controle multiway."""
        # 1. Controle de Pote Multiway no River / Pós-Flop com mãos moderadas
        if (
            num_opponents >= 2
            and (
                street == Street.RIVER
                or (street in (Street.FLOP, Street.TURN) and hand_rank_val < 3)
            )
            and adjusted_equity < (self.raise_equity_threshold + 0.10)
        ):
            metrics = GhCognitiveMetrics(
                raw_equity=raw_equity,
                adjusted_equity=adjusted_equity,
                direct_pot_odds=direct_pot_odds,
                implied_odds=implied_odds,
                expected_value_call=ev_call,
                expected_value_raise=ev_raise,
                kelly_fraction=kelly_fraction,
                outs_count=outs,
                position_name=position.value,
                tactical_rationale=(
                    "Check por controle de pote multiway no pós-flop para ver showdown sem inflar o pote"
                ),
                formula_reference="Multiway Pot Control: Check behind to minimize variance",
            )
            return MathematicalDecision(
                action_type=ActionType.CHECK,
                amount=0,
                equity=adjusted_equity,
                pot_odds=0.0,
                expected_value=0.0,
                outs=outs,
                reason="Check por controle de pote multiway no pós-flop para ver showdown",
                metrics=metrics,
            )

        has_bet_advantage = (
            adjusted_equity >= self.raise_equity_threshold
            or hand_rank_val >= 3
        )

        if ActionType.BET in legal_actions and has_bet_advantage and player_stack > 0:
            # Dimensionamento Kelly com peso de bet_sizing_factor
            sizing_ratio = max(0.33, min(1.20, kelly_fraction * 2.5 * self.bet_sizing_factor))
            target_bet = int(pot_size * sizing_ratio)
            bet_amount = min(
                player_stack, max(big_blind, min_raise, target_bet)
            )

            metrics = GhCognitiveMetrics(
                raw_equity=raw_equity,
                adjusted_equity=adjusted_equity,
                direct_pot_odds=direct_pot_odds,
                implied_odds=implied_odds,
                expected_value_call=ev_call,
                expected_value_raise=ev_raise,
                kelly_fraction=kelly_fraction,
                outs_count=outs,
                position_name=position.value,
                tactical_rationale=(
                    f"Value bet Kelly ({sizing_ratio:.0%} pot) com equidade de {adjusted_equity:.1%}"
                ),
                formula_reference="Kelly Criterion Sizing: f* = (p(b+1)-1)/b * lambda",
            )
            return MathematicalDecision(
                action_type=ActionType.BET,
                amount=bet_amount,
                equity=adjusted_equity,
                pot_odds=0.0,
                expected_value=adjusted_equity * pot_size,
                outs=outs,
                reason=f"Value bet com equidade de {adjusted_equity:.1%}",
                metrics=metrics,
            )

        # Check de Custo Zero (Preservação de Fichas)
        metrics = GhCognitiveMetrics(
            raw_equity=raw_equity,
            adjusted_equity=adjusted_equity,
            direct_pot_odds=direct_pot_odds,
            implied_odds=implied_odds,
            expected_value_call=ev_call,
            expected_value_raise=ev_raise,
            kelly_fraction=kelly_fraction,
            outs_count=outs,
            position_name=position.value,
            tactical_rationale="Check gratuito para ver a próxima carta sem custo",
            formula_reference="Zero-Cost Rule: Check when to_call == 0 and below threshold",
        )
        return MathematicalDecision(
            action_type=ActionType.CHECK,
            amount=0,
            equity=adjusted_equity,
            pot_odds=0.0,
            expected_value=0.0,
            outs=outs,
            reason="Check gratuito preservando EV",
            metrics=metrics,
        )

    def _decide_facing_cost(
        self,
        adjusted_equity: float,
        raw_equity: float,
        direct_pot_odds: float,
        implied_odds: float,
        ev_call: float,
        ev_raise: float,
        kelly_fraction: float,
        outs: int,
        pot_size: int,
        to_call: int,
        player_stack: int,
        player_current_bet: int,
        current_highest_bet: int,
        min_raise: int,
        position: GhPosition,
        legal_actions: Sequence[ActionType],
        street: Optional[Street] = None,
        num_opponents: int = 1,
        hand_rank_val: int = 1,
        comb_desc: str = "",
        is_preflop: bool = False,
        preflop_score: float = 0.0,
        big_blind: int = 20,
    ) -> MathematicalDecision:
        """Decide aumento com vantagem, call por odds ou fold disciplinado."""
        can_raise = ActionType.RAISE in legal_actions
        can_call = ActionType.CALL in legal_actions or ActionType.ALL_IN in legal_actions
        call_action_type = ActionType.CALL if ActionType.CALL in legal_actions else ActionType.ALL_IN

        # 1. Aumento por Valor com Vantagem Sólida
        strong_advantage = False
        if is_preflop:
            strong_advantage = (
                preflop_score >= 0.75
                or (adjusted_equity >= (self.raise_equity_threshold + 0.08))
            )
        else:
            strong_advantage = (
                adjusted_equity >= (self.raise_equity_threshold + 0.06)
                or hand_rank_val >= 4
            )

        if can_raise and strong_advantage and player_stack > to_call:
            min_req = current_highest_bet + min_raise
            sizing_ratio = max(0.50, min(1.50, kelly_fraction * 3.0 * self.bet_sizing_factor))
            raise_inc = max(min_raise, int(pot_size * sizing_ratio))
            total_target = current_highest_bet + raise_inc
            raise_amount = min(
                player_current_bet + player_stack, max(min_req, total_target)
            )

            metrics = GhCognitiveMetrics(
                raw_equity=raw_equity,
                adjusted_equity=adjusted_equity,
                direct_pot_odds=direct_pot_odds,
                implied_odds=implied_odds,
                expected_value_call=ev_call,
                expected_value_raise=ev_raise,
                kelly_fraction=kelly_fraction,
                outs_count=outs,
                position_name=position.value,
                tactical_rationale=f"+EV Raise: Raise por valor com equidade {adjusted_equity:.1%}",
                formula_reference="Value Raise: adjusted_equity >= base_threshold + margin",
            )
            return MathematicalDecision(
                action_type=ActionType.RAISE,
                amount=raise_amount,
                equity=adjusted_equity,
                pot_odds=direct_pot_odds,
                expected_value=ev_raise,
                outs=outs,
                reason=f"+EV Raise: Raise por valor com equidade de {adjusted_equity:.1%}",
                metrics=metrics,
            )

        # 2. Avaliação de Call Lucrativo, Implied Odds e Bluff Catching
        if is_preflop:
            # Regras refinadas pré-flop
            if preflop_score < 0.28:
                call_ok = False
            elif to_call <= big_blind and preflop_score >= 0.28:
                call_ok = True
            elif to_call <= int(big_blind * 2.5) and preflop_score >= 0.38:
                call_ok = True
            elif to_call > 3 * big_blind:
                # Contra overbets pré-flop (> 3 BB), só paga com cartas de valor e odds reais
                call_ok = (
                    preflop_score >= 0.65
                    and adjusted_equity >= (direct_pot_odds - self.call_ev_margin)
                )
            else:
                call_ok = adjusted_equity >= (direct_pot_odds - self.call_ev_margin)
            implied_call_ok = False
            is_bluff_catch = False
        else:
            has_pair = hand_rank_val >= 2
            is_mod_bet = to_call <= max(big_blind * 3, int(pot_size * 0.45))
            is_bluff_catch = (
                has_pair
                and is_mod_bet
                and (street in (Street.TURN, Street.RIVER))
                and num_opponents <= 2
            )

            bluff_margin = 0.08 if is_bluff_catch else 0.0
            direct_call_ok = adjusted_equity >= (direct_pot_odds - self.call_ev_margin - bluff_margin)
            implied_call_ok = (
                (outs >= 8)
                and (street in (Street.FLOP, Street.TURN))
                and (adjusted_equity >= implied_odds)
            )
            call_ok = direct_call_ok or implied_call_ok

            # No River sem jogo feito, nunca paga apostas
            if street == Street.RIVER and not has_pair and to_call > 0:
                call_ok = False

        if can_call and call_ok:
            if is_bluff_catch:
                call_reason = (
                    f"+EV Call: Bluff Catch com Par ({comb_desc or 'Feito'}) "
                    f"contra aposta moderada ({to_call} fichas)"
                )
            elif implied_call_ok:
                call_reason = (
                    f"+EV Implied Call: {outs} outs com Implied Odds favoráveis ({implied_odds:.1%})"
                )
            else:
                call_reason = (
                    f"+EV Direct Call: Equidade {adjusted_equity:.1%} >= Pot Odds {direct_pot_odds:.1%}"
                )

            metrics = GhCognitiveMetrics(
                raw_equity=raw_equity,
                adjusted_equity=adjusted_equity,
                direct_pot_odds=direct_pot_odds,
                implied_odds=implied_odds,
                expected_value_call=ev_call,
                expected_value_raise=ev_raise,
                kelly_fraction=kelly_fraction,
                outs_count=outs,
                position_name=position.value,
                tactical_rationale=call_reason,
                formula_reference="Call Condition: adjusted_equity >= min(direct, implied)",
            )
            return MathematicalDecision(
                action_type=call_action_type,
                amount=to_call if call_action_type == ActionType.CALL else player_stack,
                equity=adjusted_equity,
                pot_odds=direct_pot_odds,
                expected_value=ev_call,
                outs=outs,
                reason=call_reason,
                metrics=metrics,
            )

        # 3. Check de Segurança se Legal (evita fold acidental)
        if ActionType.CHECK in legal_actions:
            metrics = GhCognitiveMetrics(
                raw_equity=raw_equity,
                adjusted_equity=adjusted_equity,
                direct_pot_odds=direct_pot_odds,
                implied_odds=implied_odds,
                expected_value_call=ev_call,
                expected_value_raise=ev_raise,
                kelly_fraction=kelly_fraction,
                outs_count=outs,
                position_name=position.value,
                tactical_rationale="Check de segurança legal",
                formula_reference="Fallback Check",
            )
            return MathematicalDecision(
                action_type=ActionType.CHECK,
                amount=0,
                equity=adjusted_equity,
                pot_odds=direct_pot_odds,
                expected_value=0.0,
                outs=outs,
                reason="Check gratuito preservando EV",
                metrics=metrics,
            )

        # 4. Fold Disciplinado por Retorno Negativo (-EV Fold)
        fold_reason = (
            f"-EV Fold: Equidade {adjusted_equity:.1%} < Pot Odds {direct_pot_odds:.1%}"
        )
        metrics = GhCognitiveMetrics(
            raw_equity=raw_equity,
            adjusted_equity=adjusted_equity,
            direct_pot_odds=direct_pot_odds,
            implied_odds=implied_odds,
            expected_value_call=ev_call,
            expected_value_raise=ev_raise,
            kelly_fraction=kelly_fraction,
            outs_count=outs,
            position_name=position.value,
            tactical_rationale=fold_reason,
            formula_reference="Disciplined Fold: expected_value < 0 and no implied odds",
        )
        return MathematicalDecision(
            action_type=ActionType.FOLD,
            amount=0,
            equity=adjusted_equity,
            pot_odds=direct_pot_odds,
            expected_value=ev_call,
            outs=outs,
            reason=fold_reason,
            metrics=metrics,
        )

    def _calculate_equity_and_outs(
        self,
        hole_cards: Tuple[Card, Card],
        community_cards: Sequence[Card],
        num_opponents: int,
        position: GhPosition,
    ) -> Tuple[float, int]:
        """Calcula equidade com Chen/Monte Carlo e outs de evolução."""
        capped_opponents = min(3, max(1, num_opponents))
        sims = max(80, min(250, self.num_simulations))

        if not community_cards:
            preflop_score = self._evaluate_gh_preflop(hole_cards, position)
            sim_res = estimate_hand_equity(
                hole_cards=hole_cards,
                community_cards=(),
                num_opponents=capped_opponents,
                num_simulations=sims,
                rng=self.rng,
            )
            blended = (preflop_score * 0.45) + (sim_res.equity * 0.55)
            return blended, 0

        sim_res = estimate_hand_equity(
            hole_cards=hole_cards,
            community_cards=community_cards,
            num_opponents=capped_opponents,
            num_simulations=sims,
            rng=self.rng,
        )

        outs = self._count_outs(hole_cards, community_cards)

        # Regra de 4 e 2
        cards_to_come = 5 - len(community_cards)
        draw_prob = (
            outs * (0.04 if cards_to_come == 2 else 0.02)
            if cards_to_come in (1, 2)
            else 0.0
        )

        if outs >= 4:
            adjusted_equity = max(
                sim_res.equity,
                min(0.65, (sim_res.equity * 0.60) + (draw_prob * self.draw_weight * 0.40)),
            )
        else:
            adjusted_equity = sim_res.equity

        return adjusted_equity, outs

    def _evaluate_gh_preflop(
        self, hole_cards: Tuple[Card, Card], position: GhPosition
    ) -> float:
        """Score pré-flop calibrado com Chen Formula e ranges posicionais."""
        c1, c2 = hole_cards
        high_r = max(c1.rank.value, c2.rank.value)
        low_r = min(c1.rank.value, c2.rank.value)
        is_pair = c1.rank == c2.rank
        is_suited = c1.suit == c2.suit
        gap = high_r - low_r

        # Chen Formula base score
        if is_pair:
            pair_pts = {
                Rank.ACE.value: 20.0,
                Rank.KING.value: 16.0,
                Rank.QUEEN.value: 14.0,
                Rank.JACK.value: 12.0,
                Rank.TEN.value: 10.0,
            }
            score_pts = pair_pts.get(high_r, max(6.0, high_r * 1.1))
        else:
            rank_pts = {
                Rank.ACE.value: 10.0,
                Rank.KING.value: 8.0,
                Rank.QUEEN.value: 7.0,
                Rank.JACK.value: 6.0,
                Rank.TEN.value: 5.0,
            }
            score_pts = rank_pts.get(high_r, high_r / 2.0)

            if gap == 1:
                score_pts -= 1.0
            elif gap == 2:
                score_pts -= 2.0
            elif gap == 3:
                score_pts -= 4.0
            else:
                score_pts -= 5.0

            if gap in (0, 1) and high_r < Rank.QUEEN.value:
                score_pts += 1.0

            if is_suited:
                score_pts += 2.0

        raw_score = max(0.5, score_pts) / 20.0

        if position == GhPosition.LATE:
            raw_score += 0.06
        elif position == GhPosition.EARLY:
            raw_score -= 0.04

        return min(0.95, max(0.05, raw_score))

    def _evaluate_preflop_combinatorics(self, hole_cards: Tuple[Card, Card]) -> float:
        """Alias de compatibilidade."""
        return self._evaluate_gh_preflop(hole_cards, GhPosition.LATE)

    def _calculate_implied_odds(
        self,
        to_call: int,
        pot_size: int,
        outs: int,
        effective_stack: int,
        street: Optional[Street],
    ) -> float:
        """Calcula as odds implícitas considerando fichas futuras do adversário."""
        if to_call <= 0:
            return 0.0
        if outs < 4 or street == Street.RIVER:
            return to_call / max(1, pot_size + to_call)

        discounted_future_chips = min(effective_stack * 0.35, pot_size * 1.5)
        implied_pot = pot_size + to_call + int(discounted_future_chips)
        return to_call / max(1, implied_pot)

    def _compute_kelly_fraction(
        self, equity: float, pot_size: int, to_call: int
    ) -> float:
        """Calcula a fração ótima de aposta baseada na fórmula de Kelly."""
        b = max(1.0, pot_size / max(1, to_call))
        p = equity
        q = 1.0 - p

        raw_kelly = (b * p - q) / b
        if raw_kelly <= 0:
            return 0.0

        return min(self.kelly_fraction_limit, raw_kelly * self.kelly_fraction_limit)

    def _count_outs(
        self, hole_cards: Tuple[Card, Card], community_cards: Sequence[Card]
    ) -> int:
        """Estima a quantidade de outs para evolução da mão."""
        if len(community_cards) >= 5 or len(community_cards) < 3:
            return 0

        combined = list(hole_cards) + list(community_cards)
        outs = 0

        flush_draw = has_flush_draw(combined)
        straight_draw = has_straight_draw(combined)

        if flush_draw and straight_draw:
            outs = 15
        elif flush_draw:
            outs = 9
        elif straight_draw:
            ranks = sorted({c.rank.value for c in combined})
            if 14 in ranks:
                ranks = [1] + ranks

            is_open_ended = False
            for i in range(len(ranks) - 3):
                window = ranks[i : i + 4]
                if window[3] - window[0] == 3:
                    is_open_ended = True
                    break

            outs = 8 if is_open_ended else 4

        if outs == 0 and has_overcards(hole_cards, community_cards):
            outs = 6

        return outs

    def _calculate_draw_outs(
        self, hole_cards: Tuple[Card, Card], community_cards: Sequence[Card]
    ) -> int:
        """Alias de compatibilidade."""
        return self._count_outs(hole_cards, community_cards)

    def _determine_position(self, table: Table, my_id: str) -> GhPosition:
        """Determina a posição relativa na mesa (Early, Middle, Late ou Blinds)."""
        active_ids = [
            p.player_id for p in table.players if p.is_active or p.player_id == my_id
        ]
        if not active_ids or len(active_ids) <= 1:
            return GhPosition.MIDDLE

        try:
            my_idx = active_ids.index(my_id)
        except ValueError:
            return GhPosition.MIDDLE

        btn_pos = getattr(table, "button_idx", 0)
        btn_id = (
            table.players[btn_pos].player_id
            if 0 <= btn_pos < len(table.players)
            else active_ids[0]
        )

        total = len(active_ids)
        if total <= 2:
            return (
                GhPosition.LATE
                if my_id == btn_id
                else GhPosition.BLINDS
            )

        try:
            btn_idx = active_ids.index(btn_id)
        except ValueError:
            btn_idx = 0

        dist_from_button = (btn_idx - my_idx) % total
        if dist_from_button in (0, 1):
            return GhPosition.LATE
        if dist_from_button in (total - 1, total - 2):
            return GhPosition.BLINDS
        return GhPosition.MIDDLE

    def _track_decision_telemetry(
        self, action_type: ActionType, street: Street
    ) -> None:
        """Atualiza contadores estatísticos para métricas agregadas."""
        self.hands_played += 1
        if street == Street.PREFLOP:
            if action_type in (ActionType.CALL, ActionType.RAISE):
                self.vpip_actions += 1
            if action_type == ActionType.RAISE:
                self.pfr_actions += 1

        if action_type in (ActionType.BET, ActionType.RAISE):
            self.bets_and_raises += 1
        elif action_type == ActionType.CALL:
            self.calls += 1
        elif action_type == ActionType.CHECK:
            self.checks += 1
        elif action_type == ActionType.FOLD:
            self.folds += 1


GhMathAgent = MathematicalAgent
