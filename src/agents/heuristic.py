"""Agentes heurísticos com diferentes perfis estratégicos de Texas Hold'em."""

from enum import Enum
import random
from typing import Optional, Sequence

from src.agents.base import BaseAgent
from src.engine.deck import Card
from src.engine.hand_eval import HandRank, evaluate_hand
from src.engine.table import Action, ActionType, Table


class AgentProfile(Enum):
    """Perfis comportamentais de agentes baseados em heurísticas."""

    CONSERVATIVE = "Conservador"
    AGGRESSIVE = "Agressivo"
    BALANCED = "Equilibrado"


class HeuristicAgent(BaseAgent):
    """Agente autônomo baseado em regras heurísticas de decisão e força de mão."""

    def __init__(
        self,
        player_id: str,
        name: str,
        profile: AgentProfile = AgentProfile.BALANCED,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        self.profile: AgentProfile = profile
        self.rng: random.Random = rng if rng is not None else random.Random()

    def decide_action(self, table: Table) -> Action:
        """Determina a ação ótima estimada com base no perfil e estado da mesa."""
        legal_actions = table.get_legal_actions(self.player_id)
        if not legal_actions:
            return Action(self.player_id, ActionType.FOLD)

        player = next(p for p in table.players if p.player_id == self.player_id)
        if player.hole_cards is None:
            return Action(self.player_id, ActionType.FOLD)

        hand_strength = self._evaluate_strength(
            hole_cards=player.hole_cards,
            community_cards=table.community_cards,
        )

        to_call = table.current_highest_bet - player.current_bet

        if to_call == 0:
            return self._decide_when_free_to_check(
                legal_actions=legal_actions,
                hand_strength=hand_strength,
                table=table,
                player_stack=player.stack,
            )

        return self._decide_facing_bet(
            legal_actions=legal_actions,
            hand_strength=hand_strength,
            table=table,
            to_call=to_call,
            player_stack=player.stack,
            player_current_bet=player.current_bet,
        )

    def _decide_when_free_to_check(
        self,
        legal_actions: Sequence[ActionType],
        hand_strength: float,
        table: Table,
        player_stack: int,
    ) -> Action:
        """Decide entre apostar por valor/blefe ou passar a vez gratuitamente."""
        if ActionType.BET not in legal_actions or player_stack == 0:
            return Action(self.player_id, ActionType.CHECK)

        should_bet = False
        rand_val = self.rng.random()

        if self.profile == AgentProfile.CONSERVATIVE:
            should_bet = hand_strength >= 0.65 and rand_val < 0.70
        elif self.profile == AgentProfile.AGGRESSIVE:
            should_bet = hand_strength >= 0.40 or rand_val < 0.35
        else:
            should_bet = hand_strength >= 0.50 or rand_val < 0.18

        if should_bet:
            pot = table.pot_manager.total_pot
            bet_fraction = 0.50 if self.profile != AgentProfile.AGGRESSIVE else 0.75
            desired_bet = max(table.min_raise, int(pot * bet_fraction))
            bet_amount = min(player_stack, max(table.min_raise, desired_bet))
            return Action(self.player_id, ActionType.BET, amount=bet_amount)

        return Action(self.player_id, ActionType.CHECK)

    def _decide_facing_bet(
        self,
        legal_actions: Sequence[ActionType],
        hand_strength: float,
        table: Table,
        to_call: int,
        player_stack: int,
        player_current_bet: int,
    ) -> Action:
        """Decide reagir a uma aposta adversária (aumentar, pagar ou desistir)."""
        call_ratio = to_call / max(1, table.pot_manager.total_pot + to_call)
        rand_val = self.rng.random()

        can_raise = ActionType.RAISE in legal_actions
        should_raise = False

        if can_raise:
            if self.profile == AgentProfile.AGGRESSIVE:
                should_raise = hand_strength >= 0.70 or (
                    hand_strength < 0.30 and rand_val < 0.20
                )
            elif self.profile == AgentProfile.CONSERVATIVE:
                should_raise = hand_strength >= 0.85 and rand_val < 0.60
            else:
                should_raise = hand_strength >= 0.75 or (
                    hand_strength < 0.30 and rand_val < 0.08
                )

        if should_raise:
            min_target = table.current_highest_bet + table.min_raise
            max_target = player_current_bet + player_stack
            raise_size = min(
                max_target,
                int(min_target + table.pot_manager.total_pot * 0.4),
            )
            if raise_size >= min_target:
                return Action(self.player_id, ActionType.RAISE, amount=raise_size)

        should_call = False
        if self.profile == AgentProfile.CONSERVATIVE:
            should_call = hand_strength >= 0.50 and call_ratio <= 0.35
        elif self.profile == AgentProfile.AGGRESSIVE:
            should_call = hand_strength >= 0.35 or call_ratio <= 0.45
        else:
            should_call = hand_strength >= 0.40 and call_ratio <= 0.40

        if should_call:
            if ActionType.CALL in legal_actions:
                return Action(self.player_id, ActionType.CALL)
            if ActionType.ALL_IN in legal_actions and hand_strength >= 0.55:
                return Action(self.player_id, ActionType.ALL_IN)

        return Action(self.player_id, ActionType.FOLD)

    def _evaluate_strength(
        self,
        hole_cards: Sequence[Card],
        community_cards: Sequence[Card],
    ) -> float:
        """Estima a força normalizada da mão em um intervalo contínuo de 0.0 a 1.0."""
        if not community_cards:
            return self._evaluate_preflop_strength(hole_cards[0], hole_cards[1])

        combined = list(hole_cards) + list(community_cards)
        score = evaluate_hand(combined)

        rank_weights = {
            HandRank.HIGH_CARD: 0.15,
            HandRank.ONE_PAIR: 0.40,
            HandRank.TWO_PAIR: 0.65,
            HandRank.THREE_OF_A_KIND: 0.75,
            HandRank.STRAIGHT: 0.82,
            HandRank.FLUSH: 0.87,
            HandRank.FULL_HOUSE: 0.92,
            HandRank.FOUR_OF_A_KIND: 0.97,
            HandRank.STRAIGHT_FLUSH: 0.99,
            HandRank.ROYAL_FLUSH: 1.00,
        }

        base = rank_weights.get(score.hand_rank, 0.20)
        kicker_bonus = (score.tiebreakers[0] / 14.0) * 0.08 if score.tiebreakers else 0
        return min(1.0, base + kicker_bonus)

    def _evaluate_preflop_strength(self, c1: Card, c2: Card) -> float:
        """Calcula força pré-flop estimada com base nos ranques e naipes."""
        high_val = max(c1.rank.value, c2.rank.value)
        low_val = min(c1.rank.value, c2.rank.value)
        is_pair = high_val == low_val
        is_suited = c1.suit == c2.suit

        if is_pair:
            return min(1.0, 0.50 + (high_val / 14.0) * 0.45)

        base = (high_val + low_val) / 28.0
        if is_suited:
            base += 0.08
        if abs(high_val - low_val) <= 2:
            base += 0.05

        return min(1.0, max(0.10, base))
