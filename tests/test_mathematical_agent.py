import random

from src.agents.mathematical_agent import MathematicalAgent
from src.engine.deck import Card
from src.engine.player import Player
from src.engine.table import Action, ActionType, Table


def test_mathematical_agent_instantiation() -> None:
    """Verifica instanciação com parâmetros padrão e customizados."""
    agent = MathematicalAgent(
        player_id="bot_math_1",
        name="Euler",
        raise_equity_threshold=0.70,
        call_ev_margin=0.05,
        draw_weight=1.2,
    )
    assert agent.player_id == "bot_math_1"
    assert agent.name == "Euler"
    assert agent.raise_equity_threshold == 0.70
    assert agent.call_ev_margin == 0.05
    assert agent.draw_weight == 1.2
    assert agent.aggression_factor == 0.0


def test_mathematical_agent_free_to_check_never_folds() -> None:
    """Verifica que o agente nunca desiste quando o custo para ver cartas é zero."""
    p1 = Player("p1", "Bot1", 1000)
    p2 = Player("p2", "MathBot", 1000)
    table = Table([p1, p2], small_blind=10, big_blind=20, rng=random.Random(42))
    table.start_new_hand()

    # Preflop: p1 paga o BB, vez do p2 (BB), custo para continuar é 0
    table.apply_action(Action("p1", ActionType.CALL))

    agent = MathematicalAgent(
        player_id="p2",
        name="MathBot",
        rng=random.Random(123),
    )
    action = agent.decide_action(table)

    assert action.action_type in (ActionType.CHECK, ActionType.BET)
    assert action.action_type != ActionType.FOLD


def test_mathematical_agent_folds_negative_ev() -> None:
    """Verifica que o agente desiste de aposta alta com mão fraca (-EV)."""
    p1 = Player("p1", "Aggro", 1000)
    p2 = Player("p2", "MathBot", 1000)
    table = Table([p1, p2], small_blind=10, big_blind=20, rng=random.Random(7))
    table.start_new_hand()

    # Força cartas fracas no MathBot e aposta alta do oponente
    p2.hole_cards = (Card.from_str("7d"), Card.from_str("2c"))
    table.apply_action(Action("p1", ActionType.RAISE, amount=300))

    agent = MathematicalAgent(
        player_id="p2",
        name="MathBot",
        rng=random.Random(99),
    )
    action = agent.decide_action(table)

    # Com 7-2 contra aposta massiva, o EV é profundamente negativo
    assert action.action_type == ActionType.FOLD


def test_mathematical_agent_calls_or_raises_pocket_aces() -> None:
    """Verifica que com AA o agente toma ação agressiva ou lucrativa (+EV)."""
    p1 = Player("p1", "Opponent", 1000)
    p2 = Player("p2", "MathBot", 1000)
    table = Table([p1, p2], small_blind=10, big_blind=20, rng=random.Random(10))
    table.start_new_hand()

    p2.hole_cards = (Card.from_str("As"), Card.from_str("Ah"))
    table.apply_action(Action("p1", ActionType.CALL))

    agent = MathematicalAgent(
        player_id="p2",
        name="MathBot",
        raise_equity_threshold=0.60,
        rng=random.Random(42),
    )
    action = agent.decide_action(table)

    # Par de Ases deve optar por BET/RAISE por valor ou no mínimo CHECK
    assert action.action_type in (ActionType.BET, ActionType.CHECK)
    assert action.action_type != ActionType.FOLD


def test_mathematical_agent_evaluates_draws_correctly() -> None:
    """Valida a detecção e valoração de outs de flush e straight draws."""
    agent = MathematicalAgent(
        player_id="math",
        name="MathBot",
        rng=random.Random(5),
    )

    # Nut Flush Draw no Flop
    hole = (Card.from_str("Ah"), Card.from_str("Kh"))
    board = [Card.from_str("9h"), Card.from_str("4h"), Card.from_str("2c")]
    equity, outs = agent.calculate_effective_equity(hole, board, num_opponents=1)

    assert outs >= 9
    assert equity > 0.50


def test_mathematical_agent_isolated_decision() -> None:
    """Valida que o método evaluate_state funciona de forma 100% desacoplada."""
    agent = MathematicalAgent(player_id="math_iso", name="Math")

    decision = agent.evaluate_state(
        hole_cards=(Card.from_str("Ks"), Card.from_str("Kd")),
        community_cards=[Card.from_str("Kc"), Card.from_str("7d"), Card.from_str("2h")],
        pot_size=100,
        to_call=0,
        player_stack=500,
        player_current_bet=0,
        current_highest_bet=0,
        min_raise=20,
        big_blind=20,
        num_opponents=2,
        legal_actions=[ActionType.CHECK, ActionType.BET],
    )

    assert decision.action_type == ActionType.BET
    assert decision.equity > 0.90
    assert decision.amount >= 20
    assert "Value bet" in decision.reason
