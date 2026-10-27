"""Testes completos de integridade, calibração e treinamento do Agente Híbrido."""

from pathlib import Path
import random
import pytest

from src.agents.hybrid_agent import (
    HybridAgent,
    HybridDecision,
    HybridParameters,
)
from src.agents.trainer_agent import TrainerAgent
from src.engine.deck import Card
from src.engine.table import ActionType, Street, Table
from src.engine.player import Player
from src.training.adaptive_trainer import AdaptiveTrainer
from src.training.agent_registry import AgentRegistry, CustomAgentMetadata
from src.training.parameters import (
    clamp_parameters,
    crossover_parameters,
    generate_random_parameters,
    get_default_parameters,
    get_specs_for_agent,
    instantiate_agent,
    mutate_parameters,
)


def test_hybrid_parameters_defaults_and_serialization() -> None:
    params = HybridParameters()
    assert params.math_weight == 0.50
    assert params.raise_equity_threshold == 0.60
    assert params.call_ev_margin == 0.02
    assert params.bluff_frequency == 0.25
    assert params.semi_bluff_frequency == 0.50
    assert params.fold_equity_threshold == 0.35
    assert params.slowplay_prob == 0.20
    assert params.bet_sizing_factor == 0.55
    assert params.num_simulations == 150

    d = params.to_dict()
    assert isinstance(d, dict)
    assert d["math_weight"] == 0.50

    reconstructed = HybridParameters.from_dict(d)
    assert reconstructed.math_weight == params.math_weight
    assert reconstructed.num_simulations == params.num_simulations


def test_hybrid_parameters_from_parents() -> None:
    math_p = {
        "raise_equity_threshold": 0.54,
        "call_ev_margin": 0.05,
        "num_simulations": 200,
    }
    bluffer_p = {
        "bluff_frequency": 0.35,
        "semi_bluff_frequency": 0.65,
        "fold_equity_threshold": 0.40,
        "bet_sizing_factor": 0.60,
    }

    hybrid_p = HybridParameters.from_parents(
        math_params=math_p,
        bluffer_params=bluffer_p,
        math_weight=0.70,
    )

    assert hybrid_p.math_weight == 0.70
    assert hybrid_p.raise_equity_threshold == 0.54
    assert hybrid_p.call_ev_margin == 0.05
    assert hybrid_p.num_simulations == 200
    assert hybrid_p.bluff_frequency == 0.35
    assert hybrid_p.semi_bluff_frequency == 0.65
    assert hybrid_p.fold_equity_threshold == 0.40
    assert hybrid_p.bet_sizing_factor == 0.60


def test_hybrid_agent_instantiation_and_properties() -> None:
    agent = HybridAgent(
        player_id="h1",
        name="Híbrido Teste",
        math_weight=0.60,
        raise_equity_threshold=0.65,
        rng=random.Random(42),
    )
    assert agent.player_id == "h1"
    assert agent.name == "Híbrido Teste"
    assert agent.params.math_weight == 0.60
    assert agent.params.raise_equity_threshold == 0.65

    # Test backward compatibility aliases
    assert agent.math_threshold == 0.65
    agent.math_threshold = 0.58
    assert agent.params.raise_equity_threshold == 0.58

    assert agent.bluff_prob == 0.25
    agent.bluff_prob = 0.30
    assert agent.params.bluff_frequency == 0.30


def test_hybrid_agent_export_load_and_save(tmp_path: Path) -> None:
    agent = HybridAgent(player_id="h1", bluff_frequency=0.40)
    exported = agent.export_parameters()
    assert exported["bluff_frequency"] == 0.40

    exported["bluff_frequency"] = 0.20
    agent.load_parameters(exported)
    assert agent.params.bluff_frequency == 0.20

    filepath = tmp_path / "hybrid_test.json"
    agent.save_parameters(filepath)
    assert filepath.exists()

    agent2 = HybridAgent(player_id="h2")
    agent2.load_parameters_file(filepath)
    assert agent2.params.bluff_frequency == 0.20


def test_hybrid_agent_evaluates_state_monster_hand() -> None:
    agent = HybridAgent(
        player_id="h_monster",
        slowplay_prob=0.0,  # Não desacelera, aposta por valor
        rng=random.Random(42),
    )
    hole = [Card.from_str("As"), Card.from_str("Ks")]
    board = [Card.from_str("Qs"), Card.from_str("Js"), Card.from_str("10s")]

    dec = agent.evaluate_state(
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
        street=Street.FLOP,
    )
    assert dec.action_type == ActionType.BET
    assert dec.mode == "VALUE_BET"
    assert dec.equity >= 0.80


def test_hybrid_agent_evaluates_state_semi_bluff() -> None:
    agent = HybridAgent(
        player_id="h_draw",
        math_weight=0.20,             # Mais agressivo no blefe
        semi_bluff_frequency=1.0,     # Força semi-blefe
        rng=random.Random(42),
    )
    hole = [Card.from_str("8s"), Card.from_str("7s")]
    board = [Card.from_str("6s"), Card.from_str("2s"), Card.from_str("Kh")]

    dec = agent.evaluate_state(
        hole_cards=hole,
        community_cards=board,
        pot_size=100,
        to_call=0,
        player_stack=500,
        player_current_bet=0,
        current_highest_bet=0,
        min_raise=20,
        big_blind=20,
        num_opponents=1,
        legal_actions=[ActionType.CHECK, ActionType.BET],
        street=Street.FLOP,
    )
    assert dec.action_type == ActionType.BET
    assert dec.mode == "SEMI_BLUFF"
    assert dec.is_deceptive is True


def test_hybrid_agent_training_parameters_specs() -> None:
    specs = get_specs_for_agent("hybrid")
    spec_names = {s.name for s in specs}
    assert "math_weight" in spec_names
    assert "raise_equity_threshold" in spec_names
    assert "bluff_frequency" in spec_names
    assert "semi_bluff_frequency" in spec_names
    assert "slowplay_prob" in spec_names

    defaults = get_default_parameters("hybrid")
    assert defaults["math_weight"] == 0.50

    rand_params = generate_random_parameters("hybrid", rng=random.Random(42))
    assert 0.10 <= rand_params["math_weight"] <= 0.90

    clamped = clamp_parameters("hybrid", {"math_weight": 2.5, "bluff_frequency": -0.5})
    assert clamped["math_weight"] == 0.90
    assert clamped["bluff_frequency"] == 0.05

    mutated = mutate_parameters("hybrid", defaults, mutation_rate=1.0, rng=random.Random(42))
    assert isinstance(mutated, dict)

    child = crossover_parameters("hybrid", defaults, mutated, rng=random.Random(42))
    assert isinstance(child, dict)


def test_instantiate_agent_hybrid() -> None:
    agent = instantiate_agent(
        agent_type="hybrid",
        player_id="h_inst",
        name="Híbrido Instanciado",
        params={"math_weight": 0.75, "bluff_frequency": 0.15},
    )
    assert isinstance(agent, HybridAgent)
    assert agent.params.math_weight == 0.75
    assert agent.params.bluff_frequency == 0.15


def test_agent_registry_hybrid_support(tmp_path: Path) -> None:
    registry_file = tmp_path / "custom_agents.json"
    registry = AgentRegistry(catalog_file=registry_file)

    # 1. Instancia agente padrão
    agent_std = registry.instantiate_agent_by_id("hybrid", player_id="p_std")
    assert isinstance(agent_std, HybridAgent)

    # 2. Salva agente customizado híbrido
    meta = registry.save_custom_agent(
        name="Meu Híbrido Otimizado",
        base_type="hybrid",
        parameters={"math_weight": 0.65, "bluff_frequency": 0.30},
        qualification={"overall_fitness": 88.0, "overall_tier": "A (Mestre)"},
    )
    assert meta.base_type == "hybrid"

    # 3. Instancia agente customizado pelo ID
    agent_custom = registry.instantiate_agent_by_id(meta.agent_id, player_id="p_cust")
    assert isinstance(agent_custom, HybridAgent)
    assert agent_custom.name == "Meu Híbrido Otimizado"
    assert agent_custom.params.math_weight == 0.65


def test_trainer_agent_diagnose_hybrid() -> None:
    trainer = TrainerAgent()
    diag = trainer.diagnose_agent("hybrid")
    assert "Híbrido" in diag.target_agent
    assert len(diag.strengths) >= 2
    assert diag.recommended_metric == "bb_per_100"


def test_adaptive_trainer_hybrid_short_run(tmp_path: Path) -> None:
    trainer = AdaptiveTrainer(
        agent_type="hybrid",
        generations=1,
        population_size=2,
        hands_per_eval=5,
        models_dir=tmp_path,
        rng_seed=42,
    )
    result = trainer.train()
    assert result.agent_type == "hybrid"
    assert "math_weight" in result.best_parameters
    assert "bluff_frequency" in result.best_parameters
    assert result.qualification_card.overall_fitness >= 0.0
