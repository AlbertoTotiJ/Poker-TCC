import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.database.recorder import get_neon_connection_with_diag

def main():
    conn, err = get_neon_connection_with_diag()
    if err:
        print(f"Erro ao conectar ao Neon: {err}")
        return

    print("✓ Conexão com o Neon estabelecida com sucesso!")
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tabelas encontradas: {tables}")

    for t in tables:
        try:
            cur.execute(f"SELECT count(*) FROM {t}")
            count = cur.fetchone()[0]
            print(f"• Tabela '{t}': {count:,} registros")
        except Exception as e:
            print(f"• Tabela '{t}': erro ao contar ({e})")

    # Inspecionar colunas de game_actions e decision_telemetry_and_bluffs
    for tab in ["game_actions", "decision_telemetry_and_bluffs"]:
        if tab in tables:
            cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{tab}'")
            cols = [c[0] for c in cur.fetchall()]
            print(f"\nColunas em '{tab}': {cols}")

    # Verificar amostras de experiment_id ou seed ou datas
    if "decision_telemetry_and_bluffs" in tables:
        cur.execute("SELECT min(action_id), max(action_id) FROM decision_telemetry_and_bluffs")
        print("Range action_id em decision_telemetry_and_bluffs:", cur.fetchone())
        
        # Verificar se as seeds 101, 144 e 99 estão presentes no test_id ou action_id
    cur.execute("SELECT DISTINCT test_id FROM decision_telemetry_and_bluffs")
    test_ids = [r[0] for r in cur.fetchall()]
    print(f"\nTotal de test_ids distintos: {len(test_ids)}")
    print(f"Amostra de test_ids: {test_ids[:10]}")

    seeds_found = {"seed101": 0, "seed144": 0, "seed99": 0}
    for s in ["101", "144", "99"]:
        cur.execute(f"SELECT count(*) FROM decision_telemetry_and_bluffs WHERE test_id LIKE '%{s}%' OR action_id LIKE '%{s}%'")
        c = cur.fetchone()[0]
        seeds_found[f"seed_{s}"] = c
        print(f"• Registros com '{s}' no Neon: {c:,}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
