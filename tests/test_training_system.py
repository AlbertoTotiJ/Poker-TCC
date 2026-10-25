"""Suíte de testes automatizados para o Sistema de Treinamento e Qualificação."""

import json
from pathlib import Path
import random
import unittest

from src.agents.bluffer_agent import BlufferAgent
from src.agents.gh_math_agent import GhMathAgent
from src.agents.mathematical_agent import MathematicalAgent
from src.engine.player import Player
from src.engine.table import Action, ActionType, Table
from src.training.adaptive_trainer import AdaptiveTrainer, TrainingResult
from src.training.hall_of_fame import HallOfFame
from src.training.metrics import (
    AgentPerformanceMetrics,
    EvaluationMetric,
    FitnessEvaluator,
    MetricWeights,
    score_aggression_factor,
    score_bb_per_100,
    score_bluff_success_rate,
)
from src.training.parameters import (
    clamp_parameters,
    crossover_parameters,
    generate_random_parameters,
    get_default_parameters,
    instantiate_agent,
    mutate_parameters,
)
from src.training.recorder_bridge import TrainingRecorderBridge


class TestTrainingParameters(unittest.TestCase):
    """Testa os operadores e especificações de hiperparâmetros."""

    def setUp(self) -> None:
        self.rng = random.Random(42)

    def test_default_parameters_exist_for_all_agents(self) -> None:
        for agent_type in ["bluffer", "mathematical", "gh_math"]:
            params = get_default_parameters(agent_type)
            self.assertIsInstance(params, dict)
            self.assertGreater(len(params), 0)

    def test_generate_random_parameters_within_bounds(self) -> None:
        params = generate_random_parameters("bluffer", rng=self.rng)
        self.assertIn("bluff_frequency", params)
        self.assertGreaterEqual(params["bluff_frequency"], 0.05)
        self.assertLessEqual(params["bluff_frequency"], 0.95)

    def test_clamp_parameters(self) -> None:
        extreme_params = {
            "bluff_frequency": 5.0,  # muito alto
            "fold_equity_threshold": -1.0,  # muito baixo
        }
        clamped = clamp_parameters("bluffer", extreme_params)
        self.assertEqual(clamped["bluff_frequency"], 0.95)
        self.assertEqual(clamped["fold_equity_threshold"], 0.10)

    def test_mutate_parameters(self) -> None:
        base = get_default_parameters("bluffer")
        mutated = mutate_parameters(
            "bluffer", base, mutation_rate=1.0, mutation_scale=0.2, rng=self.rng
        )
        self.assertNotEqual(base, mutated)
        # Permanece dentro dos limites
        self.assertGreaterEqual(mutated["bluff_frequency"], 0.05)
        self.assertLessEqual(mutated["bluff_frequency"], 0.95)

    def test_crossover_parameters(self) -> None:
        p1 = {"raise_equity_threshold": 0.50, "bet_sizing_factor": 0.30}
        p2 = {"raise_equity_threshold": 0.80, "bet_sizing_factor": 0.90}
        child = crossover_parameters("mathematical", p1, p2, rng=self.rng)
        self.assertGreaterEqual(child["raise_equity_threshold"], 0.50)
        self.assertLessEqual(child["raise_equity_threshold"], 0.80)

    def test_instantiate_agent_types(self) -> None:
        bluffer = instantiate_agent("bluffer", "b1", "BlufferBot")
        self.assertIsInstance(bluffer, BlufferAgent)

        math_agent = instantiate_agent("mathematical", "m1", "MathBot")
        self.assertIsInstance(math_agent, MathematicalAgent)

        gh_agent = instantiate_agent("gh_math", "g1", "GhBot")
        self.assertIsInstance(gh_agent, GhMathAgent)


class TestMetricsAndQualification(unittest.TestCase):
    """Testa a qualificação e funções de pontuação de métricas individuais."""

    def test_score_bb_per_100_sigmoid(self) -> None:
        score_loss = score_bb_per_100(-50.0)
        score_even = score_bb_per_100(0.0)
        score_profit = score_bb_per_100(50.0)
        self.assertLess(score_loss, score_even)
        self.assertLess(score_even, score_profit)
        self.assertAlmostEqual(score_even, 50.0, delta=2.0)

    def test_score_bluff_success_rate(self) -> None:
        score_zero = score_bluff_success_rate(0.0)
        score_breakeven = score_bluff_success_rate(35.0)
        score_elite = score_bluff_success_rate(75.0)
        self.assertLess(score_zero, score_breakeven)
        self.assertLess(score_breakeven, score_elite)
        self.assertGreater(score_elite, 90.0)

    def test_score_aggression_factor_bell_curve(self) -> None:
        # Ponto ideal ~ 2.8
        score_passive = score_aggression_factor(0.5)
        score_optimal = score_aggression_factor(2.8)
        score_maniac = score_aggression_factor(8.0)
        self.assertGreater(score_optimal, score_passive)
        self.assertGreater(score_optimal, score_maniac)

    def test_single_metric_weights_focus(self) -> None:
        weights = MetricWeights.for_single_metric(
            EvaluationMetric.BLUFF_SUCCESS_RATE
        )
        evaluator = FitnessEvaluator(weights=weights)

        metrics = AgentPerformanceMetrics(
            hands_played=50,
            bluffs_attempted=10,
            bluffs_won=8,
            bluff_success_rate=80.0,
            bb_per_100=-20.0,  # mesmo com prejuízo em fichas
        )
        card = evaluator.evaluate(metrics)
        self.assertEqual(card.target_focus, "bluff_success_rate")
        # O fitness geral é dominado pela taxa de blefe
        self.assertGreater(card.overall_fitness, 85.0)
        self.assertIn(card.overall_tier, ["S (Elite)", "A (Mestre)"])


class TestHallOfFameAdaptation(unittest.TestCase):
    """Testa o repositório de campeões e a seleção adversarial de oponentes."""

    def test_add_and_retrieve_champions(self) -> None:
        tmp_hof = Path("models/test_tmp_hof.json")
        try:
            hof = HallOfFame(storage_file=tmp_hof)
            hof.champions.clear()

            champ = hof.add_champion(
                agent_type="bluffer",
                parameters={"bluff_frequency": 0.55},
                fitness_score=88.5,
                qualification_tier="A (Mestre)",
                generation=3,
            )
            self.assertEqual(champ.fitness_score, 88.5)
            self.assertEqual(len(hof.champions), 1)

            # Recarrega do arquivo
            hof2 = HallOfFame(storage_file=tmp_hof)
            self.assertEqual(len(hof2.champions), 1)
            self.assertEqual(hof2.champions[0].fitness_score, 88.5)

            # Constrói oponentes adaptativos incluindo o campeão
            opponents = hof2.build_adaptive_opponents("bluffer", num_opponents=5)
            self.assertEqual(len(opponents), 5)
            # Ao menos um oponente deve ser o campeão do Hall of Fame
            has_champ = any("Campeão" in o.name for o in opponents)
            self.assertTrue(has_champ)
        finally:
            if tmp_hof.exists():
                tmp_hof.unlink()


class TestTrainingRecorderBridge(unittest.TestCase):
    """Testa a geração de datasets de partidas a partir do treino."""

    def test_record_hand_persists_jsonl(self) -> None:
        tmp_session = Path("data/training_sessions/test_tmp_session.jsonl")
        try:
            bridge = TrainingRecorderBridge(
                session_id="test_sess",
                output_file=tmp_session,
                append_to_main_dataset=False,
                save_to_neon_db=False,
            )

            p1 = Player("p1", "Hero", 1000)
            p2 = Player("p2", "Villain", 1000)
            table = Table(players=[p1, p2], small_blind=10, big_blind=20)
            table.start_new_hand()
            # Força showdown/final
            table.apply_action(Action("p1", ActionType.FOLD))

            record = bridge.record_hand(
                table=table,
                actions_log=[{"street": "PREFLOP", "action_type": "FOLD"}],
                profile_labels={"p1": "Hero", "p2": "Villain"},
                generation=1,
                candidate_id="c0",
                candidate_params={"bluff_frequency": 0.4},
            )

            self.assertIn("hand_id", record)
            self.assertTrue(tmp_session.exists())

            with open(tmp_session, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["generation"], 1)
            self.assertEqual(lines[0]["candidate_id"], "c0")
        finally:
            if tmp_session.exists():
                tmp_session.unlink()


class TestAdaptiveTrainerQuickIntegration(unittest.TestCase):
    """Testa a execução ponta a ponta do pipeline de treino."""

    def test_fast_training_cycle(self) -> None:
        trainer = AdaptiveTrainer(
            agent_type="bluffer",
            generations=1,
            population_size=2,
            hands_per_eval=3,
            num_players=4,
            record_hands=False,  # para velocidade
            rng_seed=123,
        )
        result = trainer.train()
        self.assertIsInstance(result, TrainingResult)
        self.assertEqual(result.agent_type, "bluffer")
        self.assertIn("bluff_frequency", result.best_parameters)
        self.assertIsInstance(result.report_markdown, str)
        self.assertTrue(Path(result.model_filepath).exists())


if __name__ == "__main__":
    unittest.main()
