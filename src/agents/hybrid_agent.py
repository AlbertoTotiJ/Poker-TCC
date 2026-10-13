"""Agente Híbrido integrando rigor probabilístico e engano comportamental.

Este módulo implementa o HybridAgent, unificando a base matemática
(Monte Carlo, pot odds e EV) com adaptações táticas dinâmicas
(blefes oportunos, semi-blefes em draws e armadilhas de slow-play).
"""

from dataclasses import dataclass
from pathlib import Path
import random
import sys
from typing import Optional, Sequence

# Garante resolução de 'src' ao executar o script diretamente
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.agents.base import BaseAgent  # noqa: E402
from src.engine.deck import Card  # noqa: E402
from src.engine.equity import (  # noqa: E402
    calculate_pot_odds,
    estimate_hand_equity,
    has_flush_draw,
    has_straight_draw,
)
from src.engine.table import Action, ActionType, Street, Table  # noqa: E402


@dataclass(frozen=True)
class HybridDecision:
    """Estrutura representativa da decisão integrada do Agente Híbrido."""

    action_type: ActionType
    amount: int
    mode: str
    equity: float
    pot_odds: float
    is_deceptive: bool
    reason: str


class HybridAgent(BaseAgent):
    """Agente que mescla o modelo matemático e heurísticas táticas avançadas.

    Opera com piso probabilístico estrito para evitar jogadas de EV negativo,
    mas introduz variabilidade estratégica através de semi-blefes,
    blefes em potes fracos e desaceleração (*slow-play*) com mãos dominantes.
    """

    def __init__(
        self,
        player_id: str,
        name: str = "Agente Híbrido",
        math_threshold: float = 0.60,
        bluff_prob: float = 0.25,
        slowplay_prob: float = 0.20,
        num_simulations: int = 150,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        self.math_threshold: float = math_threshold
        self.bluff_prob: float = max(0.05, min(0.60, bluff_prob))
        self.slowplay_prob: float = max(0.05, min(0.50, slowplay_prob))
        self.num_simulations: int = max(50, num_simulations)
        self.rng: random.Random = rng if rng is not None else random.Random()

        # Telemetria analítica
        self.hands_played: int = 0
        self.bluffs_attempted: int = 0
        self.traps_attempted: int = 0
        self.vpip_actions: int = 0
        self.pfr_actions: int = 0
        self.bets_and_raises: int = 0
        self.calls: int = 0
        self.folds: int = 0

    def decide_action(self, table: Table) -> Action:
        """Determina a ação na mesa combinando matemática e oportunismo tático."""
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

        self._track_decision_telemetry(decision)
        return Action(
            player_id=self.player_id,
            action_type=decision.action_type,
            amount=decision.amount,
        )

    def evaluate_state(
        self,
        hole_cards: Sequence[Card],
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
        street: Street,
    ) -> HybridDecision:
        """Calcula equidade via Monte Carlo e aplica a camada tática de decisão."""
        # 1. Cálculo matemático de base
        eq_res = estimate_hand_equity(
            hole_cards=hole_cards,
            community_cards=community_cards,
            num_opponents=num_opponents,
            num_simulations=self.num_simulations,
            rng=self.rng,
        )
        equity = eq_res.equity
        pot_odds = calculate_pot_odds(to_call=to_call, pot_size=pot_size)

        # Detecção de Draws para Semi-blefes no Flop e Turn
        is_draw = False
        if street in (Street.FLOP, Street.TURN) and len(community_cards) >= 3:
            all_cards = list(hole_cards) + list(community_cards)
            is_draw = has_flush_draw(all_cards) or has_straight_draw(all_cards)

        roll = self.rng.random()

        # Cenário 1: Mão Monstro (Equity >= 0.80) -> Valor vs Armadilha (Slow-Play)
        if equity >= 0.80:
            if roll < self.slowplay_prob and street != Street.RIVER:
                # Armadilha: Check ou Call calmo para induzir apostas futuras
                if ActionType.CHECK in legal_actions:
                    return HybridDecision(
                        action_type=ActionType.CHECK,
                        amount=0,
                        mode="SLOW_PLAY",
                        equity=equity,
                        pot_odds=pot_odds,
                        is_deceptive=True,
                        reason=f"Slow-play com mão monstro (Eq={equity:.2%})",
                    )
                if ActionType.CALL in legal_actions and to_call <= big_blind * 4:
                    return HybridDecision(
                        action_type=ActionType.CALL,
                        amount=0,
                        mode="SLOW_PLAY",
                        equity=equity,
                        pot_odds=pot_odds,
                        is_deceptive=True,
                        reason=(
                            f"Call de armadilha com mão monstro (Eq={equity:.2%})"
                        ),
                    )

            # Aposta sólida por valor
            return self._build_value_action(
                equity=equity,
                pot_odds=pot_odds,
                pot_size=pot_size,
                player_stack=player_stack,
                player_current_bet=player_current_bet,
                current_highest_bet=current_highest_bet,
                min_raise=min_raise,
                big_blind=big_blind,
                legal_actions=legal_actions,
            )

        # Cenário 2: Equidade Alta / Forte (Equity >= math_threshold)
        if equity >= self.math_threshold:
            return self._build_value_action(
                equity=equity,
                pot_odds=pot_odds,
                pot_size=pot_size,
                player_stack=player_stack,
                player_current_bet=player_current_bet,
                current_highest_bet=current_highest_bet,
                min_raise=min_raise,
                big_blind=big_blind,
                legal_actions=legal_actions,
            )

        # Cenário 3: Semi-Blefe (Mão com draw promissor ou equidade moderada 0.35-0.59)
        if (is_draw or equity >= 0.40) and roll < 0.45:
            if ActionType.BET in legal_actions:
                bet_amt = min(player_stack, max(big_blind, int(pot_size * 0.60)))
                return HybridDecision(
                    action_type=ActionType.BET,
                    amount=bet_amt,
                    mode="SEMI_BLUFF",
                    equity=equity,
                    pot_odds=pot_odds,
                    is_deceptive=True,
                    reason=f"Semi-blefe agressivo com draw/equidade (Eq={equity:.2%})",
                )
            if ActionType.RAISE in legal_actions and to_call <= big_blind * 3:
                raise_amt = current_highest_bet + max(min_raise, to_call * 2)
                max_pos = player_current_bet + player_stack
                raise_amt = min(max_pos, raise_amt)
                return HybridDecision(
                    action_type=ActionType.RAISE,
                    amount=raise_amt,
                    mode="SEMI_BLUFF",
                    equity=equity,
                    pot_odds=pot_odds,
                    is_deceptive=True,
                    reason=(
                        f"Raise de semi-blefe aplicando fold equity "
                        f"(Eq={equity:.2%})"
                    ),
                )

        # Cenário 4: Blefe Oportunista (Mão fraca mas mesa deu check)
        if to_call == 0:
            if roll < self.bluff_prob and num_opponents <= 3:
                if ActionType.BET in legal_actions:
                    steal_amt = min(player_stack, max(big_blind, int(pot_size * 0.65)))
                    return HybridDecision(
                        action_type=ActionType.BET,
                        amount=steal_amt,
                        mode="PURE_BLUFF",
                        equity=equity,
                        pot_odds=pot_odds,
                        is_deceptive=True,
                        reason=f"Blefe oportuno em mesa passiva (Eq={equity:.2%})",
                    )
            if ActionType.CHECK in legal_actions:
                return HybridDecision(
                    action_type=ActionType.CHECK,
                    amount=0,
                    mode="PASSIVE_CHECK",
                    equity=equity,
                    pot_odds=pot_odds,
                    is_deceptive=False,
                    reason="Check gratuito preservando fichas",
                )

        # Cenário 5: Enfrentando aposta -> Avaliação de Pot Odds e EV
        if to_call > 0:
            # Se a equidade supera as pot odds (EV Positivo)
            if equity >= pot_odds and ActionType.CALL in legal_actions:
                return HybridDecision(
                    action_type=ActionType.CALL,
                    amount=0,
                    mode="EV_CALL",
                    equity=equity,
                    pot_odds=pot_odds,
                    is_deceptive=False,
                    reason=(
                        f"Call justificado por Pot Odds "
                        f"(Eq={equity:.2%} >= Odds={pot_odds:.2%})"
                    ),
                )

            # Pequeno call de float se o pote for quase grátis (to_call <= 0.5 * BB)
            if to_call <= big_blind // 2 and ActionType.CALL in legal_actions:
                return HybridDecision(
                    action_type=ActionType.CALL,
                    amount=0,
                    mode="CHEAP_CALL",
                    equity=equity,
                    pot_odds=pot_odds,
                    is_deceptive=False,
                    reason="Call de valor marginal quase gratuito",
                )

        # Cenário 6: Desistência disciplinada (EV Negativo e sem justificativa tática)
        if ActionType.FOLD in legal_actions:
            return HybridDecision(
                action_type=ActionType.FOLD,
                amount=0,
                mode="DISCIPLINED_FOLD",
                equity=equity,
                pot_odds=pot_odds,
                is_deceptive=False,
                reason=(
                    f"Fold disciplinado por EV negativo "
                    f"(Eq={equity:.2%} < Odds={pot_odds:.2%})"
                ),
            )

        fallback = legal_actions[0] if legal_actions else ActionType.FOLD
        return HybridDecision(
            action_type=fallback,
            amount=0,
            mode="FALLBACK",
            equity=equity,
            pot_odds=pot_odds,
            is_deceptive=False,
            reason="Ação de segurança",
        )

    def _build_value_action(
        self,
        equity: float,
        pot_odds: float,
        pot_size: int,
        player_stack: int,
        player_current_bet: int,
        current_highest_bet: int,
        min_raise: int,
        big_blind: int,
        legal_actions: Sequence[ActionType],
    ) -> HybridDecision:
        """Gera ação de aposta de valor proporcional à equidade."""
        if ActionType.RAISE in legal_actions and player_stack > 0:
            raise_size = current_highest_bet + max(
                min_raise, int(pot_size * 0.75)
            )
            max_pos = player_current_bet + player_stack
            raise_size = min(max_pos, raise_size)
            return HybridDecision(
                action_type=ActionType.RAISE,
                amount=raise_size,
                mode="VALUE_RAISE",
                equity=equity,
                pot_odds=pot_odds,
                is_deceptive=False,
                reason=f"Aumento por valor com vantagem de equidade ({equity:.2%})",
            )

        if ActionType.BET in legal_actions:
            bet_size = min(player_stack, max(big_blind, int(pot_size * 0.65)))
            return HybridDecision(
                action_type=ActionType.BET,
                amount=bet_size,
                mode="VALUE_BET",
                equity=equity,
                pot_odds=pot_odds,
                is_deceptive=False,
                reason=f"Aposta por valor proporcional ao pote ({equity:.2%})",
            )

        if ActionType.CALL in legal_actions:
            return HybridDecision(
                action_type=ActionType.CALL,
                amount=0,
                mode="VALUE_CALL",
                equity=equity,
                pot_odds=pot_odds,
                is_deceptive=False,
                reason=f"Call com forte equidade ({equity:.2%})",
            )

        if ActionType.CHECK in legal_actions:
            return HybridDecision(
                action_type=ActionType.CHECK,
                amount=0,
                mode="VALUE_CHECK",
                equity=equity,
                pot_odds=pot_odds,
                is_deceptive=False,
                reason="Check mantendo a mão ativa",
            )

        return HybridDecision(
            action_type=ActionType.FOLD,
            amount=0,
            mode="FALLBACK",
            equity=equity,
            pot_odds=pot_odds,
            is_deceptive=False,
            reason="Contingência",
        )

    def _track_decision_telemetry(self, decision: HybridDecision) -> None:
        """Registra telemetria das jogadas realizadas."""
        if decision.mode in ("SEMI_BLUFF", "PURE_BLUFF"):
            self.bluffs_attempted += 1
        elif decision.mode == "SLOW_PLAY":
            self.traps_attempted += 1

        if decision.action_type in (ActionType.BET, ActionType.RAISE):
            self.bets_and_raises += 1
            self.vpip_actions += 1
            self.pfr_actions += 1
        elif decision.action_type == ActionType.CALL:
            self.calls += 1
            self.vpip_actions += 1
        elif decision.action_type == ActionType.FOLD:
            self.folds += 1


if __name__ == "__main__":
    agent = HybridAgent(
        player_id="hybrid_test",
        name="Híbrido Beta",
        math_threshold=0.55,
        bluff_prob=0.30,
        rng=random.Random(42),
    )
    hole = [Card.from_str("Ks"), Card.from_str("Qs")]
    board = [Card.from_str("Js"), Card.from_str("10s"), Card.from_str("2c")]

    dec = agent.evaluate_state(
        hole_cards=hole,
        community_cards=board,
        pot_size=160,
        to_call=0,
        player_stack=950,
        player_current_bet=0,
        current_highest_bet=0,
        min_raise=20,
        big_blind=20,
        num_opponents=2,
        legal_actions=[ActionType.CHECK, ActionType.BET],
        street=Street.FLOP,
    )
    print("Decisão isolada do Agente Híbrido:")
    print(f"  Ação: {dec.action_type.value}")
    print(f"  Quantia: {dec.amount}")
    print(f"  Modo: {dec.mode}")
    print(f"  Equidade: {dec.equity:.2%}")
    print(f"  Enganoso? {dec.is_deceptive}")
    print(f"  Razão: {dec.reason}")
