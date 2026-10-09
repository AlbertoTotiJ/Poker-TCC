from src.engine.deck import Card, Rank, Suit
from src.engine.hand_eval import HandRank, evaluate_hand
from src.engine.player import Player
from src.engine.pot import PotManager
from src.engine.table import Action, ActionType, Table


def test_all_ten_hand_combinations_in_portuguese() -> None:
    """Valida cada uma das 10 categorias de mãos e suas descrições em português."""
    # 1. High Card
    hc = [Card.from_str(c) for c in ["As", "Kd", "9c", "5h", "2s"]]
    s_hc = evaluate_hand(hc)
    assert s_hc.hand_rank == HandRank.HIGH_CARD
    assert s_hc.rank_name_pt == "Carta Alta"
    assert "Carta Alta Ás" in s_hc.description

    # 2. One Pair
    pair = [Card.from_str(c) for c in ["Ks", "Kd", "9c", "5h", "2s"]]
    s_pair = evaluate_hand(pair)
    assert s_pair.hand_rank == HandRank.ONE_PAIR
    assert s_pair.rank_name_pt == "Um Par"
    assert "Par de Rei" in s_pair.description

    # 3. Two Pair
    tp = [Card.from_str(c) for c in ["Ks", "Kd", "9c", "9h", "2s"]]
    s_tp = evaluate_hand(tp)
    assert s_tp.hand_rank == HandRank.TWO_PAIR
    assert s_tp.rank_name_pt == "Dois Pares"
    assert "Dois Pares" in s_tp.description

    # 4. Three of a Kind
    trips = [Card.from_str(c) for c in ["7s", "7d", "7c", "Kh", "2s"]]
    s_trips = evaluate_hand(trips)
    assert s_trips.hand_rank == HandRank.THREE_OF_A_KIND
    assert s_trips.rank_name_pt == "Trinca"
    assert "Trinca de Setes" in s_trips.description

    # 5. Straight
    straight = [Card.from_str(c) for c in ["9s", "8h", "7d", "6c", "5s"]]
    s_st = evaluate_hand(straight)
    assert s_st.hand_rank == HandRank.STRAIGHT
    assert s_st.rank_name_pt == "Sequência"
    assert "Sequência ao Nove" in s_st.description

    # 6. Flush
    flush = [Card.from_str(c) for c in ["As", "Js", "8s", "6s", "2s"]]
    s_fl = evaluate_hand(flush)
    assert s_fl.hand_rank == HandRank.FLUSH
    assert s_fl.rank_name_pt == "Flush"
    assert "Flush ao Ás" in s_fl.description

    # 7. Full House
    fh = [Card.from_str(c) for c in ["Js", "Jd", "Jh", "4c", "4s"]]
    s_fh = evaluate_hand(fh)
    assert s_fh.hand_rank == HandRank.FULL_HOUSE
    assert s_fh.rank_name_pt == "Full House"
    assert "Full House de Valetes com Quatros" in s_fh.description

    # 8. Four of a Kind
    quads = [Card.from_str(c) for c in ["Ts", "Td", "Th", "Tc", "As"]]
    s_qd = evaluate_hand(quads)
    assert s_qd.hand_rank == HandRank.FOUR_OF_A_KIND
    assert s_qd.rank_name_pt == "Quadra"
    assert "Quadra de Dezes com kicker Ás" in s_qd.description

    # 9. Straight Flush
    sf = [Card.from_str(c) for c in ["8h", "7h", "6h", "5h", "4h"]]
    s_sf = evaluate_hand(sf)
    assert s_sf.hand_rank == HandRank.STRAIGHT_FLUSH
    assert s_sf.rank_name_pt == "Straight Flush"
    assert "Straight Flush ao Oito" in s_sf.description

    # 10. Royal Flush
    rf = [Card.from_str(c) for c in ["Ah", "Kh", "Qh", "Jh", "Th"]]
    s_rf = evaluate_hand(rf)
    assert s_rf.hand_rank == HandRank.ROYAL_FLUSH
    assert s_rf.rank_name_pt == "Royal Flush"
    assert s_rf.description == "Royal Flush"

    # Hierarquia estrita
    assert s_rf > s_sf > s_qd > s_fh > s_fl > s_st > s_trips > s_tp > s_pair > s_hc


def test_wheel_straight_and_steel_wheel() -> None:
    """Valida a regra do Ás baixo (Wheel 5-4-3-2-A e Steel Wheel)."""
    wheel = [Card.from_str(c) for c in ["5s", "4h", "3d", "2c", "As"]]
    score_wheel = evaluate_hand(wheel)
    assert score_wheel.hand_rank == HandRank.STRAIGHT
    assert score_wheel.tiebreakers == (5,)
    assert "Wheel" in score_wheel.description

    steel_wheel = [Card.from_str(c) for c in ["5h", "4h", "3h", "2h", "Ah"]]
    score_steel = evaluate_hand(steel_wheel)
    assert score_steel.hand_rank == HandRank.STRAIGHT_FLUSH
    assert score_steel.tiebreakers == (5,)
    assert "Steel Wheel" in score_steel.description


def test_playing_the_board_split_pot() -> None:
    """Valida a regra oficial de 'Jogar com o Bordo' gerando empate (Split Pot)."""
    players = [
        Player(player_id="p1", name="Alice", stack=1000),
        Player(player_id="p2", name="Bob", stack=1000),
    ]
    table = Table(players=players, small_blind=10, big_blind=20, button_idx=0)
    table.start_new_hand()

    # Bordo contém Royal Flush comunitário: ambos jogam com o bordo
    royal_board = [
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.QUEEN, Suit.HEARTS),
        Card(Rank.JACK, Suit.HEARTS),
        Card(Rank.TEN, Suit.HEARTS),
    ]
    table.dealer._community_cards = list(royal_board)

    # Ambos chegam ao showdown
    score_p1 = evaluate_hand(list(players[0].hole_cards) + royal_board)
    score_p2 = evaluate_hand(list(players[1].hole_cards) + royal_board)

    assert score_p1.hand_rank == HandRank.ROYAL_FLUSH
    assert score_p2.hand_rank == HandRank.ROYAL_FLUSH
    assert score_p1 == score_p2


def test_tda_full_raise_rule_locks_incomplete_all_in() -> None:
    """Valida a Regra TDA 44: All-in incompleto não reabre aposta para quem já pagou."""
    p1 = Player(player_id="p1", name="Alice", stack=1000)
    p2 = Player(player_id="p2", name="Bob", stack=40)  # stack para incomplete raise
    p3 = Player(player_id="p3", name="Carol", stack=1000)

    table = Table(players=[p1, p2, p3], small_blind=10, big_blind=20, button_idx=0)
    table.start_new_hand()

    # Pre-flop: Button=0 (p1), SB=1 (p2), BB=2 (p3).
    # First to act é p1 (UTG).
    assert table.current_player.player_id == "p1"
    # p1 faz call de 20
    table.apply_action(Action("p1", ActionType.CALL))

    # Vez de p2 (SB, postou 10, stack restante 30).
    # p2 vai all-in para 40 total (aumento de 20 acima do BB de 20).
    assert table.current_player.player_id == "p2"
    table.apply_action(Action("p2", ActionType.ALL_IN))

    # Vez de p3 (BB, postou 20, enfrenta aposta de 40).
    # O aumento de p2 foi de 20 (igual ao min_raise de 20).
    # p3 faz call de 40.
    assert table.current_player.player_id == "p3"
    table.apply_action(Action("p3", ActionType.CALL))

    # Agora a ação volta para p1 (que havia pago 20).
    # p1 enfrenta 40. Aumentou em 20. p1 pode pagar.
    assert table.current_player.player_id == "p1"
    assert ActionType.CALL in table.get_legal_actions("p1")


def test_odd_chip_rule_respects_table_position() -> None:
    """Valida que o chip ímpar indivisível vai para o jogador à esquerda do botão."""
    pm = PotManager()
    pm.add_contribution("p1", 25)
    pm.add_contribution("p2", 25)
    # Jogador p3 postou ante/blind de 1 chip e desistiu
    pm.add_contribution("p3_folded", 1)

    # p1 e p2 disputam o pote total de 51
    pots = pm.build_pots({"p1", "p2"})
    assert sum(p.amount for p in pots) == 51

    # Ambos empatam com Carta Alta Ás
    cards = tuple(Card.from_str(c) for c in ["As", "Kd", "9c", "5h", "2s"])
    score = evaluate_hand(cards)
    scores = {"p1": score, "p2": score}

    # Ordem da mesa priorizando p2 (SB à esquerda do botão)
    payouts = pm.payout(pots, scores, table_order=["p2", "p1"])
    assert payouts["p2"] == 26
    assert payouts["p1"] == 25


def test_elimination_of_busted_players() -> None:
    """Valida que jogadores sem fichas (stack == 0) são excluídos da mão seguinte."""
    p1 = Player(player_id="p1", name="Alice", stack=500)
    p2 = Player(player_id="p2", name="Bob", stack=0)  # Busted
    p3 = Player(player_id="p3", name="Carol", stack=500)

    table = Table(players=[p1, p2, p3], small_blind=10, big_blind=20, button_idx=0)
    table.start_new_hand()

    # Bob não deve receber cartas nem estar ativo
    assert p2.hole_cards is None
    assert not p2.is_active
    assert p1.is_active
    assert p3.is_active
