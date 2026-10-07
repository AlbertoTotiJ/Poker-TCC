import random
import pytest

from src.engine.deck import Card, Deck, Rank, Suit


def test_card_creation_and_attributes() -> None:
    card = Card(Rank.ACE, Suit.SPADES)
    assert card.rank == Rank.ACE
    assert card.suit == Suit.SPADES
    assert str(card) == "A♠"


def test_card_from_str() -> None:
    assert Card.from_str("As") == Card(Rank.ACE, Suit.SPADES)
    assert Card.from_str("Kh") == Card(Rank.KING, Suit.HEARTS)
    assert Card.from_str("Td") == Card(Rank.TEN, Suit.DIAMONDS)
    assert Card.from_str("2c") == Card(Rank.TWO, Suit.CLUBS)


def test_card_from_str_invalid() -> None:
    with pytest.raises(ValueError):
        Card.from_str("X")
    with pytest.raises(ValueError):
        Card.from_str("1s")
    with pytest.raises(ValueError):
        Card.from_str("Ax")


def test_deck_initialization_contains_52_unique_cards() -> None:
    deck = Deck()
    assert len(deck) == 52
    assert len(set(deck.remaining_cards)) == 52


def test_deck_draw_and_burn() -> None:
    deck = Deck()
    cards = deck.draw(2)
    assert len(cards) == 2
    assert len(deck) == 50

    burned = deck.burn()
    assert isinstance(burned, Card)
    assert len(deck) == 49


def test_deck_draw_exceeding_capacity_raises_error() -> None:
    deck = Deck()
    with pytest.raises(ValueError):
        deck.draw(53)


def test_deck_shuffle_deterministic() -> None:
    deck1 = Deck(rng=random.Random(42))
    deck1.shuffle()

    deck2 = Deck(rng=random.Random(42))
    deck2.shuffle()

    assert deck1.remaining_cards == deck2.remaining_cards
