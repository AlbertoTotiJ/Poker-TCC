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
        "--test-id",
        type=str,
        default=None,
        help="ID específico para o teste (ex: test_001 ou exp_duelo_50m). Se omitido, gera timestamp automático.",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Desativa a geração automática de gráficos ao final da simulação.",
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

    # Define o ID único e padronizado do teste
    from datetime import datetime

    test_id = args.test_id
    if not test_id:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_roster = args.roster.replace(" ", "_").lower()
        test_id = f"test_{timestamp_str}_{clean_roster}"
    else:
        test_id = test_id.strip().replace(" ", "_")

    base_dir = Path(args.output_dir)
    test_dir = base_dir / test_id

    print("=" * 80)
    print("🔬 SIMULADOR E GERADOR DE TELEMETRIA COGNITIVA & BLEFES (TCC POKER IA)")
    print("=" * 80)
    print(f"• 🆔 ID DO TESTE     : {test_id}")
    print(f"• 📁 PASTA DO TESTE  : {test_dir}/")
    print(f"• Mãos a simular    : {args.hands}")
    print(f"• Formato da mesa   : {args.roster}")
    print(f"• Semente (Seed)    : {args.seed}")
    print("-" * 80)
    print("▶ Iniciando simulação...")

    t0 = time.time()
    actions, telemetry, summary = simulate_and_generate_telemetry(
        num_hands=args.hands,
        roster_mode=args.roster,
        rng_seed=args.seed,
        output_dir=args.output_dir,
        test_id=test_id,
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
    print(f"📁 ARQUIVOS DO TESTE [{test_id}] GERADOS EM:")
    print(f"   {test_dir.resolve()}")
    print(f"  1. Tabela de Ações      : {test_dir / 'game_actions.csv'}")
    print(f"  2. Tabela de Telemetria : {test_dir / 'decision_telemetry_and_bluffs.csv'}")
    print(f"  3. Resumo da Rodada     : {test_dir / 'summary.json'}")
    print("=" * 80)

    # Geração automática de gráficos científicos
    if not args.no_plots:
        print("\n📈 Gerando gráficos científicos automaticamente para este teste...")
        from scripts.plot_championship_results import generate_all_plots

        plots_dir = test_dir / "plots"
        try:
            generated_plots = generate_all_plots(
                data_dir=str(test_dir),
                output_dir=str(plots_dir),
            )
            print(f"✓ {len(generated_plots)} gráficos prontos em: {plots_dir}")
            print("💡 Visualização rápida (Dashboard Consolidado):")
            print(f"   {plots_dir / 'dashboard_consolidado_tcc.png'}")
        except Exception as e:
            print(f"⚠️ Erro ao gerar gráficos: {e}")
        print("=" * 80)

    if args.save_neon:
        print("☁️ Preparando sincronização com o banco de dados Neon PostgreSQL...")
        from src.database.recorder import _load_env_fallback
        import os

        _load_env_fallback()
        neon_url = (
            args.neon_url
            or os.environ.get("DATABASE_URL")
            or os.environ.get("POSTGRES_URL")
        )

        if not neon_url:
            print("\n" + "=" * 80)
            print("🔑 DATABASE_URL não configurada no ambiente ou no arquivo .env.")
            print("Cole a URL de conexão do seu banco de dados Neon (ex: postgresql://...):")
            print("=" * 80)
            try:
                neon_url = input("👉 URL do Neon: ").strip().strip('"').strip("'")
            except (EOFError, KeyboardInterrupt):
                neon_url = ""

            if neon_url and neon_url.startswith("postgres"):
                # Salva no .env local para evitar ter que digitar novamente
                env_file = _ROOT / ".env"
                try:
                    with open(env_file, "a", encoding="utf-8") as f:
                        f.write(f"\nDATABASE_URL={neon_url}\n")
                    print(f"✓ URL salva com segurança no arquivo local .env para execuções futuras.")
                except Exception:
                    pass

        if not neon_url or not neon_url.startswith("postgres"):
            print("⚠️ Operação cancelada: Nenhuma URL válida informada. Os dados permanecem salvos nos arquivos CSV locais.")
            print("=" * 80)
            return

        ok, count, err = save_telemetry_to_neon(
            actions=actions,
            telemetry=telemetry,
            custom_url=neon_url,
        )
        if ok:
            print(f"✓ Sucesso! {count} registros gravados com sucesso nas tabelas 'game_actions' e 'decision_telemetry_and_bluffs' do Neon.")
        else:
            print(f"⚠️ Atenção ao salvar no Neon: {err}")
        print("=" * 80)


if __name__ == "__main__":
    main()
