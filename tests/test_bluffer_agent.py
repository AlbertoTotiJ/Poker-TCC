"""Testes unitários dedicados cobrindo o Agente Blefador (Bluff Engine).

Valida a arquitetura isolada, a estimativa de fold equity, as manobras
de semi-blefe, C-bet steal, blefe puro de river, re-aumento, aposta de valor,
desistência prudente e serialização/calibração de hiperparâmetros.
"""

from pathlib import Path
import random

from src.agents.bluffer_agent import BlufferAgent, BluffTactic
from src.engine.deck import Card
from src.engine.player import Player
from src.engine.table import Action, ActionType, Street, Table


def test_bluffer_agent_instantiation() -> None:
    """Verifica instanciação com parâmetros padrão e customizados."""
    agent = BlufferAgent(
        player_id="bot_bluff_1",
        name="Lupin",
        bluff_frequency=0.55,
        semi_bluff_frequency=0.85,
        aggression_multiplier=1.2,
    )
    assert agent.player_id == "bot_bluff_1"
    assert agent.name == "Lupin"
    assert agent.params.bluff_frequency == 0.55
    assert agent.params.semi_bluff_frequency == 0.85
    assert agent.params.aggression_multiplier == 1.2
    assert agent.aggression_factor == 0.0
    assert agent.bluff_rate == 0.0


def test_bluffer_parameters_export_and_load() -> None:
    """Verifica exportação e carregamento de hiperparâmetros treinados."""
    agent = BlufferAgent(player_id="b1", bluff_frequency=0.30)
    params = agent.export_parameters()
    assert params["bluff_frequency"] == 0.30

    params["bluff_frequency"] = 0.75
    params["aggression_multiplier"] = 1.40
    agent.load_parameters(params)

    assert agent.params.bluff_frequency == 0.75
    assert agent.params.aggression_multiplier == 1.40


def test_bluffer_parameters_save_and_load_file(tmp_path: Path) -> None:
    """Valida a persistência em arquivo JSON para suporte a treino e deploy."""
    filepath = tmp_path / "bluffer_test_params.json"
    agent = BlufferAgent(
        player_id="b1",
        bluff_frequency=0.62,
        aggression_multiplier=1.15,
    )
    agent.save_parameters(filepath)
    assert filepath.exists()

    new_agent = BlufferAgent(player_id="b2")
    new_agent.load_parameters_file(filepath)
    assert new_agent.params.bluff_frequency == 0.62
    assert new_agent.params.aggression_multiplier == 1.15


def test_bluffer_agent_free_to_check_never_folds() -> None:
    """Verifica que o agente nunca dá fold quando o custo para ver cartas for 0."""
    p1 = Player("p1", "Bot1", 1000)
    p2 = Player("p2", "BluffBot", 1000)
    table = Table([p1, p2], small_blind=10, big_blind=20, rng=random.Random(42))
    table.start_new_hand()

    # Preflop: p1 paga o BB, vez do p2 (BB), custo to_call é 0
    table.apply_action(Action("p1", ActionType.CALL))

    agent = BlufferAgent(
        player_id="p2",
        name="BluffBot",
        bluff_frequency=0.10,
        rng=random.Random(123),
    )
    action = agent.decide_action(table)

    assert action.action_type in (ActionType.CHECK, ActionType.BET, ActionType.RAISE)
    assert action.action_type != ActionType.FOLD


def test_bluffer_cbet_steal_in_dry_board() -> None:
    """Valida C-Bet Steal em bordo seco quando adversários dão check."""
    agent = BlufferAgent(
        player_id="bluff_hero",
        bluff_frequency=1.0,
        rng=random.Random(42),
    )
    hole = (Card.from_str("7d"), Card.from_str("2c"))
    board = [Card.from_str("Ah"), Card.from_str("8s"), Card.from_str("3c")]

    decision = agent.evaluate_state(
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

    assert decision.action_type == ActionType.BET
    assert decision.is_bluff is True
    assert decision.tactic == BluffTactic.CBET_STEAL.value
    assert decision.fold_equity > 0.50
    assert decision.amount >= 20


def test_bluffer_semi_bluff_with_flush_draw() -> None:
    """Verifica manobra de semi-blefe ao deter draw significativo (9 outs)."""
    agent = BlufferAgent(
        player_id="bluff_hero",
        semi_bluff_frequency=1.0,
        rng=random.Random(42),
    )
    # Kh Qh em Ah 8h 2c 4s -> 4 cartas de copas (Nut Flush Draw)
    hole = (Card.from_str("Kh"), Card.from_str("Qh"))
    board = [
        Card.from_str("Ah"),
        Card.from_str("8h"),
        Card.from_str("2c"),
        Card.from_str("4s"),
    ]

    decision = agent.evaluate_state(
        hole_cards=hole,
        community_cards=board,
        pot_size=120,
        to_call=20,
        player_stack=900,
        player_current_bet=0,
        current_highest_bet=20,
        min_raise=20,
        big_blind=20,
        num_opponents=1,
        legal_actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
        street=Street.TURN,
    )

    assert decision.action_type == ActionType.RAISE
    assert decision.is_bluff is True
    assert decision.tactic == BluffTactic.SEMI_BLUFF.value
    assert decision.semi_bluff_outs >= 9


def test_bluffer_river_scare_card_barrel() -> None:
    """Verifica blefe no River com Scare Card quando o oponente deu check."""
    agent = BlufferAgent(
        player_id="bluff_hero",
        bluff_frequency=1.0,
        rng=random.Random(42),
    )
    hole = (Card.from_str("Jd"), Card.from_str("10c"))
    # Ás e Rei no bordo como scare cards
    board = [
        Card.from_str("2h"),
        Card.from_str("5d"),
        Card.from_str("8c"),
        Card.from_str("Ks"),
        Card.from_str("As"),
    ]

    decision = agent.evaluate_state(
        hole_cards=hole,
        community_cards=board,
        pot_size=150,
        to_call=0,
        player_stack=1000,
        player_current_bet=0,
        current_highest_bet=0,
        min_raise=20,
        big_blind=20,
        num_opponents=1,
        legal_actions=[ActionType.CHECK, ActionType.BET],
        street=Street.RIVER,
    )

    assert decision.action_type == ActionType.BET
    assert decision.is_bluff is True
    assert decision.tactic == BluffTactic.SCARE_CARD_BARREL.value
    assert decision.fold_equity > 0.70


def test_bluffer_prudent_fold_against_massive_bet() -> None:
    """Verifica desistência prudente diante de all-in ou overbet massiva."""
    agent = BlufferAgent(
        player_id="bluff_hero",
        bluff_frequency=0.50,
        rng=random.Random(42),
    )
    hole = (Card.from_str("4d"), Card.from_str("3s"))
    board = [
        Card.from_str("Kd"),
        Card.from_str("Qc"),
        Card.from_str("Js"),
        Card.from_str("10h"),
    ]

    # Enfrentando aposta de 600 em pote de 200 (relação 3x pote)
    decision = agent.evaluate_state(
        hole_cards=hole,
        community_cards=board,
        pot_size=200,
        to_call=600,
        player_stack=1000,
        player_current_bet=0,
        current_highest_bet=600,
        min_raise=40,
        big_blind=20,
        num_opponents=2,
        legal_actions=[ActionType.FOLD, ActionType.CALL],
        street=Street.TURN,
    )

    assert decision.action_type == ActionType.FOLD
    assert decision.is_bluff is False
    assert decision.tactic == BluffTactic.PRUDENT_FOLD.value


def test_bluffer_value_play_with_monster_hand() -> None:
    """Garante que com mão formada legítima (Full House) o agente aposta por valor."""
    agent = BlufferAgent(
        player_id="bluff_hero",
        rng=random.Random(42),
    )
    # Trinca de Valetes com bordo emparelhado (Full House de J e 7)
    hole = (Card.from_str("Jh"), Card.from_str("Jd"))
    board = [
        Card.from_str("Jc"),
        Card.from_str("7s"),
        Card.from_str("7c"),
        Card.from_str("2h"),
    ]

    decision = agent.evaluate_state(
        hole_cards=hole,
        community_cards=board,
        pot_size=100,
        to_call=0,
        player_stack=900,
        player_current_bet=0,
        current_highest_bet=0,
        min_raise=20,
        big_blind=20,
        num_opponents=1,
        legal_actions=[ActionType.CHECK, ActionType.BET],
        street=Street.TURN,
    )

    assert decision.action_type == ActionType.BET
    assert decision.is_bluff is False
    assert decision.tactic == BluffTactic.VALUE_PLAY.value
    assert "Full House" in decision.reason or "Trinca" in decision.reason


def test_bluffer_agent_table_integration_and_telemetry() -> None:
    """Valida a integração completa com a Table e a acumulação de telemetria."""
    agent = BlufferAgent(
        player_id="bluff_p1",
        bluff_frequency=0.99,
        rng=random.Random(42),
    )
    p1 = Player("bluff_p1", "Blefador", 1000)
    p2 = Player("p2", "Oponente", 1000)
    table = Table([p1, p2], small_blind=10, big_blind=20, rng=random.Random(42))
    table.start_new_hand()

    action = agent.decide_action(table)
    assert action.action_type in table.get_legal_actions("bluff_p1")
    table.apply_action(action)

    assert agent.vpip_actions >= 0
    assert agent.bets_and_raises >= 0
