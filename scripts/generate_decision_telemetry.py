"""Script CLI para Geração das Tabelas de Ações e Telemetria de Decisões & Blefes (TCC).

Uso:
    python scripts/generate_decision_telemetry.py --hands 50 --roster tier_s_duelo
    python scripts/generate_decision_telemetry.py --hands 500 --roster hybrid_vs_champions
    python scripts/generate_decision_telemetry.py --hands 10000 --roster tcc_champions_9
"""

import argparse
from pathlib import Path
import sys
import time

# Garante resolução dos pacotes 'src'
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.database.telemetry_generator import (  # noqa: E402
    save_telemetry_to_neon,
    simulate_and_generate_telemetry,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera datasets de Ações na Mesa e Telemetria Cognitiva com Análise de Blefes."
    )
    parser.add_argument(
        "--hands",
        type=int,
        default=50,
        help="Quantidade de mãos a simular (ex: 50, 500, 10000).",
    )
    parser.add_argument(
        "--roster",
        type=str,
        default="tier_s_duelo",
        help="Formato do torneio: tier_s_duelo, hybrid_vs_champions, tcc_champions_9, etc.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Semente pseudoaleatória controlada para reprodutibilidade científica.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data",
        help="Diretório onde os arquivos CSV serão salvos.",
    )
    parser.add_argument(
        "--save-neon",
        action="store_true",
        help="Salva e sincroniza os registros diretamente nas tabelas do Neon PostgreSQL.",
    )
    parser.add_argument(
        "--neon-url",
        type=str,
        default=None,
        help="URL de conexão customizada do Neon (caso não utilize a DATABASE_URL do ambiente).",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("🔬 SIMULADOR E GERADOR DE TELEMETRIA COGNITIVA & BLEFES (TCC POKER IA)")
    print("=" * 80)
    print(f"• Mãos a simular   : {args.hands}")
    print(f"• Formato da mesa  : {args.roster}")
    print(f"• Semente (Seed)   : {args.seed}")
    print(f"• Diretório destino: {args.output_dir}/")
    print("-" * 80)
    print("▶ Iniciando simulação...")

    t0 = time.time()
    actions, telemetry, summary = simulate_and_generate_telemetry(
        num_hands=args.hands,
        roster_mode=args.roster,
        rng_seed=args.seed,
        output_dir=args.output_dir,
    )
    elapsed = time.time() - t0

    print(f"✓ Concluído com sucesso em {elapsed:.2f} segundos!")
    print("-" * 80)
    print("📊 RESUMO DOS DADOS GERADOS:")
    print(f"  - Total de Ações Físicas na Mesa (Tabela 1)    : {len(actions):,} registros")
    print(f"  - Total de Decisões & Telemetria (Tabela 2)   : {len(telemetry):,} registros")
    print(f"  - Total de Blefes Identificados               : {summary['total_bluffs']} tentativas")
    print(f"    • Blefes Puros (Pure Bluffs)                : {summary['pure_bluffs']}")
    print(f"    • Semi-Blefes com Draws (Semi-Bluffs)       : {summary['semi_bluffs']}")
    print(f"    • Blefes de Continuação (C-Bets)            : {summary['cbet_bluffs']}")
    print(f"    • Roubos de Blinds Pré-flop (Steals)        : {summary['steal_bluffs']}")
    print(f"    • Blefes de Bloqueador (Blockers)           : {summary['blocker_bluffs']}")
    print("  - Reação dos Oponentes aos Blefes:")
    print(f"    • Aceito pelo Vilão (Todos Folds)           : {summary['accepted_folds']} ({summary['accepted_folds'] / max(1, summary['total_bluffs']):.1%})")
    print(f"    • Recusado pelo Vilão com Call              : {summary['refused_calls']} ({summary['refused_calls'] / max(1, summary['total_bluffs']):.1%})")
    print(f"    • Recusado pelo Vilão com Re-aumento (Raise): {summary['refused_raises']} ({summary['refused_raises'] / max(1, summary['total_bluffs']):.1%})")
    print("  - Desfecho dos Blefes:")
    print(f"    • Vencidos (Sucesso na mão)                 : {summary['successful_outcomes']} ({summary['successful_outcomes'] / max(1, summary['total_bluffs']):.1%})")
    print(f"    • Perdidos (Derrotados)                     : {summary['failed_outcomes']} ({summary['failed_outcomes'] / max(1, summary['total_bluffs']):.1%})")
    print("-" * 80)
    print("📁 ARQUIVOS CSV GERADOS PARA ANÁLISE NO TCC:")
    print(f"  1. Tabela de Ações      : {Path(args.output_dir) / 'game_actions.csv'}")
    print(f"  2. Tabela de Telemetria : {Path(args.output_dir) / 'decision_telemetry_and_bluffs.csv'}")
    print("=" * 80)

    if args.save_neon:
        print("☁️ Sincronizando dados com o banco de dados Neon PostgreSQL...")
        ok, count, err = save_telemetry_to_neon(
            actions=actions,
            telemetry=telemetry,
            custom_url=args.neon_url,
        )
        if ok:
            print(f"✓ Sucesso! {count} registros gravados com sucesso nas tabelas 'game_actions' e 'decision_telemetry_and_bluffs' do Neon.")
        else:
            print(f"⚠️ Atenção ao salvar no Neon: {err}")
        print("=" * 80)


if __name__ == "__main__":
    main()
