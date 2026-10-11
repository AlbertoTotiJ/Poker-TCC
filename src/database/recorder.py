"""Módulo de autenticação, gravação dupla (arquivo + Neon) e simulação de rodadas."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
from typing import Any, Dict, List, Optional, Tuple

from src.agents.heuristic import AgentProfile, HeuristicAgent
from src.engine.player import Player
from src.engine.table import Street, Table

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RECORD_FILE = DATA_DIR / "partidas_gravadas.jsonl"
DEFAULT_AUTH_CODE = "TCC2026"


def get_auth_code() -> str:
    """Retorna o código de autenticação configurado ou o padrão TCC2026."""
    return os.environ.get("RESEARCH_ACCESS_CODE", DEFAULT_AUTH_CODE)


def verify_auth_code(code: str) -> bool:
    """Verifica se o código fornecido é válido."""
    if not code:
        return False
    expected = get_auth_code().strip()
    return code.strip() == expected


def get_neon_connection():
    """Tenta obter uma conexão com o banco Neon PostgreSQL se configurado."""
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if not db_url:
        return None
    try:
        import psycopg2

        # Conexão com timeout curto para não travar funções serverless
        conn = psycopg2.connect(db_url, connect_timeout=5)
        return conn
    except Exception:
        return None


def ensure_neon_schema(conn) -> bool:
    """Garante que a estrutura de tabelas do Neon exista."""
    schema_sql = """
    CREATE TABLE IF NOT EXISTS matches (
        id SERIAL PRIMARY KEY,
        session_id VARCHAR(64),
        num_players INT,
        hands_played INT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS hands (
        id SERIAL PRIMARY KEY,
        hand_index INT,
        pot_total INT,
        community_cards JSONB,
        winners JSONB,
        bluffs_detected INT DEFAULT 0,
        hand_details JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """
    try:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False


def save_hand_to_neon(hand_data: Dict[str, Any]) -> bool:
    """Salva os dados de uma mão no banco de dados Neon."""
    conn = get_neon_connection()
    if conn is None:
        return False
    try:
        ensure_neon_schema(conn)
        with conn.cursor() as cur:
            insert_sql = """
            INSERT INTO hands (
                hand_index, pot_total, community_cards, winners,
                bluffs_detected, hand_details
            ) VALUES (%s, %s, %s, %s, %s, %s);
            """
            cur.execute(
                insert_sql,
                (
                    hand_data.get("hand_index", 1),
                    hand_data.get("pot_total", 0),
                    json.dumps(hand_data.get("community_cards", [])),
                    json.dumps(hand_data.get("winners", [])),
                    hand_data.get("bluffs_count", 0),
                    json.dumps(hand_data, ensure_ascii=False),
                ),
            )
        conn.commit()
        conn.close()
        return True
    except Exception:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return False


def save_hand_to_file(hand_data: Dict[str, Any]) -> bool:
    """Grava a mão em formato JSON Lines no arquivo separado de segurança."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(RECORD_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(hand_data, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def build_research_roster(
    num_players: int = 6,
    starting_stack: int = 1000,
    rng: Optional[random.Random] = None,
) -> Tuple[List[Player], Dict[str, HeuristicAgent], Dict[str, str]]:
    """Gera o elenco balanceado com os 3 perfis de jogadores.

    Para 6 jogadores: 2 Matemáticos, 2 Agressivos, 2 Conservadores.
    Para 9 jogadores: 3 Matemáticos, 3 Agressivos, 3 Conservadores.
    """
    if num_players not in (6, 9):
        num_players = 6

    count_each = num_players // 3  # 2 ou 3 de cada perfil
    players: List[Player] = []
    agents: Dict[str, HeuristicAgent] = {}
    profile_labels: Dict[str, str] = {}

    idx = 1
    # 1. Matemáticos
    for i in range(1, count_each + 1):
        pid = f"bot_mat_{i}"
        pname = f"Matemático {i}"
        players.append(Player(player_id=pid, name=pname, stack=starting_stack))
        agents[pid] = HeuristicAgent(
            player_id=pid,
            name=pname,
            profile=AgentProfile.BALANCED,
            rng=rng,
        )
        profile_labels[pid] = "Matemático"
        idx += 1

    # 2. Agressivos
    for i in range(1, count_each + 1):
        pid = f"bot_agr_{i}"
        pname = f"Agressivo {i}"
        players.append(Player(player_id=pid, name=pname, stack=starting_stack))
        agents[pid] = HeuristicAgent(
            player_id=pid,
            name=pname,
            profile=AgentProfile.AGGRESSIVE,
            rng=rng,
        )
        profile_labels[pid] = "Agressivo"
        idx += 1

    # 3. Conservadores
    for i in range(1, count_each + 1):
        pid = f"bot_con_{i}"
        pname = f"Conservador {i}"
        players.append(Player(player_id=pid, name=pname, stack=starting_stack))
        agents[pid] = HeuristicAgent(
            player_id=pid,
            name=pname,
            profile=AgentProfile.CONSERVATIVE,
            rng=rng,
        )
        profile_labels[pid] = "Conservador"
        idx += 1

    # Embaralha os assentos para variedade posicional
    local_rng = rng if rng is not None else random.Random()
    local_rng.shuffle(players)

    return players, agents, profile_labels


def detect_hand_bluffs(
    table: Table,
    actions_log: List[Dict[str, Any]],
    profile_labels: Dict[str, str],
    winners: List[str],
) -> List[Dict[str, Any]]:
    """Identifica apostas com características de blefe durante a mão."""
    bluffs_found: List[Dict[str, Any]] = []

    # Analisa ações de aposta/raise
    for act in actions_log:
        if act["action_type"] in ("BET", "RAISE") and act["amount"] > 0:
            pid = act["player_id"]
            player = next((p for p in table.players if p.player_id == pid), None)
            if not player or not player.hole_cards:
                continue

            # Avalia força da mão no momento
            from src.engine.hand_eval import evaluate_hand

            all_player_cards = list(player.hole_cards) + list(table.community_cards)
            if len(all_player_cards) >= 5:
                score = evaluate_hand(all_player_cards)
                is_weak = score.hand_rank.value <= 2  # Carta Alta ou Um Par fraco
                hand_desc = score.description
            else:
                c1, c2 = player.hole_cards[0], player.hole_cards[1]
                is_pair = c1.rank.value == c2.rank.value
                high_val = max(c1.rank.value, c2.rank.value)
                is_weak = not is_pair and high_val < 11
                hand_desc = f"Pré-flop: {c1.rank.symbol}{c2.rank.symbol}"

            # Se apostou com mão fraca
            if is_weak and act["amount"] >= table._big_blind * 2:
                won_hand = pid in winners
                is_pure_bluff = won_hand and len(table.community_cards) < 5
                bluff_type = (
                    "Blefe Bem-Sucedido" if won_hand else "Tentativa de Blefe"
                )
                bluffs_found.append({
                    "player_id": pid,
                    "player_name": act["player_name"],
                    "profile": profile_labels.get(pid, "Desconhecido"),
                    "street": act["street"],
                    "amount": act["amount"],
                    "bluff_type": bluff_type,
                    "is_pure_bluff": is_pure_bluff,
                    "hand_rank": hand_desc,
                })

    return bluffs_found


def run_recording_batch(
    auth_code: str,
    num_hands: int = 10,
    num_players: int = 6,
    starting_stack: int = 1000,
    small_blind: int = 10,
    big_blind: int = 20,
    rng_seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Executa a simulação e gravação em lote de rodadas autenticadas."""
    if not verify_auth_code(auth_code):
        return {
            "success": False,
            "error": "Código de autenticação inválido. Acesso negado à gravação.",
        }

    num_hands = max(1, min(100, int(num_hands)))
    num_players = 9 if num_players == 9 else 6

    rng = random.Random(rng_seed)
    players, agents, profile_labels = build_research_roster(
        num_players=num_players,
        starting_stack=starting_stack,
        rng=rng,
    )

    hands_recorded: List[Dict[str, Any]] = []
    neon_saved_count = 0
    file_saved_count = 0
    total_bluffs_detected = 0

    wins_by_profile: Dict[str, int] = {
        "Matemático": 0,
        "Agressivo": 0,
        "Conservador": 0,
    }

    button_idx = 0

    for hand_idx in range(1, num_hands + 1):
        # Filtra jogadores com fichas para jogar a mão
        active_players = [p for p in players if p.stack > 0]
        if len(active_players) < 2:
            # Recarrega stacks se a maioria foi eliminada
            for p in players:
                p.stack = starting_stack
            active_players = players

        stacks_before = {p.player_id: p.stack for p in active_players}

        table = Table(
            players=active_players,
            small_blind=small_blind,
            big_blind=big_blind,
            rng=rng,
            button_idx=button_idx,
        )
        table.start_new_hand(rng=rng)

        actions_log: List[Dict[str, Any]] = []

        # Executa as ações até a conclusão da mão
        while table.street not in (Street.FINISHED, Street.SHOWDOWN):
            actor = table.current_player
            if actor is None:
                break

            bot = agents[actor.player_id]
            action = bot.decide_action(table)

            pot_before = table.pot_manager.total_pot
            actions_log.append({
                "street": table.street.name,
                "player_id": actor.player_id,
                "player_name": actor.name,
                "profile": profile_labels.get(actor.player_id, ""),
                "action_type": action.action_type.value,
                "amount": action.amount,
                "pot_before": pot_before,
            })

            table.apply_action(action)

        # Determina vencedores e distribuição a partir das propriedades nativas da mesa
        button_idx = table.button_idx
        payouts = table.last_payouts
        scores = table.last_scores

        winners_data: List[Dict[str, Any]] = []
        winning_names: List[str] = []
        winning_ids: List[str] = []

        for p in table.players:
            if payouts.get(p.player_id, 0) > 0:
                winning_ids.append(p.player_id)
                winning_names.append(p.name)
                comb_name = (
                    scores[p.player_id].description
                    if p.player_id in scores
                    else "Desistência dos adversários"
                )
                winners_data.append({
                    "player_id": p.player_id,
                    "name": p.name,
                    "payout": payouts[p.player_id],
                    "combination": comb_name,
                })

        # Se por algum motivo payouts estiver vazio, fallback
        if not winners_data:
            active_p = [p for p in table.players if p.is_active]
            if active_p:
                w = active_p[0]
                winning_ids.append(w.player_id)
                winning_names.append(w.name)
                winners_data.append({
                    "player_id": w.player_id,
                    "name": w.name,
                    "payout": table.pot_manager.total_pot,
                    "combination": "Desistência",
                })

        # Atualiza métricas por perfil
        for wid in winning_ids:
            prof = profile_labels.get(wid, "Desconhecido")
            if prof in wins_by_profile:
                wins_by_profile[prof] += 1

        # Detecção de blefes
        bluffs = detect_hand_bluffs(table, actions_log, profile_labels, winning_ids)
        total_bluffs_detected += len(bluffs)

        # Monta o registro completo da mão
        hand_record: Dict[str, Any] = {
            "hand_index": hand_idx,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pot_total": table.pot_manager.total_pot,
            "community_cards": [str(c) for c in table.community_cards],
            "winners": winners_data,
            "bluffs_count": len(bluffs),
            "bluffs_detected": bluffs,
            "players": [
                {
                    "player_id": p.player_id,
                    "name": p.name,
                    "profile": profile_labels.get(p.player_id, ""),
                    "hole_cards": (
                        [str(c) for c in p.hole_cards] if p.hole_cards else []
                    ),
                    "stack_before": stacks_before.get(p.player_id, starting_stack),
                    "stack_after": p.stack,
                    "net_profit": (
                        p.stack - stacks_before.get(p.player_id, starting_stack)
                    ),
                }
                for p in active_players
            ],
            "actions": actions_log,
        }

        # Gravação dupla (Arquivo Seguro + Neon)
        if save_hand_to_file(hand_record):
            file_saved_count += 1
        if save_hand_to_neon(hand_record):
            neon_saved_count += 1

        hands_recorded.append({
            "hand_index": hand_idx,
            "pot": table.pot_manager.total_pot,
            "winners": ", ".join(winning_names),
            "bluffs": len(bluffs),
            "board": " ".join(str(c) for c in table.community_cards),
        })

    return {
        "success": True,
        "auth_verified": True,
        "hands_requested": num_hands,
        "hands_completed": len(hands_recorded),
        "file_saved_count": file_saved_count,
        "file_path": str(RECORD_FILE.name),
        "neon_saved_count": neon_saved_count,
        "neon_connected": neon_saved_count > 0,
        "total_bluffs_detected": total_bluffs_detected,
        "wins_by_profile": wins_by_profile,
        "hands_summary": hands_recorded,
    }
