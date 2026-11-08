import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import pandas as pd
from src.database.recorder import get_neon_connection_with_diag

def check_local_vs_neon():
    data_dir = _ROOT / "data"
    subdirs = [
        data_dir / "01_desktop_mesas",
        data_dir / "02_notebook_headsup",
        data_dir / "03_notebook_estresse_1v5"
    ]

    local_experiments = []
    for sdir in subdirs:
        for p in sorted(sdir.iterdir()):
            if p.is_dir() and "legacy" not in p.name and "backup" not in p.name:
                tel = p / "decision_telemetry_and_bluffs.csv"
                if tel.exists():
                    df = pd.read_csv(tel)
                    local_experiments.append({
                        "category": sdir.name,
                        "folder": p.name,
                        "count": len(df)
                    })

    print(f"Total de experimentos locais definitivos: {len(local_experiments)}")
    total_local_rows = sum(e["count"] for e in local_experiments)
    print(f"Total de decisões locais: {total_local_rows:,}")

    conn, err = get_neon_connection_with_diag()
    if err:
        print(f"Erro Neon: {err}")
        return

    cur = conn.cursor()
    cur.execute("SELECT DISTINCT test_id FROM decision_telemetry_and_bluffs")
    neon_test_ids = set(r[0] for r in cur.fetchall())
    print(f"\nTotal de test_ids no Neon: {len(neon_test_ids)}")

    missing = []
    present = []
    for exp in local_experiments:
        name = exp["folder"]
        if name in neon_test_ids:
            present.append(exp)
        else:
            missing.append(exp)

    print(f"\n✓ Experimentos locais já presentes no Neon: {len(present)}")
    print(f"❌ Experimentos locais que FALTAM no Neon: {len(missing)}")

    if missing:
        print("\nLista dos experimentos que faltam sincronizar com o Neon:")
        for m in missing:
            print(f"  - [{m['category']}] {m['folder']} ({m['count']:,} linhas)")

    cur.close()
    conn.close()

if __name__ == "__main__":
    check_local_vs_neon()
