"""Script executável de linha de comando para Treinamento e Qualificação de Agentes.

Permite treinar BlufferAgent, MathematicalAgent ou GhMathAgent, qualificando
métricas individualmente (ex: focar em Taxa de Sucesso de Blefe, BB/100, Win Rate),
adaptando-se adversarialmente com cada agente produzido via Hall of Fame, e gravando
partidas em tempo real para geração de datasets de treino.

Uso:
    python scripts/train_agents.py --agent bluffer --metric bluff_success_rate
    python scripts/train_agents.py --agent mathematical --metric bb_per_100
    python scripts/train_agents.py --agent gh_math --generations 5 --population 6
"""

import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.training.adaptive_trainer import AdaptiveTrainer  # noqa: E402
from src.training.metrics import EvaluationMetric, MetricWeights  # noqa: E402


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sistema de Treinamento e Qualificação Individual de Agentes (TCC Poker)"
        )
    )
    parser.add_argument(
        "--agent",
        type=str,
        default="bluffer",
        choices=["bluffer", "mathematical", "gh_math"],
        help="Tipo de agente a ser treinado (padrão: bluffer)",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default="balanced",
        choices=[
            "balanced",
            "bluff_success_rate",
            "bb_per_100",
            "win_rate",
            "aggression_factor",
            "fold_equity_realized",
            "pfr",
            "vpip",
        ],
        help="Métrica individual para foco de qualificação ou 'balanced'",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=3,
        help="Quantidade de gerações evolutivas (padrão: 3)",
    )
    parser.add_argument(
        "--population",
        type=int,
        default=4,
        help="Tamanho da população por geração (padrão: 4)",
    )
    parser.add_argument(
        "--hands",
        type=int,
        default=20,
        help="Mãos simuladas por candidato em cada avaliação (padrão: 20)",
    )
    parser.add_argument(
        "--players",
        type=int,
        default=6,
        help="Número de jogadores na mesa de treino (padrão: 6)",
    )
    parser.add_argument(
        "--no-record",
        action="store_true",
        help="Desativa a gravação de partidas no dataset de treinamento",
    )
    parser.add_argument(
        "--save-neon",
        action="store_true",
        help="Sincroniza as partidas simuladas com o banco Neon PostgreSQL",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Semente pseudoaleatória para reprodutibilidade",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    print("\n" + "=" * 70)
    print("  🃏 SISTEMA DE TREINAMENTO ADAPTATIVO & QUALIFICAÇÃO DE AGENTES")
    print("=" * 70)
    print(f"  • Tipo de Agente:       {args.agent.upper()}")
    print(f"  • Métrica de Foco:      {args.metric.upper()}")
    print(f"  • Gerações:             {args.generations}")
    print(f"  • População:            {args.population}")
    print(f"  • Mãos por Avaliação:   {args.hands}")
    print(f"  • Jogadores na Mesa:    {args.players}")
    print(f"  • Gravação no Dataset:  {'SIM' if not args.no_record else 'NÃO'}")
    print(f"  • Sincronizar Neon:     {'SIM' if args.save_neon else 'NÃO'}")
    print("=" * 70 + "\n")

    weights: MetricWeights
    if args.metric == "balanced":
        if args.agent == "bluffer":
            weights = MetricWeights.preset_bluff_specialist()
        else:
            weights = MetricWeights.preset_balanced()
    else:
        weights = MetricWeights.for_single_metric(EvaluationMetric(args.metric))

    trainer = AdaptiveTrainer(
        agent_type=args.agent,
        metric_weights=weights,
        generations=args.generations,
        population_size=args.population,
        hands_per_eval=args.hands,
        num_players=args.players,
        record_hands=not args.no_record,
        save_to_neon=args.save_neon,
        rng_seed=args.seed,
    )

    def on_progress(info: dict) -> None:
        gen = info["generation"]
        tot = info["total_generations"]
        fit = info["best_fitness"]
        tier = info["best_tier"]
        dur = info["duration"]
        hands_rec = info["hands_recorded"]
        print(
            f"  [Geração {gen:02d}/{tot:02d}] "
            f"Melhor Fitness: {fit:5.1f} ({tier:<14}) | "
            f"Mãos no Dataset: {hands_rec:4d} | "
            f"Tempo: {dur:4.1f}s"
        )

    print("Iniciando ciclo adaptativo co-evolutivo...")
    start_time = time.perf_counter()
    result = trainer.train(progress_callback=on_progress)
    elapsed = time.perf_counter() - start_time

    print("\n" + "=" * 70)
    print("  🏆 RESULTADO FINAL DA SESSÃO DE TREINAMENTO")
    print("=" * 70)
    fit_val = result.qualification_card.overall_fitness
    print(f"  • Fitness Geral:        {fit_val:.1f} / 100.0")
    print(f"  • Tier Acadêmico:       {result.qualification_card.overall_tier}")
    print(f"  • Duração Total:        {elapsed:.2f}s")
    print(f"  • Modelo Salvo em:      {result.model_filepath}")
    print("-" * 70)
    print("  📊 BOLETIM DE QUALIFICAÇÃO DE MÉTRICAS INDIVIDUAIS:")
    print(
        f"  {'Métrica':<24} | {'Valor Real':<10} | {'Nota':<6} | {'Tier':<14}"
    )
    print("  " + "-" * 62)

    for _, m_score in result.qualification_card.individual_scores.items():
        print(
            f"  {m_score.metric.value:<24} | "
            f"{m_score.raw_value:>10.2f} | "
            f"{m_score.score:>6.1f} | "
            f"{m_score.tier:<14}"
        )

    print("-" * 70)
    print("  📁 DATASET DE PARTIDAS GRAVADAS:")
    print(f"  • Mãos Gravadas:        {result.dataset_summary['hands_recorded']}")
    print(f"  • Ações Registradas:    {result.dataset_summary['actions_recorded']}")
    print(f"  • Blefes Registrados:   {result.dataset_summary['bluffs_recorded']}")
    print(f"  • Arquivo JSONL:        {result.dataset_summary['session_file']}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
