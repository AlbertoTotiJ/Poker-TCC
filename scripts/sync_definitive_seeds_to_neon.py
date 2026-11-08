"""Script de Carga Limpa e Sincronização Integral das 3 Seeds Definitivas (101, 144, 99) no Neon PostgreSQL.

Executa:
1. Limpeza completa (TRUNCATE) dos dados legados e antigos em game_actions e decision_telemetry_and_bluffs.
2. Carga em lote (Bulk Insert de alta performance) de todos os 42 experimentos locais definitivos:
   - data/01_desktop_mesas
   - data/02_notebook_headsup
   - data/03_notebook_estresse_1v5
3. Auditoria e validação final da contagem de registros (181.083 decisões).
"""

from pathlib import Path
import sys
import time
import pandas as pd
from psycopg2.extras import execute_values

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.database.recorder import get_neon_connection_with_diag


def execute_full_clean_sync():
    print("=" * 80)
    print("CARGA INTEGRAL DAS 3 SEEDS DEFINITIVAS NO NEON POSTGRESQL")
    print("=" * 80)

    # 1. Mapeamento de todos os 42 experimentos locais
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
                act = p / "game_actions.csv"
                if tel.exists() and act.exists():
                    local_experiments.append({
                        "category": sdir.name,
                        "folder": p.name,
                        "tel_path": tel,
                        "act_path": act
                    })

    print(f"✓ Catalogados {len(local_experiments)} experimentos locais definitivos.")

    # 2. Conexão ao Neon
    conn, err = get_neon_connection_with_diag()
    if err or not conn:
        print(f"❌ Erro ao conectar ao Neon: {err}")
        return

    cur = conn.cursor()

    # 3. Limpeza dos dados legados
    print("\nLimpando registros legados das tabelas game_actions e decision_telemetry_and_bluffs...")
    cur.execute("TRUNCATE TABLE game_actions, decision_telemetry_and_bluffs CASCADE;")
    conn.commit()
    print("✓ Tabelas limpas com sucesso!")

    # 4. Inserção em Lote (Bulk Insert) de todos os experimentos
    act_cols = [
        "action_id", "hand_id", "step_order", "street", "player_id", "player_name",
        "profile", "hole_cards", "community_cards", "action_type", "amount",
        "pot_before", "pot_after", "player_stack_before", "player_stack_after",
        "test_id"
    ]
    cols_str_act = ", ".join(act_cols)
    sql_act_batch = f"INSERT INTO game_actions ({cols_str_act}) VALUES %s"

    tel_cols = [
        "action_id", "hand_id", "player_id", "player_name", "profile", "street",
        "action_taken", "amount", "decision_mode", "raw_equity", "pot_odds",
        "expected_value", "outs_count", "tactical_reason", "is_bluff", "bluff_type",
        "opponent_response", "bluff_outcome", "net_bluff_chips", "hand_result",
        "showdown_occurred", "test_id"
    ]
    cols_str_tel = ", ".join(tel_cols)
    sql_tel_batch = f"INSERT INTO decision_telemetry_and_bluffs ({cols_str_tel}) VALUES %s"

    t0 = time.time()
    total_actions_inserted = 0
    total_telemetry_inserted = 0

    print(f"\nIniciando inserção em lote dos {len(local_experiments)} experimentos...")

    for idx, exp in enumerate(local_experiments, 1):
        test_id = exp["folder"]
        df_act = pd.read_csv(exp["act_path"])
        df_tel = pd.read_csv(exp["tel_path"])

        df_act["test_id"] = test_id
        df_tel["test_id"] = test_id

        # Garantir action_id globalmente único prefixando com test_id se necessário
        df_act["action_id"] = df_act["action_id"].apply(
            lambda x: str(x) if str(x).startswith(test_id) else f"{test_id}_{x}"
        )
        df_tel["action_id"] = df_tel["action_id"].apply(
            lambda x: str(x) if str(x).startswith(test_id) else f"{test_id}_{x}"
        )

        # Garantir presença de todas as colunas
        for col in act_cols:
            if col not in df_act.columns:
                df_act[col] = None

        for col in tel_cols:
            if col not in df_tel.columns:
                df_tel[col] = None

        # Substituir NaNs por None para o PostgreSQL
        df_act = df_act[act_cols].where(pd.notnull(df_act[act_cols]), None)
        df_tel = df_tel[tel_cols].where(pd.notnull(df_tel[tel_cols]), None)

        # Preparar tuplas
        act_records = [tuple(x) for x in df_act.to_numpy()]
        tel_records = [tuple(x) for x in df_tel.to_numpy()]

        # Executar em páginas de 3000
        execute_values(cur, sql_act_batch, act_records, page_size=3000)
        execute_values(cur, sql_tel_batch, tel_records, page_size=3000)
        conn.commit()

        total_actions_inserted += len(act_records)
        total_telemetry_inserted += len(tel_records)

        if idx % 5 == 0 or idx == len(local_experiments):
            elapsed = time.time() - t0
            print(f"  [{idx:2d}/{len(local_experiments)}] {test_id} | Inseridas {total_actions_inserted:,} decisões ({elapsed:.1f}s)")

    # 5. Auditoria de Contagem Final no Neon
    print("\n" + "=" * 80)
    print("AUDITORIA FINAL DA CARGA NO NEON POSTGRESQL")
    print("=" * 80)

    cur.execute("SELECT count(*) FROM game_actions;")
    neon_actions_cnt = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM decision_telemetry_and_bluffs;")
    neon_telemetry_cnt = cur.fetchone()[0]

    cur.execute("SELECT count(DISTINCT test_id) FROM decision_telemetry_and_bluffs;")
    neon_tests_cnt = cur.fetchone()[0]

    # Contagem por Seed
    print(f"• Total de Registros em 'game_actions': {neon_actions_cnt:,}")
    print(f"• Total de Registros em 'decision_telemetry_and_bluffs': {neon_telemetry_cnt:,}")
    print(f"• Total de Experimentos Distintos: {neon_tests_cnt}")

    for s in ["101", "144", "99"]:
        cur.execute(f"SELECT count(*) FROM decision_telemetry_and_bluffs WHERE test_id LIKE '%{s}%';")
        cnt_seed = cur.fetchone()[0]
        print(f"  - Decisões da Seed {s}: {cnt_seed:,}")

    cur.close()
    conn.close()

    total_time = time.time() - t0
    print("\n" + "=" * 80)
    print(f"✓ PROCESSO CONCLUÍDO COM SUCESSO EM {total_time:.1f}s!")
    print("=" * 80)


if __name__ == "__main__":
    execute_full_clean_sync()
