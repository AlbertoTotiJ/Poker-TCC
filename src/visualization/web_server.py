"""Servidor HTTP e API REST para a interface gráfica web de Texas Hold'em."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import random
import socket
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from src.agents.heuristic import AgentProfile, HeuristicAgent
from src.engine.deck import Card, Suit
from src.engine.player import Player
from src.engine.table import Action, ActionType, Street, Table
from src.visualization.backend_view import (
    format_hand_combination,
    get_position_label,
)

_WEB_DIR = Path(__file__).resolve().parent / "web"

_BOT_PRESETS: List[Tuple[str, AgentProfile]] = [
    ("Bot Alpha (Agressivo)", AgentProfile.AGGRESSIVE),
    ("Bot Beta (Conservador)", AgentProfile.CONSERVATIVE),
    ("Bot Gamma (Equilibrado)", AgentProfile.BALANCED),
    ("Bot Delta (Agressivo)", AgentProfile.AGGRESSIVE),
    ("Bot Epsilon (Conservador)", AgentProfile.CONSERVATIVE),
    ("Bot Zeta (Equilibrado)", AgentProfile.BALANCED),
    ("Bot Eta (Agressivo)", AgentProfile.AGGRESSIVE),
    ("Bot Theta (Equilibrado)", AgentProfile.BALANCED),
]


def card_to_dict(card: Optional[Card]) -> Optional[Dict[str, Any]]:
    """Serializa uma instância de Card em formato compatível com JSON."""
    if card is None:
        return None
    is_red = card.suit in (Suit.HEARTS, Suit.DIAMONDS)
    rank_display = "10" if card.rank.symbol == "T" else card.rank.symbol
    return {
        "rank": rank_display,
        "suit": card.suit.value,
        "color": "red" if is_red else "black",
        "text": f"{rank_display}{card.suit.value}",
    }


class WebPokerSession:
    """Controlador de estado e transições da partida para consumo via API web."""

    def __init__(
        self,
        num_players: int = 4,
        starting_stack: int = 1000,
        small_blind: int = 10,
        big_blind: int = 20,
        human_name: str = "Você (Humano)",
        rng: Optional[random.Random] = None,
    ) -> None:
        if not (2 <= num_players <= 9):
            raise ValueError("Quantidade de jogadores deve estar entre 2 e 9.")

        self.human_id: str = "p_human"
        self.starting_stack: int = starting_stack
        self.small_blind: int = small_blind
        self.big_blind: int = big_blind
        self.rng: random.Random = rng if rng is not None else random.Random()

        self.players: List[Player] = [
            Player(player_id=self.human_id, name=human_name, stack=starting_stack)
        ]
        self.bot_agents: Dict[str, HeuristicAgent] = {}

        for i in range(num_players - 1):
            bot_id = f"p_bot_{i + 1}"
            bot_name, bot_profile = _BOT_PRESETS[i % len(_BOT_PRESETS)]
            self.players.append(
                Player(player_id=bot_id, name=bot_name, stack=starting_stack)
            )
            self.bot_agents[bot_id] = HeuristicAgent(
                player_id=bot_id,
                name=bot_name,
                profile=bot_profile,
                rng=random.Random(self.rng.randint(1, 1000000)),
            )

        self.hand_number: int = 0
        self.event_log: List[str] = []
        self._button_idx: int = 0
        self.player_last_actions: Dict[str, str] = {}
        self.table: Optional[Table] = None

        self.start_next_hand()

    def start_next_hand(self) -> None:
        """Configura a mesa e distribui cartas para o início de uma nova mão."""
        active_survivors = [p for p in self.players if p.stack > 0]
        if len(active_survivors) < 2:
            return

        self.hand_number += 1
        self.player_last_actions.clear()
        self.event_log.clear()

        self.table = Table(
            players=active_survivors,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            rng=self.rng,
            button_idx=self._button_idx,
        )
        self.table.start_new_hand(rng=self.rng)
        self.event_log.append(f"Mão #{self.hand_number} iniciada. Blinds postados.")

    def step_bot(self) -> Optional[str]:
        """Avança o turno de um bot se a ação atual pertencer a uma máquina."""
        if self.table is None:
            return None

        if self.table.street in (Street.FINISHED, Street.SHOWDOWN):
            return None

        current = self.table.current_player
        if current is None or current.player_id == self.human_id:
            return None

        bot = self.bot_agents.get(current.player_id)
        if bot is None:
            return None

        action = bot.decide_action(self.table)
        action_desc = self._record_and_apply_action(current, action)
        return action_desc

    def apply_human_action(self, action_type_str: str, amount: int = 0) -> str:
        """Executa a ação comandada pelo usuário humano."""
        if self.table is None:
            raise RuntimeError("Nenhuma mesa ativa no momento.")

        current = self.table.current_player
        if current is None or current.player_id != self.human_id:
            raise ValueError("Não é a vez do jogador humano.")

        act_type = ActionType(action_type_str.upper())
        action = Action(
            player_id=self.human_id,
            action_type=act_type,
            amount=amount,
        )
        return self._record_and_apply_action(current, action)

    def _record_and_apply_action(self, actor: Player, action: Action) -> str:
        """Processa a ação de aposta, gera texto de feedback e atualiza a mesa."""
        assert self.table is not None
        act_type = action.action_type

        if act_type == ActionType.FOLD:
            desc = "FOLD"
            log_msg = f"{actor.name} desistiu (FOLD)."
        elif act_type == ActionType.CHECK:
            desc = "CHECK"
            log_msg = f"{actor.name} deu CHECK."
        elif act_type == ActionType.CALL:
            gap = self.table.current_highest_bet - actor.current_bet
            desc = f"CALL {gap}"
            log_msg = f"{actor.name} pagou {gap} fichas (CALL)."
        elif act_type == ActionType.BET:
            desc = f"BET {action.amount}"
            log_msg = f"{actor.name} apostou {action.amount} fichas (BET)."
        elif act_type == ActionType.RAISE:
            desc = f"RAISE {action.amount}"
            log_msg = f"{actor.name} aumentou para {action.amount} fichas (RAISE)."
        elif act_type == ActionType.ALL_IN:
            desc = f"ALL-IN {actor.stack}"
            log_msg = f"{actor.name} foi ALL-IN ({actor.stack} fichas)!"
        else:
            desc = act_type.value
            log_msg = f"{actor.name} agiu com {desc}."

        self.player_last_actions[actor.player_id] = desc
        self.event_log.append(log_msg)
        self.table.apply_action(action)

        if self.table.street == Street.FINISHED:
            self._button_idx = self.table.button_idx

        return desc

    def get_serialized_state(self) -> Dict[str, Any]:
        """Gera o snapshot estruturado do estado da mesa para a interface."""
        if self.table is None:
            return {"active": False}

        t = self.table
        is_finished = t.street in (Street.FINISHED, Street.SHOWDOWN)
        current = t.current_player

        comm_cards = [card_to_dict(c) for c in t.community_cards]

        players_data = []
        active_ids = {p.player_id for p in t.players}

        for idx, p in enumerate(self.players):
            is_at_table = p.player_id in active_ids
            pos_label = ""
            if is_at_table:
                table_idx = next(
                    i for i, tp in enumerate(t.players) if tp.player_id == p.player_id
                )
                pos_label = get_position_label(table_idx, t.button_idx, len(t.players))

            is_human = p.player_id == self.human_id
            reveal = is_human or is_finished

            hole_cards_data = None
            if p.hole_cards is not None:
                if reveal:
                    hole_cards_data = [
                        card_to_dict(p.hole_cards[0]),
                        card_to_dict(p.hole_cards[1]),
                    ]
                else:
                    hole_cards_data = [{"hidden": True}, {"hidden": True}]

            is_turn = current is not None and current.player_id == p.player_id

            players_data.append(
                {
                    "id": p.player_id,
                    "name": p.name,
                    "stack": p.stack,
                    "current_bet": p.current_bet,
                    "is_active": p.is_active and is_at_table,
                    "is_all_in": p.is_all_in,
                    "is_eliminated": p.stack == 0,
                    "is_human": is_human,
                    "position": pos_label.strip(),
                    "hole_cards": hole_cards_data,
                    "last_action": self.player_last_actions.get(p.player_id, ""),
                    "is_turn": is_turn,
                }
            )

        legal_actions_data = []
        to_call = 0
        min_raise_amount = 0
        max_raise_amount = 0

        human_obj = next(p for p in self.players if p.player_id == self.human_id)

        if current is not None and current.player_id == self.human_id:
            to_call = t.current_highest_bet - human_obj.current_bet
            for act_type in t.get_legal_actions(self.human_id):
                legal_actions_data.append(act_type.value)

            min_raise_amount = t.current_highest_bet + t.min_raise
            max_raise_amount = human_obj.current_bet + human_obj.stack

        showdown_data = None
        if is_finished:
            payouts_list = []
            for pid, amt in t.last_payouts.items():
                p = next(p for p in self.players if p.player_id == pid)
                payouts_list.append({"name": p.name, "amount": amt})

            scores_list = []
            for pid, score in t.last_scores.items():
                p = next(p for p in self.players if p.player_id == pid)
                comb = format_hand_combination(score)
                best = [card_to_dict(c) for c in score.cards]
                scores_list.append(
                    {"name": p.name, "combination": comb, "best_cards": best}
                )

            winner_names = [item["name"] for item in payouts_list if item["amount"] > 0]
            showdown_data = {
                "payouts": payouts_list,
                "scores": scores_list,
                "winner_names": winner_names,
            }

        survivors = [p for p in self.players if p.stack > 0]
        champion = survivors[0].name if len(survivors) == 1 else None

        return {
            "active": True,
            "hand_number": self.hand_number,
            "street": t.street.name,
            "pot_total": t.pot_manager.total_pot,
            "current_highest_bet": t.current_highest_bet,
            "min_raise": t.min_raise,
            "community_cards": comm_cards,
            "players": players_data,
            "current_player_id": current.player_id if current else None,
            "is_human_turn": current is not None and current.player_id == self.human_id,
            "legal_actions": legal_actions_data,
            "to_call": to_call,
            "min_raise_amount": min_raise_amount,
            "max_raise_amount": max_raise_amount,
            "event_log": self.event_log[-8:],
            "is_hand_finished": is_finished,
            "showdown": showdown_data,
            "champion": champion,
        }


_WEB_DIR = Path(__file__).resolve().parent / "web"
_PUBLIC_DIR = Path(__file__).resolve().parent.parent.parent / "public"
_SESSIONS: Dict[str, WebPokerSession] = {}
_DEFAULT_SESSION_ID = "default_session"


def get_html_path() -> Path:
    """Retorna o caminho do arquivo index.html em public/ ou web/."""
    pub_index = _PUBLIC_DIR / "index.html"
    if pub_index.exists():
        return pub_index
    return _WEB_DIR / "index.html"


class PokerApiHandler(BaseHTTPRequestHandler):
    """Tratador de requisições HTTP para a aplicação web e Vercel Serverless."""

    session: Optional[WebPokerSession] = None

    def log_message(self, format: str, *args: Any) -> None:
        """Suprime logs padrão de requisições no console para manter saída limpa."""
        return

    def _set_cors_headers(self) -> None:
        """Configura cabeçalhos de CORS para permitir requisições seguras."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Session-ID")

    def do_OPTIONS(self) -> None:
        """Responde a requisições de preflight CORS."""
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def _resolve_session(self, session_id: Optional[str] = None) -> WebPokerSession:
        """Obtém ou cria a sessão associada ao identificador."""
        sid = session_id or self.headers.get("X-Session-ID") or _DEFAULT_SESSION_ID
        if sid not in _SESSIONS:
            if PokerApiHandler.session is not None and sid == _DEFAULT_SESSION_ID:
                _SESSIONS[sid] = PokerApiHandler.session
            else:
                _SESSIONS[sid] = WebPokerSession()
        return _SESSIONS[sid]

    def do_GET(self) -> None:
        """Serve a interface gráfica HTML e retorna estado atual da API."""
        parsed = urlparse(self.path)
        clean_path = parsed.path.rstrip("/")

        if clean_path in ("", "/", "/index.html"):
            index_path = get_html_path()
            if not index_path.exists():
                self.send_error(404, "Arquivo index.html não encontrado.")
                return
            content = index_path.read_bytes()
            self.send_response(200)
            self._set_cors_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if clean_path.endswith("/state"):
            query_sid = None
            if parsed.query:
                params = dict(
                    qc.split("=", 1) for qc in parsed.query.split("&") if "=" in qc
                )
                query_sid = params.get("session_id")

            session = self._resolve_session(query_sid)
            state = session.get_serialized_state()
            self._send_json(state)
            return

        self.send_error(404, "Rota não encontrada.")

    def do_POST(self) -> None:
        """Processa comandos da partida (início, apostas e avanço de turnos)."""
        parsed = urlparse(self.path)
        clean_path = parsed.path.rstrip("/")

        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
        data = json.loads(body) if body else {}

        sid = (
            data.get("session_id")
            or self.headers.get("X-Session-ID")
            or _DEFAULT_SESSION_ID
        )

        if clean_path.endswith("/start_game"):
            num_players = int(data.get("num_players", 4))
            starting_stack = int(data.get("starting_stack", 1000))
            new_session = WebPokerSession(
                num_players=num_players,
                starting_stack=starting_stack,
            )
            _SESSIONS[sid] = new_session
            PokerApiHandler.session = new_session
            state = new_session.get_serialized_state()
            self._send_json({"success": True, "session_id": sid, "state": state})
            return

        session = self._resolve_session(sid)

        if clean_path.endswith("/action"):
            action_type = data.get("action_type", "")
            amount = int(data.get("amount", 0))
            try:
                desc = session.apply_human_action(action_type, amount)
                state = session.get_serialized_state()
                self._send_json({"success": True, "action": desc, "state": state})
            except Exception as ex:
                self._send_json({"success": False, "error": str(ex)})
            return

        if clean_path.endswith("/bot_step"):
            desc = session.step_bot()
            state = session.get_serialized_state()
            self._send_json(
                {"success": True, "action_performed": desc is not None, "state": state}
            )
            return

        if clean_path.endswith("/next_hand"):
            session.start_next_hand()
            state = session.get_serialized_state()
            self._send_json({"success": True, "state": state})
            return

        self.send_error(404, "Endpoint POST não encontrado.")

    def _send_json(self, payload: Dict[str, Any]) -> None:
        """Codifica e transmite payload JSON com cabeçalhos apropriados."""
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def find_free_port(start_port: int = 5000) -> int:
    """Busca a primeira porta TCP livre disponível a partir do número inicial."""
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def start_poker_web_server(
    port: Optional[int] = None,
    num_players: int = 4,
    starting_stack: int = 1000,
) -> Tuple[ThreadingHTTPServer, int]:
    """Inicializa e vincula o servidor web na porta disponível configurada."""
    chosen_port = port if port is not None else find_free_port(5000)
    server_address = ("127.0.0.1", chosen_port)

    PokerApiHandler.session = WebPokerSession(
        num_players=num_players,
        starting_stack=starting_stack,
    )

    httpd = ThreadingHTTPServer(server_address, PokerApiHandler)
    return httpd, chosen_port
