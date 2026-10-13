"""Testes unitários cobrindo os agentes autônomos baseados em heurística."""

import random

from src.agents.heuristic import AgentProfile, HeuristicAgent
from src.engine.deck import Card
from src.engine.player import Player
from src.engine.table import Action, ActionType, Table


def test_heuristic_agent_free_to_check() -> None:
    p1 = Player("p1", "Bot1", 1000)
    p2 = Player("p2", "Bot2", 1000)
    table = Table([p1, p2], small_blind=10, big_blind=20, rng=random.Random(42))
    table.start_new_hand()

    # Preflop: p1 paga o BB, p2 tem opção de dar CHECK ou BET
    table.apply_action(Action("p1", ActionType.CALL))

    agent = HeuristicAgent(
        player_id="p2",
        name="Bot2",
        profile=AgentProfile.CONSERVATIVE,
        rng=random.Random(10),
    )
    action = agent.decide_action(table)

    # Nunca deve dar FOLD quando o custo para continuar for 0
    assert action.action_type in (ActionType.CHECK, ActionType.BET)
    assert action.action_type != ActionType.FOLD


def test_heuristic_agent_profiles_instantiation() -> None:
    agent_c = HeuristicAgent("p1", "Bot_C", AgentProfile.CONSERVATIVE)
    agent_a = HeuristicAgent("p2", "Bot_A", AgentProfile.AGGRESSIVE)
    agent_b = HeuristicAgent("p3", "Bot_B", AgentProfile.BALANCED)

    assert agent_c.profile == AgentProfile.CONSERVATIVE
    assert agent_a.profile == AgentProfile.AGGRESSIVE
    assert agent_b.profile == AgentProfile.BALANCED


def test_heuristic_agent_evaluates_preflop_strength() -> None:
    agent = HeuristicAgent("p1", "Bot", AgentProfile.BALANCED)

    # Par de Áses deve ter força consideravelmente superior a 7 e 2 offsuit
    aa_score = agent._evaluate_preflop_strength(
        Card.from_str("Ah"), Card.from_str("As")
    )
    seven_two_score = agent._evaluate_preflop_strength(
        Card.from_str("7h"), Card.from_str("2c")
    )

    assert aa_score > 0.85
    assert seven_two_score < 0.45
    assert aa_score > seven_two_score


def test_heuristic_agent_decides_facing_all_in() -> None:
    p1 = Player("p1", "Bot1", 1000)
    p2 = Player("p2", "Bot2", 30)
    table = Table([p1, p2], small_blind=10, big_blind=20, rng=random.Random(5))
    table.start_new_hand()

    # p1 vai all-in
    table.apply_action(Action("p1", ActionType.ALL_IN))

    agent = HeuristicAgent("p2", "Bot2", AgentProfile.AGGRESSIVE, rng=random.Random(1))
    legal = table.get_legal_actions("p2")
    if legal:
        action = agent.decide_action(table)
        assert action.action_type in legal


def test_bluffer_agent_steals_and_acts_in_table() -> None:
    from src.agents.bluffer_agent import BlufferAgent
    from src.engine.table import Street

    agent = BlufferAgent(
        player_id="bluffer_1",
        name="Blefador 1",
        bluff_frequency=0.99,  # Força blefe para teste determinístico
        rng=random.Random(42),
    )

    # Avaliação em mesa seca e mão fraca
    hole = [Card.from_str("7c"), Card.from_str("2d")]
    board = [Card.from_str("Ah"), Card.from_str("8s"), Card.from_str("3c")]
    dec = agent.evaluate_state(
        hole_cards=hole,
        community_cards=board,
        pot_size=100,
        to_call=0,
        player_stack=1000,
        player_current_bet=0,
        current_highest_bet=0,
        min_raise=20,
        big_blind=20,
        num_opponents=1,
        legal_actions=[ActionType.CHECK, ActionType.BET],
        street=Street.FLOP,
    )
    assert dec.action_type == ActionType.BET
    assert dec.is_bluff is True
    assert dec.fold_equity > 0.5

    # Teste de execução em mesa real
    p1 = Player("bluffer_1", "Blefador", 1000)
    p2 = Player("p2", "Oponente", 1000)
    table = Table([p1, p2], small_blind=10, big_blind=20, rng=random.Random(42))
    table.start_new_hand()
    table.apply_action(Action("bluffer_1", ActionType.CALL))
    # Vez do oponente dar check
    table.apply_action(Action("p2", ActionType.CHECK))
    # Flop
    act = agent.decide_action(table)
    assert act.action_type in table.get_legal_actions("bluffer_1")


def test_hybrid_agent_evaluates_equity_and_acts() -> None:
    from src.agents.hybrid_agent import HybridAgent
    from src.engine.table import Street

    agent = HybridAgent(
        player_id="hybrid_1",
        name="Híbrido 1",
        math_threshold=0.55,
        bluff_prob=0.0,
        slowplay_prob=0.0,
        num_simulations=50,
        rng=random.Random(42),
    )

    # Mão monstro: Royal/Straight flush draw forte
    hole = [Card.from_str("As"), Card.from_str("Ks")]
    board = [Card.from_str("Qs"), Card.from_str("Js"), Card.from_str("10s")]
    dec = agent.evaluate_state(
        hole_cards=hole,
        community_cards=board,
        pot_size=150,
        to_call=0,
        player_stack=900,
        player_current_bet=0,
        current_highest_bet=0,
        min_raise=20,
        big_blind=20,
        num_opponents=1,
        legal_actions=[ActionType.CHECK, ActionType.BET],
        street=Street.FLOP,
    )
    assert dec.action_type == ActionType.BET
    assert dec.equity > 0.90
    assert dec.mode in ("VALUE_BET", "VALUE_RAISE", "SLOW_PLAY")

    # Teste de mesa ativa
    p1 = Player("hybrid_1", "Híbrido", 1000)
    p2 = Player("p2", "Oponente", 1000)
    table = Table([p1, p2], small_blind=10, big_blind=20, rng=random.Random(42))
    table.start_new_hand()
    act = agent.decide_action(table)
    assert act.action_type in table.get_legal_actions("hybrid_1")
