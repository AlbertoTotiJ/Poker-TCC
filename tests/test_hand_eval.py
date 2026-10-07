from src.engine.deck import Card
from src.engine.hand_eval import HandRank, evaluate_hand


def test_high_card() -> None:
    cards = [Card.from_str(c) for c in ["As", "Kd", "9c", "5h", "2s"]]
    score = evaluate_hand(cards)
    assert score.hand_rank == HandRank.HIGH_CARD
    assert score.tiebreakers == (14, 13, 9, 5, 2)


def test_one_pair() -> None:
    cards = [Card.from_str(c) for c in ["As", "Ad", "9c", "5h", "2s"]]
    score = evaluate_hand(cards)
    assert score.hand_rank == HandRank.ONE_PAIR
    assert score.tiebreakers == (14, 9, 5, 2)


def test_two_pair_and_kicker() -> None:
    cards1 = [Card.from_str(c) for c in ["Ks", "Kd", "3c", "3h", "As"]]
    cards2 = [Card.from_str(c) for c in ["Ks", "Kh", "4d", "4c", "2s"]]
    score1 = evaluate_hand(cards1)
    score2 = evaluate_hand(cards2)

    assert score1.hand_rank == HandRank.TWO_PAIR
    assert score2.hand_rank == HandRank.TWO_PAIR
    # Ambos têm par de K, mas o segundo par de score2 (4) é maior que o de score1 (3)
    assert score2 > score1


def test_three_of_a_kind() -> None:
    cards = [Card.from_str(c) for c in ["7s", "7d", "7c", "Kh", "2s"]]
    score = evaluate_hand(cards)
    assert score.hand_rank == HandRank.THREE_OF_A_KIND
    assert score.tiebreakers == (7, 13, 2)


def test_straight_regular_and_wheel() -> None:
    regular = [Card.from_str(c) for c in ["9s", "8h", "7d", "6c", "5s"]]
    wheel = [Card.from_str(c) for c in ["5s", "4h", "3d", "2c", "As"]]

    score_regular = evaluate_hand(regular)
    score_wheel = evaluate_hand(wheel)

    assert score_regular.hand_rank == HandRank.STRAIGHT
    assert score_regular.tiebreakers == (9,)

    assert score_wheel.hand_rank == HandRank.STRAIGHT
    assert score_wheel.tiebreakers == (5,)
    assert score_regular > score_wheel


def test_flush() -> None:
    cards = [Card.from_str(c) for c in ["As", "Js", "8s", "6s", "2s"]]
    score = evaluate_hand(cards)
    assert score.hand_rank == HandRank.FLUSH
    assert score.tiebreakers == (14, 11, 8, 6, 2)


def test_full_house() -> None:
    cards = [Card.from_str(c) for c in ["8s", "8d", "8h", "2c", "2s"]]
    score = evaluate_hand(cards)
    assert score.hand_rank == HandRank.FULL_HOUSE
    assert score.tiebreakers == (8, 2)


def test_four_of_a_kind() -> None:
    cards = [Card.from_str(c) for c in ["Qs", "Qd", "Qh", "Qc", "5s"]]
    score = evaluate_hand(cards)
    assert score.hand_rank == HandRank.FOUR_OF_A_KIND
    assert score.tiebreakers == (12, 5)


def test_straight_flush_and_royal_flush() -> None:
    sf = [Card.from_str(c) for c in ["9h", "8h", "7h", "6h", "5h"]]
    rf = [Card.from_str(c) for c in ["Ah", "Kh", "Qh", "Jh", "Th"]]

    score_sf = evaluate_hand(sf)
    score_rf = evaluate_hand(rf)

    assert score_sf.hand_rank == HandRank.STRAIGHT_FLUSH
    assert score_sf.tiebreakers == (9,)

    assert score_rf.hand_rank == HandRank.ROYAL_FLUSH
    assert score_rf > score_sf


def test_seven_card_evaluation_picks_best_five() -> None:
    seven_cards = [Card.from_str(c) for c in ["Ah", "Kh", "Qh", "Jh", "Th", "2c", "3d"]]
    score = evaluate_hand(seven_cards)
    assert score.hand_rank == HandRank.ROYAL_FLUSH
