"""Servidor HTTP e API REST para a interface gráfica web de Texas Hold'em."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import random
import socket
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from src.agents.base import BaseAgent
from src.agents.bluffer_agent import BlufferAgent
from src.agents.gh_math_agent import GhMathAgent
from src.agents.heuristic import AgentProfile, HeuristicAgent
from src.agents.hybrid_agent import HybridAgent
from src.agents.mathematical_agent import MathematicalAgent
from src.engine.deck import Card, Suit
from src.engine.player import Player
from src.engine.table import Action, ActionType, Street, Table
from src.visualization.backend_view import (
    format_hand_combination,
    get_position_label,
)

_WEB_DIR = Path(__file__).resolve().parent / "web"

_BOT_PRESETS: List[Tuple[str, AgentProfile]] = [
    ("Matemático 1", AgentProfile.BALANCED),
    ("Agressivo 1", AgentProfile.AGGRESSIVE),
    ("Conservador 1", AgentProfile.CONSERVATIVE),
    ("Matemático 2", AgentProfile.BALANCED),
    ("Agressivo 2", AgentProfile.AGGRESSIVE),
    ("Conservador 2", AgentProfile.CONSERVATIVE),
    ("Matemático 3", AgentProfile.BALANCED),
    ("Agressivo 3", AgentProfile.AGGRESSIVE),
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
        agent_mode: str = "gh_math",
        custom_agents: Optional[List[str]] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        if not (2 <= num_players <= 9):
            raise ValueError("Quantidade de jogadores deve estar entre 2 e 9.")

        self.human_id: str = "p_human"
        self.starting_stack: int = starting_stack
        self.small_blind: int = small_blind
        self.big_blind: int = big_blind
        self.agent_mode: str = agent_mode
        self.rng: random.Random = rng if rng is not None else random.Random()

        self.players: List[Player] = [
            Player(player_id=self.human_id, name=human_name, stack=starting_stack)
        ]
        self.bot_agents: Dict[str, BaseAgent] = {}
        self.agent_types: Dict[str, str] = {self.human_id: "human"}

        for i in range(num_players - 1):
            bot_id = f"p_bot_{i + 1}"
            agent_type = "bot"
            if agent_mode == "gh_math":
                agent_type = "gh_math"
            elif agent_mode == "math":
                agent_type = "math"
            elif agent_mode == "mixed":
                agent_type = "math" if (i % 2 == 0) else "bot"
            elif agent_mode == "all_ai":
                ai_cycle = ["math", "bluffer", "hybrid"]
                agent_type = ai_cycle[i % len(ai_cycle)]
            elif agent_mode == "custom" and custom_agents and i < len(custom_agents):
                agent_type = custom_agents[i]

            if agent_type == "gh_math":
                bot_name = f"GhMath {i + 1} (GH)"
                bot = GhMathAgent(
                    player_id=bot_id,
                    name=bot_name,
                    base_threshold=0.58,
                    kelly_fraction_limit=0.25,
                    num_simulations=120,
                    rng=random.Random(self.rng.randint(1, 1000000)),
                )
            elif agent_type == "math":
                bot_name = f"Agente Matemático {i + 1}"
                bot: BaseAgent = MathematicalAgent(
                    player_id=bot_id,
                    name=bot_name,
                    raise_equity_threshold=0.65,
                    call_ev_margin=-0.02,
                    rng=random.Random(self.rng.randint(1, 1000000)),
                )
            elif agent_type == "bluffer":
                bot_name = f"Agente Blefador {i + 1}"
                bot = BlufferAgent(
                    player_id=bot_id,
                    name=bot_name,
                    bluff_frequency=0.45,
                    rng=random.Random(self.rng.randint(1, 1000000)),
                )
            elif agent_type == "hybrid":
                bot_name = f"Agente Híbrido {i + 1}"
                bot = HybridAgent(
                    player_id=bot_id,
                    name=bot_name,
                    math_threshold=0.60,
                    bluff_prob=0.25,
                    num_simulations=100,
                    rng=random.Random(self.rng.randint(1, 1000000)),
                )
            elif agent_type == "aggressive":
                bot_name = f"Agressivo {i + 1}"
                bot = HeuristicAgent(
                    player_id=bot_id,
                    name=bot_name,
                    profile=AgentProfile.AGGRESSIVE,
                    rng=random.Random(self.rng.randint(1, 1000000)),
                )
            elif agent_type == "conservative":
                bot_name = f"Conservador {i + 1}"
                bot = HeuristicAgent(
                    player_id=bot_id,
                    name=bot_name,
                    profile=AgentProfile.CONSERVATIVE,
                    rng=random.Random(self.rng.randint(1, 1000000)),
                )
            elif agent_type == "balanced":
                bot_name = f"Equilibrado {i + 1}"
                bot = HeuristicAgent(
                    player_id=bot_id,
                    name=bot_name,
                    profile=AgentProfile.BALANCED,
                    rng=random.Random(self.rng.randint(1, 1000000)),
                )
            else:
                bot_name, bot_profile = _BOT_PRESETS[i % len(_BOT_PRESETS)]
                bot = HeuristicAgent(
                    player_id=bot_id,
                    name=bot_name,
                    profile=bot_profile,
                    rng=random.Random(self.rng.randint(1, 1000000)),
                )

            self.players.append(
                Player(player_id=bot_id, name=bot_name, stack=starting_stack)
            )
            self.bot_agents[bot_id] = bot
            self.agent_types[bot_id] = agent_type

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
            self._log_hand_conclusion()

        return desc

    def _log_hand_conclusion(self) -> None:
        """Gera um registro detalhado do desfecho da mão para o log de eventos."""
        t = self.table
        if t is None or t.street != Street.FINISHED:
            return

        awards = getattr(t, "last_pot_awards", [])
        if not awards:
            return

        main_award = awards[0]
        win_names = [
            next((p.name for p in self.players if p.player_id == pid), pid)
            for pid in main_award.winning_player_ids
        ]

        if main_award.is_split:
            each_val = main_award.amount // max(1, len(win_names))
            comb_text = (
                main_award.winning_score.description
                if main_award.winning_score
                else "combinações equivalentes"
            )
            self.event_log.append(
                f"🤝 Empate no Showdown! Pote de {main_award.amount} fichas dividido "
                f"entre {', '.join(win_names)} ({each_val} para cada) com {comb_text}."
            )
        elif main_award.winning_score is not None:
            comb_text = main_award.winning_score.description
            winner = win_names[0] if win_names else "Alguém"
            self.event_log.append(
                f"🏆 {winner} venceu com {comb_text} e levou o pote de "
                f"{main_award.amount} fichas!"
            )
        else:
            winner = win_names[0] if win_names else "Alguém"
            self.event_log.append(
                f"🏆 {winner} venceu a mão por desistência dos adversários "
                f"({main_award.amount} fichas)."
            )

        for aw in awards[1:]:
            side_winners = [
                next((p.name for p in self.players if p.player_id == pid), pid)
                for pid in aw.winning_player_ids
            ]
            self.event_log.append(
                f"💰 Pote Paralelo ({aw.amount} fichas): levado por "
                f"{', '.join(side_winners)}."
            )

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

            agent_type = self.agent_types.get(
                p.player_id, "human" if is_human else "bot"
            )
            if is_human:
                agent_label = "Você (Humano)"
            elif agent_type == "gh_math":
                agent_label = "🧠 GhMathAgent (Gustavo)"
            elif agent_type == "math":
                agent_label = "📐 Agente Matemático"
            elif agent_type == "bluffer":
                agent_label = "🃏 Agente Blefador"
            elif agent_type == "hybrid":
                agent_label = "🧠 Agente Híbrido"
            elif agent_type == "aggressive":
                agent_label = "⚔️ Agressivo"
            elif agent_type == "conservative":
                agent_label = "🛡️ Conservador"
            elif agent_type == "balanced":
                agent_label = "⚖️ Equilibrado"
            else:
                agent_label = "🤖 Bot Padrão"

            players_data.append(
                {
                    "id": p.player_id,
                    "name": p.name,
                    "agent_type": agent_type,
                    "agent_label": agent_label,
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
                p = next((p for p in self.players if p.player_id == pid), None)
                if p:
                    payouts_list.append(
                        {"name": p.name, "amount": amt, "player_id": pid}
                    )

            # Scores ordenados pelo HandScore de forma decrescente (melhor mão no topo)
            sorted_scores = sorted(
                t.last_scores.items(), key=lambda item: item[1], reverse=True
            )
            scores_list = []
            for pid, score in sorted_scores:
                p = next((p for p in self.players if p.player_id == pid), None)
                if p:
                    comb = format_hand_combination(score)
                    best = [card_to_dict(c) for c in score.cards]
                    scores_list.append(
                        {
                            "name": p.name,
                            "player_id": pid,
                            "combination": comb,
                            "full_description": score.description,
                            "best_cards": best,
                        }
                    )

            awards_data = []
            is_true_tie = False
            main_winning_names: List[str] = []
            main_winning_comb = ""

            for aw in getattr(t, "last_pot_awards", []):
                win_names = [
                    next((p.name for p in self.players if p.player_id == pid), pid)
                    for pid in aw.winning_player_ids
                ]
                comb_str = (
                    format_hand_combination(aw.winning_score)
                    if aw.winning_score
                    else "Desistência"
                )
                if aw.pot_index == 0:
                    main_winning_names = win_names
                    main_winning_comb = comb_str
                    if aw.is_split:
                        is_true_tie = True

                awards_data.append(
                    {
                        "pot_index": aw.pot_index,
                        "pot_type": aw.pot_type,
                        "amount": aw.amount,
                        "winners": win_names,
                        "combination": comb_str,
                        "is_split": aw.is_split,
                        "payouts": {
                            next(
                                (p.name for p in self.players if p.player_id == k), k
                            ): v
                            for k, v in aw.payouts.items()
                        },
                    }
                )

            winner_names = main_winning_names or [
                item["name"] for item in payouts_list if item["amount"] > 0
            ]
            winning_comb = main_winning_comb or (
                scores_list[0]["combination"] if scores_list else "Desistência"
            )

            if is_true_tie:
                each_amt = (
                    awards_data[0]["amount"] // max(1, len(main_winning_names))
                    if awards_data
                    else 0
                )
                summary_msg = (
                    f"🤝 Empate (Split Pot)! {', '.join(main_winning_names)} dividiram "
                    f"o pote ({each_amt} fichas cada) com {winning_comb}!"
                )
            elif scores_list:
                w_name = winner_names[0] if winner_names else "Vencedor"
                summary_msg = f"🏆 Vitória de {w_name} com {winning_comb}!"
            else:
                w_name = winner_names[0] if winner_names else "Vencedor"
                summary_msg = f"🏆 Vitória de {w_name} por desistência dos adversários!"

            showdown_data = {
                "payouts": payouts_list,
                "scores": scores_list,
                "winner_names": winner_names,
                "winning_combination": winning_comb,
                "is_split_pot": is_true_tie,
                "summary_message": summary_msg,
                "pot_awards": awards_data,
            }

        survivors = [p for p in self.players if p.stack > 0]
        champion = survivors[0].name if len(survivors) == 1 else None

        return {
            "active": True,
            "agent_mode": self.agent_mode,
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

    def send_error(
        self,
        code: int,
        message: Optional[str] = None,
        explain: Optional[str] = None,
    ) -> None:
        """Emite respostas de erro exclusivamente em JSON padronizado."""
        err_msg = message or f"Erro HTTP {code}"
        self.send_response(code)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        payload = json.dumps(
            {"success": False, "error": err_msg, "status_code": code}
        ).encode("utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

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

    def _resolve_clean_path(
        self, parsed, data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Determina a rota inspecionando URL, query, proxy e payload."""
        if data and isinstance(data, dict):
            ep = data.get("endpoint") or data.get("action")
            if ep and isinstance(ep, str):
                return f"/{ep.lstrip('/')}".rstrip("/")

        for hdr in (
            "x-forwarded-uri",
            "x-matched-path",
            "x-invoke-path",
            "x-original-uri",
            "x-now-route-matches",
        ):
            val = self.headers.get(hdr)
            if val:
                if hdr == "x-now-route-matches" and "=" in val:
                    val = val.split("=")[-1]
                uri_path = urlparse(val).path.rstrip("/")
                if (
                    uri_path
                    and not uri_path.endswith("/index.py")
                    and not uri_path.endswith("/index")
                ):
                    return uri_path

        if parsed.query:
            params = dict(
                qc.split("=", 1) for qc in parsed.query.split("&") if "=" in qc
            )
            for qk in ("__route__", "endpoint", "route"):
                if qk in params and params[qk]:
                    r_val = params[qk].lstrip("/")
                    if not r_val.endswith(".py"):
                        return f"/{r_val}".rstrip("/")

        raw_path = parsed.path.rstrip("/")
        if raw_path.endswith(".py"):
            raw_path = raw_path[:-3]
        return raw_path

    def do_GET(self) -> None:
        """Serve a interface gráfica HTML e retorna estado atual da API."""
        try:
            parsed = urlparse(self.path)
            clean_path = self._resolve_clean_path(parsed)

            if clean_path in ("", "/", "/index.html", "/index"):
                index_path = get_html_path()
                if not index_path.exists():
                    self.send_error(404, "Arquivo index.html não encontrado.")
                    return
                content = index_path.read_bytes()
                self.send_response(200)
                self._set_cors_headers()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header(
                    "Cache-Control", "no-cache, no-store, must-revalidate, max-age=0"
                )
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

            if clean_path.endswith("/favicon.ico") or clean_path == "/favicon.ico":
                self.send_response(204)
                self._set_cors_headers()
                self.end_headers()
                return

            if (
                clean_path in ("/api", "/api/health", "/health", "/api/health.py")
                or clean_path.endswith("/health")
            ):
                self._send_json(
                    {
                        "status": "ok",
                        "service": "poker-tcc",
                        "message": "Texas Hold'em Poker API online",
                    }
                )
                return

            if clean_path.endswith("/state") or clean_path == "/state":
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

            if clean_path.endswith("/check_db") or clean_path == "/check_db":
                import os
                import shutil
                from src.database.recorder import (
                    RECORD_FILE,
                    get_neon_connection_with_diag,
                    get_record_file,
                )
                conn, neon_diag = get_neon_connection_with_diag()
                neon_ok = conn is not None
                neon_hands_count = 0
                neon_columns = []
                neon_sample = []
                if conn:
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT COUNT(*) FROM hands;")
                        row = cur.fetchone()
                        if row:
                            neon_hands_count = int(row[0])
                        cur.execute(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_name = 'hands';"
                        )
                        neon_columns = [r[0] for r in cur.fetchall()]
                        cur.execute(
                            "SELECT id, pot_total, created_at FROM hands "
                            "ORDER BY id DESC LIMIT 2;"
                        )
                        for r in cur.fetchall():
                            neon_sample.append({
                                "id": r[0],
                                "pot_total": r[1],
                                "created_at": str(r[2]),
                            })
                        cur.close()
                    except Exception as ex:
                        neon_diag = f"Erro na inspeção: {str(ex)}"
                    finally:
                        try:
                            conn.close()
                        except Exception:
                            pass
                rec_file = get_record_file()
                target_file = rec_file if rec_file.exists() else RECORD_FILE
                total_hands = 0
                if target_file.exists():
                    try:
                        with open(target_file, "r", encoding="utf-8") as f:
                            total_hands = sum(1 for line in f if line.strip())
                    except Exception:
                        pass
                has_github_token = bool(
                    os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PAT")
                )
                neon_host = ""
                neon_db = ""
                raw_db_url = (
                    os.environ.get("DATABASE_URL")
                    or os.environ.get("POSTGRES_URL")
                    or ""
                )
                if raw_db_url:
                    try:
                        p_url = urlparse(raw_db_url)
                        neon_host = p_url.hostname or ""
                        neon_db = p_url.path.lstrip("/") or ""
                    except Exception:
                        pass

                self._send_json({
                    "success": True,
                    "neon_connected": neon_ok,
                    "neon_diag": neon_diag,
                    "neon_hands_count": neon_hands_count,
                    "neon_columns": neon_columns,
                    "neon_sample": neon_sample,
                    "neon_host": neon_host,
                    "neon_database": neon_db,
                    "database_url_configured": bool(raw_db_url),
                    "github_token_configured": has_github_token,
                    "git_cli_available": shutil.which("git") is not None,
                    "file_exists": target_file.exists(),
                    "total_hands_recorded": total_hands,
                    "file_name": target_file.name,
                })
                return

            if (
                clean_path.endswith("/download_dataset")
                or clean_path == "/download_dataset"
            ):
                from src.database.recorder import RECORD_FILE, get_record_file
                rec_file = get_record_file()
                target_file = rec_file if rec_file.exists() else RECORD_FILE
                if not target_file.exists():
                    self.send_error(
                        404, "Nenhum arquivo de partidas gravadas encontrado."
                    )
                    return
                content = target_file.read_bytes()
                self.send_response(200)
                self._set_cors_headers()
                self.send_header(
                    "Content-Type", "application/x-jsonlines; charset=utf-8"
                )
                self.send_header(
                    "Content-Disposition",
                    'attachment; filename="partidas_gravadas.jsonl"',
                )
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

            self.send_error(404, f"Rota GET não encontrada: {clean_path}")
        except Exception as ex:
            self._send_json(
                {"success": False, "error": f"Erro interno do servidor: {str(ex)}"}
            )

    def do_POST(self) -> None:
        """Processa comandos da partida (início, apostas e avanço de turnos)."""
        try:
            parsed = urlparse(self.path)
            try:
                content_len = int(self.headers.get("Content-Length", 0) or 0)
            except (ValueError, TypeError):
                content_len = 0
            body = (
                self.rfile.read(content_len).decode("utf-8")
                if content_len > 0
                else "{}"
            )
            try:
                data = json.loads(body) if body else {}
            except Exception:
                data = {}

            clean_path = self._resolve_clean_path(parsed, data=data)

            sid = (
                data.get("session_id")
                or self.headers.get("X-Session-ID")
                or _DEFAULT_SESSION_ID
            )

            if (
                clean_path.endswith("/record_batch")
                or clean_path == "/record_batch"
            ):
                from src.database.recorder import run_recording_batch
                auth_code = str(data.get("auth_code", ""))
                num_hands = int(data.get("num_hands", 10))
                num_players = int(data.get("num_players", 6))
                roster_mode = str(data.get("roster_mode", "")).strip()
                result = run_recording_batch(
                    auth_code=auth_code,
                    num_hands=num_hands,
                    num_players=num_players,
                    roster_mode=roster_mode or (
                        "classic_9" if num_players == 9 else "classic_6"
                    ),
                )
                self._send_json(result)
                return

            if (
                clean_path.endswith("/save_to_github")
                or clean_path == "/save_to_github"
            ):
                from src.database.recorder import save_dataset_to_github
                auth_code = str(data.get("auth_code", ""))
                commit_msg = data.get("commit_message")
                token = data.get("github_token")
                result = save_dataset_to_github(
                    auth_code=auth_code,
                    commit_message=commit_msg,
                    github_token=token,
                )
                self._send_json(result)
                return

            if clean_path.endswith("/save_to_neon") or clean_path == "/save_to_neon":
                from src.database.recorder import save_dataset_to_neon
                auth_code = str(data.get("auth_code", ""))
                custom_url = data.get("database_url")
                hands = data.get("hands")
                result = save_dataset_to_neon(
                    auth_code=auth_code,
                    custom_db_url=custom_url,
                    hands=hands,
                )
                self._send_json(result)
                return

            if clean_path.endswith("/start_game") or clean_path == "/start_game":
                num_players = int(data.get("num_players", 4))
                starting_stack = int(data.get("starting_stack", 1000))
                agent_mode = str(data.get("agent_mode", "bots"))
                custom_agents = data.get("custom_agents", None)
                new_session = WebPokerSession(
                    num_players=num_players,
                    starting_stack=starting_stack,
                    agent_mode=agent_mode,
                    custom_agents=custom_agents,
                )
                _SESSIONS[sid] = new_session
                PokerApiHandler.session = new_session
                state = new_session.get_serialized_state()
                self._send_json({"success": True, "session_id": sid, "state": state})
                return

            session = self._resolve_session(sid)

            if clean_path.endswith("/action") or clean_path == "/action":
                action_type = data.get("action_type", "")
                amount = int(data.get("amount", 0))
                try:
                    desc = session.apply_human_action(action_type, amount)
                    state = session.get_serialized_state()
                    self._send_json({"success": True, "action": desc, "state": state})
                except Exception as ex:
                    self._send_json({"success": False, "error": str(ex)})
                return

            if clean_path.endswith("/bot_step") or clean_path == "/bot_step":
                desc = session.step_bot()
                state = session.get_serialized_state()
                self._send_json(
                    {
                        "success": True,
                        "action_performed": desc is not None,
                        "state": state,
                    }
                )
                return

            if clean_path.endswith("/next_hand") or clean_path == "/next_hand":
                session.start_next_hand()
                state = session.get_serialized_state()
                self._send_json({"success": True, "state": state})
                return

            self.send_error(404, f"Endpoint POST não encontrado: {clean_path}")
        except Exception as ex:
            self._send_json(
                {"success": False, "error": f"Erro interno do servidor: {str(ex)}"}
            )

    def _send_json(self, payload: Dict[str, Any]) -> None:
        """Codifica e transmite payload JSON com cabeçalhos apropriados."""
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def find_free_port(start_port: int = 5000, host: str = "0.0.0.0") -> int:
    """Busca a primeira porta TCP livre disponível a partir do número inicial."""
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    return start_port


def start_poker_web_server(
    host: str = "0.0.0.0",
    port: Optional[int] = None,
    num_players: int = 4,
    starting_stack: int = 1000,
    agent_mode: str = "bots",
) -> Tuple[ThreadingHTTPServer, int]:
    """Inicializa e vincula o servidor web na porta disponível configurada."""
    chosen_port = port if port is not None else find_free_port(5000, host=host)
    server_address = (host, chosen_port)

    PokerApiHandler.session = WebPokerSession(
        num_players=num_players,
        starting_stack=starting_stack,
        agent_mode=agent_mode,
    )

    httpd = ThreadingHTTPServer(server_address, PokerApiHandler)
    return httpd, chosen_port


if __name__ == "__main__":
    import webbrowser

    httpd, port = start_poker_web_server(host="0.0.0.0", port=5000)
    print("=" * 72)
    print(" MESA GRÁFICA VIRTUAL DE TEXAS HOLD'EM INICIADA! ".center(72, "="))
    print("=" * 72)
    print(f" > Acesso Local (este computador): http://localhost:{port}")
    print(" Pressione Ctrl+C a qualquer momento para encerrar.")
    print("=" * 72)
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuário.")
        httpd.server_close()
