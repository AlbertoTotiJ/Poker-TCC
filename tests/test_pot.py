from src.engine.deck import Card
from src.engine.hand_eval import evaluate_hand
from src.engine.pot import PotManager


def test_simple_uncontested_pot() -> None:
    pm = PotManager()
    pm.add_contribution("p1", 50)
    pm.add_contribution("p2", 50)

    assert pm.total_pot == 100
    pots = pm.build_pots({"p1", "p2"})
    assert len(pots) == 1
    assert pots[0].amount == 100
    assert pots[0].eligible_players == {"p1", "p2"}


def test_side_pot_creation_with_all_in() -> None:
    pm = PotManager()
    # p1 vai all-in com 20, p2 e p3 pagam 50
    pm.add_contribution("p1", 20)
    pm.add_contribution("p2", 50)
    pm.add_contribution("p3", 50)

    assert pm.total_pot == 120
    pots = pm.build_pots({"p1", "p2", "p3"})

    # Espera-se:
    # Pote Principal: 20 * 3 = 60 (disputado por p1, p2, p3)
    # Side Pot: (50 - 20) * 2 = 60 (disputado apenas por p2 e p3)
    assert len(pots) == 2
    assert pots[0].amount == 60
    assert pots[0].eligible_players == {"p1", "p2", "p3"}
    assert pots[1].amount == 60
    assert pots[1].eligible_players == {"p2", "p3"}


def test_payout_with_side_pots() -> None:
    pm = PotManager()
    pm.add_contribution("p1", 20)
    pm.add_contribution("p2", 50)
    pm.add_contribution("p3", 50)

    pots = pm.build_pots({"p1", "p2", "p3"})

    # p1 tem Royal Flush (melhor mão), p2 tem Trinca, p3 tem Par
    p1_score = evaluate_hand([Card.from_str(c) for c in ["As", "Ks", "Qs", "Js", "Ts"]])
    p2_score = evaluate_hand([Card.from_str(c) for c in ["8s", "8h", "8d", "2c", "3d"]])
    p3_score = evaluate_hand([Card.from_str(c) for c in ["7s", "7h", "4d", "2c", "3d"]])

    scores = {"p1": p1_score, "p2": p2_score, "p3": p3_score}
    payouts = pm.payout(pots, scores)

    # p1 ganha o pote principal de 60
    assert payouts["p1"] == 60
    # p2 ganha o side pot de 60 (pois p1 não é elegível para o side pot)
    assert payouts["p2"] == 60
    assert payouts["p3"] == 0
