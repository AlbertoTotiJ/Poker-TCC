"""Módulo de autenticação, gravação dupla (arquivo + Neon) e simulação de rodadas."""

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
from typing import Any, Dict, List, Optional, Tuple

from src.agents.base import BaseAgent
from src.agents.bluffer_agent import BlufferAgent
from src.agents.heuristic import AgentProfile, HeuristicAgent
from src.agents.hybrid_agent import HybridAgent
from src.agents.mathematical_agent import MathematicalAgent
from src.engine.hand_eval import HandScore, evaluate_hand
from src.engine.player import Player
from src.engine.table import Street, Table

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RECORD_FILE = DATA_DIR / "partidas_gravadas.jsonl"
DEFAULT_AUTH_CODE = "TCC2026"


def get_record_file() -> Path:
    """Retorna o caminho seguro para o dataset com fallback para /tmp."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        test_file = DATA_DIR / ".write_test"
        test_file.touch()
        test_file.unlink(missing_ok=True)
        return RECORD_FILE
    except Exception:
        pass

    tmp_path = Path("/tmp/data/partidas_gravadas.jsonl")
    try:
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        return tmp_path
    except Exception:
        return RECORD_FILE


def get_auth_code() -> str:
    """Retorna o código de autenticação configurado ou o padrão TCC2026."""
    return os.environ.get("RESEARCH_ACCESS_CODE", DEFAULT_AUTH_CODE)


def verify_auth_code(code: str) -> bool:
    """Verifica se o código fornecido é válido."""
    if not code:
        return False
    expected = get_auth_code().strip()
    return code.strip() == expected


def _load_env_fallback() -> None:
    """Carrega variáveis do arquivo .env caso existam e não estejam no os.environ."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except Exception:
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


def _connect_via_pg8000(db_url: str) -> Any:
    """Estabelece conexão com PostgreSQL via driver puro em Python pg8000."""
    import ssl
    from urllib.parse import unquote, urlparse
    import pg8000.dbapi

    parsed = urlparse(db_url)
    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    database = unquote(parsed.path.lstrip("/") or "neondb")
    host = parsed.hostname or ""
    port = int(parsed.port or 5432)

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    return pg8000.dbapi.connect(
        user=username,
        password=password,
        host=host,
        port=port,
        database=database,
        ssl_context=ssl_context,
        timeout=8,
    )


def get_neon_connection_with_diag(
    custom_url: Optional[str] = None,
) -> Tuple[Any, Optional[str]]:
    """Tenta obter uma conexão com o Neon e retorna diagnóstico em falha."""
    _load_env_fallback()
    db_url = (
        custom_url
        or os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
    )
    if not db_url:
        return (
            None,
            (
                "DATABASE_URL não configurada no ambiente. Adicione a variável "
                "DATABASE_URL na Vercel ou informe a URL do Neon diretamente."
            ),
        )

    psycopg2_err: Optional[str] = None
    # 1. Tenta conectar via psycopg2
    try:
        import psycopg2

        conn = psycopg2.connect(db_url, connect_timeout=8)
        return (conn, None)
    except ImportError as ie:
        psycopg2_err = f"psycopg2 indisponível: {str(ie)}"
    except Exception as ex:
        psycopg2_err = f"psycopg2: {str(ex)}"

    # 2. Fallback resiliente via pg8000 (driver 100% Python puro para Serverless)
    try:
        conn = _connect_via_pg8000(db_url)
        return (conn, None)
    except ImportError as ie:
        pg8000_err = f"pg8000 indisponível: {str(ie)}"
    except Exception as ex:
        pg8000_err = f"pg8000: {str(ex)}"

    return (
        None,
        f"Falha de conexão com o Neon: [{psycopg2_err}] | [{pg8000_err}]",
    )


def get_neon_connection(custom_url: Optional[str] = None):
    """Tenta obter uma conexão com o banco Neon PostgreSQL se configurado."""
    conn, _ = get_neon_connection_with_diag(custom_url=custom_url)
    return conn


def ensure_neon_schema(conn) -> bool:
    """Garante que a estrutura de tabelas do Neon exista."""
    schema_matches = """
    CREATE TABLE IF NOT EXISTS matches (
        id SERIAL PRIMARY KEY,
        session_id VARCHAR(64),
        num_players INT,
        hands_played INT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """
    schema_hands = """
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
    cur = conn.cursor()
    try:
        cur.execute(schema_matches)
        cur.execute(schema_hands)
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            cur.close()
        except Exception:
            pass


def save_hand_to_neon(
    hand_data: Dict[str, Any], custom_url: Optional[str] = None
) -> bool:
    """Salva os dados de uma mão no banco de dados Neon."""
    conn = get_neon_connection(custom_url=custom_url)
    if conn is None:
        return False
    cur = conn.cursor()
    try:
        ensure_neon_schema(conn)
        insert_sql = """
        INSERT INTO hands (
            hand_index, pot_total, community_cards, winners,
            bluffs_detected, hand_details
        ) VALUES (%s, %s, CAST(%s AS jsonb), CAST(%s AS jsonb), %s, CAST(%s AS jsonb));
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
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


def save_hand_to_file(hand_data: Dict[str, Any]) -> bool:
    """Grava a mão em formato JSON Lines no arquivo separado de segurança."""
    try:
        target_file = get_record_file()
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(hand_data, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


ROSTER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "classic_6": {
        "name": "Clássica 6-Max",
        "description": "2 Matemáticos Reais, 2 Agressivos, 2 Conservadores",
        "num_players": 6,
    },
    "classic_9": {
        "name": "Mesa Cheia 9-Max",
        "description": "3 Matemáticos Reais, 3 Agressivos, 3 Conservadores",
        "num_players": 9,
    },
    "math_vs_bots": {
        "name": "Duelo: Matemáticos vs Bots",
        "description": (
            "3 Matemáticos Reais vs 3 Bots Heurísticos "
            "(1 Agressivo, 1 Conservador, 1 Equilibrado)"
        ),
        "num_players": 6,
    },
    "full_ai_tournament": {
        "name": "Torneio Completo de IAs",
        "description": "2 Matemáticos Reais, 2 Blefadores, 2 Híbridos",
        "num_players": 6,
    },
    "bluff_challenge": {
        "name": "Desafio de Blefe",
        "description": "2 Blefadores, 2 Matemáticos Reais, 2 Conservadores",
        "num_players": 6,
    },
    "hybrid_lab": {
        "name": "Laboratório Híbrido",
        "description": "3 Agentes Híbridos vs 3 Agentes Matemáticos Reais",
        "num_players": 6,
    },
    "math_tournament": {
        "name": "Torneio Puro de IA Matemática",
        "description": "6 Agentes Matemáticos Reais com calibrações variadas",
        "num_players": 6,
    },
    "all_models_9": {
        "name": "Grande Torneio Multimodelo 9-Max",
        "description": (
            "3 Matemáticos, 2 Blefadores, 2 Híbridos, 1 Agressivo, 1 Conservador"
        ),
        "num_players": 9,
    },
}


def build_research_roster(
    num_players: int = 6,
    starting_stack: int = 1000,
    roster_mode: str = "classic_6",
    rng: Optional[random.Random] = None,
) -> Tuple[List[Player], Dict[str, BaseAgent], Dict[str, str]]:
    """Gera o elenco balanceado de agentes para experimentos e gravação.

    Suporta os agentes atuais (Matemático Real, Bots Heurísticos) e os novos agentes
    táticos de pesquisa (Blefador e Híbrido).
    """
    local_rng = rng if rng is not None else random.Random()

    # Normalização de roster_mode
    if roster_mode not in ROSTER_CONFIGS:
        roster_mode = "classic_9" if num_players == 9 else "classic_6"

    expected_players = ROSTER_CONFIGS[roster_mode]["num_players"]
    if num_players not in (6, 9) or roster_mode not in ("classic_6", "classic_9"):
        num_players = expected_players

    players: List[Player] = []
    agents: Dict[str, BaseAgent] = {}
    profile_labels: Dict[str, str] = {}

    def _add_player(pid: str, name: str, agent: BaseAgent, profile: str) -> None:
        players.append(Player(player_id=pid, name=name, stack=starting_stack))
        agents[pid] = agent
        profile_labels[pid] = profile

    if roster_mode == "math_vs_bots":
        # 3 Matemáticos Reais vs 3 Bots (Agressivo, Conservador, Equilibrado)
        for i in range(1, 4):
            pid = f"bot_mat_{i}"
            pname = f"Matemático {i}"
            _add_player(
                pid,
                pname,
                MathematicalAgent(
                    player_id=pid,
                    name=pname,
                    num_simulations=100,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Matemático",
            )
        _add_player(
            "bot_agr_1",
            "Agressivo 1",
            HeuristicAgent(
                "bot_agr_1",
                "Agressivo 1",
                profile=AgentProfile.AGGRESSIVE,
                rng=random.Random(local_rng.randint(1, 1000000)),
            ),
            "Agressivo",
        )
        _add_player(
            "bot_con_1",
            "Conservador 1",
            HeuristicAgent(
                "bot_con_1",
                "Conservador 1",
                profile=AgentProfile.CONSERVATIVE,
                rng=random.Random(local_rng.randint(1, 1000000)),
            ),
            "Conservador",
        )
        _add_player(
            "bot_bal_1",
            "Equilibrado 1",
            HeuristicAgent(
                "bot_bal_1",
                "Equilibrado 1",
                profile=AgentProfile.BALANCED,
                rng=random.Random(local_rng.randint(1, 1000000)),
            ),
            "Equilibrado",
        )

    elif roster_mode == "full_ai_tournament":
        # 2 Matemáticos, 2 Blefadores, 2 Híbridos
        for i in range(1, 3):
            pid = f"bot_mat_{i}"
            pname = f"Matemático {i}"
            _add_player(
                pid,
                pname,
                MathematicalAgent(
                    player_id=pid,
                    name=pname,
                    num_simulations=100,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Matemático",
            )
        for i in range(1, 3):
            pid = f"bot_blf_{i}"
            pname = f"Blefador {i}"
            _add_player(
                pid,
                pname,
                BlufferAgent(
                    player_id=pid,
                    name=pname,
                    bluff_frequency=0.42,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Blefador",
            )
        for i in range(1, 3):
            pid = f"bot_hyb_{i}"
            pname = f"Híbrido {i}"
            _add_player(
                pid,
                pname,
                HybridAgent(
                    player_id=pid,
                    name=pname,
                    num_simulations=100,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Híbrido",
            )

    elif roster_mode == "bluff_challenge":
        # 2 Blefadores, 2 Matemáticos, 2 Conservadores
        for i in range(1, 3):
            pid = f"bot_blf_{i}"
            pname = f"Blefador {i}"
            _add_player(
                pid,
                pname,
                BlufferAgent(
                    player_id=pid,
                    name=pname,
                    bluff_frequency=0.45,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Blefador",
            )
        for i in range(1, 3):
            pid = f"bot_mat_{i}"
            pname = f"Matemático {i}"
            _add_player(
                pid,
                pname,
                MathematicalAgent(
                    player_id=pid,
                    name=pname,
                    num_simulations=100,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Matemático",
            )
        for i in range(1, 3):
            pid = f"bot_con_{i}"
            pname = f"Conservador {i}"
            _add_player(
                pid,
                pname,
                HeuristicAgent(
                    player_id=pid,
                    name=pname,
                    profile=AgentProfile.CONSERVATIVE,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Conservador",
            )

    elif roster_mode == "hybrid_lab":
        # 3 Híbridos vs 3 Matemáticos
        for i in range(1, 4):
            pid = f"bot_hyb_{i}"
            pname = f"Híbrido {i}"
            _add_player(
                pid,
                pname,
                HybridAgent(
                    player_id=pid,
                    name=pname,
                    num_simulations=100,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Híbrido",
            )
        for i in range(1, 4):
            pid = f"bot_mat_{i}"
            pname = f"Matemático {i}"
            _add_player(
                pid,
                pname,
                MathematicalAgent(
                    player_id=pid,
                    name=pname,
                    num_simulations=100,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Matemático",
            )

    elif roster_mode == "math_tournament":
        # 6 Matemáticos com limiares variados
        thresholds = [0.58, 0.60, 0.64, 0.67, 0.70, 0.73]
        for i, th in enumerate(thresholds, start=1):
            pid = f"bot_mat_{i}"
            pname = f"Matemático (Th {int(th * 100)}%)"
            _add_player(
                pid,
                pname,
                MathematicalAgent(
                    player_id=pid,
                    name=pname,
                    raise_equity_threshold=th,
                    num_simulations=100,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Matemático",
            )

    elif roster_mode == "all_models_9":
        # 3 Matemáticos, 2 Blefadores, 2 Híbridos, 1 Agressivo, 1 Conservador
        for i in range(1, 4):
            pid = f"bot_mat_{i}"
            pname = f"Matemático {i}"
            _add_player(
                pid,
                pname,
                MathematicalAgent(
                    player_id=pid,
                    name=pname,
                    num_simulations=100,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Matemático",
            )
        for i in range(1, 3):
            pid = f"bot_blf_{i}"
            pname = f"Blefador {i}"
            _add_player(
                pid,
                pname,
                BlufferAgent(
                    player_id=pid,
                    name=pname,
                    bluff_frequency=0.42,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Blefador",
            )
        for i in range(1, 3):
            pid = f"bot_hyb_{i}"
            pname = f"Híbrido {i}"
            _add_player(
                pid,
                pname,
                HybridAgent(
                    player_id=pid,
                    name=pname,
                    num_simulations=100,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Híbrido",
            )
        _add_player(
            "bot_agr_1",
            "Agressivo 1",
            HeuristicAgent(
                "bot_agr_1",
                "Agressivo 1",
                profile=AgentProfile.AGGRESSIVE,
                rng=random.Random(local_rng.randint(1, 1000000)),
            ),
            "Agressivo",
        )
        _add_player(
            "bot_con_1",
            "Conservador 1",
            HeuristicAgent(
                "bot_con_1",
                "Conservador 1",
                profile=AgentProfile.CONSERVATIVE,
                rng=random.Random(local_rng.randint(1, 1000000)),
            ),
            "Conservador",
        )

    else:
        # classic_6 ou classic_9
        count_each = num_players // 3
        for i in range(1, count_each + 1):
            pid = f"bot_mat_{i}"
            pname = f"Matemático {i}"
            _add_player(
                pid,
                pname,
                MathematicalAgent(
                    player_id=pid,
                    name=pname,
                    num_simulations=100,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Matemático",
            )
        for i in range(1, count_each + 1):
            pid = f"bot_agr_{i}"
            pname = f"Agressivo {i}"
            _add_player(
                pid,
                pname,
                HeuristicAgent(
                    player_id=pid,
                    name=pname,
                    profile=AgentProfile.AGGRESSIVE,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Agressivo",
            )
        for i in range(1, count_each + 1):
            pid = f"bot_con_{i}"
            pname = f"Conservador {i}"
            _add_player(
                pid,
                pname,
                HeuristicAgent(
                    player_id=pid,
                    name=pname,
                    profile=AgentProfile.CONSERVATIVE,
                    rng=random.Random(local_rng.randint(1, 1000000)),
                ),
                "Conservador",
            )

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

    for act in actions_log:
        if act["action_type"] in ("BET", "RAISE") and act["amount"] > 0:
            pid = act["player_id"]
            player = next((p for p in table.players if p.player_id == pid), None)
            if not player or not player.hole_cards:
                continue

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
    roster_mode: str = "classic_6",
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

    if roster_mode in ROSTER_CONFIGS:
        num_players = ROSTER_CONFIGS[roster_mode]["num_players"]
    else:
        num_players = 9 if num_players == 9 else 6
        roster_mode = "classic_9" if num_players == 9 else "classic_6"

    rng = random.Random(rng_seed)
    players, agents, profile_labels = build_research_roster(
        num_players=num_players,
        starting_stack=starting_stack,
        roster_mode=roster_mode,
        rng=rng,
    )

    hands_recorded: List[Dict[str, Any]] = []
    full_hand_records: List[Dict[str, Any]] = []
    neon_saved_count = 0
    file_saved_count = 0
    total_bluffs_detected = 0

    wins_by_profile: Dict[str, int] = {
        label: 0 for label in sorted(set(profile_labels.values()))
    }
    player_wins: Counter = Counter()

    best_score_overall: Optional[HandScore] = None
    best_score_details: Optional[Dict[str, Any]] = None

    button_idx = 0

    for hand_idx in range(1, num_hands + 1):
        active_players = [p for p in players if p.stack > 0]
        if len(active_players) < 2:
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

        button_idx = table.button_idx
        payouts = table.last_payouts
        scores = table.last_scores

        winners_data: List[Dict[str, Any]] = []
        winning_names: List[str] = []
        winning_ids: List[str] = []
        is_hand_split = False
        winning_comb_desc = "Desistência dos adversários"

        pot_awards = getattr(table, "last_pot_awards", [])
        if pot_awards:
            main_award = pot_awards[0]
            winning_ids = list(main_award.winning_player_ids)
            winning_names = [
                next(p.name for p in table.players if p.player_id == wid)
                for wid in winning_ids
            ]
            is_hand_split = main_award.is_split
            if main_award.winning_score:
                winning_comb_desc = main_award.winning_score.description
                if (
                    best_score_overall is None
                    or main_award.winning_score > best_score_overall
                ):
                    best_score_overall = main_award.winning_score
                    best_score_details = {
                        "combination": main_award.winning_score.description,
                        "player": winning_names[0] if winning_names else "N/A",
                        "profile": (
                            profile_labels.get(winning_ids[0], "")
                            if winning_ids
                            else ""
                        ),
                        "hand_index": hand_idx,
                    }
        else:
            for p in table.players:
                if payouts.get(p.player_id, 0) > 0:
                    winning_ids.append(p.player_id)
                    winning_names.append(p.name)

        for p in table.players:
            if payouts.get(p.player_id, 0) > 0:
                p_comb = (
                    scores[p.player_id].description
                    if p.player_id in scores
                    else "Desistência dos adversários"
                )
                winners_data.append({
                    "player_id": p.player_id,
                    "name": p.name,
                    "payout": payouts[p.player_id],
                    "combination": p_comb,
                    "is_main_winner": p.player_id in winning_ids,
                })

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
                    "is_main_winner": True,
                })

        for wid in winning_ids:
            player_wins[wid] += 1
            prof = profile_labels.get(wid, "Desconhecido")
            wins_by_profile[prof] = wins_by_profile.get(prof, 0) + 1

        bluffs = detect_hand_bluffs(table, actions_log, profile_labels, winning_ids)
        total_bluffs_detected += len(bluffs)

        hand_record: Dict[str, Any] = {
            "hand_index": hand_idx,
            "roster_mode": roster_mode,
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

        full_hand_records.append(hand_record)

        if save_hand_to_file(hand_record):
            file_saved_count += 1
        if save_hand_to_neon(hand_record):
            neon_saved_count += 1

        top_comb = (
            f"{winning_comb_desc} (Empate)"
            if is_hand_split
            else winning_comb_desc
        )
        hands_recorded.append({
            "hand_index": hand_idx,
            "pot": table.pot_manager.total_pot,
            "winners": ", ".join(winning_names),
            "combination": top_comb,
            "is_split": is_hand_split,
            "bluffs": len(bluffs),
            "board": " ".join(str(c) for c in table.community_cards),
        })

    leaderboard = [
        {
            "player_id": p.player_id,
            "name": p.name,
            "profile": profile_labels.get(p.player_id, ""),
            "final_stack": p.stack,
            "net_profit": p.stack - starting_stack,
            "wins": player_wins.get(p.player_id, 0),
        }
        for p in players
    ]
    leaderboard.sort(key=lambda x: x["final_stack"], reverse=True)
    champion = leaderboard[0] if leaderboard else None
    highest_pot = max((h["pot"] for h in hands_recorded), default=0)

    return {
        "success": True,
        "auth_verified": True,
        "roster_mode": roster_mode,
        "roster_name": ROSTER_CONFIGS.get(roster_mode, {}).get("name", roster_mode),
        "hands_requested": num_hands,
        "hands_completed": len(hands_recorded),
        "file_saved_count": file_saved_count,
        "file_path": str(RECORD_FILE.name),
        "neon_saved_count": neon_saved_count,
        "neon_connected": neon_saved_count > 0,
        "total_bluffs_detected": total_bluffs_detected,
        "highest_pot": highest_pot,
        "best_combination": best_score_details or {
            "combination": "Vitória por desistência dos adversários",
            "player": champion["name"] if champion else "N/A",
            "profile": champion["profile"] if champion else "N/A",
            "hand_index": "-",
        },
        "champion": champion,
        "leaderboard": leaderboard,
        "wins_by_profile": wins_by_profile,
        "hands_summary": hands_recorded,
        "full_records": full_hand_records,
    }


def _save_via_github_api(
    token: str,
    file_bytes: bytes,
    commit_message: str,
    repo: str = "AlbertoTotiJ/Poker-TCC",
    file_path: str = "data/partidas_gravadas.jsonl",
    branch: str = "main",
) -> Dict[str, Any]:
    """Envia o arquivo para o GitHub usando a API REST oficial."""
    import base64
    import json
    import urllib.error
    import urllib.request

    clean_token = token.strip()
    if clean_token.lower().startswith("bearer "):
        clean_token = clean_token[7:].strip()
    elif clean_token.lower().startswith("token "):
        clean_token = clean_token[6:].strip()

    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {clean_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Poker-TCC-App",
    }

    sha = None
    try:
        req_get = urllib.request.Request(
            f"{url}?ref={branch}", headers=headers, method="GET"
        )
        with urllib.request.urlopen(req_get, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            sha = data.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                msg = err_body.get("message", str(e))
            except Exception:
                msg = str(e)
            return {
                "success": False,
                "error": f"Erro de permissão no GitHub ({e.code}): {msg}",
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Falha ao consultar repositório no GitHub: {str(e)}",
        }

    content_b64 = base64.b64encode(file_bytes).decode("ascii")
    payload: Dict[str, Any] = {
        "message": commit_message,
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    req_data = json.dumps(payload).encode("utf-8")
    req_put = urllib.request.Request(
        url,
        data=req_data,
        headers={**headers, "Content-Type": "application/json"},
        method="PUT",
    )

    try:
        with urllib.request.urlopen(req_put, timeout=30) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
            commit_sha = resp_body.get("commit", {}).get("sha", "")[:7]
            return {
                "success": True,
                "message": "Dataset salvo e enviado com sucesso para o GitHub!",
                "details": f"Commit {commit_sha} na branch {branch} (via GitHub API).",
            }
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            msg = err_body.get("message", str(e))
        except Exception:
            msg = str(e)
        return {
            "success": False,
            "error": f"Falha ao gravar no GitHub via API ({e.code}): {msg}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Erro na requisição para GitHub: {str(e)}",
        }


def save_dataset_to_github(
    auth_code: str,
    commit_message: Optional[str] = None,
    github_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Salva o arquivo de dataset no Git/GitHub (via API REST ou via git CLI local)."""
    if not verify_auth_code(auth_code):
        return {"success": False, "error": "Código de autenticação inválido."}

    target_file = get_record_file()
    actual_file = target_file if target_file.exists() else RECORD_FILE
    if not actual_file.exists():
        return {
            "success": False,
            "error": "Nenhum arquivo de partidas gravadas encontrado para enviar.",
        }

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    msg = commit_message or (
        f"data: dataset de partidas gravadas do TCC ({now_str})"
    )
    token = (
        github_token
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GITHUB_PAT")
    )
    repo = os.environ.get("GITHUB_REPO", "AlbertoTotiJ/Poker-TCC")

    # 1. Se houver token, usa a API oficial do GitHub (compatível com Serverless)
    if token:
        try:
            file_bytes = actual_file.read_bytes()
            return _save_via_github_api(
                token=token,
                file_bytes=file_bytes,
                commit_message=msg,
                repo=repo,
            )
        except Exception as ex:
            return {
                "success": False,
                "error": f"Erro ao salvar via GitHub API: {str(ex)}",
            }

    # 2. Se não houver token, tenta utilizar o executável 'git' no host local
    import shutil

    if shutil.which("git"):
        import subprocess

        try:
            subprocess.run(
                ["git", "add", "-f", str(actual_file)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", msg], capture_output=True, text=True
            )

            push_proc = subprocess.run(
                ["git", "push", "origin", "main"],
                capture_output=True,
                text=True,
                timeout=35,
            )
            if push_proc.returncode == 0:
                return {
                    "success": True,
                    "message": "Dataset salvo e enviado com sucesso para o GitHub!",
                    "details": push_proc.stdout.strip()
                    or "Branch main atualizada.",
                }
            else:
                err_out = push_proc.stderr or push_proc.stdout
                return {
                    "success": False,
                    "error": f"Falha no git push: {err_out}",
                }
        except Exception as ex:
            return {
                "success": False,
                "error": f"Erro ao executar git local: {str(ex)}",
            }

    # 3. Caso esteja na Vercel (sem git local) e sem token configurado
    return {
        "success": False,
        "error": (
            "No ambiente da Vercel, o 'git' não está instalado. "
            "Configure a variável GITHUB_TOKEN no painel da Vercel "
            "ou utilize o botão 'Baixar Arquivo' para download do dataset (.jsonl)."
        ),
    }


def save_dataset_to_neon(
    auth_code: str,
    custom_db_url: Optional[str] = None,
    hands: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Salva partidas no banco Neon (a partir da lista fornecida ou do arquivo)."""
    if not verify_auth_code(auth_code):
        return {"success": False, "error": "Código de autenticação inválido."}

    hands_to_save: List[Dict[str, Any]] = []
    if hands and isinstance(hands, list) and len(hands) > 0:
        hands_to_save = hands
    else:
        target_file = get_record_file()
        actual_file = target_file if target_file.exists() else RECORD_FILE
        if actual_file.exists():
            with open(actual_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            hands_to_save.append(json.loads(line))
                        except Exception:
                            pass

    if not hands_to_save:
        return {
            "success": False,
            "error": (
                "Nenhuma partida encontrada para salvar. "
                "Simule as rodadas primeiro."
            ),
        }

    conn, diag_err = get_neon_connection_with_diag(custom_url=custom_db_url)
    if conn is None:
        return {
            "success": False,
            "error": (
                diag_err
                or "Não foi possível conectar ao Neon. Verifique DATABASE_URL."
            ),
        }

    cur = conn.cursor()
    try:
        ensure_neon_schema(conn)
        saved_count = 0
        insert_sql = """
        INSERT INTO hands (
            hand_index, pot_total, community_cards,
            winners, bluffs_detected, hand_details
        ) VALUES (%s, %s, CAST(%s AS jsonb), CAST(%s AS jsonb), %s, CAST(%s AS jsonb));
        """
        for hand_data in hands_to_save:
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
            saved_count += 1
        conn.commit()
        return {
            "success": True,
            "message": f"{saved_count} mãos gravadas com sucesso no banco Neon!",
            "hands_saved": saved_count,
        }
    except Exception as ex:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "error": f"Erro ao gravar no Neon: {str(ex)}"}
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass
