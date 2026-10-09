"""Módulo de codificação vetorial de cartas e estados para Machine Learning e RL."""

from typing import Dict, List, Sequence

from src.engine.deck import Card, Rank, Suit
from src.engine.hand_eval import HandRank

# Mapeamento determinístico de naipes para índices numéricos [0..3]
SUIT_TO_INDEX: Dict[Suit, int] = {
    Suit.SPADES: 0,
    Suit.HEARTS: 1,
    Suit.DIAMONDS: 2,
    Suit.CLUBS: 3,
}

INDEX_TO_SUIT: Dict[int, Suit] = {v: k for k, v in SUIT_TO_INDEX.items()}


def card_to_id(card: Card) -> int:
    """Converte uma carta para um índice inteiro único de 0 a 51.

    Ranques: 2 (valor 2) até Ás (valor 14) -> 13 ranques.
    Fórmula: (rank.value - 2) * 4 + suit_index.
    """
    rank_idx = card.rank.value - 2
    suit_idx = SUIT_TO_INDEX[card.suit]
    return rank_idx * 4 + suit_idx


def id_to_card(card_id: int) -> Card:
    """Reconstitui uma instância de Card a partir do índice inteiro de 0 a 51."""
    if not (0 <= card_id < 52):
        raise ValueError(f"ID de carta fora do intervalo [0, 51]: {card_id}")
    rank_value = 2 + (card_id // 4)
    suit_idx = card_id % 4
    return Card(rank=Rank(rank_value), suit=INDEX_TO_SUIT[suit_idx])


def cards_to_one_hot(cards: Sequence[Card]) -> List[float]:
    """Gera um vetor binário one-hot/multi-hot de 52 dimensões para as cartas."""
    vector = [0.0] * 52
    for card in cards:
        idx = card_to_id(card)
        vector[idx] = 1.0
    return vector


def hand_rank_to_one_hot(hand_rank: HandRank) -> List[float]:
    """Gera um vetor one-hot de 10 dimensões representando a categoria de mão."""
    vector = [0.0] * 10
    idx = hand_rank.value - 1
    if 0 <= idx < 10:
        vector[idx] = 1.0
    return vector


def street_to_one_hot(street_index: int) -> List[float]:
    """Gera um vetor one-hot de 4 dimensões (Preflop, Flop, Turn, River)."""
    vector = [0.0] * 4
    if 0 <= street_index < 4:
        vector[street_index] = 1.0
    return vector
