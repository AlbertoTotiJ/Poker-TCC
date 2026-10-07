from src.engine.player import Player
from src.engine.table import Action, ActionType, Street, Table


def test_table_initialization_and_start_hand() -> None:
    p1 = Player("p1", "Alice", 1000)
    p2 = Player("p2", "Bob", 1000)
    table = Table([p1, p2], small_blind=10, big_blind=20)

    table.start_new_hand()

    assert table.street == Street.PREFLOP
    assert p1.hole_cards is not None
    assert p2.hole_cards is not None
    # No heads-up: dealer (p1) posta SB 10, p2 posta BB 20
    assert p1.current_bet == 10
    assert p2.current_bet == 20
    assert table.pot_manager.total_pot == 30
    assert table.current_player == p1


def test_table_fold_uncontested_win() -> None:
    p1 = Player("p1", "Alice", 1000)
    p2 = Player("p2", "Bob", 1000)
    table = Table([p1, p2], small_blind=10, big_blind=20)

    table.start_new_hand()
    # Alice dá FOLD
    table.apply_action(Action("p1", ActionType.FOLD))

    assert table.street == Street.FINISHED
    assert not p1.is_active
    assert p2.is_active
    # Bob deve receber os 30 do pote (10 de Alice + 20 que ele postou)
    assert p2.stack == 1010
    assert p1.stack == 990


def test_table_complete_hand_to_showdown() -> None:
    p1 = Player("p1", "Alice", 1000)
    p2 = Player("p2", "Bob", 1000)
    table = Table([p1, p2], small_blind=10, big_blind=20)

    table.start_new_hand()

    # Preflop: p1 paga o BB (CALL 10 a mais), p2 dá CHECK
    table.apply_action(Action("p1", ActionType.CALL))
    table.apply_action(Action("p2", ActionType.CHECK))
    assert table.street == Street.FLOP
    assert len(table.community_cards) == 3

    # Flop: ambos dão CHECK
    table.apply_action(Action("p2", ActionType.CHECK))
    table.apply_action(Action("p1", ActionType.CHECK))
    assert table.street == Street.TURN
    assert len(table.community_cards) == 4

    # Turn: ambos dão CHECK
    table.apply_action(Action("p2", ActionType.CHECK))
    table.apply_action(Action("p1", ActionType.CHECK))
    assert table.street == Street.RIVER
    assert len(table.community_cards) == 5

    # River: ambos dão CHECK -> Showdown
    table.apply_action(Action("p2", ActionType.CHECK))
    table.apply_action(Action("p1", ActionType.CHECK))
    assert table.street == Street.FINISHED
    # Total de fichas em jogo deve ser conservado
    assert p1.stack + p2.stack == 2000
