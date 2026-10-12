"""Agente de Poker baseado estritamente na teoria das probabilidades e EV.

Este módulo implementa o MathematicalAgent conforme especificado no
documento de arquitetura dos agentes (read.me agents.md). Ele avalia
equidade da mão, probabilidades de draws (out rules), pot odds e
valor esperado (Expected Value - EV) sem vieses psicológicos.
"""

from dataclasses import dataclass
from pathlib import Path
import random
import sys
from typing import Optional, Sequence, Tuple

# Garante resolucao de 'src' ao executar o script diretamente
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.agents.base import BaseAgent  # noqa: E402
from src.engine.deck import Card, Rank  # noqa: E402
from src.engine.equity import (  # noqa: E402
    calculate_pot_odds,
    estimate_hand_equity,
    has_flush_draw,
    has_overcards,
    has_straight_draw,
)
from src.engine.table import Action, ActionType, Street, Table  # noqa: E402


@dataclass(frozen=True)
class MathematicalDecision:
    """Estrutura analítica contendo os fundamentos matemáticos da decisão."""

    action_type: ActionType
    amount: int
    equity: float
    pot_odds: float
    expected_value: float
    outs: int
    reason: str


class MathematicalAgent(BaseAgent):
    """Agente autônomo estritamente probabilístico e analítico para Texas Hold'em.

    Toma decisões determinísticas fundamentadas em equidade de Monte Carlo,
    pot odds, valor esperado (EV) e outs de evolução no Flop/Turn.
    """

    def __init__(
        self,
        player_id: str,
        name: str = "Agente Matemático",
        raise_equity_threshold: float = 0.65,
        call_ev_margin: float = 0.0,
        draw_weight: float = 1.0,
        bet_sizing_factor: float = 0.75,
        num_simulations: int = 200,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        self.raise_equity_threshold: float = raise_equity_threshold
        self.call_ev_margin: float = call_ev_margin
        self.draw_weight: float = draw_weight
        self.bet_sizing_factor: float = bet_sizing_factor
        self.num_simulations: int = num_simulations
        self.rng: random.Random = rng if rng is not None else random.Random()

        # Telemetria acumulada de partidas
        self.hands_played: int = 0
        self.vpip_actions: int = 0
        self.pfr_actions: int = 0
        self.bets_and_raises: int = 0
        self.calls: int = 0
        self.folds: int = 0

    def decide_action(self, table: Table) -> Action:
        """Determina a ação ótima na mesa com base em probabilidade e EV."""
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
        )

        self._track_decision_telemetry(decision.action_type, table.street)
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
        street: Optional[Street] = None,
    ) -> MathematicalDecision:
        """Calcula equidade, EV e retorna a decisão matemática estruturada."""
        equity, outs = self.calculate_effective_equity(
            hole_cards=hole_cards,
            community_cards=community_cards,
            num_opponents=num_opponents,
        )

        pot_odds = calculate_pot_odds(to_call=to_call, pot_size=pot_size)

        # Expected Value para ação de pagar (Call): EV = (Equity * TotalPot) - ToCall
        expected_value = (
            (equity * (pot_size + to_call)) - to_call if to_call > 0 else 0.0
        )

        if to_call == 0:
            return self._decide_zero_cost(
                equity=equity,
                outs=outs,
                pot_size=pot_size,
                player_stack=player_stack,
                big_blind=big_blind,
                min_raise=min_raise,
                legal_actions=legal_actions,
            )

        return self._decide_facing_cost(
            equity=equity,
            pot_odds=pot_odds,
            expected_value=expected_value,
            outs=outs,
            pot_size=pot_size,
            to_call=to_call,
            player_stack=player_stack,
            player_current_bet=player_current_bet,
            current_highest_bet=current_highest_bet,
            min_raise=min_raise,
            legal_actions=legal_actions,
        )

    def calculate_effective_equity(
        self,
        hole_cards: Tuple[Card, Card],
        community_cards: Sequence[Card],
        num_opponents: int = 1,
    ) -> Tuple[float, int]:
        """Calcula a equidade ajustada incluindo Monte Carlo e outs de draws."""
        if not community_cards:
            preflop_score = self._evaluate_preflop_combinatorics(hole_cards)
            eq_res = estimate_hand_equity(
                hole_cards=hole_cards,
                community_cards=(),
                num_opponents=num_opponents,
                num_simulations=self.num_simulations,
                rng=self.rng,
            )
            blended_equity = (preflop_score * 0.40) + (eq_res.equity * 0.60)
            return blended_equity, 0

        eq_res = estimate_hand_equity(
            hole_cards=hole_cards,
            community_cards=community_cards,
            num_opponents=num_opponents,
            num_simulations=self.num_simulations,
            rng=self.rng,
        )

        outs = self._calculate_draw_outs(hole_cards, community_cards)

        # Regra de 4 e 2 para Texas Hold'em
        draw_prob = 0.0
        if len(community_cards) == 3:  # Flop (2 cartas por vir)
            draw_prob = min(0.65, outs * 0.04)
        elif len(community_cards) == 4:  # Turn (1 carta por vir)
            draw_prob = min(0.40, outs * 0.02)

        adjusted_equity = max(eq_res.equity, draw_prob * self.draw_weight)
        return adjusted_equity, outs

    def _decide_zero_cost(
        self,
        equity: float,
        outs: int,
        pot_size: int,
        player_stack: int,
        big_blind: int,
        min_raise: int,
        legal_actions: Sequence[ActionType],
    ) -> MathematicalDecision:
        """Determina se abre aposta por valor ou passa a vez gratuitamente."""
        if ActionType.BET in legal_actions and player_stack > 0:
            if equity >= self.raise_equity_threshold:
                target_fraction = min(1.0, equity) * self.bet_sizing_factor
                desired_bet = max(big_blind, min_raise, int(pot_size * target_fraction))
                bet_amount = min(player_stack, max(min_raise, desired_bet))
                return MathematicalDecision(
                    action_type=ActionType.BET,
                    amount=bet_amount,
                    equity=equity,
                    pot_odds=0.0,
                    expected_value=equity * pot_size,
                    outs=outs,
                    reason=f"Value bet com equidade de {equity:.1%}",
                )

        return MathematicalDecision(
            action_type=ActionType.CHECK,
            amount=0,
            equity=equity,
            pot_odds=0.0,
            expected_value=0.0,
            outs=outs,
            reason="Check gratuito preservando EV",
        )

    def _decide_facing_cost(
        self,
        equity: float,
        pot_odds: float,
        expected_value: float,
        outs: int,
        pot_size: int,
        to_call: int,
        player_stack: int,
        player_current_bet: int,
        current_highest_bet: int,
        min_raise: int,
        legal_actions: Sequence[ActionType],
    ) -> MathematicalDecision:
        """Determina se aumenta por valor puro, paga por EV positivo ou desiste."""
        is_profitable = equity >= (pot_odds - self.call_ev_margin)
        strong_advantage = equity >= (self.raise_equity_threshold + 0.08)

        # Aumento por valor com vantagem significativa de equidade
        if (
            ActionType.RAISE in legal_actions
            and strong_advantage
            and player_stack > to_call
        ):
            min_required = current_highest_bet + min_raise
            raise_addition = max(
                min_raise, int(pot_size * equity * self.bet_sizing_factor)
            )
            total_target = current_highest_bet + raise_addition
            raise_amount = min(
                player_current_bet + player_stack, max(min_required, total_target)
            )

            if raise_amount >= min_required:
                return MathematicalDecision(
                    action_type=ActionType.RAISE,
                    amount=raise_amount,
                    equity=equity,
                    pot_odds=pot_odds,
                    expected_value=expected_value,
                    outs=outs,
                    reason=f"Raise por valor com equidade dominante ({equity:.1%})",
                )

        if ActionType.CALL in legal_actions and is_profitable:
            return MathematicalDecision(
                action_type=ActionType.CALL,
                amount=to_call,
                equity=equity,
                pot_odds=pot_odds,
                expected_value=expected_value,
                outs=outs,
                reason=f"+EV Call: Equidade {equity:.1%} >= Pot Odds {pot_odds:.1%}",
            )

        if ActionType.CHECK in legal_actions:
            return MathematicalDecision(
                action_type=ActionType.CHECK,
                amount=0,
                equity=equity,
                pot_odds=pot_odds,
                expected_value=expected_value,
                outs=outs,
                reason="Check legal viável",
            )

        return MathematicalDecision(
            action_type=ActionType.FOLD,
            amount=0,
            equity=equity,
            pot_odds=pot_odds,
            expected_value=expected_value,
            outs=outs,
            reason=f"-EV Fold: Equidade {equity:.1%} < Pot Odds {pot_odds:.1%}",
        )

    def _calculate_draw_outs(
        self, hole_cards: Tuple[Card, Card], community_cards: Sequence[Card]
    ) -> int:
        """Calcula a quantidade estimada de outs para evolução de mãos especulativas."""
        combined = list(hole_cards) + list(community_cards)
        outs = 0

        if has_flush_draw(combined):
            outs += 9

        if has_straight_draw(combined):
            outs += 8

        if has_overcards(hole_cards, community_cards):
            outs += 6

        return outs

    def _evaluate_preflop_combinatorics(self, hole_cards: Tuple[Card, Card]) -> float:
        """Calcula força pré-flop baseada em combinatória de pares e conectores."""
        c1, c2 = hole_cards
        high_r = max(c1.rank.value, c2.rank.value)
        low_r = min(c1.rank.value, c2.rank.value)
        is_pair = c1.rank == c2.rank
        is_suited = c1.suit == c2.suit
        gap = high_r - low_r

        if is_pair:
            return 0.52 + ((high_r / 14.0) * 0.40)

        base_score = ((high_r + (low_r * 0.60)) / 22.4) * 0.70
        if is_suited:
            base_score += 0.05
        if gap == 1:
            base_score += 0.04
        elif gap == 2:
            base_score += 0.02

        if high_r == Rank.ACE.value:
            base_score += 0.06

        return min(0.95, max(0.15, base_score))

    def _track_decision_telemetry(
        self, action_type: ActionType, street: Street
    ) -> None:
        """Atualiza contadores para métricas VPIP, PFR e Aggression Factor."""
        if street == Street.PREFLOP:
            if action_type in (
                ActionType.CALL,
                ActionType.BET,
                ActionType.RAISE,
                ActionType.ALL_IN,
            ):
                self.vpip_actions += 1
            if action_type in (ActionType.RAISE, ActionType.BET):
                self.pfr_actions += 1

        if action_type in (ActionType.BET, ActionType.RAISE):
            self.bets_and_raises += 1
        elif action_type == ActionType.CALL:
            self.calls += 1
        elif action_type == ActionType.FOLD:
            self.folds += 1

    @property
    def aggression_factor(self) -> float:
        """Calcula o Fator de Agressão clássico (AF = (Bets + Raises) / Calls)."""
        if self.calls == 0:
            return float(self.bets_and_raises)
        return round(self.bets_and_raises / self.calls, 2)


def run_isolated_demo() -> None:
    """Demonstração prática e isolada do Agente Matemático em cenários canônicos."""
    agent = MathematicalAgent(player_id="bot_math", name="Agente Matemático")
    print("=" * 75)
    print("DEMONSTRAÇÃO DE EXECUÇÃO ISOLADA: AGENTE MATEMÁTICO (EV & PROBABILIDADE)")
    print("=" * 75)

    c1 = "Cenário 1: Par de Ases Pré-flop (AA) contra bet de 20 em pote de 40"
    c2 = "Cenário 2: Nut Flush Draw no Flop (Kh Qh em Ah 8h 2c) bet 15 em pote 80"
    c3 = "Cenário 3: Mão fraca (7d 2c) no River contra bet de 100 em pote de 120"
    c4 = "Cenário 4: Trinca no Flop (Jh Jd em Jc 7s 2h) com check gratuito"

    scenarios = [
        (
            c1,
            (Card.from_str("As"), Card.from_str("Ah")),
            (),
            40,
            20,
            1000,
            1,
            [ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
        ),
        (
            c2,
            (Card.from_str("Kh"), Card.from_str("Qh")),
            [Card.from_str("Ah"), Card.from_str("8h"), Card.from_str("2c")],
            80,
            15,
            1000,
            1,
            [ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
        ),
        (
            c3,
            (Card.from_str("7d"), Card.from_str("2c")),
            [
                Card.from_str("Kd"),
                Card.from_str("Js"),
                Card.from_str("4h"),
                Card.from_str("9c"),
                Card.from_str("3s"),
            ],
            120,
            100,
            1000,
            1,
            [ActionType.FOLD, ActionType.CALL],
        ),
        (
            c4,
            (Card.from_str("Jh"), Card.from_str("Jd")),
            [Card.from_str("Jc"), Card.from_str("7s"), Card.from_str("2h")],
            60,
            0,
            1000,
            2,
            [ActionType.CHECK, ActionType.BET],
        ),
    ]

    for title, hole, board, pot, to_call, stack, opps, legals in scenarios:
        board_str = " ".join(str(c) for c in board) if board else "(Pré-flop)"
        print(f"\n> {title}")
        print(
            f"  Mão: {hole[0]} {hole[1]} | Bordo: [{board_str}] | "
            f"Pote: {pot} | A pagar: {to_call}"
        )

        decision = agent.evaluate_state(
            hole_cards=hole,
            community_cards=board,
            pot_size=pot,
            to_call=to_call,
            player_stack=stack,
            player_current_bet=0,
            current_highest_bet=to_call,
            min_raise=20,
            big_blind=20,
            num_opponents=opps,
            legal_actions=legals,
        )

        amount_info = f" (Valor: {decision.amount})" if decision.amount > 0 else ""
        print(f"  -> Decisão: {decision.action_type.name}{amount_info}")
        print(
            f"  -> Equidade: {decision.equity:.1%} | "
            f"Pot Odds: {decision.pot_odds:.1%} | Outs: {decision.outs}"
        )
        print(
            f"  -> EV Esperado: {decision.expected_value:+.2f} fichas | "
            f"Justificativa: {decision.reason}"
        )


if __name__ == "__main__":
    run_isolated_demo()
