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
