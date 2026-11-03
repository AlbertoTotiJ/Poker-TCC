"""Treinamento dos Agentes Baseado no Notebook e Diagnóstico do Rigor.

Executa o pipeline completo de treinamento adaptativo co-evolutivo inspirado no
notebook 'notebooks/treinamento_agentes_colab.ipynb', aplicando as correções e
recomendações prescritas no diagnóstico do Rigor:
1. BlufferAgent focado em Taxa de Sucesso de Blefe (eliminação de sangria).
2. MathematicalAgent focado em BB/100 (extração de valor e margens de EV).
3. HybridAgent focado em Equilíbrio Competitivo com herança cruzada dos campeões.
"""

from pathlib import Path
import sys
import time
from typing import Any, Dict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.agents.trainer_agent import TrainerAgent  # noqa: E402
from src.training.adaptive_trainer import AdaptiveTrainer  # noqa: E402
from src.training.agent_registry import global_registry  # noqa: E402
from src.training.metrics import MetricWeights  # noqa: E402


def run_pipeline() -> Dict[str, Any]:
    print("=" * 78)
    print("  🃏 INICIANDO TREINAMENTO ADAPTATIVO DOS AGENTES (BASEADO NO NOTEBOOK)")
    print("=" * 78)
    print("  Auditor de Referência: Rigor")
    print("  Motor de Treino: AdaptiveTrainer com Hall of Fame Adversarial")
    print("=" * 78 + "\n")

    coach = TrainerAgent()
    results: Dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # 1. TREINAMENTO DO AGENTE BLEFADOR (Foco: bluff_success_rate)
    # -------------------------------------------------------------------------
    print(">>> [1/3] DIAGNÓSTICO E TREINAMENTO: AGENTE BLEFADOR")
    diag_bluffer = coach.diagnose_agent("bluffer")
    print(f"  • Diagnóstico do Mentor: {diag_bluffer.recommended_focus_rationale}")
    print(f"  • Métrica Alvo Prescrita: {diag_bluffer.recommended_metric}")

    def progress_bluffer(info: dict) -> None:
        print(
            f"    [Gen {info['generation']:02d}/{info['total_generations']:02d}] "
            f"Melhor Fitness: {info['best_fitness']:5.1f} ({info['best_tier']:<12}) | "
            f"Tempo: {info['duration']:4.1f}s"
        )

    t0 = time.time()
    trainer_bluffer = AdaptiveTrainer(
        agent_type="bluffer",
        target_metric=diag_bluffer.recommended_metric,
        generations=4,
        population_size=4,
        hands_per_eval=15,
        record_hands=True,
        rng_seed=42,
    )
    res_bluffer = trainer_bluffer.train(progress_callback=progress_bluffer)
    dur_bluffer = time.time() - t0

    b_card = res_bluffer.qualification_card
    bluffer_meta = global_registry.save_custom_agent(
        name="Bluffer Calibrado v2 (Anti-Leak)",
        base_type="bluffer",
        parameters=res_bluffer.best_parameters,
        qualification=b_card.to_dict(),
        session_id=res_bluffer.session_id,
        description="Foco em bluff_success_rate contra calling stations.",
    )
    print(
        f"  ✅ Concluído em {dur_bluffer:.1f}s | "
        f"Fitness: {b_card.overall_fitness:.1f} ({b_card.overall_tier})"
    )
    print(
        f"  💾 Agente registrado: {bluffer_meta.name} "
        f"[ID: {bluffer_meta.agent_id}]\n"
    )
    results["bluffer"] = {
        "metadata": bluffer_meta.to_dict(),
        "baseline": res_bluffer.baseline_parameters,
        "best": res_bluffer.best_parameters,
        "qualification": b_card.to_dict(),
        "duration": dur_bluffer,
    }

    # -------------------------------------------------------------------------
    # 2. TREINAMENTO DO AGENTE MATEMÁTICO (Foco: bb_per_100)
    # -------------------------------------------------------------------------
    print(">>> [2/3] DIAGNÓSTICO E TREINAMENTO: AGENTE MATEMÁTICO")
    diag_math = coach.diagnose_agent("mathematical")
    print(f"  • Diagnóstico do Mentor: {diag_math.recommended_focus_rationale}")
    print(f"  • Métrica Alvo Prescrita: {diag_math.recommended_metric}")

    def progress_math(info: dict) -> None:
        print(
            f"    [Gen {info['generation']:02d}/{info['total_generations']:02d}] "
            f"Melhor Fitness: {info['best_fitness']:5.1f} ({info['best_tier']:<12}) | "
            f"Tempo: {info['duration']:4.1f}s"
        )

    t0 = time.time()
    trainer_math = AdaptiveTrainer(
        agent_type="mathematical",
        target_metric=diag_math.recommended_metric,
        generations=4,
        population_size=4,
        hands_per_eval=15,
        record_hands=True,
        rng_seed=123,
    )
    res_math = trainer_math.train(progress_callback=progress_math)
    dur_math = time.time() - t0

    m_card = res_math.qualification_card
    math_meta = global_registry.save_custom_agent(
        name="Matemático Otimizado v2 (Max-BB)",
        base_type="mathematical",
        parameters=res_math.best_parameters,
        qualification=m_card.to_dict(),
        session_id=res_math.session_id,
        description="Foco em bb_per_100 para balancear extração e margens de EV.",
    )
    print(
        f"  ✅ Concluído em {dur_math:.1f}s | "
        f"Fitness: {m_card.overall_fitness:.1f} ({m_card.overall_tier})"
    )
    print(
        f"  💾 Agente registrado: {math_meta.name} "
        f"[ID: {math_meta.agent_id}]\n"
    )
    results["mathematical"] = {
        "metadata": math_meta.to_dict(),
        "baseline": res_math.baseline_parameters,
        "best": res_math.best_parameters,
        "qualification": m_card.to_dict(),
        "duration": dur_math,
    }

    # -------------------------------------------------------------------------
    # 3. TREINAMENTO DO AGENTE HÍBRIDO (Foco: balanced / herança cruzada)
    # -------------------------------------------------------------------------
    print(">>> [3/3] DIAGNÓSTICO E TREINAMENTO: AGENTE HÍBRIDO")
    diag_hybrid = coach.diagnose_agent("hybrid")
    print(f"  • Diagnóstico do Mentor: {diag_hybrid.recommended_focus_rationale}")

    # Inicializa o genoma híbrido herdando os melhores parâmetros dos dois campeões
    math_best = res_math.best_parameters
    bluff_best = res_bluffer.best_parameters
    hybrid_initial = {
        "math_weight": 0.60,
        "raise_equity_threshold": math_best.get("raise_equity_threshold", 0.65),
        "call_ev_margin": math_best.get("call_ev_margin", 0.03),
        "bluff_frequency": bluff_best.get("bluff_frequency", 0.30),
        "semi_bluff_frequency": bluff_best.get("semi_bluff_frequency", 0.65),
        "fold_equity_threshold": bluff_best.get("fold_equity_threshold", 0.42),
        "slowplay_prob": 0.15,
        "bet_sizing_factor": 0.55,
        "num_simulations": 120,
    }

    def progress_hybrid(info: dict) -> None:
        print(
            f"    [Gen {info['generation']:02d}/{info['total_generations']:02d}] "
            f"Melhor Fitness: {info['best_fitness']:5.1f} ({info['best_tier']:<12}) | "
            f"Tempo: {info['duration']:4.1f}s"
        )

    t0 = time.time()
    trainer_hybrid = AdaptiveTrainer(
        agent_type="hybrid",
        initial_parameters=hybrid_initial,
        metric_weights=MetricWeights.preset_balanced(),
        target_metric=None,  # Balanced
        generations=4,
        population_size=4,
        hands_per_eval=15,
        record_hands=True,
        rng_seed=999,
    )
    res_hybrid = trainer_hybrid.train(progress_callback=progress_hybrid)
    dur_hybrid = time.time() - t0

    h_card = res_hybrid.qualification_card
    hybrid_meta = global_registry.save_custom_agent(
        name="Híbrido Mestre v2 (GTO-Deception)",
        base_type="hybrid",
        parameters=res_hybrid.best_parameters,
        qualification=h_card.to_dict(),
        session_id=res_hybrid.session_id,
        description="Evoluído a partir da fusão dos campeões Bluffer e Matemático.",
    )
    print(
        f"  ✅ Concluído em {dur_hybrid:.1f}s | "
        f"Fitness: {h_card.overall_fitness:.1f} ({h_card.overall_tier})"
    )
    print(
        f"  💾 Agente registrado: {hybrid_meta.name} "
        f"[ID: {hybrid_meta.agent_id}]\n"
    )
    results["hybrid"] = {
        "metadata": hybrid_meta.to_dict(),
        "baseline": res_hybrid.baseline_parameters,
        "best": res_hybrid.best_parameters,
        "qualification": h_card.to_dict(),
        "duration": dur_hybrid,
    }

    print("=" * 78)
    print("  🏆 CICLO DE TREINAMENTO CONCLUÍDO COM SUCESSO!")
    print("=" * 78)
    return results


if __name__ == "__main__":
    run_pipeline()
