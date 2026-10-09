"""Cálculo de probabilidade de vitória (Equity), Pot Odds e texturas de bordo."""

from collections import Counter
from dataclasses import dataclass
import random
from typing import Optional, Sequence, Tuple

from src.engine.deck import Card, Deck, Rank
from src.engine.hand_eval import evaluate_hand


@dataclass(frozen=True)
class EquityResult:
    """Resultado estatístico de simulação de Monte Carlo para equidade da mão."""

    win_rate: float
    tie_rate: float
    loss_rate: float
    equity: float
    simulations: int


def calculate_pot_odds(to_call: int, pot_size: int) -> float:
    """Calcula a proporção de pot odds para uma decisão de pagamento.

    Args:
        to_call: Quantidade de fichas necessárias para cobrir a aposta.
        pot_size: Montante total acumulado no pote antes do call.

    Returns:
        Pot odds como fração decimal entre 0.0 e 1.0 (ex: 0.25 = 25%).
    """
    total_after_call = pot_size + to_call
    if total_after_call <= 0 or to_call <= 0:
        return 0.0
    return to_call / total_after_call


def is_profitable_call(equity: float, pot_odds: float) -> bool:
    """Indica se um call possui valor esperado positivo (+EV) frente aos pot odds."""
    return equity >= pot_odds


def has_flush_draw(cards: Sequence[Card]) -> bool:
    """Detecta se há 4 cartas do mesmo naipe (draw para Flush)."""
    if len(cards) < 4:
        return False
    suit_counts = Counter(c.suit for c in cards)
    return any(count == 4 for count in suit_counts.values())


def has_straight_draw(cards: Sequence[Card]) -> bool:
    """Detecta se há 4 cartas conectadas formando straight draw (open ou gutshot)."""
    if len(cards) < 4:
        return False
    ranks = sorted({c.rank.value for c in cards})
    if 14 in ranks:
        ranks = [1] + ranks  # Permite avaliar A-2-3-4

    # Varre janelas consecutivas de amplitude <= 4
    for i in range(len(ranks)):
        window = [r for r in ranks if ranks[i] <= r <= ranks[i] + 4]
        if len(window) == 4:
            return True
    return False


def has_overcards(
    hole_cards: Tuple[Card, Card], community_cards: Sequence[Card]
) -> bool:
    """Indica se as cartas privadas são maiores que a maior do bordo."""
    if not community_cards:
        return hole_cards[0].rank >= Rank.TEN and hole_cards[1].rank >= Rank.TEN
    max_board_rank = max(c.rank.value for c in community_cards)
    return (
        hole_cards[0].rank.value > max_board_rank
        and hole_cards[1].rank.value > max_board_rank
    )


def estimate_hand_equity(
    hole_cards: Tuple[Card, Card],
    community_cards: Sequence[Card] = (),
    num_opponents: int = 1,
    num_simulations: int = 300,
    rng: Optional[random.Random] = None,
) -> EquityResult:
    """Calcula a equidade esperada via simulações de Monte Carlo contra mãos aleatórias.

    Args:
        hole_cards: Par de cartas fechadas do jogador.
        community_cards: Cartas comunitárias já abertas (0, 3, 4 ou 5).
        num_opponents: Quantidade de oponentes ativos na mão.
        num_simulations: Número de iterações de Monte Carlo.
        rng: Gerador de números pseudoaleatórios opcional.

    Returns:
        Instância de EquityResult contendo as taxas estimadas.
    """
    if num_opponents < 1:
        return EquityResult(1.0, 0.0, 0.0, 1.0, num_simulations)

    known_cards = set(hole_cards) | set(community_cards)
    full_deck = Deck()
    available_cards = [c for c in full_deck.remaining_cards if c not in known_cards]

    local_rng = rng if rng is not None else random.Random()
    wins = 0
    ties = 0
    losses = 0

    cards_needed_board = 5 - len(community_cards)
    cards_needed_opponents = num_opponents * 2
    total_needed = cards_needed_board + cards_needed_opponents

    if total_needed > len(available_cards):
        raise ValueError("Cartas disponíveis insuficientes no baralho para simulação.")

    for _ in range(num_simulations):
        sampled = local_rng.sample(available_cards, total_needed)

        # Completa as cartas do bordo
        simulated_board = list(community_cards) + sampled[:cards_needed_board]

        # Avalia a mão do jogador
        my_score = evaluate_hand(list(hole_cards) + simulated_board)

        # Avalia as mãos de cada oponente
        opponents_scores = []
        offset = cards_needed_board
        for _ in range(num_opponents):
            opp_hole = (sampled[offset], sampled[offset + 1])
            offset += 2
            opp_score = evaluate_hand(list(opp_hole) + simulated_board)
            opponents_scores.append(opp_score)

        best_opp_score = max(opponents_scores)

        if my_score > best_opp_score:
            wins += 1
        elif my_score == best_opp_score:
            ties += 1
        else:
            losses += 1

    win_rate = wins / num_simulations
    tie_rate = ties / num_simulations
    loss_rate = losses / num_simulations
    equity = win_rate + (tie_rate / 2.0)

    return EquityResult(
        win_rate=win_rate,
        tie_rate=tie_rate,
        loss_rate=loss_rate,
        equity=equity,
        simulations=num_simulations,
    )
