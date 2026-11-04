"""Script Automatizado de Execução dos Experimentos de Notebook (TCC Poker IA).

Executa:
1. Três Duelos Heads-Up 1v1 (500 mãos cada)      -> data/02_notebook_headsup/
2. Três Mesas de Estresse Homogêneas 1v5 (500 mãos) -> data/03_notebook_estresse_1v5/
3. Geração de gráficos científicos (300 DPI) para cada experimento.
4. Proteção contra perda de dados: se os dados já existirem, cria backup automático
   ou aceita o argumento --tag (ex: --tag v2) para gerar em pastas separadas.

Uso:
    python scripts/run_experiments_notebook.py
    python scripts/run_experiments_notebook.py --tag v2
"""

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.plot_championship_results import generate_all_plots  # noqa: E402
from src.database.telemetry_generator import (  # noqa: E402
    simulate_and_generate_telemetry,
)


def run_single_exp(
    name: str,
    hands: int,
    custom_seats: list,
    seed: int,
    test_id: str,
    output_dir: str,
) -> None:
    target_dir = Path(output_dir) / test_id

    # Proteção de dados: se já existirem resultados, cria backup de segurança
    if (target_dir / "game_actions.csv").exists():
        backup_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dest = target_dir.parent / f"{target_dir.name}_backup_{backup_stamp}"
        print(f"\n⚠️ Dados anteriores detectados em {target_dir.name}!")
        print(f"📦 Criando backup de segurança automático em {backup_dest.name}...")
        shutil.copytree(target_dir, backup_dest)
        print("✓ Backup concluído! Os dados anteriores estão 100% preservados.")

    print("\n" + "=" * 80)
    print(f"🚀 INICIANDO: {name}")
    print(f"• Mãos: {hands} | Seed: {seed} | Saída: {output_dir}/{test_id}/")
    print("=" * 80)

    t0 = time.time()
    simulate_and_generate_telemetry(
        num_hands=hands,
        rng_seed=seed,
        custom_seats=custom_seats,
        output_dir=output_dir,
        test_id=test_id,
    )
    elapsed = time.time() - t0
    print(f"✓ Simulação concluída em {elapsed:.2f}s!")

    plots_dir = target_dir / "plots"
    print(f"📊 Gerando gráficos científicos (300 DPI) em {plots_dir}...")
    try:
        plots = generate_all_plots(data_dir=str(target_dir), output_dir=str(plots_dir))
        print(f"✓ {len(plots)} gráficos gerados com sucesso!")
    except Exception as e:
        print(f"⚠️ Aviso ao gerar gráficos: {e}")

    # Sincroniza metadados de modificação das pastas para o Windows Explorer exibir o horário exato
    try:
        now_ts = time.time()
        import os
        os.utime(target_dir, (now_ts, now_ts))
        if plots_dir.exists():
            os.utime(plots_dir, (now_ts, now_ts))
        if target_dir.parent.exists():
            os.utime(target_dir.parent, (now_ts, now_ts))
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Experimentos Notebook TCC")
    parser.add_argument(
        "--tag",
        type=str,
        default="",
        help="Sufixo ou versão da rodada (ex: v2, seed999, run2).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Semente pseudoaleatória controlada (padrão: 42).",
    )
    parser.add_argument(
        "--stress-extra",
        action="store_true",
        help="Executa apenas os novos cenários de estresse 1v5 dos outros agentes (04 a 10).",
    )
    args = parser.parse_args()

    t_start = time.time()
    print("*" * 80)
    print("💻 ORQUESTRADOR DE EXPERIMENTOS DO NOTEBOOK — TCC POKER IA")
    print("*" * 80)

    suffix = f"_{args.tag}" if args.tag else ""
    stress_base = "data/03_notebook_estresse_1v5"
    headsup_base = "data/02_notebook_headsup"

    if not args.stress_extra:
        # ---------------------------------------------------------
        # PARTE 1: DUELOS HEADS-UP 1v1 (data/02_notebook_headsup)
        # ---------------------------------------------------------
        run_single_exp(
            name="Duelo Heads-Up 1: GhBluffer (GTO Nash) vs Matemático (Baseline)",
            hands=500,
            custom_seats=["gh_bluffer", "math"],
            seed=args.seed if args.seed != 42 else 101,
            test_id=f"duel_ghbluffer_vs_matematico{suffix}",
            output_dir=headsup_base,
        )

        run_single_exp(
            name="Duelo Heads-Up 2: Híbrido (Evolutivo) vs GhMath (Kelly/XAI)",
            hands=500,
            custom_seats=["hybrid", "gh_math"],
            seed=args.seed if args.seed != 42 else 102,
            test_id=f"duel_hibrido_vs_ghmath{suffix}",
            output_dir=headsup_base,
        )

        run_single_exp(
            name="Duelo Heads-Up 3: Blefador (Heurístico) vs Matemático (Baseline)",
            hands=500,
            custom_seats=["bluffer", "math"],
            seed=args.seed if args.seed != 42 else 103,
            test_id=f"duel_bluffer_vs_matematico{suffix}",
            output_dir=headsup_base,
        )

        # ---------------------------------------------------------
        # PARTE 2: MESAS DE ESTRESSE 1v5 INICIAIS (01 a 03)
        # ---------------------------------------------------------
        run_single_exp(
            name="Estresse 1: 1 Matemático vs 5 Blefadores Maníacos",
            hands=500,
            custom_seats=["math", "bluffer", "bluffer", "bluffer", "bluffer", "bluffer"],
            seed=args.seed if args.seed != 42 else 201,
            test_id=f"01_math_vs_5_bluffers{suffix}",
            output_dir=stress_base,
        )

        run_single_exp(
            name="Estresse 2: 1 GhBluffer vs 5 Conservadores Passivos (NITs)",
            hands=500,
            custom_seats=[
                "gh_bluffer",
                "conservative",
                "conservative",
                "conservative",
                "conservative",
                "conservative",
            ],
            seed=args.seed if args.seed != 42 else 202,
            test_id=f"02_ghbluffer_vs_5_passivos{suffix}",
            output_dir=stress_base,
        )

        run_single_exp(
            name="Estresse 3: 1 Híbrido Mestre vs 5 Agressivos Descontrolados (LAGs)",
            hands=500,
            custom_seats=[
                "hybrid",
                "aggressive",
                "aggressive",
                "aggressive",
                "aggressive",
                "aggressive",
            ],
            seed=args.seed if args.seed != 42 else 203,
            test_id=f"03_hibrido_vs_5_agressivos{suffix}",
            output_dir=stress_base,
        )

    # ---------------------------------------------------------
    # PARTE 3: MESAS DE ESTRESSE 1v5 DOS OUTROS AGENTES (04 a 10)
    # ---------------------------------------------------------
    seed_s = args.seed

    run_single_exp(
        name="Estresse 4: 1 GhMath (Gustavo) vs 5 Blefadores Maníacos",
        hands=500,
        custom_seats=["gh_math", "bluffer", "bluffer", "bluffer", "bluffer", "bluffer"],
        seed=seed_s,
        test_id=f"04_ghmath_vs_5_bluffers{suffix}",
        output_dir=stress_base,
    )

    run_single_exp(
        name="Estresse 5: 1 Matemático Treinado (Tier S) vs 5 Blefadores Maníacos",
        hands=500,
        custom_seats=["trained_math", "bluffer", "bluffer", "bluffer", "bluffer", "bluffer"],
        seed=seed_s,
        test_id=f"05_trained_math_vs_5_bluffers{suffix}",
        output_dir=stress_base,
    )

    run_single_exp(
        name="Estresse 6: 1 Blefador Treinado (Tier S) vs 5 Conservadores Passivos (NITs)",
        hands=500,
        custom_seats=["trained_bluffer", "conservative", "conservative", "conservative", "conservative", "conservative"],
        seed=seed_s,
        test_id=f"06_trained_bluffer_vs_5_passivos{suffix}",
        output_dir=stress_base,
    )

    run_single_exp(
        name="Estresse 7: 1 Blefador Heurístico vs 5 Matemáticos Baseline",
        hands=500,
        custom_seats=["bluffer", "math", "math", "math", "math", "math"],
        seed=seed_s,
        test_id=f"07_bluffer_vs_5_matematicos{suffix}",
        output_dir=stress_base,
    )

    run_single_exp(
        name="Estresse 8: 1 Equilibrado (TAG) vs 5 Blefadores Maníacos",
        hands=500,
        custom_seats=["balanced", "bluffer", "bluffer", "bluffer", "bluffer", "bluffer"],
        seed=seed_s,
        test_id=f"08_balanced_vs_5_bluffers{suffix}",
        output_dir=stress_base,
    )

    run_single_exp(
        name="Estresse 9: 1 Conservador (NIT) vs 5 Agressivos Descontrolados (LAGs)",
        hands=500,
        custom_seats=["conservative", "aggressive", "aggressive", "aggressive", "aggressive", "aggressive"],
        seed=seed_s,
        test_id=f"09_conservative_vs_5_agressivos{suffix}",
        output_dir=stress_base,
    )

    run_single_exp(
        name="Estresse 10: 1 Agressivo (LAG) vs 5 Conservadores Passivos (NITs)",
        hands=500,
        custom_seats=["aggressive", "conservative", "conservative", "conservative", "conservative", "conservative"],
        seed=seed_s,
        test_id=f"10_aggressive_vs_5_passivos{suffix}",
        output_dir=stress_base,
    )

    total_min = (time.time() - t_start) / 60
    print("\n" + "*" * 80)
    print(f"🎉 EXPERIMENTOS CONCLUÍDOS EM {total_min:.2f} MINUTOS!")
    print(f"📁 Pasta de Estresse 1v5: {Path(stress_base).resolve()}")
    print("*" * 80)


if __name__ == "__main__":
    main()
