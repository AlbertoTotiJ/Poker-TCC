"""Suíte de testes unitários para o serviço de Grafos Cognitivos XAI (Macro e Micro)."""

import unittest
from unittest.mock import MagicMock, patch

from src.visualization.xai_graph_service import (
    build_macro_graph,
    build_micro_graph,
    get_available_hands_for_xai,
)


class TestXaiGraphService(unittest.TestCase):
    """Testa os endpoints e montagem de nós/arestas para XAI."""

    def test_get_available_hands_structure(self) -> None:
        result = get_available_hands_for_xai(limit=5)
        self.assertTrue(result["success"])
        self.assertIn("hands", result)
        self.assertIn("source", result)
        if result["hands"]:
            first = result["hands"][0]
            self.assertIn("hand_id", first)
            self.assertIn("total_pot", first)
            self.assertIn("has_bluff", first)

    def test_build_macro_graph_structure(self) -> None:
        # Pega a primeira mão disponível
        hands_res = get_available_hands_for_xai(limit=1)
        if not hands_res["hands"]:
            self.skipTest("Nenhuma mão disponível no banco ou local para teste.")

        target_hand_id = hands_res["hands"][0]["hand_id"]
        macro = build_macro_graph(target_hand_id)

        self.assertTrue(macro["success"])
        self.assertEqual(macro["view"], "macro")
        self.assertEqual(macro["hand_id"], target_hand_id)
        self.assertGreater(len(macro["nodes"]), 0)
        self.assertGreater(len(macro["edges"]), 0)

        # Verifica se o nó raiz da mão existe
        root_nodes = [n for n in macro["nodes"] if n.get("customData", {}).get("type") == "hand_root"]
        self.assertEqual(len(root_nodes), 1)

        # Verifica se o nó vencedor existe
        winner_nodes = [n for n in macro["nodes"] if n.get("customData", {}).get("type") == "winner_node"]
        self.assertEqual(len(winner_nodes), 1)

    def test_build_micro_graph_structure(self) -> None:
        hands_res = get_available_hands_for_xai(limit=1)
        if not hands_res["hands"]:
            self.skipTest("Nenhuma mão disponível para teste.")

        target_hand_id = hands_res["hands"][0]["hand_id"]
        macro = build_macro_graph(target_hand_id)
        if not macro["actions"]:
            self.skipTest("Nenhuma ação encontrada para testar Micro.")

        first_action_id = macro["actions"][0]["action_id"]
        micro = build_micro_graph(first_action_id)

        self.assertTrue(micro["success"])
        self.assertEqual(micro["view"], "micro")
        self.assertEqual(micro["action_id"], first_action_id)
        self.assertGreater(len(micro["nodes"]), 0)
        self.assertGreater(len(micro["edges"]), 0)

        # Verifica se as 3 camadas neurais estão presentes
        layers = {n.get("customData", {}).get("layer") for n in micro["nodes"]}
        self.assertIn("input", layers)
        self.assertIn("hidden", layers)
        self.assertIn("output", layers)

        # Verifica pilares do Estado da Arte em XAI
        self.assertIn("board_texture", micro)
        self.assertIn("blocker", micro)
        self.assertIn("fold_equity", micro)
        self.assertIn("counterfactuals", micro)

        # Validação da Matriz Contrafactual
        cf = micro["counterfactuals"]
        self.assertIn("chosen_action", cf)
        self.assertIn("options", cf)
        self.assertGreaterEqual(len(cf["options"]), 2)
        self.assertIn("rationale_contrast", cf)

        # Validação dos nós enriquecidos
        categories = {n.get("customData", {}).get("category") for n in micro["nodes"]}
        self.assertIn("board_texture", categories)
        self.assertIn("blocker", categories)
        self.assertIn("fold_equity", categories)


if __name__ == "__main__":
    unittest.main()
