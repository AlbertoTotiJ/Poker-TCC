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


def test_mathematical_agent_preflop_calls_suited_connectors_and_pairs() -> None:
    """Verifica que o agente não dá fold pré-flop pagando 1 BB com mãos jogáveis."""
    agent = MathematicalAgent(player_id="math_spec", name="MathSpec")

    # 9s 8s (conectores de mesmo naipe) contra 3 oponentes
    dec_sc = agent.evaluate_state(
        hole_cards=(Card.from_str("9s"), Card.from_str("8s")),
        community_cards=(),
        pot_size=30,
        to_call=20,
        player_stack=1000,
        player_current_bet=0,
        current_highest_bet=20,
        min_raise=20,
        big_blind=20,
        num_opponents=3,
        legal_actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
    )
    assert dec_sc.action_type in (ActionType.CALL, ActionType.RAISE)
    assert dec_sc.action_type != ActionType.FOLD

    # 5s 5d (par baixo) em mesa multiway de 6 jogadores (5 oponentes)
    dec_pair = agent.evaluate_state(
        hole_cards=(Card.from_str("5s"), Card.from_str("5d")),
        community_cards=(),
        pot_size=30,
        to_call=20,
        player_stack=1000,
        player_current_bet=0,
        current_highest_bet=20,
        min_raise=20,
        big_blind=20,
        num_opponents=5,
        legal_actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
    )
    assert dec_pair.action_type in (ActionType.CALL, ActionType.RAISE)
    assert dec_pair.action_type != ActionType.FOLD


def test_mathematical_agent_preflop_raises_premium_hands() -> None:
    """Verifica que o agente aumenta por valor pré-flop com mãos premium (AA/KK)."""
    agent = MathematicalAgent(player_id="math_prem", name="MathPrem")

    dec_aa = agent.evaluate_state(
        hole_cards=(Card.from_str("As"), Card.from_str("Ah")),
        community_cards=(),
        pot_size=30,
        to_call=20,
        player_stack=1000,
        player_current_bet=0,
        current_highest_bet=20,
        min_raise=20,
        big_blind=20,
        num_opponents=3,
        legal_actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
    )
    assert dec_aa.action_type == ActionType.RAISE
    assert dec_aa.amount >= 40
    assert "Raise por valor" in dec_aa.reason


def test_mathematical_agent_preflop_folds_trash_facing_bet() -> None:
    """Verifica que cartas lixo (7d 2c) desistem pré-flop diante de custo."""
    agent = MathematicalAgent(player_id="math_trash", name="MathTrash")

    dec_trash = agent.evaluate_state(
        hole_cards=(Card.from_str("7d"), Card.from_str("2c")),
        community_cards=(),
        pot_size=30,
        to_call=20,
        player_stack=1000,
        player_current_bet=0,
        current_highest_bet=20,
        min_raise=20,
        big_blind=20,
        num_opponents=3,
        legal_actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
    )
    assert dec_trash.action_type == ActionType.FOLD
    assert "-EV Fold" in dec_trash.reason


def test_mathematical_agent_preflop_rejects_huge_bet_with_speculative_hands() -> None:
    """Verifica que mãos especulativas desistem de apostas desproporcionais."""
    agent = MathematicalAgent(player_id="math_safe", name="MathSafe")

    # 9s 8s contra aposta massiva de 14x BB (to_call = 280)
    dec_huge = agent.evaluate_state(
        hole_cards=(Card.from_str("9s"), Card.from_str("8s")),
        community_cards=(),
        pot_size=310,
        to_call=280,
        player_stack=1000,
        player_current_bet=0,
        current_highest_bet=280,
        min_raise=20,
        big_blind=20,
        num_opponents=1,
        legal_actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
    )
    assert dec_huge.action_type == ActionType.FOLD
    assert "-EV Fold" in dec_huge.reason
