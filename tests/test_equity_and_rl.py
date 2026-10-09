"""Testes de utilitários vetoriais, cálculo de equidade e ambiente de RL."""

import random

import pytest

from src.engine.deck import Card, Deck
from src.engine.encoding import (
    card_to_id,
    cards_to_one_hot,
    hand_rank_to_one_hot,
    id_to_card,
    street_to_one_hot,
)
from src.engine.equity import (
    calculate_pot_odds,
    estimate_hand_equity,
    has_flush_draw,
    has_overcards,
    has_straight_draw,
    is_profitable_call,
)
from src.engine.hand_eval import HandRank
from src.engine.rl_env import DiscreteAction, PokerEnv


def test_card_to_id_bijection_all_52_cards() -> None:
    """Verifica que a conversão card <-> id é bijetora para o baralho todo."""
    deck = Deck()
    assert len(deck) == 52

    seen_ids = set()
    for card in deck.remaining_cards:
        cid = card_to_id(card)
        assert 0 <= cid < 52
        assert cid not in seen_ids
        seen_ids.add(cid)

        # Inversa perfeita
        reconstructed = id_to_card(cid)
        assert reconstructed == card

    assert len(seen_ids) == 52


def test_one_hot_encodings() -> None:
    """Valida as codificações one-hot de cartas, ranks e streets."""
    cards = [Card.from_str("Ah"), Card.from_str("Kd")]
    vec = cards_to_one_hot(cards)
    assert len(vec) == 52
    assert sum(vec) == 2.0
    assert vec[card_to_id(Card.from_str("Ah"))] == 1.0
    assert vec[card_to_id(Card.from_str("Kd"))] == 1.0

    hr_vec = hand_rank_to_one_hot(HandRank.ROYAL_FLUSH)
    assert len(hr_vec) == 10
    assert hr_vec[9] == 1.0
    assert sum(hr_vec) == 1.0

    st_vec = street_to_one_hot(1)
    assert len(st_vec) == 4
    assert st_vec == [0.0, 1.0, 0.0, 0.0]


def test_equity_and_draw_detection() -> None:
    """Valida detecção de draws e cálculo de pot odds / equity."""
    # Flush draw: 4 copas
    four_hearts = [
        Card.from_str("Ah"),
        Card.from_str("Kh"),
        Card.from_str("7h"),
        Card.from_str("2h"),
        Card.from_str("Qc"),
    ]
    assert has_flush_draw(four_hearts)
    assert not has_flush_draw(four_hearts[:3])

    # Straight draw: 9, 8, 7, 6
    st_draw = [
        Card.from_str("9s"),
        Card.from_str("8h"),
        Card.from_str("7d"),
        Card.from_str("6c"),
        Card.from_str("2c"),
    ]
    assert has_straight_draw(st_draw)

    # Overcards: AK contra bordo 9-7-2
    ak = (Card.from_str("As"), Card.from_str("Kd"))
    low_board = [Card.from_str("9h"), Card.from_str("7d"), Card.from_str("2c")]
    assert has_overcards(ak, low_board)

    # Pot odds: pagar 20 para pote de 80 -> 20 / (80 + 20) = 0.20 (20%)
    odds = calculate_pot_odds(to_call=20, pot_size=80)
    assert odds == pytest.approx(0.20)
    assert is_profitable_call(equity=0.30, pot_odds=odds)
    assert not is_profitable_call(equity=0.15, pot_odds=odds)

    # Simulação Monte Carlo: Pocket Aces vs mão aleatória
    aces = (Card.from_str("As"), Card.from_str("Ah"))
    rng = random.Random(42)
    eq_result = estimate_hand_equity(
        hole_cards=aces,
        community_cards=(),
        num_opponents=1,
        num_simulations=150,
        rng=rng,
    )
    # Par de Ases tem ~80-85% de equidade pré-flop contra 1 oponente aleatório
    assert eq_result.equity > 0.70
    assert eq_result.win_rate > 0.65


def test_poker_env_gymnasium_cycle() -> None:
    """Valida o ciclo completo de treinamento (reset e step) no PokerEnv."""
    env = PokerEnv(num_players=3, starting_stack=1000, seed=123)
    obs, info = env.reset(seed=123)

    assert "vector" in obs
    assert len(obs["vector"]) == 132
    assert "action_mask" in obs
    assert len(obs["action_mask"]) == 6
    assert isinstance(info["pot"], int)

    # Verifica action mask no Hero
    mask = env.get_action_mask(env.hero_id)
    assert any(mask)

    # Executa uma ação legal (ex: CHECK/CALL)
    next_obs, reward, terminated, truncated, next_info = env.step(
        DiscreteAction.CHECK_CALL
    )
    assert "vector" in next_obs
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert not truncated
    assert "is_bluff" in next_info
