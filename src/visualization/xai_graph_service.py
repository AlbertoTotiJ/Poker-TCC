"""Serviço de Geração de Grafos Interativos para Explicabilidade de IA (XAI).

Suporta duas perspectivas complementares:
1. Visão MACRO (Trilha da Vitória):
   Mapeia o fluxo completo de uma mão de poker (Pré-Flop -> Flop -> Turn -> River -> Showdown),
   destacando as ações físicas, pontos de desistência (folds), tentativas de blefe e a rota
   vitoriosa contínua até a conquista do pote.

2. Visão MICRO (Rede Neural de Tomada de Decisão):
   Representa a tomada de decisão individual como um grafo de 3 camadas:
   - Camada 1 (Percepção/Entrada): Cartas privadas, textura do bordo, Pot Odds, tamanho do pote e posição.
   - Camada 2 (Ponderação Cognitiva): Equidade calculada, outs, fold equity percebida, modo de decisão e XAI textual.
   - Camada 3 (Saída/Veredito): Ação executada, classificação do blefe, reação do adversário e saldo financeiro.
"""

from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.database.recorder import get_neon_connection
from src.engine.deck import Card, Rank, Suit
from src.engine.table import Street
from src.agents.gh_bluffer_agent import GhBlufferAgent

_XAI_AGENT: Optional[GhBlufferAgent] = None


def _get_xai_agent() -> GhBlufferAgent:
    """Retorna instância singleton do motor analítico do GhBlufferAgent."""
    global _XAI_AGENT
    if _XAI_AGENT is None:
        _XAI_AGENT = GhBlufferAgent(player_id="xai_telemetry_engine")
    return _XAI_AGENT


def parse_cards_str(card_str: Any) -> List[Card]:
    """Converte representações textuais de cartas em instâncias do motor Card."""
    if not card_str or str(card_str).strip() in (
        "",
        "None",
        "Desconhecido",
        "Sem cartas",
        "Oculta",
        "Ocultas",
    ):
        return []

    suit_map = {
        "♥": Suit.HEARTS,
        "♦": Suit.DIAMONDS,
        "♣": Suit.CLUBS,
        "♠": Suit.SPADES,
        "H": Suit.HEARTS,
        "D": Suit.DIAMONDS,
        "C": Suit.CLUBS,
        "S": Suit.SPADES,
        "h": Suit.HEARTS,
        "d": Suit.DIAMONDS,
        "c": Suit.CLUBS,
        "s": Suit.SPADES,
    }
    rank_map = {
        "2": Rank.TWO,
        "3": Rank.THREE,
        "4": Rank.FOUR,
        "5": Rank.FIVE,
        "6": Rank.SIX,
        "7": Rank.SEVEN,
        "8": Rank.EIGHT,
        "9": Rank.NINE,
        "10": Rank.TEN,
        "T": Rank.TEN,
        "t": Rank.TEN,
        "J": Rank.JACK,
        "j": Rank.JACK,
        "Q": Rank.QUEEN,
        "q": Rank.QUEEN,
        "K": Rank.KING,
        "k": Rank.KING,
        "A": Rank.ACE,
        "a": Rank.ACE,
    }

    tokens = (
        str(card_str).replace("[", "").replace("]", "").replace(",", " ").split()
    )
    cards: List[Card] = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        r_part = (
            token[:-1]
            if len(token) >= 2 and token[-1] in suit_map
            else token[0]
        )
        s_part = (
            token[-1]
            if len(token) >= 2 and token[-1] in suit_map
            else (token[1:] if len(token) > 1 else "")
        )
        if token.upper().startswith("10") and len(token) >= 3:
            r_part = "10"
            s_part = token[2:]
        rank = rank_map.get(r_part.upper())
        suit = suit_map.get(s_part)
        if rank and suit:
            cards.append(Card(rank, suit))
    return cards


def analyze_advanced_xai(
    hole_str: str,
    board_str: str,
    street_str: str,
    pot_before: int,
    amount: int,
    action_type: str,
    raw_equity: float,
    pot_odds: float,
    db_ev: float = 0.0,
    is_bluff: bool = False,
) -> Dict[str, Any]:
    """Calcula os pilares do Estado da Arte em XAI: Textura do Bordo, Blockers, Fold Equity e Matriz Contrafactual."""
    agent = _get_xai_agent()
    hole_cards = parse_cards_str(hole_str)
    board_cards = parse_cards_str(board_str)

    st_upper = (street_str or "FLOP").upper()
    st_enum = Street.PREFLOP
    if st_upper == "FLOP":
        st_enum = Street.FLOP
    elif st_upper == "TURN":
        st_enum = Street.TURN
    elif st_upper == "RIVER":
        st_enum = Street.RIVER

    is_dry, is_wet, has_scare = agent.analyze_board_texture(board_cards)
    blocker_score = agent.evaluate_blockers(hole_cards, board_cards)
    fold_equity = agent.estimate_fold_equity(
        num_opponents=1,
        is_dry=is_dry,
        has_scare=has_scare,
        street=st_enum,
        pot_size=pot_before,
        bet_size=amount,
    )

    if not board_cards:
        texture_name = "PRÉ-FLOP"
        texture_label = "Mesa Limpa"
        texture_desc = "Fase inicial: equidade baseada na força das cartas privadas e blockers de roubo de blinds."
    elif is_wet:
        texture_name = "WET (Dinâmico)"
        scare_txt = " + Scare Cards" if has_scare else ""
        texture_label = f"Conectado{scare_txt}"
        texture_desc = "Bordo molhado e coordenado. Favorece semi-blefes com draws e blockers de flush/straight."
    elif is_dry:
        texture_name = "DRY (Seco)"
        scare_txt = " + Scare Cards" if has_scare else ""
        texture_label = f"Desconexo{scare_txt}"
        texture_desc = "Bordo seco e desconexo. Dificulta mãos feitas no adversário, aumentando a eficiência de C-Bets de blefe."
    else:
        texture_name = "NEUTRO"
        texture_label = "Moderado"
        texture_desc = "Bordo com textura intermediária e conectividade média."

    if blocker_score >= 0.45:
        blocker_label = f"🔥 Alto ({blocker_score:.2f})"
        blocker_desc = "Remove combos críticos do oponente (ex: Nut Flush ou Trinca máxima)."
    elif blocker_score >= 0.20:
        blocker_label = f"🛡️ Moderado ({blocker_score:.2f})"
        blocker_desc = "Reduz chances do adversário possuir Top Pair ou conectores fortes."
    else:
        blocker_label = f"Neutro ({blocker_score:.2f})"
        blocker_desc = "Remoção residual ou insignificante de cartas do range oponente."

    # Matriz Contrafactual (Contraste de Decisão)
    bb = 20
    bet_amt = amount if amount > 0 else int(pot_before * 0.5) or bb
    ev_fold = 0.0
    ev_check = round((raw_equity * pot_before) / bb, 2)
    called_ev_chips = (raw_equity * (pot_before + bet_amt)) - ((1.0 - raw_equity) * bet_amt)
    bet_ev_chips = (fold_equity * pot_before) + ((1.0 - fold_equity) * called_ev_chips)
    ev_bet = round(bet_ev_chips / bb, 2)
    if db_ev != 0.0 and action_type in ("BET", "RAISE"):
        ev_bet = round(db_ev, 2)

    act_norm = (action_type or "CHECK").upper()
    options: List[Dict[str, Any]] = []
    if act_norm in ("BET", "RAISE"):
        chosen_ev = ev_bet
        options.append({
            "action": f"{act_norm} {amount if amount > 0 else ''}".strip(),
            "ev": ev_bet,
            "status": "CHOSEN",
            "color": "#10b981",
        })
        options.append({
            "action": "CHECK (Passivo)",
            "ev": ev_check,
            "status": "REJECTED",
            "color": "#ef4444" if ev_check < ev_bet else "#64748b",
        })
        options.append({
            "action": "FOLD (Desistência)",
            "ev": ev_fold,
            "status": "REJECTED",
            "color": "#64748b",
        })
        delta = round(ev_bet - ev_check, 2)
        contrast = f"A IA escolheu {act_norm} ({ev_bet:+.2f} BB) superando CHECK ({ev_check:+.2f} BB) em {delta:+.2f} BB por alavancar {fold_equity*100:.0f}% de Fold Equity."
    elif act_norm == "CHECK":
        chosen_ev = ev_check
        options.append({
            "action": "CHECK",
            "ev": ev_check,
            "status": "CHOSEN",
            "color": "#10b981",
        })
        options.append({
            "action": f"BET {bet_amt}",
            "ev": ev_bet,
            "status": "REJECTED",
            "color": "#ef4444" if ev_bet < ev_check else "#64748b",
        })
        options.append({
            "action": "FOLD",
            "ev": ev_fold,
            "status": "REJECTED",
            "color": "#64748b",
        })
        delta = round(ev_check - ev_bet, 2)
        contrast = f"A IA escolheu CHECK ({ev_check:+.2f} BB) para controle de pote sem inflar riscos (supera aposta em {delta:+.2f} BB)."
    elif act_norm == "CALL":
        to_call = int(pot_before * pot_odds / (1.0 - pot_odds)) if (0 < pot_odds < 1.0) else bb
        call_ev_chips = (raw_equity * (pot_before + to_call)) - ((1.0 - raw_equity) * to_call)
        ev_call = round(call_ev_chips / bb, 2)
        chosen_ev = ev_call
        options.append({
            "action": f"CALL {amount if amount > 0 else ''}".strip(),
            "ev": ev_call,
            "status": "CHOSEN",
            "color": "#10b981",
        })
        options.append({
            "action": f"RAISE {bet_amt * 2}",
            "ev": ev_bet,
            "status": "REJECTED",
            "color": "#64748b",
        })
        options.append({
            "action": "FOLD",
            "ev": ev_fold,
            "status": "REJECTED",
            "color": "#ef4444" if ev_fold < ev_call else "#64748b",
        })
        delta = round(ev_call - ev_fold, 2)
        contrast = f"A IA escolheu CALL ({ev_call:+.2f} BB) porque a equidade ({raw_equity*100:.1f}%) cobre as Pot Odds ({pot_odds*100:.1f}%), superando FOLD em {delta:+.2f} BB."
    else:  # FOLD
        chosen_ev = ev_fold
        ev_call_neg = round(-pot_before * 0.15 / bb, 2)
        options.append({
            "action": "FOLD",
            "ev": ev_fold,
            "status": "CHOSEN",
            "color": "#10b981",
        })
        options.append({
            "action": "CALL",
            "ev": ev_call_neg,
            "status": "REJECTED",
            "color": "#ef4444",
        })
        delta = round(ev_fold - ev_call_neg, 2)
        contrast = f"A IA escolheu FOLD ({ev_fold:+.2f} BB) porque continuar teria expectativa matemática negativa ({ev_call_neg:+.2f} BB)."

    ev_delta = round(options[0]["ev"] - options[1]["ev"], 2) if len(options) > 1 else 0.0

    return {
        "board_texture": {
            "type": texture_name,
            "label": texture_label,
            "is_dry": is_dry,
            "is_wet": is_wet,
            "has_scare": has_scare,
            "description": texture_desc,
        },
        "blocker": {
            "score": round(blocker_score, 2),
            "label": blocker_label,
            "description": blocker_desc,
        },
        "fold_equity": {
            "value": round(fold_equity, 3),
            "percent": round(fold_equity * 100, 1),
            "label": f"{fold_equity * 100:.1f}%",
        },
        "counterfactuals": {
            "chosen_action": act_norm,
            "chosen_ev": chosen_ev,
            "options": options,
            "rationale_contrast": contrast,
            "ev_delta": ev_delta,
        },
    }


def _serialize_val(val: Any) -> Any:
    """Serializa tipos não-JSON nativos como Decimal e Path."""
    if isinstance(val, Decimal):
        return float(val)
    return val


def get_available_hands_for_xai(
    only_bluffs: bool = False,
    limit: int = 50,
    custom_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Retorna a lista de mãos disponíveis com resumos executivos para seleção no frontend."""
    conn = get_neon_connection(custom_url=custom_url)
    if conn is None:
        # Fallback local se o Neon estiver indisponível
        return _get_local_fallback_hands(only_bluffs=only_bluffs, limit=limit)

    cur = conn.cursor()
    try:
        # Query agregada sobre game_actions e decision_telemetry_and_bluffs
        bluff_filter = "HAVING bool_or(t.is_bluff = TRUE)" if only_bluffs else ""
        query = f"""
        SELECT 
            a.hand_id,
            MAX(a.pot_after) as total_pot,
            COUNT(a.action_id) as total_actions,
            COALESCE(bool_or(t.is_bluff = TRUE), FALSE) as has_bluff,
            COUNT(CASE WHEN t.is_bluff = TRUE THEN 1 END) as bluff_count,
            STRING_AGG(DISTINCT t.bluff_type, ', ') FILTER (WHERE t.is_bluff = TRUE) as bluff_types,
            STRING_AGG(DISTINCT a.player_name, ', ') as players,
            (
                SELECT t_sub.player_name 
                FROM decision_telemetry_and_bluffs t_sub 
                WHERE t_sub.hand_id = a.hand_id AND t_sub.hand_result IN ('WON_HAND', 'SPLIT_POT') 
                LIMIT 1
            ) as winner_name,
            (
                SELECT t_sub.profile 
                FROM decision_telemetry_and_bluffs t_sub 
                WHERE t_sub.hand_id = a.hand_id AND t_sub.hand_result IN ('WON_HAND', 'SPLIT_POT') 
                LIMIT 1
            ) as winner_profile
        FROM game_actions a
        LEFT JOIN decision_telemetry_and_bluffs t ON a.action_id = t.action_id
        GROUP BY a.hand_id
        {bluff_filter}
        ORDER BY a.hand_id DESC
        LIMIT %s;
        """
        cur.execute(query, (limit,))
        cols = [desc[0] for desc in cur.description]
        hands_list = []
        for row in cur.fetchall():
            item = dict(zip(cols, row))
            item = {k: _serialize_val(v) for k, v in item.items()}
            hands_list.append(item)

        return {
            "success": True,
            "source": "neon_database",
            "count": len(hands_list),
            "hands": hands_list,
        }
    except Exception as e:
        return _get_local_fallback_hands(only_bluffs=only_bluffs, limit=limit, error_msg=str(e))
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


def build_macro_graph(hand_id: int, custom_url: Optional[str] = None) -> Dict[str, Any]:
    """Constrói os nós e arestas para a Visão MACRO (Trilha da Vitória) da mão especificada."""
    conn = get_neon_connection(custom_url=custom_url)
    actions: List[Dict[str, Any]] = []

    if conn is not None:
        cur = conn.cursor()
        try:
            query = """
            SELECT 
                a.action_id, a.hand_id, a.step_order, a.street, a.player_id, a.player_name,
                a.profile, a.hole_cards, a.community_cards, a.action_type, a.amount,
                a.pot_before, a.pot_after, a.player_stack_before, a.player_stack_after,
                COALESCE(t.decision_mode, 'STANDARD') as decision_mode,
                COALESCE(t.raw_equity, 0.0) as raw_equity,
                COALESCE(t.pot_odds, 0.0) as pot_odds,
                COALESCE(t.expected_value, 0.0) as expected_value,
                COALESCE(t.outs_count, 0) as outs_count,
                COALESCE(t.tactical_reason, '') as tactical_reason,
                COALESCE(t.is_bluff, FALSE) as is_bluff,
                COALESCE(t.bluff_type, 'NONE') as bluff_type,
                COALESCE(t.opponent_response, 'NOT_APPLICABLE') as opponent_response,
                COALESCE(t.bluff_outcome, 'NOT_APPLICABLE') as bluff_outcome,
                COALESCE(t.net_bluff_chips, 0) as net_bluff_chips,
                COALESCE(t.hand_result, 'UNKNOWN') as hand_result
            FROM game_actions a
            LEFT JOIN decision_telemetry_and_bluffs t ON a.action_id = t.action_id
            WHERE a.hand_id = %s
            ORDER BY a.step_order ASC;
            """
            cur.execute(query, (hand_id,))
            cols = [desc[0] for desc in cur.description]
            for row in cur.fetchall():
                act = dict(zip(cols, row))
                act = {k: _serialize_val(v) for k, v in act.items()}
                actions.append(act)
        except Exception:
            actions = []
        finally:
            try:
                cur.close()
                conn.close()
            except Exception:
                pass

    if not actions:
        actions = _load_local_fallback_actions(hand_id)

    if not actions:
        return {
            "success": False,
            "error": f"Nenhuma ação encontrada para a mão {hand_id}.",
            "nodes": [],
            "edges": [],
        }

    # Identificar o vencedor da mão
    winner_name = "Desconhecido"
    winner_profile = "Indefinido"
    winner_id = ""
    for a in actions:
        if a.get("hand_result") in ("WON_HAND", "SPLIT_POT"):
            winner_name = a.get("player_name", "")
            winner_profile = a.get("profile", "")
            winner_id = a.get("player_id", "")
            break

    # Se não foi explicitamente marcado, o vencedor é o último jogador a não dar fold
    if not winner_id:
        active_players = {a["player_id"]: a["player_name"] for a in actions if a["action_type"] != "FOLD"}
        if len(active_players) == 1:
            winner_id, winner_name = list(active_players.items())[0]

    max_pot = max([a.get("pot_after", 0) for a in actions] or [0])
    streets_seen: List[str] = []
    for a in actions:
        st = a.get("street", "PREFLOP")
        if st not in streets_seen:
            streets_seen.append(st)

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    # 1. Nó Raiz: Mão de Poker
    hand_node_id = f"hand_{hand_id}"
    nodes.append({
        "id": hand_node_id,
        "label": f"♠️ MÃO #{hand_id}\nPote Final: {max_pot} fichas",
        "title": f"Mão #{hand_id} • Vencedor: {winner_name} ({winner_profile})",
        "shape": "box",
        "color": {
            "background": "#1e293b",
            "border": "#38bdf8",
            "highlight": {"background": "#0f172a", "border": "#7dd3fc"},
        },
        "font": {"color": "#f8fafc", "size": 16, "face": "monospace", "bold": True},
        "borderWidth": 2,
        "margin": 12,
        "level": 0,
        "customData": {
            "type": "hand_root",
            "hand_id": hand_id,
            "total_pot": max_pot,
            "winner_name": winner_name,
            "winner_profile": winner_profile,
        },
    })

    # 2. Nós das Streets (Fases da rodada)
    street_node_ids: Dict[str, str] = {}
    street_levels = {"PREFLOP": 1, "FLOP": 3, "TURN": 5, "RIVER": 7, "SHOWDOWN": 9}

    for idx, st in enumerate(streets_seen):
        st_id = f"street_{hand_id}_{st}"
        street_node_ids[st] = st_id
        lvl = street_levels.get(st, idx * 2 + 1)

        # Obter cartas comunitárias desta street se houver
        comm_cards = ""
        for a in actions:
            if a.get("street") == st and a.get("community_cards"):
                comm_cards = a.get("community_cards")
                break

        st_label = f"📍 {st}"
        if comm_cards:
            st_label += f"\n[{comm_cards}]"

        nodes.append({
            "id": st_id,
            "label": st_label,
            "title": f"Fase {st}" + (f" • Bordo: {comm_cards}" if comm_cards else ""),
            "shape": "ellipse",
            "color": {
                "background": "#334155",
                "border": "#94a3b8",
                "highlight": {"background": "#1e293b", "border": "#cbd5e1"},
            },
            "font": {"color": "#e2e8f0", "size": 13, "bold": True},
            "borderWidth": 2,
            "level": lvl,
            "customData": {"type": "street_node", "street": st, "community_cards": comm_cards},
        })

        # Aresta entre streets sucessivas
        if idx == 0:
            edges.append({
                "from": hand_node_id,
                "to": st_id,
                "label": "início",
                "color": {"color": "#64748b"},
                "arrows": "to",
                "width": 2,
            })
        else:
            prev_st = streets_seen[idx - 1]
            edges.append({
                "from": street_node_ids[prev_st],
                "to": st_id,
                "label": "avanço",
                "color": {"color": "#64748b"},
                "arrows": "to",
                "width": 2,
                "dashes": True,
            })

    # 3. Nós de Ações Físicas
    prev_action_by_player: Dict[str, str] = {}
    prev_action_overall: Optional[str] = None

    for a in actions:
        act_id = f"act_{a['action_id']}"
        st = a.get("street", "PREFLOP")
        player_name = a.get("player_name", "Bot")
        profile = a.get("profile", "")
        act_type = a.get("action_type", "CHECK")
        amount = a.get("amount", 0)
        is_bluff = a.get("is_bluff", False)
        bluff_type = a.get("bluff_type", "NONE")
        is_winner = (a.get("player_id") == winner_id) or (player_name == winner_name)

        # Montar rótulo do nó
        label_lines = [f"{player_name}"]
        if amount > 0:
            label_lines.append(f"{act_type} {amount}")
        else:
            label_lines.append(f"{act_type}")

        if is_bluff:
            label_lines.append(f"🎭 {bluff_type}")

        node_label = "\n".join(label_lines)

        # Cores e estilos do nó
        if is_bluff:
            bg_color = "#450a0a"
            border_color = "#ef4444"
            font_color = "#fecaca"
        elif act_type == "FOLD":
            bg_color = "#1f2937"
            border_color = "#6b7280"
            font_color = "#9ca3af"
        elif is_winner:
            bg_color = "#064e3b"
            border_color = "#10b981"
            font_color = "#a7f3d0"
        elif "Matemático" in profile:
            bg_color = "#172554"
            border_color = "#3b82f6"
            font_color = "#bfdbfe"
        elif "Híbrido" in profile:
            bg_color = "#14532d"
            border_color = "#22c55e"
            font_color = "#bbf7d0"
        elif "Blefador" in profile:
            bg_color = "#431407"
            border_color = "#f97316"
            font_color = "#fed7aa"
        else:
            bg_color = "#1e293b"
            border_color = "#64748b"
            font_color = "#f1f5f9"

        st_lvl = street_levels.get(st, 1)
        action_lvl = st_lvl + 1

        tooltip = (
            f"<b>{player_name}</b> ({profile})<br>"
            f"<b>Ação:</b> {act_type} {amount if amount > 0 else ''}<br>"
            f"<b>Cartas Privadas:</b> {a.get('hole_cards', 'Ocultas')}<br>"
            f"<b>Pote após:</b> {a.get('pot_after', 0)} fichas<br>"
            f"<b>Stack restante:</b> {a.get('player_stack_after', 0)} fichas<br>"
        )
        if a.get("tactical_reason"):
            tooltip += f"<b>XAI Motivo:</b> <i>{a.get('tactical_reason')}</i><br>"
        if is_bluff:
            tooltip += f"<b>Detecção de Blefe:</b> <span style='color:#f87171'>SIM ({bluff_type})</span><br>"

        adv = analyze_advanced_xai(
            hole_str=a.get("hole_cards", ""),
            board_str=a.get("community_cards", ""),
            street_str=st,
            pot_before=a.get("pot_before", 0),
            amount=amount,
            action_type=act_type,
            raw_equity=float(a.get("raw_equity", 0.0) or 0.0),
            pot_odds=float(a.get("pot_odds", 0.0) or 0.0),
            db_ev=float(a.get("expected_value", 0.0) or 0.0),
            is_bluff=is_bluff,
        )

        nodes.append({
            "id": act_id,
            "label": node_label,
            "title": tooltip,
            "shape": "box",
            "color": {
                "background": bg_color,
                "border": border_color,
                "highlight": {"background": "#020617", "border": "#38bdf8"},
            },
            "font": {"color": font_color, "size": 12, "face": "monospace"},
            "borderWidth": 2 if is_winner or is_bluff else 1,
            "level": action_lvl,
            "customData": {
                "type": "action_node",
                "action_id": a["action_id"],
                "hand_id": hand_id,
                "player_name": player_name,
                "profile": profile,
                "action_type": act_type,
                "amount": amount,
                "street": st,
                "is_bluff": is_bluff,
                "bluff_type": bluff_type,
                "is_winner": is_winner,
                "tactical_reason": a.get("tactical_reason", ""),
                "hole_cards": a.get("hole_cards", ""),
                "community_cards": a.get("community_cards", ""),
                "raw_equity": a.get("raw_equity", 0.0),
                "pot_odds": a.get("pot_odds", 0.0),
                "pot_before": a.get("pot_before", 0),
                "pot_after": a.get("pot_after", 0),
                "board_texture": adv["board_texture"],
                "blocker": adv["blocker"],
                "fold_equity": adv["fold_equity"],
                "counterfactuals": adv["counterfactuals"],
            },
        })

        # Conectar a street correspondente com a primeira ação
        st_node_id = street_node_ids.get(st)
        if st_node_id:
            edges.append({
                "from": st_node_id,
                "to": act_id,
                "label": f"#{a.get('step_order', 1)}",
                "color": {"color": "#475569"},
                "arrows": "to",
                "width": 1,
            })

        # Aresta cronológica sequencial da mão
        if prev_action_overall:
            edges.append({
                "from": prev_action_overall,
                "to": act_id,
                "color": {"color": "#334155"},
                "arrows": "to",
                "width": 1,
                "dashes": True,
            })

        # 🌟 Trilha da Vitória (Victory Path): Arestas douradas contínuas do vencedor!
        if is_winner and a["player_id"] in prev_action_by_player:
            prev_winner_act = prev_action_by_player[a["player_id"]]
            edges.append({
                "from": prev_winner_act,
                "to": act_id,
                "label": "👑 ROTA VITÓRIA",
                "color": {"color": "#fbbf24", "highlight": "#fef08a"},
                "arrows": "to",
                "width": 4,
                "smooth": {"type": "curvedCW", "roundness": 0.2},
            })

        prev_action_by_player[a["player_id"]] = act_id
        prev_action_overall = act_id

    # 4. Nó de Encerramento e Vitória (Pote Conquistado)
    winner_node_id = f"winner_{hand_id}"
    nodes.append({
        "id": winner_node_id,
        "label": f"🏆 VENCEDOR\n{winner_name}\n+{max_pot} fichas",
        "title": f"Vencedor da mão #{hand_id}: {winner_name} ({winner_profile})",
        "shape": "box",
        "color": {
            "background": "#064e3b",
            "border": "#34d399",
            "highlight": {"background": "#022c22", "border": "#6ee7b7"},
        },
        "font": {"color": "#ecfdf5", "size": 14, "bold": True},
        "borderWidth": 3,
        "level": 11,
        "customData": {
            "type": "winner_node",
            "winner_name": winner_name,
            "winner_profile": winner_profile,
            "pot_won": max_pot,
        },
    })

    # Conectar última ação do vencedor ao nó de Vitória
    if winner_id in prev_action_by_player:
        edges.append({
            "from": prev_action_by_player[winner_id],
            "to": winner_node_id,
            "label": "COLETA POTE",
            "color": {"color": "#fbbf24"},
            "arrows": "to",
            "width": 5,
        })
    elif prev_action_overall:
        edges.append({
            "from": prev_action_overall,
            "to": winner_node_id,
            "label": "POTE",
            "color": {"color": "#10b981"},
            "arrows": "to",
            "width": 3,
        })

    return {
        "success": True,
        "view": "macro",
        "hand_id": hand_id,
        "winner_name": winner_name,
        "winner_profile": winner_profile,
        "max_pot": max_pot,
        "total_actions": len(actions),
        "bluff_count": sum(1 for a in actions if a.get("is_bluff")),
        "nodes": nodes,
        "edges": edges,
        "actions": actions,
    }


def build_micro_graph(action_id: str, custom_url: Optional[str] = None) -> Dict[str, Any]:
    """Constrói o Grafo Cognitivo / Rede Neural em 3 camadas para uma decisão específica (Visão MICRO)."""
    conn = get_neon_connection(custom_url=custom_url)
    rec: Optional[Dict[str, Any]] = None

    if conn is not None:
        cur = conn.cursor()
        try:
            query = """
            SELECT 
                a.action_id, a.hand_id, a.step_order, a.street, a.player_id, a.player_name,
                a.profile, a.hole_cards, a.community_cards, a.action_type, a.amount,
                a.pot_before, a.pot_after, a.player_stack_before, a.player_stack_after,
                COALESCE(t.decision_mode, 'STANDARD') as decision_mode,
                COALESCE(t.raw_equity, 0.0) as raw_equity,
                COALESCE(t.pot_odds, 0.0) as pot_odds,
                COALESCE(t.expected_value, 0.0) as expected_value,
                COALESCE(t.outs_count, 0) as outs_count,
                COALESCE(t.tactical_reason, '') as tactical_reason,
                COALESCE(t.is_bluff, FALSE) as is_bluff,
                COALESCE(t.bluff_type, 'NONE') as bluff_type,
                COALESCE(t.opponent_response, 'NOT_APPLICABLE') as opponent_response,
                COALESCE(t.bluff_outcome, 'NOT_APPLICABLE') as bluff_outcome,
                COALESCE(t.net_bluff_chips, 0) as net_bluff_chips,
                COALESCE(t.hand_result, 'UNKNOWN') as hand_result,
                COALESCE(t.showdown_occurred, FALSE) as showdown_occurred
            FROM game_actions a
            LEFT JOIN decision_telemetry_and_bluffs t ON a.action_id = t.action_id
            WHERE a.action_id = %s
            LIMIT 1;
            """
            cur.execute(query, (action_id,))
            row = cur.fetchone()
            if row:
                cols = [desc[0] for desc in cur.description]
                rec = dict(zip(cols, row))
                rec = {k: _serialize_val(v) for k, v in rec.items()}
        except Exception:
            rec = None
        finally:
            try:
                cur.close()
                conn.close()
            except Exception:
                pass

    if rec is None:
        rec = _find_local_fallback_action(action_id)

    if not rec:
        return {
            "success": False,
            "error": f"Ação {action_id} não encontrada.",
            "nodes": [],
            "edges": [],
        }

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    # Extrair campos da decisão
    hand_id = rec.get("hand_id", 0)
    street = rec.get("street", "FLOP")
    player_name = rec.get("player_name", "Agente")
    profile = rec.get("profile", "")
    hole_cards = rec.get("hole_cards", "Desconhecido")
    comm_cards = rec.get("community_cards", "") or "Sem cartas"
    pot_odds = rec.get("pot_odds", 0.0)
    raw_equity = rec.get("raw_equity", 0.0)
    ev_val = rec.get("expected_value", 0.0)
    outs_count = rec.get("outs_count", 0)
    tactical_reason = rec.get("tactical_reason", "Decisão analítica padrão")
    decision_mode = rec.get("decision_mode", "MATHEMATICAL")
    action_type = rec.get("action_type", "BET")
    amount = rec.get("amount", 0)
    is_bluff = rec.get("is_bluff", False)
    bluff_type = rec.get("bluff_type", "NONE")
    opponent_response = rec.get("opponent_response", "NOT_APPLICABLE")
    bluff_outcome = rec.get("bluff_outcome", "NOT_APPLICABLE")
    net_chips = rec.get("net_bluff_chips", 0)
    pot_before = rec.get("pot_before", 0)

    # =========================================================================
    # ANÁLISE AVANÇADA DE XAI (ESTADO DA ARTE: TEXTURA, BLOCKERS, CONTRAFACTUAIS)
    # =========================================================================
    adv = analyze_advanced_xai(
        hole_str=hole_cards,
        board_str=comm_cards,
        street_str=street,
        pot_before=pot_before,
        amount=amount,
        action_type=action_type,
        raw_equity=float(raw_equity or 0.0),
        pot_odds=float(pot_odds or 0.0),
        db_ev=float(ev_val or 0.0),
        is_bluff=is_bluff,
    )
    b_texture = adv["board_texture"]
    b_blocker = adv["blocker"]
    b_foldeq = adv["fold_equity"]
    b_counter = adv["counterfactuals"]

    # =========================================================================
    # CAMADA 1: ENTRADA / PERCEPÇÃO DA MESA (Input Layer - Level 0)
    # =========================================================================
    in_cards_id = "in_cards"
    nodes.append({
        "id": in_cards_id,
        "label": f"🎴 Cartas Próprias\n{hole_cards}",
        "title": f"Mão Privada: {hole_cards}",
        "shape": "box",
        "color": {"background": "#0f172a", "border": "#38bdf8"},
        "font": {"color": "#f0f9ff", "size": 13, "bold": True},
        "level": 0,
        "customData": {"layer": "input", "category": "hole_cards", "value": hole_cards},
    })

    in_board_id = "in_board"
    nodes.append({
        "id": in_board_id,
        "label": f"🃏 Bordo ({street})\n{comm_cards}",
        "title": f"Cartas Comunitárias abertas na street {street}",
        "shape": "box",
        "color": {"background": "#0f172a", "border": "#38bdf8"},
        "font": {"color": "#f0f9ff", "size": 13, "bold": True},
        "level": 0,
        "customData": {"layer": "input", "category": "community_cards", "value": comm_cards},
    })

    in_texture_id = "in_texture"
    nodes.append({
        "id": in_texture_id,
        "label": f"🎲 Textura da Mesa\n{b_texture['type']}\n({b_texture['label']})",
        "title": f"Textura da Mesa: {b_texture['type']}\n{b_texture['description']}",
        "shape": "box",
        "color": {
            "background": "#1e1b4b" if b_texture["is_wet"] else "#0f172a",
            "border": "#818cf8" if b_texture["is_wet"] else "#38bdf8",
        },
        "font": {"color": "#e0e7ff", "size": 12, "bold": True},
        "level": 0,
        "customData": {"layer": "input", "category": "board_texture", "data": b_texture},
    })

    in_odds_id = "in_odds"
    nodes.append({
        "id": in_odds_id,
        "label": f"⚖️ Pot Odds\n{pot_odds * 100:.1f}%",
        "title": f"Relação exigida entre aposta e pote (Odds: {pot_odds * 100:.1f}%)",
        "shape": "box",
        "color": {"background": "#0f172a", "border": "#38bdf8"},
        "font": {"color": "#f0f9ff", "size": 13, "bold": True},
        "level": 0,
        "customData": {"layer": "input", "category": "pot_odds", "value": pot_odds},
    })

    in_pot_id = "in_pot"
    nodes.append({
        "id": in_pot_id,
        "label": f"💰 Pote na Mesa\n{pot_before} fichas",
        "title": f"Valor total acumulado no centro da mesa antes desta ação",
        "shape": "box",
        "color": {"background": "#0f172a", "border": "#38bdf8"},
        "font": {"color": "#f0f9ff", "size": 13, "bold": True},
        "level": 0,
        "customData": {"layer": "input", "category": "pot_size", "value": pot_before},
    })

    # =========================================================================
    # CAMADA 2: PONDERAÇÃO COGNITIVA (Hidden Layer - Level 1)
    # =========================================================================
    hid_equity_id = "hid_equity"
    nodes.append({
        "id": hid_equity_id,
        "label": f"📈 Equidade Monte Carlo\n{raw_equity * 100:.1f}% ({outs_count} outs)",
        "title": f"Probabilidade estimada de vitória calculada pelo motor: {raw_equity * 100:.1f}%",
        "shape": "box",
        "color": {"background": "#2e1065", "border": "#a855f7"},
        "font": {"color": "#f5f3ff", "size": 13, "bold": True},
        "level": 1,
        "customData": {"layer": "hidden", "category": "equity", "raw_equity": raw_equity, "outs": outs_count},
    })

    hid_blocker_id = "hid_blocker"
    nodes.append({
        "id": hid_blocker_id,
        "label": f"🛡️ Blocker (Remoção)\n{b_blocker['label']}",
        "title": f"Efeito de Remoção de Cartas (Blocker Score: {b_blocker['score']}):\n{b_blocker['description']}",
        "shape": "box",
        "color": {
            "background": "#4a044e" if b_blocker["score"] >= 0.25 else "#2e1065",
            "border": "#f472b6" if b_blocker["score"] >= 0.25 else "#a855f7",
        },
        "font": {"color": "#fdf2f8", "size": 12, "bold": True},
        "level": 1,
        "customData": {"layer": "hidden", "category": "blocker", "data": b_blocker},
    })

    hid_foldeq_id = "hid_foldeq"
    nodes.append({
        "id": hid_foldeq_id,
        "label": f"👥 Fold Equity\n{b_foldeq['label']} Pressão",
        "title": f"Probabilidade estimada de oponentes desistirem da mão: {b_foldeq['label']}",
        "shape": "box",
        "color": {
            "background": "#3f1404" if is_bluff else "#2e1065",
            "border": "#fb923c" if is_bluff else "#a855f7",
        },
        "font": {"color": "#fff7ed", "size": 12, "bold": True},
        "level": 1,
        "customData": {"layer": "hidden", "category": "fold_equity", "data": b_foldeq},
    })

    hid_mode_id = "hid_mode"
    nodes.append({
        "id": hid_mode_id,
        "label": f"⚙️ Modo Ativado\n{decision_mode}",
        "title": f"Estratégia e heurística ativada pelo agente: {decision_mode}",
        "shape": "box",
        "color": {"background": "#2e1065", "border": "#a855f7"},
        "font": {"color": "#f5f3ff", "size": 12, "bold": True},
        "level": 1,
        "customData": {"layer": "hidden", "category": "decision_mode", "value": decision_mode},
    })

    hid_ev_id = "hid_ev"
    nodes.append({
        "id": hid_ev_id,
        "label": f"💲 Expected Value (EV)\n{b_counter['chosen_ev']:+.2f} BB",
        "title": f"Retorno financeiro matemático esperado da jogada: {b_counter['chosen_ev']:+.2f} BB",
        "shape": "box",
        "color": {"background": "#2e1065", "border": "#a855f7"},
        "font": {"color": "#f5f3ff", "size": 13, "bold": True},
        "level": 1,
        "customData": {"layer": "hidden", "category": "expected_value", "value": b_counter["chosen_ev"], "counterfactuals": b_counter},
    })

    hid_reason_id = "hid_reason"
    nodes.append({
        "id": hid_reason_id,
        "label": f"🧠 Raciocínio (XAI)\n\"{tactical_reason[:42]}...\"",
        "title": f"Explicação detalhada da IA:\n{tactical_reason}",
        "shape": "box",
        "color": {"background": "#3b0764", "border": "#d8b4fe"},
        "font": {"color": "#faf5ff", "size": 12, "bold": True},
        "borderWidth": 2,
        "level": 1,
        "customData": {"layer": "hidden", "category": "xai_reason", "full_text": tactical_reason},
    })

    # =========================================================================
    # CAMADA 3: SAÍDA / VEREDITO (Output Layer - Level 2)
    # =========================================================================
    out_act_id = "out_act"
    nodes.append({
        "id": out_act_id,
        "label": f"🎯 Ação Executada\n{action_type} {amount if amount > 0 else ''}",
        "title": f"Ação física realizada pelo agente: {action_type} {amount if amount > 0 else ''}",
        "shape": "box",
        "color": {
            "background": "#064e3b" if not is_bluff else "#450a0a",
            "border": "#34d399" if not is_bluff else "#f87171",
        },
        "font": {"color": "#ecfdf5", "size": 14, "bold": True},
        "borderWidth": 3,
        "level": 2,
        "customData": {"layer": "output", "category": "action_taken"},
    })

    out_bluff_id = "out_bluff"
    bluff_badge = f"🎭 {bluff_type}" if is_bluff else "🛡️ VALOR LEGÍTIMO"
    nodes.append({
        "id": out_bluff_id,
        "label": f"Detector de Blefe\n{bluff_badge}",
        "title": f"Classificação científica da aposta: {bluff_badge}",
        "shape": "box",
        "color": {
            "background": "#450a0a" if is_bluff else "#0f172a",
            "border": "#ef4444" if is_bluff else "#22c55e",
        },
        "font": {"color": "#fef2f2" if is_bluff else "#f0fdf4", "size": 13, "bold": True},
        "level": 2,
        "customData": {"layer": "output", "category": "bluff_classification"},
    })

    out_resp_id = "out_resp"
    nodes.append({
        "id": out_resp_id,
        "label": f"👥 Reação dos Oponentes\n{opponent_response}",
        "title": f"Comportamento da mesa diante desta aposta: {opponent_response}",
        "shape": "box",
        "color": {"background": "#0f172a", "border": "#64748b"},
        "font": {"color": "#e2e8f0", "size": 12},
        "level": 2,
        "customData": {"layer": "output", "category": "opponent_response"},
    })

    out_chips_id = "out_chips"
    nodes.append({
        "id": out_chips_id,
        "label": f"💵 Desfecho Financeiro\n{net_chips:+} fichas",
        "title": f"Impacto financeiro do blefe ou jogada: {net_chips} fichas ({bluff_outcome})",
        "shape": "box",
        "color": {
            "background": "#064e3b" if net_chips >= 0 else "#450a0a",
            "border": "#10b981" if net_chips >= 0 else "#ef4444",
        },
        "font": {"color": "#ecfdf5", "size": 13, "bold": True},
        "level": 2,
        "customData": {"layer": "output", "category": "chips_result"},
    })

    # =========================================================================
    # ARESTAS DA REDE NEURAL (PONDERAÇÃO CAUSAL / FEATURE ATTRIBUTION)
    # =========================================================================
    # 1. Entrada -> Cognição
    edges.append({"from": in_cards_id, "to": hid_equity_id, "label": "avaliação", "color": {"color": "#38bdf8"}, "arrows": "to", "width": 2})
    edges.append({"from": in_board_id, "to": hid_equity_id, "label": "combinação", "color": {"color": "#38bdf8"}, "arrows": "to", "width": 2})
    edges.append({"from": in_board_id, "to": in_texture_id, "label": "análise", "color": {"color": "#38bdf8"}, "arrows": "to", "width": 2})
    edges.append({"from": in_cards_id, "to": hid_blocker_id, "label": "remoção", "color": {"color": "#38bdf8"}, "arrows": "to", "width": 2})
    edges.append({"from": in_board_id, "to": hid_blocker_id, "label": "combos", "color": {"color": "#38bdf8"}, "arrows": "to", "width": 1})
    edges.append({"from": in_texture_id, "to": hid_foldeq_id, "label": "leitura", "color": {"color": "#818cf8"}, "arrows": "to", "width": 2})
    edges.append({"from": in_odds_id, "to": hid_ev_id, "label": "risco", "color": {"color": "#38bdf8"}, "arrows": "to", "width": 2})
    edges.append({"from": in_pot_id, "to": hid_ev_id, "label": "recompensa", "color": {"color": "#38bdf8"}, "arrows": "to", "width": 2})
    edges.append({"from": in_cards_id, "to": hid_reason_id, "color": {"color": "#64748b"}, "arrows": "to", "width": 1})
    edges.append({"from": in_board_id, "to": hid_reason_id, "color": {"color": "#64748b"}, "arrows": "to", "width": 1})

    # 2. Cognição -> Saída (Ponderação Causal Atribuída)
    if is_bluff:
        # No blefe, o motor é puxado pela Fold Equity e Blockers!
        edges.append({"from": hid_foldeq_id, "to": out_act_id, "label": f"pressão ({b_foldeq['label']})", "color": {"color": "#f59e0b", "highlight": "#fde047"}, "arrows": "to", "width": 4})
        edges.append({"from": hid_blocker_id, "to": out_bluff_id, "label": f"filtro ({b_blocker['score']:.2f})", "color": {"color": "#ef4444", "highlight": "#fca5a5"}, "arrows": "to", "width": 3})
        edges.append({"from": hid_equity_id, "to": out_act_id, "label": "equidade", "color": {"color": "#64748b"}, "arrows": "to", "width": 1})
    else:
        # Em valor, o motor é puxado pela Equidade!
        edges.append({"from": hid_equity_id, "to": out_act_id, "label": "força", "color": {"color": "#10b981", "highlight": "#6ee7b7"}, "arrows": "to", "width": 4})
        edges.append({"from": hid_foldeq_id, "to": out_act_id, "label": "apoio", "color": {"color": "#64748b"}, "arrows": "to", "width": 1})
        edges.append({"from": hid_blocker_id, "to": out_bluff_id, "label": "limpeza", "color": {"color": "#64748b"}, "arrows": "to", "width": 1})

    edges.append({"from": hid_ev_id, "to": out_act_id, "label": "decisão", "color": {"color": "#a855f7"}, "arrows": "to", "width": 3})
    edges.append({"from": hid_mode_id, "to": out_bluff_id, "label": "filtro", "color": {"color": "#a855f7"}, "arrows": "to", "width": 2})
    edges.append({"from": hid_reason_id, "to": out_act_id, "label": "motivo", "color": {"color": "#c084fc"}, "arrows": "to", "width": 2})
    edges.append({"from": out_act_id, "to": out_resp_id, "label": "indução", "color": {"color": "#64748b"}, "arrows": "to", "width": 2})
    edges.append({"from": out_bluff_id, "to": out_chips_id, "label": "resultado", "color": {"color": "#64748b"}, "arrows": "to", "width": 2})

    return {
        "success": True,
        "view": "micro",
        "action_id": action_id,
        "hand_id": hand_id,
        "street": street,
        "player_name": player_name,
        "profile": profile,
        "is_bluff": is_bluff,
        "bluff_type": bluff_type,
        "action_type": action_type,
        "amount": amount,
        "tactical_reason": tactical_reason,
        "board_texture": b_texture,
        "blocker": b_blocker,
        "fold_equity": b_foldeq,
        "counterfactuals": b_counter,
        "nodes": nodes,
        "edges": edges,
    }


def _get_local_fallback_hands(
    only_bluffs: bool = False,
    limit: int = 50,
    error_msg: Optional[str] = None,
) -> Dict[str, Any]:
    """Lê mãos de simulações salvas localmente em CSV se o Neon estiver fora do ar."""
    import csv

    project_root = Path(__file__).resolve().parent.parent.parent
    data_dir = project_root / "data"
    all_tests = sorted(data_dir.glob("test_*"), key=lambda p: p.stat().st_mtime, reverse=True)

    hands_map: Dict[int, Dict[str, Any]] = {}

    for t_dir in all_tests:
        actions_csv = t_dir / "game_actions.csv"
        telemetry_csv = t_dir / "decision_telemetry_and_bluffs.csv"
        if not (actions_csv.exists() and telemetry_csv.exists()):
            continue

        try:
            with open(actions_csv, "r", encoding="utf-8") as fa:
                reader = csv.DictReader(fa)
                for row in reader:
                    hid = int(row["hand_id"])
                    if hid not in hands_map:
                        hands_map[hid] = {
                            "hand_id": hid,
                            "total_pot": int(row.get("pot_after", 0)),
                            "total_actions": 0,
                            "has_bluff": False,
                            "bluff_count": 0,
                            "bluff_types": "",
                            "players": set(),
                            "winner_name": "Agente Vencedor",
                            "winner_profile": "Tier S",
                        }
                    h = hands_map[hid]
                    h["total_actions"] += 1
                    h["total_pot"] = max(h["total_pot"], int(row.get("pot_after", 0)))
                    h["players"].add(row.get("player_name", ""))

            with open(telemetry_csv, "r", encoding="utf-8") as ft:
                reader = csv.DictReader(ft)
                for row in reader:
                    hid = int(row["hand_id"])
                    if hid in hands_map and row.get("is_bluff") == "True":
                        h = hands_map[hid]
                        h["has_bluff"] = True
                        h["bluff_count"] += 1
                        btype = row.get("bluff_type", "NONE")
                        if btype not in h["bluff_types"]:
                            h["bluff_types"] = (h["bluff_types"] + ", " + btype).strip(", ")
                    if hid in hands_map and row.get("hand_result") in ("WON_HAND", "SPLIT_POT"):
                        hands_map[hid]["winner_name"] = row.get("player_name")
                        hands_map[hid]["winner_profile"] = row.get("profile")
        except Exception:
            continue

    formatted = []
    for hid in sorted(hands_map.keys(), reverse=True):
        item = hands_map[hid]
        if only_bluffs and not item["has_bluff"]:
            continue
        item["players"] = ", ".join(list(item["players"])[:4])
        formatted.append(item)
        if len(formatted) >= limit:
            break

    return {
        "success": True,
        "source": "local_csv_fallback",
        "error_neon": error_msg,
        "count": len(formatted),
        "hands": formatted,
    }


def _load_local_fallback_actions(hand_id: int) -> List[Dict[str, Any]]:
    """Carrega ações locais correspondentes ao hand_id."""
    import csv

    project_root = Path(__file__).resolve().parent.parent.parent
    data_dir = project_root / "data"
    all_tests = sorted(data_dir.glob("test_*"), key=lambda p: p.stat().st_mtime, reverse=True)

    actions = []
    telemetries = {}

    for t_dir in all_tests:
        actions_csv = t_dir / "game_actions.csv"
        telemetry_csv = t_dir / "decision_telemetry_and_bluffs.csv"
        if not (actions_csv.exists() and telemetry_csv.exists()):
            continue

        try:
            with open(telemetry_csv, "r", encoding="utf-8") as ft:
                for row in csv.DictReader(ft):
                    if int(row["hand_id"]) == hand_id:
                        telemetries[row["action_id"]] = row

            with open(actions_csv, "r", encoding="utf-8") as fa:
                for row in csv.DictReader(fa):
                    if int(row["hand_id"]) == hand_id:
                        aid = row["action_id"]
                        t = telemetries.get(aid, {})
                        actions.append({
                            "action_id": aid,
                            "hand_id": hand_id,
                            "step_order": int(row.get("step_order", 1)),
                            "street": row.get("street", "PREFLOP"),
                            "player_id": row.get("player_id", ""),
                            "player_name": row.get("player_name", "Bot"),
                            "profile": row.get("profile", ""),
                            "hole_cards": row.get("hole_cards", ""),
                            "community_cards": row.get("community_cards", ""),
                            "action_type": row.get("action_type", "CHECK"),
                            "amount": int(row.get("amount", 0)),
                            "pot_before": int(row.get("pot_before", 0)),
                            "pot_after": int(row.get("pot_after", 0)),
                            "player_stack_before": int(row.get("player_stack_before", 0)),
                            "player_stack_after": int(row.get("player_stack_after", 0)),
                            "decision_mode": t.get("decision_mode", "STANDARD"),
                            "raw_equity": float(t.get("raw_equity", 0.0) or 0.0),
                            "pot_odds": float(t.get("pot_odds", 0.0) or 0.0),
                            "expected_value": float(t.get("expected_value", 0.0) or 0.0),
                            "outs_count": int(t.get("outs_count", 0) or 0),
                            "tactical_reason": t.get("tactical_reason", ""),
                            "is_bluff": t.get("is_bluff") == "True",
                            "bluff_type": t.get("bluff_type", "NONE"),
                            "opponent_response": t.get("opponent_response", "NOT_APPLICABLE"),
                            "bluff_outcome": t.get("bluff_outcome", "NOT_APPLICABLE"),
                            "net_bluff_chips": int(t.get("net_bluff_chips", 0) or 0),
                            "hand_result": t.get("hand_result", "UNKNOWN"),
                        })
            if actions:
                break
        except Exception:
            continue

    return sorted(actions, key=lambda x: x["step_order"])


def _find_local_fallback_action(action_id: str) -> Optional[Dict[str, Any]]:
    """Localiza uma ação específica nos CSVs locais."""
    import csv

    project_root = Path(__file__).resolve().parent.parent.parent
    data_dir = project_root / "data"
    for t_dir in sorted(data_dir.glob("test_*"), key=lambda p: p.stat().st_mtime, reverse=True):
        actions_csv = t_dir / "game_actions.csv"
        telemetry_csv = t_dir / "decision_telemetry_and_bluffs.csv"
        if not (actions_csv.exists() and telemetry_csv.exists()):
            continue
        try:
            target_a = None
            with open(actions_csv, "r", encoding="utf-8") as fa:
                for row in csv.DictReader(fa):
                    if row["action_id"] == action_id:
                        target_a = row
                        break
            if not target_a:
                continue

            target_t = {}
            with open(telemetry_csv, "r", encoding="utf-8") as ft:
                for row in csv.DictReader(ft):
                    if row["action_id"] == action_id:
                        target_t = row
                        break

            return {
                "action_id": action_id,
                "hand_id": int(target_a.get("hand_id", 0)),
                "step_order": int(target_a.get("step_order", 1)),
                "street": target_a.get("street", "FLOP"),
                "player_id": target_a.get("player_id", ""),
                "player_name": target_a.get("player_name", "Bot"),
                "profile": target_a.get("profile", ""),
                "hole_cards": target_a.get("hole_cards", ""),
                "community_cards": target_a.get("community_cards", ""),
                "action_type": target_a.get("action_type", "CHECK"),
                "amount": int(target_a.get("amount", 0)),
                "pot_before": int(target_a.get("pot_before", 0)),
                "pot_after": int(target_a.get("pot_after", 0)),
                "player_stack_before": int(target_a.get("player_stack_before", 0)),
                "player_stack_after": int(target_a.get("player_stack_after", 0)),
                "decision_mode": target_t.get("decision_mode", "STANDARD"),
                "raw_equity": float(target_t.get("raw_equity", 0.0) or 0.0),
                "pot_odds": float(target_t.get("pot_odds", 0.0) or 0.0),
                "expected_value": float(target_t.get("expected_value", 0.0) or 0.0),
                "outs_count": int(target_t.get("outs_count", 0) or 0),
                "tactical_reason": target_t.get("tactical_reason", ""),
                "is_bluff": target_t.get("is_bluff") == "True",
                "bluff_type": target_t.get("bluff_type", "NONE"),
                "opponent_response": target_t.get("opponent_response", "NOT_APPLICABLE"),
                "bluff_outcome": target_t.get("bluff_outcome", "NOT_APPLICABLE"),
                "net_bluff_chips": int(target_t.get("net_bluff_chips", 0) or 0),
                "hand_result": target_t.get("hand_result", "UNKNOWN"),
            }
        except Exception:
            continue
    return None
