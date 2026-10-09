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


RANK_NAMES_PT = {
    2: "Dois",
    3: "Três",
    4: "Quatro",
    5: "Cinco",
    6: "Seis",
    7: "Sete",
    8: "Oito",
    9: "Nove",
    10: "Dez",
    11: "Valete",
    12: "Dama",
    13: "Rei",
    14: "Ás",
}

RANK_NAMES_PLURAL_PT = {
    2: "Dois",
    3: "Três",
    4: "Quatros",
    5: "Cincos",
    6: "Seis",
    7: "Setes",
    8: "Oitos",
    9: "Noves",
    10: "Dezes",
    11: "Valetes",
    12: "Damas",
    13: "Reis",
    14: "Ases",
}

HAND_RANK_NAMES_PT = {
    HandRank.HIGH_CARD: "Carta Alta",
    HandRank.ONE_PAIR: "Um Par",
    HandRank.TWO_PAIR: "Dois Pares",
    HandRank.THREE_OF_A_KIND: "Trinca",
    HandRank.STRAIGHT: "Sequência",
    HandRank.FLUSH: "Flush",
    HandRank.FULL_HOUSE: "Full House",
    HandRank.FOUR_OF_A_KIND: "Quadra",
    HandRank.STRAIGHT_FLUSH: "Straight Flush",
    HandRank.ROYAL_FLUSH: "Royal Flush",
}


def get_hand_rank_name_pt(hand_rank: HandRank) -> str:
    """Retorna o nome em português da categoria de mão."""
    return HAND_RANK_NAMES_PT.get(hand_rank, hand_rank.name)


def describe_hand(score: "HandScore") -> str:
    """Retorna a descrição detalhada e formal em português da combinação de cartas."""
    hr = score.hand_rank
    tb = score.tiebreakers

    if hr == HandRank.ROYAL_FLUSH:
        return "Royal Flush"

    if hr == HandRank.STRAIGHT_FLUSH:
        if tb[0] == 5:
            return "Straight Flush ao Cinco (Steel Wheel: A-2-3-4-5)"
        return f"Straight Flush ao {RANK_NAMES_PT.get(tb[0], str(tb[0]))}"

    if hr == HandRank.FOUR_OF_A_KIND:
        quad_name = RANK_NAMES_PLURAL_PT.get(tb[0], str(tb[0]))
        kicker_name = RANK_NAMES_PT.get(tb[1], str(tb[1]))
        return f"Quadra de {quad_name} com kicker {kicker_name}"

    if hr == HandRank.FULL_HOUSE:
        trips_name = RANK_NAMES_PLURAL_PT.get(tb[0], str(tb[0]))
        pair_name = RANK_NAMES_PLURAL_PT.get(tb[1], str(tb[1]))
        return f"Full House de {trips_name} com {pair_name}"

    if hr == HandRank.FLUSH:
        high_name = RANK_NAMES_PT.get(tb[0], str(tb[0]))
        return f"Flush ao {high_name}"

    if hr == HandRank.STRAIGHT:
        if tb[0] == 5:
            return "Sequência ao Cinco (Wheel: A-2-3-4-5)"
        return f"Sequência ao {RANK_NAMES_PT.get(tb[0], str(tb[0]))}"

    if hr == HandRank.THREE_OF_A_KIND:
        trips_name = RANK_NAMES_PLURAL_PT.get(tb[0], str(tb[0]))
        kickers_str = ", ".join(RANK_NAMES_PT.get(k, str(k)) for k in tb[1:])
        return f"Trinca de {trips_name} (kickers: {kickers_str})"

    if hr == HandRank.TWO_PAIR:
        high_pair = RANK_NAMES_PLURAL_PT.get(tb[0], str(tb[0]))
        low_pair = RANK_NAMES_PLURAL_PT.get(tb[1], str(tb[1]))
        kicker_name = RANK_NAMES_PT.get(tb[2], str(tb[2]))
        return f"Dois Pares ({high_pair} e {low_pair}) com kicker {kicker_name}"

    if hr == HandRank.ONE_PAIR:
        pair_name = RANK_NAMES_PT.get(tb[0], str(tb[0]))
        kickers_str = ", ".join(RANK_NAMES_PT.get(k, str(k)) for k in tb[1:])
        return f"Par de {pair_name} (kickers: {kickers_str})"

    # High Card
    high_name = RANK_NAMES_PT.get(tb[0], str(tb[0]))
    kickers_str = ", ".join(RANK_NAMES_PT.get(k, str(k)) for k in tb[1:])
    return f"Carta Alta {high_name} (kickers: {kickers_str})"


@dataclass(frozen=True)
class HandScore:
    hand_rank: HandRank
    tiebreakers: Tuple[int, ...]
    cards: Tuple[Card, ...]

    @property
    def description(self) -> str:
        """Descrição legível da combinação em português."""
        return describe_hand(self)

    @property
    def rank_name_pt(self) -> str:
        """Nome simplificado da categoria em português."""
        return get_hand_rank_name_pt(self.hand_rank)

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
