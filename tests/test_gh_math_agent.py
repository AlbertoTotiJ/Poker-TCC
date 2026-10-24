"""Testes unitários para o GhMathAgent (Agente Matemático GH).

Desenvolvido por Gustavo (GH) para o TCC de Poker Texas Hold'em.
Cobre:
- Instanciação e limites de hiperparâmetros
- Decisões pré-flop por posição (evitando folds excessivos em BTN/BB)
- Cálculo e defesa baseados em Implied Odds
- Dimensionamento de apostas via Critério de Kelly Fracionário
- Regra sagrada do Check Gratuito (nunca foldar quando to_call == 0)
- Integridade do payload explicativo GhCognitiveMetrics (XAI)
- Decisão isolada sem estado de mesa (evaluate_state)
"""

from pathlib import Path
import random
import sys
import unittest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.agents.gh_math_agent import (  # noqa: E402
    GhCognitiveMetrics,
    GhMathAgent,
    GhPosition,
)
from src.engine.deck import Card  # noqa: E402
from src.engine.player import Player  # noqa: E402
from src.engine.table import Action, ActionType, Street, Table  # noqa: E402


class TestGhMathAgent(unittest.TestCase):
    """Suíte de validação formal do GhMathAgent."""

    def setUp(self) -> None:
        self.rng = random.Random(42)

    def test_instantiation_and_parameter_clamping(self) -> None:
        """Verifica clamping de segurança de base_threshold e kelly_fraction_limit."""
        agent = GhMathAgent(
            player_id="gh_1",
            name="GhTester",
            base_threshold=0.99,  # deve ser limitado a 0.80
            kelly_fraction_limit=0.80,  # deve ser limitado a 0.50
            num_simulations=50,  # deve ser elevado a 100
        )
        self.assertEqual(agent.player_id, "gh_1")
        self.assertEqual(agent.name, "GhTester")
        self.assertEqual(agent.base_threshold, 0.80)
        self.assertEqual(agent.kelly_fraction_limit, 0.50)
        self.assertEqual(agent.num_simulations, 100)

    def test_never_folds_when_free_to_check(self) -> None:
        """Garante que o agente JAMAIS folda quando o custo para ver cartas é zero."""
        p1 = Player("p1", "Opponent", 1000)
        p2 = Player("gh_bot", "GhAgent", 1000)
        table = Table([p1, p2], small_blind=10, big_blind=20, rng=random.Random(10))
        table.start_new_hand()

        # Preflop: p1 paga o BB (call 20), vez de p2 (BB), to_call = 0
        table.apply_action(Action("p1", ActionType.CALL))

        # Atribui mão marginal (7-2 offsuit)
        p2.hole_cards = (Card.from_str("7s"), Card.from_str("2c"))

        agent = GhMathAgent("gh_bot", rng=random.Random(10))
        action = agent.decide_action(table)

        self.assertIn(action.action_type, (ActionType.CHECK, ActionType.BET))
        self.assertNotEqual(action.action_type, ActionType.FOLD)

    def test_preflop_speculative_hand_defends_in_late_position(self) -> None:
        """Verifica que conectores em Late Position não tomam fold passivo."""
        p1 = Player("p1", "Raiser", 1000)
        p2 = Player("gh_btn", "GhButton", 1000)
        table = Table([p1, p2], small_blind=10, big_blind=20, rng=random.Random(21))
        table.start_new_hand()

        # Dá conector do mesmo naipe (8s-9s)
        p2.hole_cards = (Card.from_str("8s"), Card.from_str("9s"))

        # Oponente faz mini-raise padrão
        table.apply_action(Action("p1", ActionType.RAISE, amount=40))

        agent = GhMathAgent("gh_btn", rng=random.Random(99))
        action = agent.decide_action(table)

        # Em posição vantajosa com pot odds favoráveis, não deve dar fold
        self.assertIn(action.action_type, (ActionType.CALL, ActionType.RAISE))
        self.assertIsNotNone(agent.last_decision)
        self.assertGreater(agent.last_decision.metrics.adjusted_equity, 0.25)

    def test_preflop_pocket_pair_set_mining(self) -> None:
        """Verifica que pocket pairs pagam para buscar trinca (set mining)."""
        agent = GhMathAgent("gh_pair", rng=random.Random(7))
        decision = agent.evaluate_state(
            hole_cards=(Card.from_str("4h"), Card.from_str("4d")),
            community_cards=[],
            pot_size=80,
            to_call=30,
            player_stack=950,
            player_current_bet=10,
            current_highest_bet=40,
            min_raise=20,
            big_blind=20,
            num_opponents=2,
            legal_actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
            effective_stack_behind=950,
            position=GhPosition.LATE,
        )

        self.assertIn(decision.action_type, (ActionType.CALL, ActionType.RAISE))
        self.assertIn("Call", decision.metrics.tactical_rationale)
        self.assertGreater(decision.metrics.adjusted_equity, 0.35)

    def test_implied_odds_call_with_flush_draw(self) -> None:
        """Valida que Implied Odds viabilizam o Call no flop com Flush Draw."""
        agent = GhMathAgent("gh_draw", rng=random.Random(33))
        # Flush draw no flop (4 cartas de copas: 2 na mão, 2 na mesa)
        decision = agent.evaluate_state(
            hole_cards=(Card.from_str("Ah"), Card.from_str("5h")),
            community_cards=[
                Card.from_str("Kh"),
                Card.from_str("8h"),
                Card.from_str("2c"),
            ],
            pot_size=120,
            to_call=40,
            player_stack=800,
            player_current_bet=0,
            current_highest_bet=40,
            min_raise=40,
            big_blind=20,
            num_opponents=1,
            legal_actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
            effective_stack_behind=800,  # Bastante stack para extrair
            position=GhPosition.MIDDLE,
        )

        self.assertIn(decision.action_type, (ActionType.CALL, ActionType.RAISE))
        self.assertGreater(decision.metrics.outs_count, 8)
        self.assertLess(decision.metrics.implied_odds, decision.metrics.direct_pot_odds)

    def test_kelly_fractional_bet_sizing(self) -> None:
        """Verifica dimensionamento do Critério de Kelly com limite seguro."""
        agent = GhMathAgent(
            "gh_kelly", kelly_fraction_limit=0.25, rng=random.Random(15)
        )

        # Mão fortíssima (Top Full House no River: As-Ah com As-Kh-Kd-Ks-2c)
        decision = agent.evaluate_state(
            hole_cards=(Card.from_str("As"), Card.from_str("Ah")),
            community_cards=[
                Card.from_str("Ad"),
                Card.from_str("Kh"),
                Card.from_str("Kd"),
                Card.from_str("Ks"),
                Card.from_str("2c"),
            ],
            pot_size=200,
            to_call=0,
            player_stack=600,
            player_current_bet=0,
            current_highest_bet=0,
            min_raise=20,
            big_blind=20,
            num_opponents=1,
            legal_actions=[ActionType.CHECK, ActionType.BET],
            effective_stack_behind=600,
            position=GhPosition.LATE,
        )

        self.assertEqual(decision.action_type, ActionType.BET)
        self.assertGreaterEqual(decision.amount, 20)
        self.assertLessEqual(decision.amount, 600)
        self.assertGreater(decision.metrics.kelly_fraction, 0.0)
        self.assertLessEqual(decision.metrics.kelly_fraction, 0.25)

    def test_cognitive_metrics_payload_integrity(self) -> None:
        """Garante preenchimento de GhCognitiveMetrics para o Quartz."""
        p1 = Player("p1", "Player1", 1000)
        p2 = Player("gh_xai", "GhXai", 1000)
        table = Table([p1, p2], small_blind=10, big_blind=20, rng=random.Random(88))
        table.start_new_hand()

        agent = GhMathAgent("gh_xai", rng=random.Random(88))
        agent.decide_action(table)

        self.assertIsNotNone(agent.last_decision)
        metrics = agent.last_decision.metrics
        self.assertIsInstance(metrics, GhCognitiveMetrics)
        self.assertIsInstance(metrics.raw_equity, float)
        self.assertIsInstance(metrics.adjusted_equity, float)
        self.assertIsInstance(metrics.direct_pot_odds, float)
        self.assertIsInstance(metrics.implied_odds, float)
        self.assertIsInstance(metrics.expected_value_call, float)
        self.assertIsInstance(metrics.expected_value_raise, float)
        self.assertIsInstance(metrics.kelly_fraction, float)
        self.assertIsInstance(metrics.outs_count, int)
        self.assertIn(metrics.position_name, ["Early", "Middle", "Late", "Blinds"])
        self.assertTrue(len(metrics.tactical_rationale) > 5)
        self.assertTrue(len(metrics.formula_reference) > 5)

    def test_disciplined_fold_facing_huge_overbet_with_weak_hand(self) -> None:
        """Garante fold disciplinado contra overbet sem equidade ou odds."""
        agent = GhMathAgent("gh_fold", rng=random.Random(4))
        decision = agent.evaluate_state(
            hole_cards=(Card.from_str("7d"), Card.from_str("2c")),
            community_cards=[
                Card.from_str("Ac"),
                Card.from_str("Kd"),
                Card.from_str("Jh"),
            ],
            pot_size=100,
            to_call=500,  # Aposta de 5x o pote
            player_stack=600,
            player_current_bet=0,
            current_highest_bet=500,
            min_raise=500,
            big_blind=20,
            num_opponents=1,
            legal_actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
            effective_stack_behind=100,
            position=GhPosition.EARLY,
        )

        self.assertEqual(decision.action_type, ActionType.FOLD)
        self.assertEqual(decision.amount, 0)
        self.assertIn("-EV Fold", decision.metrics.tactical_rationale)

    def test_multiway_pot_control_on_river(self) -> None:
        """Verifica que em mesa multiway no River o agente dá Check."""
        agent = GhMathAgent("gh_ctrl", rng=random.Random(12))
        decision = agent.evaluate_state(
            hole_cards=(Card.from_str("Kd"), Card.from_str("Tc")),
            community_cards=[
                Card.from_str("Ks"),
                Card.from_str("8h"),
                Card.from_str("4c"),
                Card.from_str("3d"),
                Card.from_str("2s"),
            ],
            pot_size=300,
            to_call=0,
            player_stack=800,
            player_current_bet=0,
            current_highest_bet=0,
            min_raise=20,
            big_blind=20,
            num_opponents=2,
            legal_actions=[ActionType.CHECK, ActionType.BET],
            position=GhPosition.MIDDLE,
            street=Street.RIVER,
        )

        self.assertEqual(decision.action_type, ActionType.CHECK)
        self.assertIn("multiway", decision.metrics.tactical_rationale.lower())

    def test_bluff_catch_on_river_with_pair(self) -> None:
        """Verifica tenacidade de showdown com par formado."""
        agent = GhMathAgent("gh_catch", rng=random.Random(19))
        decision = agent.evaluate_state(
            hole_cards=(Card.from_str("As"), Card.from_str("9d")),
            community_cards=[
                Card.from_str("Ah"),
                Card.from_str("Jc"),
                Card.from_str("7s"),
                Card.from_str("4d"),
                Card.from_str("2c"),
            ],
            pot_size=200,
            to_call=40,
            player_stack=700,
            player_current_bet=0,
            current_highest_bet=40,
            min_raise=40,
            big_blind=20,
            num_opponents=1,
            legal_actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
            position=GhPosition.LATE,
            street=Street.RIVER,
        )

        self.assertIn(decision.action_type, (ActionType.CALL, ActionType.RAISE))


if __name__ == "__main__":
    unittest.main()
