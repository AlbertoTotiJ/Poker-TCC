"""Script Automatizado de Execução dos Experimentos de Desktop (TCC Poker IA).

Executa:
1. Mesa 6-Max Heterogênea (1.000 mãos) -> data/01_desktop_mesas/6max_heterogeneo_1000m
2. Mesa 9-Max Full Ring (1.000 mãos)    -> data/01_desktop_mesas/9max_full_ring_1000m
3. Geração de gráficos científicos (300 DPI) para cada experimento.
4. Proteção contra perda de dados: se os dados já existirem, cria backup automático
   ou aceita o argumento --tag (ex: --tag v2) para gerar em pastas separadas.

Uso:
    python scripts/run_experiments_desktop.py
    python scripts/run_experiments_desktop.py --tag v2 --seed 101
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Experimentos Desktop TCC")
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
        help="Semente pseudoaleatória controlada.",
    )
    args = parser.parse_args()

    t_start = time.time()
    print("*" * 80)
    print("🖥️  ORQUESTRADOR DE EXPERIMENTOS DO COMPUTADOR DESKTOP — TCC POKER IA")
    print("*" * 80)

    out_base = "data/01_desktop_mesas"
    suffix = f"_{args.tag}" if args.tag else ""

    # 1. Mesa 6-Max Heterogênea
    seats_6max = [
        "gh_bluffer",
        "gh_math",
        "math",
        "bluffer",
        "hybrid",
        "balanced",
    ]
    run_single_exp(
        name="Experimento 1: Mesa 6-Max Heterogênea",
        hands=1000,
        custom_seats=seats_6max,
        seed=args.seed,
        test_id=f"6max_heterogeneo_1000m{suffix}",
        output_dir=out_base,
    )

    # 2. Mesa 9-Max Full Ring
    seats_9max = [
        "gh_bluffer",
        "gh_math",
        "math",
        "trained_math",
        "bluffer",
        "trained_bluffer",
        "hybrid",
        "aggressive",
        "conservative",
    ]
    run_single_exp(
        name="Experimento 2: Mesa 9-Max Full Ring Completa",
        hands=1000,
        custom_seats=seats_9max,
        seed=args.seed,
        test_id=f"9max_full_ring_1000m{suffix}",
        output_dir=out_base,
    )

    total_min = (time.time() - t_start) / 60
    print("\n" + "*" * 80)
    print(f"🎉 EXPERIMENTOS DE DESKTOP CONCLUÍDOS EM {total_min:.2f} MINUTOS!")
    print(f"📁 Verifique os resultados e gráficos em: {Path(out_base).resolve()}")
    print("*" * 80)


if __name__ == "__main__":
    main()
