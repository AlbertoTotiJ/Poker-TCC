from collections import Counter
from dataclasses import dataclass
from enum import IntEnum
import itertools
from typing import Optional, Sequence, Tuple

from src.engine.deck import Card, Rank


class HandRank(IntEnum):
    HIGH_CARD = 1
    ONE_PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10


@dataclass(frozen=True)
class HandScore:
    hand_rank: HandRank
    tiebreakers: Tuple[int, ...]
    cards: Tuple[Card, ...]

    def __lt__(self, other: "HandScore") -> bool:
        if self.hand_rank != other.hand_rank:
            return self.hand_rank < other.hand_rank
        return self.tiebreakers < other.tiebreakers

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HandScore):
            return False
        return (
            self.hand_rank == other.hand_rank and self.tiebreakers == other.tiebreakers
        )

    def __gt__(self, other: "HandScore") -> bool:
        if self.hand_rank != other.hand_rank:
            return self.hand_rank > other.hand_rank
        return self.tiebreakers > other.tiebreakers

    def __le__(self, other: "HandScore") -> bool:
        return self < other or self == other

    def __ge__(self, other: "HandScore") -> bool:
        return self > other or self == other


def _evaluate_five_card_hand(cards: Sequence[Card]) -> HandScore:
    """Classifica cinco cartas e extrai os critérios de desempate."""
    sorted_cards = sorted(cards, key=lambda c: c.rank.value, reverse=True)
    ranks = [c.rank.value for c in sorted_cards]
    is_flush = len({c.suit for c in sorted_cards}) == 1

    unique_ranks = sorted(set(ranks), reverse=True)
    is_straight = False
    straight_high = 0

    if len(unique_ranks) == 5:
        if unique_ranks[0] - unique_ranks[4] == 4:
            is_straight = True
            straight_high = unique_ranks[0]
        # Regra do Ás como carta baixa (sequência 5-4-3-2-A / 'Wheel')
        elif unique_ranks == [14, 5, 4, 3, 2]:
            is_straight = True
            straight_high = 5

    if is_flush and is_straight:
        if (
            straight_high == 14
            and sorted_cards[0].rank == Rank.ACE
            and sorted_cards[1].rank == Rank.KING
        ):
            return HandScore(HandRank.ROYAL_FLUSH, (14,), tuple(sorted_cards))
        return HandScore(HandRank.STRAIGHT_FLUSH, (straight_high,), tuple(sorted_cards))

    counts = Counter(ranks)
    frequency_groups = sorted(
        counts.items(), key=lambda item: (item[1], item[0]), reverse=True
    )
    pattern = [item[1] for item in frequency_groups]

    if pattern == [4, 1]:
        quad_rank = frequency_groups[0][0]
        kicker = frequency_groups[1][0]
        return HandScore(
            HandRank.FOUR_OF_A_KIND, (quad_rank, kicker), tuple(sorted_cards)
        )

    if pattern == [3, 2]:
        trips_rank = frequency_groups[0][0]
        pair_rank = frequency_groups[1][0]
        return HandScore(
            HandRank.FULL_HOUSE, (trips_rank, pair_rank), tuple(sorted_cards)
        )

    if is_flush:
        return HandScore(HandRank.FLUSH, tuple(ranks), tuple(sorted_cards))

    if is_straight:
        return HandScore(HandRank.STRAIGHT, (straight_high,), tuple(sorted_cards))

    if pattern == [3, 1, 1]:
        trips_rank = frequency_groups[0][0]
        kickers = tuple(item[0] for item in frequency_groups[1:])
        return HandScore(
            HandRank.THREE_OF_A_KIND, (trips_rank, *kickers), tuple(sorted_cards)
        )

    if pattern == [2, 2, 1]:
        high_pair = frequency_groups[0][0]
        low_pair = frequency_groups[1][0]
        kicker = frequency_groups[2][0]
        return HandScore(
            HandRank.TWO_PAIR, (high_pair, low_pair, kicker), tuple(sorted_cards)
        )

    if pattern == [2, 1, 1, 1]:
        pair_rank = frequency_groups[0][0]
        kickers = tuple(item[0] for item in frequency_groups[1:])
        return HandScore(HandRank.ONE_PAIR, (pair_rank, *kickers), tuple(sorted_cards))

    return HandScore(HandRank.HIGH_CARD, tuple(ranks), tuple(sorted_cards))


def evaluate_hand(cards: Sequence[Card]) -> HandScore:
    """Determina a melhor combinação a partir de 5 a 7 cartas.

    Args:
        cards: Sequência contendo de 5 a 7 instâncias de Card.

    Returns:
        A melhor pontuação de mão HandScore encontrada.

    Raises:
        ValueError: Se a quantidade de cartas for inferior a 5.
    """
    if len(cards) < 5:
        raise ValueError(f"Avaliação exige ao menos 5 cartas. Fornecido: {len(cards)}")

    if len(cards) == 5:
        return _evaluate_five_card_hand(cards)

    all_combinations = itertools.combinations(cards, 5)
    best_score: Optional[HandScore] = None

    for combination in all_combinations:
        score = _evaluate_five_card_hand(combination)
        if best_score is None or score > best_score:
            best_score = score

    assert best_score is not None
    return best_score
