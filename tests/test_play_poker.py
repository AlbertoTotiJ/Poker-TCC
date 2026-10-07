"""Testes unitários e de integração para o simulador de poker.

Cobre a visualização back-end e o loop de jogo.
"""

import random
import pytest

from scripts.play_poker import PokerGame
from src.engine.deck import Card
from src.engine.hand_eval import HandRank, HandScore
from src.visualization.backend_view import (
    format_card,
    format_community_cards,
    format_hand_combination,
    get_position_label,
)


def test_format_card() -> None:
    card = Card.from_str("As")
    assert "A♠" in format_card(card)
    assert format_card(None) == "[ -- ]"
    assert format_card(card, hidden=True) == "[ ?? ]"


def test_format_hand_combination() -> None:
    score = HandScore(
        hand_rank=HandRank.ROYAL_FLUSH,
        tiebreakers=(14,),
        cards=tuple(Card.from_str(c) for c in ["As", "Ks", "Qs", "Js", "Ts"]),
    )
    assert format_hand_combination(score) == "Royal Flush"

    score_pair = HandScore(
        hand_rank=HandRank.ONE_PAIR,
        tiebreakers=(14, 13, 12, 10),
        cards=tuple(Card.from_str(c) for c in ["Ah", "As", "Kd", "Qc", "Ts"]),
    )
    assert "Par de Ás" in format_hand_combination(score_pair)


def test_format_community_cards() -> None:
    flop = [Card.from_str("Ah"), Card.from_str("Kd"), Card.from_str("Qc")]
    formatted = format_community_cards(flop)
    assert "A♥" in formatted
    assert "[ -- ]" in formatted


def test_get_position_label() -> None:
    # Heads-up (2 jogadores)
    assert get_position_label(player_idx=0, button_idx=0, total_players=2) == "D/SB"
    assert get_position_label(player_idx=1, button_idx=0, total_players=2) == "BB"

    # 4 jogadores
    assert get_position_label(player_idx=0, button_idx=0, total_players=4) == "D"
    assert get_position_label(player_idx=1, button_idx=0, total_players=4) == "SB"
    assert get_position_label(player_idx=2, button_idx=0, total_players=4) == "BB"
    assert get_position_label(player_idx=3, button_idx=0, total_players=4) == "  "


def test_poker_game_validation() -> None:
    with pytest.raises(ValueError, match="entre 2 e 9"):
        PokerGame(num_players=1)

    with pytest.raises(ValueError, match="entre 2 e 9"):
        PokerGame(num_players=10)

    game = PokerGame(num_players=5, starting_stack=500)
    assert len(game.players) == 5
    assert len(game.bot_agents) == 4
    assert game.players[0].name == "Você (Humano)"


def test_poker_game_auto_simulation_conserves_chips() -> None:
    starting_stack = 1000
    num_players = 4
    total_expected = starting_stack * num_players

    game = PokerGame(
        num_players=num_players,
        starting_stack=starting_stack,
        small_blind=10,
        big_blind=20,
        rng=random.Random(123),
        auto_mode=True,
    )

    game.play(max_hands=5)

    assert game.hand_number >= 1
    # A soma de todas as fichas dos jogadores deve ser rigorosamente constante
    assert sum(p.stack for p in game.players) == total_expected
