"""Testes unitários dedicados para o GhBlufferAgent.

Desenvolvido por Gustavo (GH) para o TCC de Inteligência Artificial para Poker.
Valida:
1. Instanciação e limites seguros de parâmetros
2. Regra inviolável do Check Gratuito (nunca foldar quando to_call == 0)
3. 3-Bet de blefe polarizada no pré-flop com ases fracos naipados (A5s/A4s)
4. Classificação de textura do bordo (Dry, Wet, Scare Cards)
5. Motor de Bloqueadores (Nut Flush Blocker e Straight Blockers)
6. Semi-blefes com retenção de equidade no Flop e Turn (Flush/Straight Draws)
7. Blefe polarizado de River sob Teorema da Indiferença de Nash (B / (P + 2B))
8. Desistência disciplinada (eliminação da anomalia de calling station de 60%)
9. Integridade do payload explicativo GhBluffMetrics (XAI)
"""

from pathlib import Path
import random
import sys
import unittest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.agents.gh_bluffer_agent import (  # noqa: E402
    GhBluffDecision,
    GhBlufferAgent,
    GhBluffMetrics,
    GhBluffTactic,
)
from src.engine.deck import Card  # noqa: E402
from src.engine.player import Player  # noqa: E402
from src.engine.table import Action, ActionType, Street, Table  # noqa: E402


class TestGhBlufferAgent(unittest.TestCase):
    """Suíte de testes formais para o GhBlufferAgent."""

    def setUp(self) -> None:
        self.rng = random.Random(42)

    def test_instantiation_and_parameter_clamping(self) -> None:
        """Verifica clamping de segurança de parâmetros do GhBlufferAgent."""
        agent = GhBlufferAgent(
            player_id="gh_bluff_test",
            name="GhBlufferTester",
            bluff_aggression=3.5,  # deve ser limitado a 2.0
            gto_balance_factor=0.2,  # deve ser elevado a 0.5
            min_blocker_threshold=0.90,  # deve ser limitado a 0.70
            num_simulations=50,  # deve ser elevado a 100
        )
        self.assertEqual(agent.player_id, "gh_bluff_test")
        self.assertEqual(agent.name, "GhBlufferTester")
        self.assertEqual(agent.bluff_aggression, 2.0)
        self.assertEqual(agent.gto_balance_factor, 0.5)
        self.assertEqual(agent.min_blocker_threshold, 0.70)
        self.assertEqual(agent.num_simulations, 100)

    def test_never_folds_when_free_to_check(self) -> None:
        """Garante que o agente JAMAIS desiste se o custo para continuar for zero."""
        p1 = Player("p1", "Opponent", 1000)
        p2 = Player("gh_bot", "GhBluffer", 1000)
        table = Table([p1, p2], small_blind=10, big_blind=20, rng=random.Random(10))
        table.start_new_hand()

        # Preflop: p1 paga o BB (call 20), vez de p2 (BB), to_call = 0
        table.apply_action(Action("p1", ActionType.CALL))
        p2.hole_cards = (Card.from_str("7s"), Card.from_str("2c"))

        agent = GhBlufferAgent("gh_bot", rng=random.Random(10))
        action = agent.decide_action(table)

        self.assertIn(action.action_type, (ActionType.CHECK, ActionType.BET))
        self.assertNotEqual(action.action_type, ActionType.FOLD)

    def test_board_texture_analysis(self) -> None:
        """Valida a classificação de textura da mesa (Dry, Wet, Scare)."""
        agent = GhBlufferAgent("tester")

        # Bordo Seco: K de Espadas, 7 de Ouros, 2 de Paus (desconexo, naipes diferentes)
        dry_board = [Card.from_str("Ks"), Card.from_str("7d"), Card.from_str("2c")]
        is_dry, is_wet, has_scare = agent.analyze_board_texture(dry_board)
        self.assertTrue(is_dry)
        self.assertFalse(is_wet)
        self.assertTrue(has_scare)  # Contém Rei

        # Bordo Conectado/Wet: Valete de Copas, 10 de Copas, 9 de Copas (3 copas, conectores)
        wet_board = [Card.from_str("Jh"), Card.from_str("Th"), Card.from_str("9h")]
        is_dry_wet, is_wet_wet, has_scare_wet = agent.analyze_board_texture(wet_board)
        self.assertFalse(is_dry_wet)
        self.assertTrue(is_wet_wet)

    def test_nut_flush_blocker_detection(self) -> None:
        """Verifica se o motor atribui alta pontuação ao segurar o Ás do naipe do flush."""
        agent = GhBlufferAgent("tester")

        # Bordo com 3 Espadas: 8s, 4s, 2s
        board = [Card.from_str("8s"), Card.from_str("4s"), Card.from_str("2s")]

        # Mão com o Ás de Espadas (Nut Flush Blocker)
        hero_with_nut_blocker = (Card.from_str("As"), Card.from_str("Td"))
        score_nut = agent.evaluate_blockers(hero_with_nut_blocker, board)

        # Mão sem cartas de Espadas
        hero_without_blocker = (Card.from_str("Ah"), Card.from_str("Td"))
        score_none = agent.evaluate_blockers(hero_without_blocker, board)

        self.assertGreaterEqual(score_nut, 0.50)
        self.assertLess(score_none, score_nut)

    def test_semi_bluff_on_flop_with_flush_draw(self) -> None:
        """Garante que um flush draw com 9 outs no flop executa semi-blefe ofensivo."""
        agent = GhBlufferAgent("tester", bluff_aggression=1.5, rng=random.Random(123))

        # Hero tem duas cartas de Espadas: Qs, Js
        hole = (Card.from_str("Qs"), Card.from_str("Js"))
        # Bordo tem duas cartas de Espadas: 9s, 4s, 2d (Total 4 cartas de Espadas = 9 outs)
        board = [Card.from_str("9s"), Card.from_str("4s"), Card.from_str("2d")]

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

        self.assertEqual(decision.action_type, ActionType.BET)
        self.assertTrue(decision.metrics.is_bluff)
        self.assertEqual(decision.metrics.tactic, GhBluffTactic.SEMI_BLUFF_DRAW.value)
        self.assertGreaterEqual(decision.metrics.semi_bluff_outs, 9)

    def test_river_polarized_bluff_with_nut_blocker(self) -> None:
        """Verifica blefe no river sob Teorema da Indiferença quando possui Nut Blocker."""
        # Força seed onde roll < threshold
        agent = GhBlufferAgent(
            "tester",
            bluff_aggression=1.2,
            gto_balance_factor=1.2,
            min_blocker_threshold=0.30,
            rng=random.Random(1),  # roll baixo garante o blefe
        )

        # Hero com Ás de Ouros e carta fraca num bordo com 3 ouros
        hole = (Card.from_str("Ad"), Card.from_str("3c"))
        board = [
            Card.from_str("Kd"),
            Card.from_str("9d"),
            Card.from_str("4d"),
            Card.from_str("7s"),
            Card.from_str("2h"),
        ]

        decision = agent.evaluate_state(
            hole_cards=hole,
            community_cards=board,
            pot_size=200,
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

        # Deve disparar aposta polarizada de blefe
        self.assertEqual(decision.action_type, ActionType.BET)
        self.assertTrue(decision.metrics.is_bluff)
        self.assertEqual(decision.metrics.tactic, GhBluffTactic.NUT_BLOCKER_BLUFF.value)
        self.assertGreaterEqual(decision.metrics.blocker_score, 0.45)
        self.assertGreater(decision.amount, 100)  # Sizing polarizado > 50% do pote

    def test_disciplined_fold_facing_heavy_bet_without_odds(self) -> None:
        """Elimina o vício do Alberto (que pagava 60% com lixo): desiste disciplinadamente."""
        agent = GhBlufferAgent("tester", rng=random.Random(42))

        # Mão lixo no turn sem outs e sem blockers
        hole = (Card.from_str("7s"), Card.from_str("2c"))
        board = [
            Card.from_str("Kh"),
            Card.from_str("Qd"),
            Card.from_str("9c"),
            Card.from_str("4h"),
        ]

        # Enfrentando aposta pesada de 100 em pote de 150
        decision = agent.evaluate_state(
            hole_cards=hole,
            community_cards=board,
            pot_size=150,
            to_call=100,
            player_stack=500,
            player_current_bet=0,
            current_highest_bet=100,
            min_raise=20,
            big_blind=20,
            num_opponents=1,
            legal_actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
            street=Street.TURN,
        )

        self.assertEqual(decision.action_type, ActionType.FOLD)
        self.assertFalse(decision.metrics.is_bluff)
        self.assertEqual(decision.metrics.tactic, GhBluffTactic.DISCIPLINED_FOLD.value)

    def test_preflop_polarized_3bet_bluff_with_wheel_ace(self) -> None:
        """Verifica se o agente aplica 3-bet de blefe pré-flop com A5s sob roll favorável."""
        agent = GhBlufferAgent("tester", bluff_aggression=1.5, rng=random.Random(3))

        hole = (Card.from_str("Ah"), Card.from_str("5h"))  # A5 suited

        decision = agent.evaluate_state(
            hole_cards=hole,
            community_cards=[],
            pot_size=50,
            to_call=40,  # Aumento padrão de 2 BBs
            player_stack=1000,
            player_current_bet=20,
            current_highest_bet=60,
            min_raise=40,
            big_blind=20,
            num_opponents=1,
            legal_actions=[ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
            street=Street.PREFLOP,
        )

        # Deve aplicar 3-bet de blefe ou call por implied odds
        self.assertIn(decision.action_type, (ActionType.RAISE, ActionType.CALL))
        if decision.action_type == ActionType.RAISE:
            self.assertTrue(decision.metrics.is_bluff)
            self.assertEqual(
                decision.metrics.tactic,
                GhBluffTactic.PREFLOP_3BET_BLUFF.value,
            )


if __name__ == "__main__":
    unittest.main()
