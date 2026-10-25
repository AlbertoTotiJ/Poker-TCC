"""Suíte de testes para o TrainerAgent e o catálogo de preservação de agentes."""

from pathlib import Path
import random
import unittest

from src.agents.bluffer_agent import BlufferAgent
from src.agents.trainer_agent import AgentDiagnostic, TrainerAgent
from src.training.agent_registry import AgentRegistry


class TestTrainerAgent(unittest.TestCase):
    """Testa o Agente Treinador de IA e a preservação de agentes originais."""

    def setUp(self) -> None:
        self.tmp_catalog = Path("models/test_tmp_custom_agents.json")
        self.registry = AgentRegistry(catalog_file=self.tmp_catalog)
        self.trainer = TrainerAgent(registry=self.registry)

    def tearDown(self) -> None:
        if self.tmp_catalog.exists():
            self.tmp_catalog.unlink()

    def test_instantiate_trainer_agent(self) -> None:
        self.assertEqual(self.trainer.name, "Agente Treinador (Mentor de IA)")
        self.assertEqual(self.trainer.player_id, "trainer_coach")

    def test_diagnose_bluffer_agent(self) -> None:
        diag: AgentDiagnostic = self.trainer.diagnose_agent("bluffer")
        self.assertEqual(diag.target_agent, "Agente Blefador")
        self.assertEqual(diag.recommended_metric, "bluff_success_rate")
        self.assertGreater(len(diag.strengths), 0)
        self.assertGreater(len(diag.vulnerabilities), 0)

    def test_diagnose_mathematical_agent(self) -> None:
        diag: AgentDiagnostic = self.trainer.diagnose_agent("mathematical")
        self.assertEqual(diag.target_agent, "Agente Matemático (Alberto)")
        self.assertEqual(diag.recommended_metric, "bb_per_100")

    def test_train_and_produce_agent_preserves_original(self) -> None:
        # Verifica parâmetros originais do agente blefador
        original_bluffer = BlufferAgent(player_id="orig", name="Original")
        orig_bluff_freq = original_bluffer.bluff_frequency
        orig_semi_bluff = original_bluffer.params.semi_bluff_frequency

        # Executa treino rápido supervisionado pelo TrainerAgent
        result = self.trainer.train_and_produce_agent(
            base_agent_type="bluffer",
            new_agent_name="Meu Blefador Otimizado v1",
            target_metric="bluff_success_rate",
            generations=1,
            population_size=2,
            hands_per_eval=3,
            record_hands=False,
            rng_seed=42,
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["original_agent_preserved"])
        self.assertEqual(result["new_agent"]["name"], "Meu Blefador Otimizado v1")

        # Verifica que o agente original permanece com os mesmos parâmetros de base
        refreshed_original = BlufferAgent(player_id="orig2", name="Original 2")
        self.assertEqual(refreshed_original.bluff_frequency, orig_bluff_freq)
        self.assertEqual(
            refreshed_original.params.semi_bluff_frequency, orig_semi_bluff
        )

        # Verifica que o novo agente customizado foi salvo no catálogo
        agents_list = self.registry.list_available_agents()
        custom_entries = [a for a in agents_list if a.get("is_custom")]
        self.assertGreaterEqual(len(custom_entries), 1)

        # O agente original também continua na lista de disponíveis
        original_entries = [
            a for a in agents_list if a["agent_id"] == "bluffer"
        ]
        self.assertEqual(len(original_entries), 1)
        self.assertFalse(original_entries[0]["is_custom"])

    def test_instantiate_custom_agent_by_id(self) -> None:
        saved = self.registry.save_custom_agent(
            name="Super Blefador Especialista",
            base_type="bluffer",
            parameters={"bluff_frequency": 0.88, "fold_equity_threshold": 0.22},
            qualification={"overall_fitness": 92.5, "overall_tier": "S (Elite)"},
        )
        custom_id = saved.agent_id

        # Instancia o agente customizado pelo ID
        inst = self.registry.instantiate_agent_by_id(
            agent_id=custom_id, player_id="seat_1", rng=random.Random(1)
        )
        self.assertIsInstance(inst, BlufferAgent)
        self.assertEqual(inst.name, "Super Blefador Especialista")
        self.assertEqual(inst.params.bluff_frequency, 0.88)
        self.assertEqual(inst.params.fold_equity_threshold, 0.22)

        # O agente original continua intacto com os valores padrão
        inst_orig = self.registry.instantiate_agent_by_id(
            agent_id="bluffer", player_id="seat_2", rng=random.Random(1)
        )
        self.assertEqual(inst_orig.params.bluff_frequency, 0.40)


if __name__ == "__main__":
    unittest.main()
