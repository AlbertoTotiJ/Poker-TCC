"""Módulo de autenticação, gravação dupla (arquivo + Neon) e simulação de rodadas."""

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
from typing import Any, Dict, List, Optional, Tuple

from src.agents.heuristic import AgentProfile, HeuristicAgent
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
    try:
        import psycopg2

        conn = psycopg2.connect(db_url, connect_timeout=8)
        return (conn, None)
    except ImportError:
        return (
            None,
            (
                "Driver psycopg2 não está disponível no runtime. Certifique-se de "
                "que psycopg2-binary está listado no requirements.txt."
            ),
        )
    except Exception as ex:
        return (None, f"Falha ao conectar no Neon: {str(ex)}")


def get_neon_connection(custom_url: Optional[str] = None):
    """Tenta obter uma conexão com o banco Neon PostgreSQL se configurado."""
    conn, _ = get_neon_connection_with_diag(custom_url=custom_url)
    return conn


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


def save_hand_to_neon(
    hand_data: Dict[str, Any], custom_url: Optional[str] = None
) -> bool:
    """Salva os dados de uma mão no banco de dados Neon."""
    conn = get_neon_connection(custom_url=custom_url)
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
        target_file = get_record_file()
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, "a", encoding="utf-8") as f:
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

    count_each = num_players // 3
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
            if prof in wins_by_profile:
                wins_by_profile[prof] += 1

        bluffs = detect_hand_bluffs(table, actions_log, profile_labels, winning_ids)
        total_bluffs_detected += len(bluffs)

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
) -> Dict[str, Any]:
    """Salva todas as partidas do arquivo de dataset no banco de dados Neon."""
    if not verify_auth_code(auth_code):
        return {"success": False, "error": "Código de autenticação inválido."}

    target_file = get_record_file()
    actual_file = target_file if target_file.exists() else RECORD_FILE
    if not actual_file.exists():
        return {
            "success": False,
            "error": "Nenhum arquivo de partidas gravadas encontrado.",
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

    try:
        ensure_neon_schema(conn)
        saved_count = 0
        with open(actual_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                hand_data = json.loads(line)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO hands (
                            hand_index, pot_total, community_cards,
                            winners, bluffs_detected, hand_details
                        ) VALUES (%s, %s, %s, %s, %s, %s);
                        """,
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
        conn.close()
        return {
            "success": True,
            "message": f"{saved_count} mãos gravadas com sucesso no banco Neon!",
            "hands_saved": saved_count,
        }
    except Exception as ex:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": f"Erro ao gravar no Neon: {str(ex)}"}
