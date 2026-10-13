"""Agente de Poker com foco em blefes, pressão psicológica e exploração de mesa.

Este módulo implementa o BlufferAgent, projetado para explorar fraquezas
dos oponentes através de agressão calculada, fold equity, leitura de texturas
de mesa (dry boards, scare cards) e roubo de blinds/potes órfãos.
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
from src.engine.deck import Card, Rank  # noqa: E402
from src.engine.hand_eval import evaluate_hand  # noqa: E402
from src.engine.table import Action, ActionType, Street, Table  # noqa: E402


@dataclass(frozen=True)
class BluffDecision:
    """Estrutura descritiva contendo a fundamentação tática do blefe."""

    action_type: ActionType
    amount: int
    is_bluff: bool
    tactic: str
    fold_equity: float
    reason: str


class BlufferAgent(BaseAgent):
    """Agente autônomo focado em agressão desbalanceada e blefes táticos.

    Explora situações de fraqueza na mesa (checks dos oponentes, potes
    abandonados, cartas intimidatórias no turn/river e texturas secas de flop).
    """

    def __init__(
        self,
        player_id: str,
        name: str = "Agente Blefador",
        bluff_frequency: float = 0.40,
        aggression_multiplier: float = 1.0,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        self.bluff_frequency: float = max(0.1, min(0.9, bluff_frequency))
        self.aggression_multiplier: float = max(0.5, min(2.5, aggression_multiplier))
        self.rng: random.Random = rng if rng is not None else random.Random()

        # Telemetria acumulada
        self.hands_played: int = 0
        self.bluffs_attempted: int = 0
        self.vpip_actions: int = 0
        self.pfr_actions: int = 0
        self.bets_and_raises: int = 0
        self.calls: int = 0
        self.folds: int = 0

    def decide_action(self, table: Table) -> Action:
        """Determina a ação na mesa priorizando pressão e blefes calculados."""
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
    ) -> BluffDecision:
        """Avalia a mesa e decide entre blefe tático, aposta de valor ou fold."""
        # Avaliação da mão atual
        all_cards = list(hole_cards) + list(community_cards)
        is_strong = False
        hand_desc = "Desconhecido"

        if len(all_cards) >= 5:
            score = evaluate_hand(all_cards)
            # Dois pares ou melhor é considerado forte
            is_strong = score.hand_rank.value >= 3
            hand_desc = score.description
        else:
            # Pré-flop: pares médios/altos ou Ás alto
            c1, c2 = hole_cards[0], hole_cards[1]
            is_pair = c1.rank.value == c2.rank.value
            high_rank = max(c1.rank.value, c2.rank.value)
            is_strong = (is_pair and high_rank >= 9) or (
                high_rank == Rank.ACE.value and min(c1.rank.value, c2.rank.value) >= 10
            )
            hand_desc = f"{c1.rank.symbol}{c2.rank.symbol}"

        # Cálculo estimado de Fold Equity (quanto menos oponentes, maior a fold equity)
        fold_equity = max(0.15, 0.75 - (num_opponents * 0.12))
        is_dry_board = self._is_dry_board(community_cards)
        is_scare = self._has_scare_card(community_cards)

        if is_dry_board:
            fold_equity += 0.10
        if is_scare and street in (Street.TURN, Street.RIVER):
            fold_equity += 0.15

        fold_equity = min(0.90, fold_equity)

        # 1. Se tem mão forte legítima: aposta por valor
        if is_strong:
            return self._decide_value_play(
                pot_size=pot_size,
                to_call=to_call,
                player_stack=player_stack,
                player_current_bet=player_current_bet,
                current_highest_bet=current_highest_bet,
                min_raise=min_raise,
                big_blind=big_blind,
                legal_actions=legal_actions,
                hand_desc=hand_desc,
            )

        # 2. Mão fraca / média: oportunidade de blefe
        roll = self.rng.random()
        should_bluff = roll < (self.bluff_frequency * (fold_equity / 0.5))

        # Cenário A: Mesa deu CHECK (to_call == 0) -> Steal / C-Bet Bluff
        if to_call == 0:
            if should_bluff and (
                ActionType.BET in legal_actions or ActionType.RAISE in legal_actions
            ):
                target_bet = int(pot_size * 0.70 * self.aggression_multiplier)
                target_bet = max(big_blind, target_bet)
                target_bet = min(player_stack, target_bet)

                if ActionType.BET in legal_actions and target_bet > 0:
                    return BluffDecision(
                        action_type=ActionType.BET,
                        amount=target_bet,
                        is_bluff=True,
                        tactic="C-Bet Steal",
                        fold_equity=fold_equity,
                        reason=(
                            f"Blefe de continuação sem apostas (FE={fold_equity:.2f})"
                        ),
                    )
            # Se não blefar, dá Check grátis
            if ActionType.CHECK in legal_actions:
                return BluffDecision(
                    action_type=ActionType.CHECK,
                    amount=0,
                    is_bluff=False,
                    tactic="Free Check",
                    fold_equity=fold_equity,
                    reason="Check gratuito para ver a próxima carta",
                )

        # Cenário B: Enfrentando aposta (to_call > 0)
        # Blefe de re-aumento (3-Bet / Bluff Raise)
        can_raise = ActionType.RAISE in legal_actions and player_stack > to_call
        is_small_bet = to_call <= pot_size * 0.35

        if should_bluff and can_raise and (is_small_bet or is_scare):
            # Raise agressivo de 2.5x a 3x
            raise_amount = current_highest_bet + max(
                min_raise, int(to_call * 2.2 * self.aggression_multiplier)
            )
            max_possible = player_current_bet + player_stack
            raise_amount = min(max_possible, raise_amount)

            if raise_amount > current_highest_bet:
                return BluffDecision(
                    action_type=ActionType.RAISE,
                    amount=raise_amount,
                    is_bluff=True,
                    tactic="Bluff Raise",
                    fold_equity=fold_equity,
                    reason=(
                        f"Re-aumento de blefe contra aposta fraca "
                        f"(FE={fold_equity:.2f})"
                    ),
                )

        # Float / Call especulativo em pote barato
        if ActionType.CALL in legal_actions and to_call <= big_blind * 2:
            if roll < 0.35:
                return BluffDecision(
                    action_type=ActionType.CALL,
                    amount=0,
                    is_bluff=False,
                    tactic="Float Call",
                    fold_equity=fold_equity,
                    reason="Float barato para tentar roubar o pote na street seguinte",
                )

        # Desistência prudente quando o adversário aposta pesado
        if ActionType.FOLD in legal_actions:
            return BluffDecision(
                action_type=ActionType.FOLD,
                amount=0,
                is_bluff=False,
                tactic="Prudent Fold",
                fold_equity=fold_equity,
                reason="Desistência contra pressão adversária sem valor matemático",
            )

        # Fallback seguro
        fallback_action = legal_actions[0] if legal_actions else ActionType.FOLD
        return BluffDecision(
            action_type=fallback_action,
            amount=0,
            is_bluff=False,
            tactic="Fallback",
            fold_equity=fold_equity,
            reason="Ação de contingência",
        )

    def _decide_value_play(
        self,
        pot_size: int,
        to_call: int,
        player_stack: int,
        player_current_bet: int,
        current_highest_bet: int,
        min_raise: int,
        big_blind: int,
        legal_actions: Sequence[ActionType],
        hand_desc: str,
    ) -> BluffDecision:
        """Executa aposta legítima de valor ao possuir mão consolidada."""
        if ActionType.RAISE in legal_actions and player_stack > to_call:
            raise_val = current_highest_bet + max(
                min_raise, int(pot_size * 0.75 * self.aggression_multiplier)
            )
            max_possible = player_current_bet + player_stack
            raise_val = min(max_possible, raise_val)
            return BluffDecision(
                action_type=ActionType.RAISE,
                amount=raise_val,
                is_bluff=False,
                tactic="Value Raise",
                fold_equity=0.3,
                reason=f"Aposta de valor com mão forte ({hand_desc})",
            )

        if ActionType.BET in legal_actions:
            bet_val = max(big_blind, int(pot_size * 0.65))
            bet_val = min(player_stack, bet_val)
            return BluffDecision(
                action_type=ActionType.BET,
                amount=bet_val,
                is_bluff=False,
                tactic="Value Bet",
                fold_equity=0.3,
                reason=f"Abertura por valor ({hand_desc})",
            )

        if ActionType.CALL in legal_actions:
            return BluffDecision(
                action_type=ActionType.CALL,
                amount=0,
                is_bluff=False,
                tactic="Value Call",
                fold_equity=0.3,
                reason=f"Call de valor ({hand_desc})",
            )

        if ActionType.CHECK in legal_actions:
            return BluffDecision(
                action_type=ActionType.CHECK,
                amount=0,
                is_bluff=False,
                tactic="Check Trap",
                fold_equity=0.3,
                reason="Check por controle de pote com mão formada",
            )

        return BluffDecision(
            action_type=ActionType.FOLD,
            amount=0,
            is_bluff=False,
            tactic="Safe",
            fold_equity=0.0,
            reason="Contingência",
        )

    def _is_dry_board(self, community_cards: Sequence[Card]) -> bool:
        """Determina se o bordo é seco (desconectado, sem draws óbvios)."""
        if len(community_cards) < 3:
            return False

        suits = [c.suit for c in community_cards[:3]]
        # Se 3 cartas têm naipes diferentes (rainbow)
        is_rainbow = len(set(suits)) == 3

        ranks = sorted([c.rank.value for c in community_cards[:3]])
        # Dispersão alta entre as cartas (pouco potencial de sequência)
        gap = ranks[-1] - ranks[0]
        is_disconnected = gap >= 5 and (ranks[1] - ranks[0] >= 2)

        return is_rainbow and is_disconnected

    def _has_scare_card(self, community_cards: Sequence[Card]) -> bool:
        """Verifica se há cartas intimidatórias (Ás, Rei ou 3 cartas do mesmo naipe)."""
        if not community_cards:
            return False

        has_high_card = any(
            c.rank in (Rank.ACE, Rank.KING) for c in community_cards
        )
        suit_counts: dict = {}
        for c in community_cards:
            suit_counts[c.suit] = suit_counts.get(c.suit, 0) + 1
        has_flush_scare = any(count >= 3 for count in suit_counts.values())

        return has_high_card or has_flush_scare

    def _track_decision_telemetry(self, decision: BluffDecision) -> None:
        """Atualiza os contadores internos para relatórios estatísticos."""
        if decision.is_bluff:
            self.bluffs_attempted += 1

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
    agent = BlufferAgent(
        player_id="bluffer_test",
        name="Blefador Alpha",
        bluff_frequency=0.6,
        rng=random.Random(42),
    )
    hole = [Card.from_str("7s"), Card.from_str("2c")]
    board = [Card.from_str("Ah"), Card.from_str("8d"), Card.from_str("3c")]

    dec = agent.evaluate_state(
        hole_cards=hole,
        community_cards=board,
        pot_size=120,
        to_call=0,
        player_stack=900,
        player_current_bet=0,
        current_highest_bet=0,
        min_raise=20,
        big_blind=20,
        num_opponents=2,
        legal_actions=[ActionType.CHECK, ActionType.BET],
        street=Street.FLOP,
    )
    print("Decisão isolada do Agente Blefador:")
    print(f"  Ação: {dec.action_type.value}")
    print(f"  Quantia: {dec.amount}")
    print(f"  Blefe? {dec.is_bluff}")
    print(f"  Tática: {dec.tactic}")
    print(f"  Fold Equity: {dec.fold_equity:.2f}")
    print(f"  Razão: {dec.reason}")
