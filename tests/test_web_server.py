"""Testes unitários cobrindo a sessão e a API do servidor web de poker."""

import random
from src.engine.table import ActionType
from src.visualization.web_server import WebPokerSession, card_to_dict


def test_card_to_dict() -> None:
    assert card_to_dict(None) is None

    from src.engine.deck import Card

    c = Card.from_str("Ah")
    d = card_to_dict(c)
    assert d is not None
    assert d["rank"] == "A"
    assert d["suit"] == "♥"
    assert d["color"] == "red"


def test_web_poker_session_init_and_state() -> None:
    session = WebPokerSession(num_players=4, starting_stack=1000, rng=random.Random(42))
    state = session.get_serialized_state()

    assert state["active"] is True
    assert len(state["players"]) == 4
    assert state["pot_total"] >= 30
    assert state["hand_number"] == 1
    assert "community_cards" in state


def test_web_poker_session_bot_step_and_transitions() -> None:
    session = WebPokerSession(num_players=3, starting_stack=1000, rng=random.Random(10))

    # Avança ações de bots se houver algum na vez
    for _ in range(10):
        state = session.get_serialized_state()
        if state["is_human_turn"] or state["is_hand_finished"]:
            break
        desc = session.step_bot()
        assert desc is not None


def test_web_poker_session_human_action() -> None:
    session = WebPokerSession(num_players=2, starting_stack=1000, rng=random.Random(7))
    state = session.get_serialized_state()

    # Em heads-up, se for a vez do humano, testa a aplicação de ação válida
    if state["is_human_turn"]:
        legal = state["legal_actions"]
        action_to_try = ActionType.CHECK.value if "CHECK" in legal else "CALL"
        desc = session.apply_human_action(action_to_try)
        assert desc is not None
        new_state = session.get_serialized_state()
        assert new_state["active"] is True
