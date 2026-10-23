"""Agente Matemático GH para Texas Hold'em.

Desenvolvido por Gustavo (GH) para o TCC de Inteligência Artificial e Detecção de Blefe.
Opera com cálculo de equidade ponderada, implied odds em draws, dimensionamento
otimizado via Critério de Kelly Fracionário e ranges de posição (RFI) para
eliminar a passividade e o excesso de folds pré-flop.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import random
import sys
from typing import Dict, List, Optional, Sequence, Tuple

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
    """Métricas explicáveis para a Visão Micro da Rede Neural no Quartz."""

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
class GhMathDecision:
    """Estrutura formal da decisão tomada com payload explicativo."""

    action_type: ActionType
    amount: int
    metrics: GhCognitiveMetrics


class GhMathAgent(BaseAgent):
    """Agente Matemático de alta precisão com Implied Odds e Critério de Kelly."""

    def __init__(
        self,
        player_id: str,
        name: str = "Gh Math Agent",
        base_threshold: float = 0.58,
        kelly_fraction_limit: float = 0.25,
        num_simulations: int = 250,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        self.base_threshold: float = max(0.50, min(0.80, base_threshold))
        self.kelly_fraction_limit: float = max(
            0.10, min(0.50, kelly_fraction_limit)
        )
        self.num_simulations: int = max(100, min(1000, num_simulations))
        self.rng: random.Random = rng if rng is not None else random.Random()

        # Telemetria acumulada de partidas
        self.hands_played: int = 0
        self.vpip_actions: int = 0
        self.pfr_actions: int = 0
        self.bets_and_raises: int = 0
        self.calls: int = 0
        self.folds: int = 0
        self.last_decision: Optional[GhMathDecision] = None

    def decide_action(self, table: Table) -> Action:
        """Determina a ação ótima na mesa considerando posição e odds implícitas."""
        legal_actions = table.get_legal_actions(self.player_id)
        if not legal_actions:
            return Action(self.player_id, ActionType.FOLD)

        player = next(
            (p for p in table.players if p.player_id == self.player_id), None
        )
        if player is None or player.hole_cards is None:
            return Action(self.player_id, ActionType.FOLD)

        to_call = table.current_highest_bet - player.current_bet
        active_opponents = [
            p
            for p in table.players
            if p.is_active and p.player_id != self.player_id
        ]
        num_opponents = max(1, len(active_opponents))

        # Posição relativa na mesa
        position = self._determine_position(table, player.player_id)

        # Maior stack remanescente entre oponentes para cálculo de implied odds
        max_opp_stack = max(
            (p.stack for p in active_opponents), default=player.stack
        )
        effective_stack = min(player.stack, max_opp_stack)

        decision = self.evaluate_cognitive_state(
            hole_cards=player.hole_cards,
            community_cards=table.community_cards,
            pot_size=table.pot_manager.total_pot,
            to_call=to_call,
            player_stack=player.stack,
            player_current_bet=player.current_bet,
            current_highest_bet=table.current_highest_bet,
            min_raise=table.min_raise,
            big_blind=table.big_blind,
            num_opponents=num_opponents,
            effective_stack=effective_stack,
            position=position,
            legal_actions=legal_actions,
            street=table.street,
        )

        self.last_decision = decision
        self._track_telemetry(decision.action_type, table.street)

        return Action(
            player_id=self.player_id,
            action_type=decision.action_type,
            amount=decision.amount,
        )

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
        effective_stack_behind: Optional[int] = None,
        position: Optional[GhPosition] = None,
        street: Optional[Street] = None,
    ) -> GhMathDecision:
        """Interface desacoplada compatível para simulações e testes unitários."""
        eff_stack = (
            effective_stack_behind
            if effective_stack_behind is not None
            else player_stack
        )
        pos = position if position is not None else GhPosition.MIDDLE
        decision = self.evaluate_cognitive_state(
            hole_cards=hole_cards,
            community_cards=community_cards,
            pot_size=pot_size,
            to_call=to_call,
            player_stack=player_stack,
            player_current_bet=player_current_bet,
            current_highest_bet=current_highest_bet,
            min_raise=min_raise,
            big_blind=big_blind,
            num_opponents=num_opponents,
            effective_stack=eff_stack,
            position=pos,
            legal_actions=legal_actions,
            street=street,
        )
        self.last_decision = decision
        return decision

    def evaluate_cognitive_state(
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
        effective_stack: int,
        position: GhPosition,
        legal_actions: Sequence[ActionType],
        street: Optional[Street] = None,
    ) -> GhMathDecision:
        """Computa métricas probabilísticas completas e gera o payload explicável."""
        # 1. Cálculo de Equidade e Outs
        raw_equity, outs = self._calculate_equity_and_outs(
            hole_cards=hole_cards,
            community_cards=community_cards,
            num_opponents=num_opponents,
            position=position,
        )

        # 2. Ajuste Posicional na Equidade Real
        pos_factor = self._position_weight(position)
        adjusted_equity = min(0.99, max(0.01, raw_equity * (1.0 + pos_factor)))

        # 3. Cálculo de Pot Odds Diretas
        direct_pot_odds = calculate_pot_odds(
            to_call=to_call, pot_size=pot_size
        )

        # 4. Cálculo de Implied Odds para Draws
        implied_odds = self._calculate_implied_odds(
            to_call=to_call,
            pot_size=pot_size,
            outs=outs,
            effective_stack=effective_stack,
            street=street,
        )

        # 5. Valor Esperado (EV) de Call e de Raise
        ev_call = (
            (adjusted_equity * (pot_size + to_call)) - to_call
            if to_call > 0
            else adjusted_equity * pot_size
        )
        ev_raise = (adjusted_equity * (pot_size + to_call + min_raise)) - (
            to_call + min_raise
        )

        # 6. Dimensionamento Fracionário via Critério de Kelly
        kelly_fraction = self._compute_kelly_fraction(
            equity=adjusted_equity,
            pot_size=pot_size,
            to_call=max(to_call, big_blind),
        )

        all_cards = list(hole_cards) + list(community_cards)
        score = evaluate_hand(all_cards) if len(all_cards) >= 5 else None
        hand_rank_val = score.hand_rank.value if score else 1
        comb_desc = score.description if score else ""

        # Tomada de Decisão em Custo Zero (Check disponível)
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
                position=position,
                legal_actions=legal_actions,
                street=street,
                num_opponents=num_opponents,
                hand_rank_val=hand_rank_val,
            )

        # Tomada de Decisão Enfrentando Aposta
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
            position=position,
            legal_actions=legal_actions,
            street=street,
            num_opponents=num_opponents,
            hand_rank_val=hand_rank_val,
            comb_desc=comb_desc,
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
    ) -> GhMathDecision:
        """Determina se aposta por valor ou dá check gratuito com controle de pote multiway."""
        # Controle de Pote Multiway no River / Pós-Flop com mãos fracas
        if (
            num_opponents >= 2
            and (
                street == Street.RIVER
                or (street in (Street.FLOP, Street.TURN) and hand_rank_val < 3)
            )
            and adjusted_equity < (self.base_threshold + 0.10)
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
                tactical_rationale="Controle de pote multiway para ver showdown sem inflar o pote",
                formula_reference="Multiway Pot Control: Check behind to minimize variance and see showdown",
            )
            return GhMathDecision(ActionType.CHECK, amount=0, metrics=metrics)

        has_bet_advantage = adjusted_equity >= self.base_threshold

        if ActionType.BET in legal_actions and has_bet_advantage:
            # Dimensionamento baseado no Critério de Kelly
            sizing_ratio = max(0.33, min(1.20, kelly_fraction * 2.5))
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
                tactical_rationale=f"Value Bet Kelly ({sizing_ratio:.0%} pot) com equidade de {adjusted_equity:.1%}",
                formula_reference="Kelly Criterion Sizing: f* = (p(b+1)-1)/b * lambda",
            )
            return GhMathDecision(
                ActionType.BET, amount=bet_amount, metrics=metrics
            )

        # Check de Custo Zero (Preservação de Fichas e Observação Gratuita)
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
            formula_reference="Zero-Cost Rule: Check whenever to_call == 0 and advantage is below threshold",
        )
        return GhMathDecision(ActionType.CHECK, amount=0, metrics=metrics)

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
    ) -> GhMathDecision:
        """Determina se aumenta com vantagem, paga por odds ou desiste por -EV com tenacidade de showdown."""
        can_raise = ActionType.RAISE in legal_actions
        can_call = ActionType.CALL in legal_actions

        # Aumento por Valor com Vantagem Sólida
        if (
            can_raise
            and adjusted_equity >= (self.base_threshold + 0.06)
            and player_stack > to_call
        ):
            min_req = current_highest_bet + min_raise
            sizing_ratio = max(0.50, min(1.50, kelly_fraction * 3.0))
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
                tactical_rationale=f"+EV Raise: Equidade {adjusted_equity:.1%} supera limiar de agressão",
                formula_reference="Value Raise: adjusted_equity >= base_threshold + margin",
            )
            return GhMathDecision(
                ActionType.RAISE, amount=raise_amount, metrics=metrics
            )

        # Call Lucrativo, Implied Odds e Tenacidade de Showdown (Bluff Catching)
        has_pair = hand_rank_val >= 2
        is_mod_bet = to_call <= max(20 * 4, int(pot_size * 0.50))
        is_bluff_catch = (
            has_pair
            and is_mod_bet
            and (street in (Street.TURN, Street.RIVER))
            and num_opponents <= 2
        )

        bluff_margin = 0.08 if is_bluff_catch else 0.0
        direct_call_ok = adjusted_equity >= (direct_pot_odds - bluff_margin)
        implied_call_ok = (outs >= 8) and (adjusted_equity >= implied_odds)

        if can_call and (direct_call_ok or implied_call_ok):
            if is_bluff_catch and not (adjusted_equity >= direct_pot_odds):
                call_reason = (
                    f"+EV Bluff Catch: Par formado ({comb_desc or 'Feito'}) com tenacidade "
                    f"de showdown contra aposta moderada ({to_call} fichas)"
                )
            elif direct_call_ok:
                call_reason = f"+EV Direct Call: Equidade {adjusted_equity:.1%} >= Pot Odds {direct_pot_odds:.1%}"
            else:
                call_reason = f"+EV Implied Call: {outs} outs com Implied Odds favoráveis ({implied_odds:.1%})"

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
                formula_reference="Call Condition: adjusted_equity >= min(direct_pot_odds, implied_odds)",
            )
            return GhMathDecision(ActionType.CALL, amount=to_call, metrics=metrics)

        # Check Legal se disponível (evita fold acidental)
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
            return GhMathDecision(ActionType.CHECK, amount=0, metrics=metrics)

        # Fold Disciplinado por Retorno Negativo (-EV)
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
            tactical_rationale=f"-EV Fold: Equidade {adjusted_equity:.1%} < Pot Odds {direct_pot_odds:.1%}",
            formula_reference="Disciplined Fold: expected_value < 0 and no implied odds support",
        )
        return GhMathDecision(ActionType.FOLD, amount=0, metrics=metrics)

    def _calculate_equity_and_outs(
        self,
        hole_cards: Tuple[Card, Card],
        community_cards: Sequence[Card],
        num_opponents: int,
        position: GhPosition,
    ) -> Tuple[float, int]:
        """Calcula equidade de forma realista sem penalização cega pré-flop."""
        if not community_cards:
            # Avaliação pré-flop com score combinatório posicional
            preflop_score = self._evaluate_gh_preflop(hole_cards, position)
            # Simulação contra oponente de referência representativo
            sim_res = estimate_hand_equity(
                hole_cards=hole_cards,
                community_cards=(),
                num_opponents=min(3, max(1, num_opponents)),
                num_simulations=self.num_simulations,
                rng=self.rng,
            )
            blended = (preflop_score * 0.50) + (sim_res.equity * 0.50)
            return blended, 0

        # Pós-Flop: Monte Carlo + detecção de outs para draws
        sim_res = estimate_hand_equity(
            hole_cards=hole_cards,
            community_cards=community_cards,
            num_opponents=min(3, num_opponents),
            num_simulations=self.num_simulations,
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

        final_equity = max(sim_res.equity, min(0.60, draw_prob))
        return final_equity, outs

    def _evaluate_gh_preflop(
        self, hole_cards: Tuple[Card, Card], position: GhPosition
    ) -> float:
        """Gera score pré-flop calibrado com Chen Formula e ranges posicionais."""
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

            # Penalidade de Gap
            if gap == 1:
                score_pts -= 1.0
            elif gap == 2:
                score_pts -= 2.0
            elif gap == 3:
                score_pts -= 4.0
            else:
                score_pts -= 5.0

            # Bônus para conectores de cartas médias/baixas
            if gap in (0, 1) and high_r < Rank.QUEEN.value:
                score_pts += 1.0

            # Bônus de mesmo naipe
            if is_suited:
                score_pts += 2.0

        raw_score = max(0.5, score_pts) / 20.0  # Normalizado entre 0.025 e 1.0

        # Modificador posicional
        if position == GhPosition.LATE:
            raw_score += 0.06
        elif position == GhPosition.EARLY:
            raw_score -= 0.04

        return min(0.95, max(0.05, raw_score))

    def _calculate_implied_odds(
        self,
        to_call: int,
        pot_size: int,
        outs: int,
        effective_stack: int,
        street: Optional[Street],
    ) -> float:
        """Calcula as odds implícitas considerando fichas futuras do adversário."""
        if to_call <= 0 or outs < 4:
            return 1.0

        # Mãos pós-flop com draws têm expectativa de extrair fichas futuras
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

        # Aplica o fator de segurança fracionário (Quarto de Kelly)
        return min(self.kelly_fraction_limit, raw_kelly * self.kelly_fraction_limit)

    def _count_outs(
        self, hole_cards: Tuple[Card, Card], community_cards: Sequence[Card]
    ) -> int:
        """Estima a quantidade de outs para evolução da mão."""
        combined = list(hole_cards) + list(community_cards)
        outs = 0

        if has_flush_draw(combined):
            outs += 9
        if has_straight_draw(combined):
            outs += 8
        if has_overcards(hole_cards, community_cards):
            outs += 6

        return outs

    def _determine_position(self, table: Table, my_id: str) -> GhPosition:
        """Identifica a categoria posicional do agente na mesa."""
        active_ids = [p.player_id for p in table.players if p.is_active]
        if not active_ids:
            return GhPosition.MIDDLE

        try:
            my_idx = active_ids.index(my_id)
        except ValueError:
            return GhPosition.MIDDLE

        btn_id = (
            table.players[table.button_idx].player_id
            if 0 <= table.button_idx < len(table.players)
            else active_ids[0]
        )

        total = len(active_ids)
        if total <= 2:
            # Heads-up: Button é posição tardia
            return (
                GhPosition.LATE
                if my_id == btn_id
                else GhPosition.BLINDS
            )

        try:
            btn_idx = active_ids.index(btn_id)
        except ValueError:
            btn_idx = 0

        # Distância em relação ao botão (0 = botão, 1 = cutoff, etc.)
        dist_from_button = (btn_idx - my_idx) % total

        if dist_from_button in (0, 1):
            return GhPosition.LATE
        if dist_from_button in (total - 1, total - 2):
            return GhPosition.BLINDS
        return GhPosition.MIDDLE

    def _position_weight(self, position: GhPosition) -> float:
        """Modificador matemático do valor da informação por posição."""
        if position == GhPosition.LATE:
            return 0.05
        if position == GhPosition.MIDDLE:
            return 0.00
        if position == GhPosition.BLINDS:
            return -0.03
        return -0.04

    def _track_telemetry(self, action_type: ActionType, street: Street) -> None:
        """Atualiza indicadores estatísticos acumulados do agente."""
        if street == Street.PREFLOP:
            if action_type in (ActionType.CALL, ActionType.BET, ActionType.RAISE):
                self.vpip_actions += 1
            if action_type in (ActionType.BET, ActionType.RAISE):
                self.pfr_actions += 1

        if action_type in (ActionType.BET, ActionType.RAISE):
            self.bets_and_raises += 1
        elif action_type == ActionType.CALL:
            self.calls += 1
        elif action_type == ActionType.FOLD:
            self.folds += 1
