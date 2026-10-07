import pytest

from src.engine.dealer import Dealer
from src.engine.deck import Card


def test_dealer_initial_state() -> None:
    dealer = Dealer()
    assert len(dealer.community_cards) == 0
    assert len(dealer.burn_cards) == 0
    assert len(dealer.deck) == 52


def test_dealer_deal_hole_cards() -> None:
    dealer = Dealer()
    dealer.start_new_hand()
    player_ids = ["p1", "p2", "p3"]
    hole_cards = dealer.deal_hole_cards(player_ids)

    assert len(hole_cards) == 3
    all_dealt_cards = []
    for pid in player_ids:
        cards = hole_cards[pid]
        assert len(cards) == 2
        all_dealt_cards.extend(cards)

    # Todas as cartas distribuídas aos jogadores devem ser distintas
    assert len(set(all_dealt_cards)) == 6
    assert len(dealer.deck) == 52 - 6


def test_dealer_full_board_sequence_with_burns() -> None:
    dealer = Dealer()
    dealer.start_new_hand()
    dealer.deal_hole_cards(["p1", "p2"])

    flop = dealer.deal_flop()
    assert len(flop) == 3
    assert len(dealer.community_cards) == 3
    assert len(dealer.burn_cards) == 1

    turn = dealer.deal_turn()
    assert isinstance(turn, Card)
    assert len(dealer.community_cards) == 4
    assert len(dealer.burn_cards) == 2

    river = dealer.deal_river()
    assert isinstance(river, Card)
    assert len(dealer.community_cards) == 5
    assert len(dealer.burn_cards) == 3

    # Total consumido do baralho: 4 (players) + 3 (burns) + 5 (board) = 12 cartas
    assert len(dealer.deck) == 40


def test_dealer_invalid_transitions_raise_error() -> None:
    dealer = Dealer()
    dealer.start_new_hand()

    with pytest.raises(RuntimeError):
        dealer.deal_turn()

    dealer.deal_flop()
    with pytest.raises(RuntimeError):
        dealer.deal_flop()
    with pytest.raises(RuntimeError):
        dealer.deal_river()
