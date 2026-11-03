"""Script de Backup e Preservação de Resultados Experimentais (TCC Poker IA).

Cria um snapshot congelado e imutável de todos os experimentos em data/
para uma pasta de backup datada (ex: data/backups/backup_20261103_154500/).

Uso:
    python scripts/backup_experiment_data.py [--label "bateria_oficial_run1"]
"""

import argparse
from datetime import datetime
from pathlib import Path
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parent.parent


def backup_data(label: str = "bateria_oficial_run1") -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{label}_{timestamp}"
    backup_dir = _ROOT / "data" / "backups" / backup_name
    backup_dir.mkdir(parents=True, exist_ok=True)

    sources = [
        "01_desktop_mesas",
        "02_notebook_headsup",
        "03_notebook_estresse_1v5",
    ]

    print("=" * 80)
    print("🛡️  BACKUP E CONGELAMENTO DE DADOS EXPERIMENTAIS DO TCC")
    print(f"• Destino do Snapshot: {backup_dir}")
    print("=" * 80)

    total_files = 0
    for src_name in sources:
        src_path = _ROOT / "data" / src_name
        if src_path.exists():
            dest_path = backup_dir / src_name
            shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
            files_count = len(list(dest_path.rglob("*.*")))
            total_files += files_count
            print(f"✓ Preservado: data/{src_name}/ -> {files_count} arquivos salvos.")

    print("-" * 80)
    print(f"✨ Snapshot concluído com sucesso! {total_files} arquivos preservados.")
    print(f"📁 Pasta segura: {backup_dir}")
    print("=" * 80)
    return backup_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup de Dados do TCC")
    parser.add_argument(
        "--label",
        type=str,
        default="bateria_oficial_run1",
        help="Rótulo identificador do backup.",
    )
    args = parser.parse_args()
    backup_data(label=args.label)
