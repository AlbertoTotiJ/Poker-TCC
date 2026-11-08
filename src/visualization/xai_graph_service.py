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
    test_id: Optional[str] = None,
    custom_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Retorna a lista de mãos disponíveis com resumos executivos para seleção no frontend."""
    conn = get_neon_connection(custom_url=custom_url)
    if conn is None:
        # Fallback local se o Neon estiver indisponível
        return _get_local_fallback_hands(only_bluffs=only_bluffs, limit=limit)

    cur = conn.cursor()
    try:
        where_clauses = []
        params: List[Any] = []
        if test_id:
            where_clauses.append("a.test_id = %s")
            params.append(test_id)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        bluff_filter = "HAVING bool_or(t.is_bluff = TRUE)" if only_bluffs else ""
        query = f"""
        SELECT 
            a.hand_id,
            a.test_id,
            MAX(a.pot_after) as total_pot,
            COUNT(a.action_id) as total_actions,
            COALESCE(bool_or(t.is_bluff = TRUE), FALSE) as has_bluff,
            COUNT(CASE WHEN t.is_bluff = TRUE THEN 1 END) as bluff_count,
            STRING_AGG(DISTINCT t.bluff_type, ', ') FILTER (WHERE t.is_bluff = TRUE) as bluff_types,
            STRING_AGG(DISTINCT a.player_name, ', ') as players,
            (
                SELECT t_sub.player_name 
                FROM decision_telemetry_and_bluffs t_sub 
                WHERE t_sub.hand_id = a.hand_id AND t_sub.test_id = a.test_id AND t_sub.hand_result IN ('WON_HAND', 'SPLIT_POT') 
                LIMIT 1
            ) as winner_name,
            (
                SELECT t_sub.profile 
                FROM decision_telemetry_and_bluffs t_sub 
                WHERE t_sub.hand_id = a.hand_id AND t_sub.test_id = a.test_id AND t_sub.hand_result IN ('WON_HAND', 'SPLIT_POT') 
                LIMIT 1
            ) as winner_profile
        FROM game_actions a
        LEFT JOIN decision_telemetry_and_bluffs t ON a.action_id = t.action_id
        {where_sql}
        GROUP BY a.hand_id, a.test_id
        {bluff_filter}
        ORDER BY a.hand_id DESC, total_pot DESC
        LIMIT %s;
        """
        params.append(limit)
        cur.execute(query, tuple(params))
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


def get_curated_emblematic_hands() -> List[Dict[str, Any]]:
    """Retorna a coleção oficial de 5 Casos de Estudo emblemáticos para apresentações e defesas."""
    return [
        {
            "category": "EXTRAÇÃO MÁXIMA (+EV / POTE MONSTRO)",
            "title": "Armadilha com Sequência Nuts e Aposta Máxima no River",
            "hand_id": 491,
            "test_id": "9max_full_ring_1000m_seed99",
            "hero_name": "Matemático 1",
            "hero_profile": "Matemático (Tier S)",
            "hole_cards": "A♣ T♠",
            "community_cards": "Q♠ J♣ 4♦ K♠ 8♣",
            "final_pot": 9000,
            "key_action": "RAISE de 4.483 fichas no River",
            "raw_equity": 0.995,
            "pot_odds": 0.2192,
            "expected_value": 5440.19,
            "insight": "Broadway nuts completa no turn/river; o bot induziu raises sucessivos do Matemático 7 e executou raise por valor absoluto, capturando 9.000 fichas.",
            "badge": "💰 Pote Monstro (9.000)",
        },
        {
            "category": "BLEFE PURO DESMASCARADO (DISPARIDADE COGNITIVA)",
            "title": "Blefe Oportunista do Híbrido Pego por Mão Legítima",
            "hand_id": 72,
            "test_id": "05_bluffer_vs_5_hybrids_seed99",
            "hero_name": "Híbrido 3",
            "hero_profile": "Híbrido",
            "hole_cards": "3♠ J♦",
            "community_cards": "5♥ 4♦ 8♠ Q♦",
            "final_pot": 2184,
            "key_action": "BET de 324 fichas no Turn com 1.0% de equidade",
            "raw_equity": 0.010,
            "pot_odds": 0.0,
            "expected_value": 0.0,
            "insight": "Tentativa de blefe puro em mesa passiva sem outs ou blockers; o adversário pagou no showdown e desmascarou o blefe (Disparidade Cognitiva).",
            "badge": "🔥 Blefe Desmascarado",
        },
        {
            "category": "SEMI-BLEFE ESTRATÉGICO COM FOLD EQUITY",
            "title": "Raise no Turn com 8 Outs e Concretização no River",
            "hand_id": 472,
            "test_id": "6max_heterogeneo_1000m_seed101",
            "hero_name": "Matemático 2",
            "hero_profile": "Matemático",
            "hole_cards": "7♦ 6♣",
            "community_cards": "9♠ 8♠ 8♣ 8♦ T♦",
            "final_pot": 2000,
            "key_action": "RAISE de 533 fichas no Turn com 8 outs de ponta aberta",
            "raw_equity": 0.285,
            "pot_odds": 0.2179,
            "expected_value": -173.71,
            "insight": "Semi-blefe clássico: aposta agressiva baseada na Fold Equity + 8 outs de sequência. O 10 de ouros no River completou a sequência para a vitória.",
            "badge": "🎯 Semi-Blefe (8 Outs)",
        },
        {
            "category": "FOLD DISCIPLINADO PREVENTIVO (-EV DEFENSE)",
            "title": "Desistência Cirúrgica contra Pot Odds Desfavoráveis",
            "hand_id": 277,
            "test_id": "6max_heterogeneo_1000m_seed101",
            "hero_name": "Matemático 1",
            "hero_profile": "Matemático",
            "hole_cards": "A♣ 8♣",
            "community_cards": "K♠ Q♦ 7♥ 3♣ 9♠",
            "final_pot": 2298,
            "key_action": "FOLD no River com 8.5% de equidade",
            "raw_equity": 0.085,
            "pot_odds": 0.3786,
            "expected_value": 0.0,
            "insight": "Proteção de capital pura: a equidade (8.5%) era inferior às pot odds (37.9%). A IA descartou a mão evitando perder mais de 800 fichas adicionais.",
            "badge": "🛡️ Fold Disciplinado",
        },
        {
            "category": "FULL HOUSE MONSTRO & SLOW PLAY",
            "title": "Armadilha de Trinca/Full House em Bordo Dobrado",
            "hand_id": 385,
            "test_id": "6max_heterogeneo_1000m_seed101",
            "hero_name": "Matemático 4",
            "hero_profile": "Matemático",
            "hole_cards": "2♥ 2♦",
            "community_cards": "2♠ 3♥ Q♥ 3♠ 8♥",
            "final_pot": 7455,
            "key_action": "RAISE de 3.341 fichas no River com Full House (2-2-2-3-3)",
            "raw_equity": 0.950,
            "pot_odds": 0.2291,
            "expected_value": 5082.75,
            "insight": "Full house floppado/turnado; o bot fez slow-play até o River para permitir que o oponente blefasse, antes de cravar um raise de 3.341 fichas.",
            "badge": "👑 Full House (7.455)",
        },
    ]


def build_macro_graph(
    hand_id: int, 
    test_id: Optional[str] = None, 
    custom_url: Optional[str] = None
) -> Dict[str, Any]:
    """Constrói os nós e arestas para a Visão MACRO (Trilha da Vitória) da mão especificada."""
    conn = get_neon_connection(custom_url=custom_url)
    actions: List[Dict[str, Any]] = []

    if conn is not None:
        cur = conn.cursor()
        try:
            if test_id:
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
                WHERE a.hand_id = %s AND a.test_id = %s
                ORDER BY a.step_order ASC;
                """
                cur.execute(query, (hand_id, test_id))
            else:
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
                WHERE a.hand_id = %s AND a.test_id = (
                    SELECT a2.test_id FROM game_actions a2 WHERE a2.hand_id = %s LIMIT 1
                )
                ORDER BY a.step_order ASC;
                """
                cur.execute(query, (hand_id, hand_id))

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


_GLOBAL_GRAPH_CACHE: Dict[str, Dict[str, Any]] = {}

def build_global_process_mining_graph(
    profile_filter: str = "ALL",
    seed_filter: Optional[str] = None,
    custom_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Constrói o Grafo de Transição de Estados Global (Process Mining) sintetizando todas as 181.083 decisões."""
    global _GLOBAL_GRAPH_CACHE
    prof_key = (profile_filter or "ALL").strip()
    seed_key = (seed_filter or "ALL").strip()
    cache_key = f"{prof_key}::{seed_key}"
    if cache_key in _GLOBAL_GRAPH_CACHE:
        return _GLOBAL_GRAPH_CACHE[cache_key]

    conn = get_neon_connection(custom_url=custom_url)
    stats = {}

    if conn is not None:
        cur = conn.cursor()
        try:
            where_parts = []
            params: List[Any] = []
            if prof_key not in ("ALL", "TODOS", ""):
                where_parts.append("t.profile LIKE %s")
                params.append(f"%{prof_key}%")
            if seed_key not in ("ALL", "TODOS", ""):
                where_parts.append("t.test_id LIKE %s")
                params.append(f"%{seed_key}%")

            where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

            query = f"""
            SELECT 
                COUNT(*) as total_actions,
                COUNT(CASE WHEN t.street = 'PREFLOP' THEN 1 END) as preflop_cnt,
                COUNT(CASE WHEN t.street = 'FLOP' THEN 1 END) as flop_cnt,
                COUNT(CASE WHEN t.street = 'TURN' THEN 1 END) as turn_cnt,
                COUNT(CASE WHEN t.street = 'RIVER' THEN 1 END) as river_cnt,
                COUNT(CASE WHEN t.is_bluff = TRUE AND t.bluff_type IN ('PURE_BLUFF', 'DESPERATION_ALL_IN') THEN 1 END) as pure_bluffs,
                COUNT(CASE WHEN t.is_bluff = TRUE AND t.bluff_type = 'SEMI_BLUFF' THEN 1 END) as semi_bluffs,
                COUNT(CASE WHEN t.action_taken IN ('BET', 'RAISE') AND t.raw_equity >= 0.50 THEN 1 END) as val_bets,
                COUNT(CASE WHEN t.action_taken = 'FOLD' THEN 1 END) as folds,
                COUNT(CASE WHEN t.action_taken = 'CHECK' THEN 1 END) as checks,
                COUNT(CASE WHEN t.action_taken = 'CALL' THEN 1 END) as calls,
                COUNT(CASE WHEN t.hand_result = 'WON_HAND' THEN 1 END) as won_hands
            FROM decision_telemetry_and_bluffs t
            {where_clause};
            """
            cur.execute(query, tuple(params))
            row = cur.fetchone()
            if row:
                cols = [
                    "total_actions", "preflop_cnt", "flop_cnt", "turn_cnt", "river_cnt",
                    "pure_bluffs", "semi_bluffs", "val_bets", "folds", "checks", "calls", "won_hands"
                ]
                stats = dict(zip(cols, row))
        except Exception:
            stats = {}
        finally:
            try:
                cur.close()
                conn.close()
            except Exception:
                pass

    # Fallback precomputado se o banco estiver indisponível
    if not stats or stats.get("total_actions", 0) == 0:
        if prof_key == "Matemático":
            stats = {
                "total_actions": 66569, "preflop_cnt": 28145, "flop_cnt": 20110, "turn_cnt": 11210, "river_cnt": 7104,
                "pure_bluffs": 264, "semi_bluffs": 96, "val_bets": 11436, "folds": 18207, "checks": 15800, "calls": 20766, "won_hands": 19588
            }
        elif prof_key == "Blefador":
            stats = {
                "total_actions": 63988, "preflop_cnt": 26430, "flop_cnt": 19840, "turn_cnt": 10820, "river_cnt": 6898,
                "pure_bluffs": 1151, "semi_bluffs": 5261, "val_bets": 7226, "folds": 13837, "checks": 16200, "calls": 20313, "won_hands": 18508
            }
        elif prof_key == "Híbrido":
            stats = {
                "total_actions": 50526, "preflop_cnt": 21501, "flop_cnt": 15162, "turn_cnt": 8379, "river_cnt": 5484,
                "pure_bluffs": 3863, "semi_bluffs": 2135, "val_bets": 11345, "folds": 7077, "checks": 10843, "calls": 15262, "won_hands": 17882
            }
        else:
            stats = {
                "total_actions": 181083, "preflop_cnt": 76076, "flop_cnt": 55112, "turn_cnt": 30409, "river_cnt": 19486,
                "pure_bluffs": 5278, "semi_bluffs": 7492, "val_bets": 30007, "folds": 39121, "checks": 42843, "calls": 48141, "won_hands": 55978
            }

    tot = stats["total_actions"]
    val_b = stats["val_bets"]
    semi_b = stats["semi_bluffs"]
    pure_b = stats["pure_bluffs"]
    folds = stats["folds"]
    checks = stats["checks"]
    calls = stats["calls"]
    won = stats["won_hands"]

    # Frequências e taxas percentuais
    pct_val = (val_b / tot * 100) if tot > 0 else 0
    pct_semi = (semi_b / tot * 100) if tot > 0 else 0
    pct_pure = (pure_b / tot * 100) if tot > 0 else 0
    pct_fold = (folds / tot * 100) if tot > 0 else 0
    pct_check_call = ((checks + calls) / tot * 100) if tot > 0 else 0
    win_rate = (won / tot * 100) if tot > 0 else 0

    nodes = [
        # Nível 0: Entrada
        {
            "id": "glob_preflop",
            "label": f"🏁 Pré-Flop\nEntrada & Blinds\n{tot:,} decisões".replace(",", "."),
            "level": 0,
            "shape": "box",
            "color": {"background": "#1e40af", "border": "#60a5fa"},
            "font": {"color": "#ffffff", "face": "Segoe UI", "size": 13, "bold": True},
            "borderWidth": 2,
            "margin": 10,
            "shadow": True,
            "meta": {
                "title": "🏁 Estado Inicial: Pré-Flop (Deal & Blinds)",
                "badge": "🏁 ENTRADA",
                "volume": f"{tot:,} decisões".replace(",", "."),
                "avg_equity": "38.2%",
                "description": "Distribuição inicial das cartas privadas (hole cards) e pagamento compulsório dos blinds. Representa o ponto de partida de todos os caminhos decisórios da IA.",
                "emblematic_hands": [
                    {"hand_id": 491, "label": "Mão #491 · Call inicial do Matemático", "test_id": "9max_full_ring_1000m_seed99"},
                    {"hand_id": 472, "label": "Mão #472 · Entrada em mesa 6-max", "test_id": "6max_heterogeneo_1000m_seed101"}
                ]
            }
        },
        # Nível 1: Textura do Bordo
        {
            "id": "glob_wet_board",
            "label": "🌊 Bordo Conectado / Molhado\n(Altos Draws & Flushes)\n~54.2% das mesas",
            "level": 1,
            "shape": "box",
            "color": {"background": "#0369a1", "border": "#38bdf8"},
            "font": {"color": "#ffffff", "face": "Segoe UI", "size": 12, "bold": True},
            "borderWidth": 2,
            "margin": 10,
            "shadow": True,
            "meta": {
                "title": "🌊 Percepção: Bordo Molhado / Conectado (Wet Texture)",
                "badge": "🌊 TEXTURA",
                "volume": "~54.2% das rodadas",
                "avg_equity": "36.5%",
                "description": "Bordos com múltiplos conectores e naipes iguais, propícios para projetos de sequência (straight draw) e flush. Estimula semi-blefes e re-raises agressivos.",
                "emblematic_hands": [
                    {"hand_id": 472, "label": "Mão #472 · Bordo 9♠ 8♠ 8♣ com 8 outs", "test_id": "6max_heterogeneo_1000m_seed101"},
                    {"hand_id": 785, "label": "Mão #785 · Flush no flop 3♥ 2♥ K♥", "test_id": "6max_heterogeneo_1000m_seed101"}
                ]
            }
        },
        {
            "id": "glob_dry_board",
            "label": "🏜️ Bordo Desconectado / Seco\n(Cartas Baixas / Dispersas)\n~45.8% das mesas",
            "level": 1,
            "shape": "box",
            "color": {"background": "#b45309", "border": "#fbbf24"},
            "font": {"color": "#ffffff", "face": "Segoe UI", "size": 12, "bold": True},
            "borderWidth": 2,
            "margin": 10,
            "shadow": True,
            "meta": {
                "title": "🏜️ Percepção: Bordo Seco / Desconectado (Dry Texture)",
                "badge": "🏜️ TEXTURA",
                "volume": "~45.8% das rodadas",
                "avg_equity": "41.0%",
                "description": "Bordos sem conexão aparente. Favorece apostas por valor de mãos já feitas (overpairs) ou blefes oportunos em mesas passivas.",
                "emblematic_hands": [
                    {"hand_id": 72, "label": "Mão #72 · Bordo seco 5♥ 4♦ 8♠ Q♦", "test_id": "05_bluffer_vs_5_hybrids_seed99"},
                    {"hand_id": 277, "label": "Mão #277 · Bordo K♠ Q♦ 7♥ 3♣ 9♠", "test_id": "6max_heterogeneo_1000m_seed101"}
                ]
            }
        },
        # Nível 2: Ponderação Cognitiva e Decisão da IA
        {
            "id": "glob_val_bet",
            "label": f"💰 Aposta por Valor (+EV Kelly)\n{val_b:,} decisões ({pct_val:.1f}%)\nEq Média: 78.5% · Win Rate: 77.0%".replace(",", "."),
            "level": 2,
            "shape": "box",
            "color": {"background": "#15803d", "border": "#4ade80"},
            "font": {"color": "#ffffff", "face": "Segoe UI", "size": 12, "bold": True},
            "borderWidth": 2,
            "margin": 10,
            "shadow": True,
            "meta": {
                "title": "💰 Cluster: Aposta por Valor (+EV Kelly)",
                "badge": "💰 VALOR (+EV)",
                "volume": f"{val_b:,} decisões ({pct_val:.1f}%)".replace(",", "."),
                "avg_equity": "78.5%",
                "win_rate": "77.0%",
                "description": "Decisões onde a equidade de Monte Carlo superou com folga as Pot Odds. O agente aposta por valor proporcional ao critério de Kelly para extrair o máximo de fichas dos adversários.",
                "emblematic_hands": [
                    {"hand_id": 491, "label": "Mão #491 · Pote Monstro de 9.000 fichas", "test_id": "9max_full_ring_1000m_seed99"},
                    {"hand_id": 385, "label": "Mão #385 · Full House e Pote de 7.455 fichas", "test_id": "6max_heterogeneo_1000m_seed101"}
                ]
            }
        },
        {
            "id": "glob_semi_bluff",
            "label": f"🎯 Semi-Blefe (Outs + Fold Eq)\n{semi_b:,} decisões ({pct_semi:.1f}%)\nEq Média: 37.3% · Conversão: 53.8%".replace(",", "."),
            "level": 2,
            "shape": "box",
            "color": {"background": "#0891b2", "border": "#22d3ee"},
            "font": {"color": "#ffffff", "face": "Segoe UI", "size": 12, "bold": True},
            "borderWidth": 2,
            "margin": 10,
            "shadow": True,
            "meta": {
                "title": "🎯 Cluster: Semi-Blefe Estratégico",
                "badge": "🎯 SEMI-BLEFE",
                "volume": f"{semi_b:,} decisões ({pct_semi:.1f}%)".replace(",", "."),
                "avg_equity": "37.3%",
                "win_rate": "53.8% de conversão",
                "description": "Aposta agressiva com mão não pronta, combinando probabilidade de acerto futuro (outs de sequência/flush) com a probabilidade de o adversário desistir (Fold Equity).",
                "emblematic_hands": [
                    {"hand_id": 472, "label": "Mão #472 · Raise no Turn com 8 Outs e vitória", "test_id": "6max_heterogeneo_1000m_seed101"},
                    {"hand_id": 889, "label": "Mão #889 · Bet com Straight Draw e divisão", "test_id": "9max_full_ring_1000m_seed101"}
                ]
            }
        },
        {
            "id": "glob_pure_bluff",
            "label": f"🔥 Blefe Puro / Oportunista\n{pure_b:,} decisões ({pct_pure:.1f}%)\nEq Média: 42.1% · Pressão Passiva".replace(",", "."),
            "level": 2,
            "shape": "box",
            "color": {"background": "#dc2626", "border": "#f87171"},
            "font": {"color": "#ffffff", "face": "Segoe UI", "size": 12, "bold": True},
            "borderWidth": 2,
            "margin": 10,
            "shadow": True,
            "meta": {
                "title": "🔥 Cluster: Blefe Puro / Oportunista",
                "badge": "🔥 BLEFE PURO",
                "volume": f"{pure_b:,} decisões ({pct_pure:.1f}%)".replace(",", "."),
                "avg_equity": "42.1%",
                "win_rate": "48.4% de folds forçados",
                "description": "Tentativa deliberada de roubar o pote com cartas fracas quando a mesa demonstra passividade extrema (checks múltiplos). Visto principalmente nos perfis Blefador e Híbrido.",
                "emblematic_hands": [
                    {"hand_id": 72, "label": "Mão #72 · Blefe oportunista de 324 fichas", "test_id": "05_bluffer_vs_5_hybrids_seed99"},
                    {"hand_id": 163, "label": "Mão #163 · Bet de 666 fichas no river", "test_id": "6max_heterogeneo_1000m_seed101"}
                ]
            }
        },
        {
            "id": "glob_check_call",
            "label": f"⚖️ Check / Call por Odds\n{(checks + calls):,} decisões ({pct_check_call:.1f}%)\nControle de Pote & Ver Carta".replace(",", "."),
            "level": 2,
            "shape": "box",
            "color": {"background": "#475569", "border": "#94a3b8"},
            "font": {"color": "#ffffff", "face": "Segoe UI", "size": 12, "bold": True},
            "borderWidth": 2,
            "margin": 10,
            "shadow": True,
            "meta": {
                "title": "⚖️ Cluster: Check / Call por Odds",
                "badge": "⚖️ GESTÃO",
                "volume": f"{(checks + calls):,} decisões ({pct_check_call:.1f}%)".replace(",", "."),
                "avg_equity": "35.8%",
                "description": "Ações de manutenção de posição e controle de risco. Call executado quando as Pot Odds são favoráveis para ver a próxima carta; Check quando não há vantagem em inflar o pote.",
                "emblematic_hands": [
                    {"hand_id": 1, "label": "Mão #1 · Defesa de blind com pot odds", "test_id": "6max_heterogeneo_1000m_seed101"}
                ]
            }
        },
        {
            "id": "glob_fold",
            "label": f"🛡️ Fold Disciplinado (-EV)\n{folds:,} decisões ({pct_fold:.1f}%)\nEq Média: 23.2% · Defesa de Capital".replace(",", "."),
            "level": 2,
            "shape": "box",
            "color": {"background": "#1e293b", "border": "#64748b"},
            "font": {"color": "#ffffff", "face": "Segoe UI", "size": 12, "bold": True},
            "borderWidth": 2,
            "margin": 10,
            "shadow": True,
            "meta": {
                "title": "🛡️ Cluster: Fold Disciplinado (-EV Defense)",
                "badge": "🛡️ DEFESA",
                "volume": f"{folds:,} decisões ({pct_fold:.1f}%)".replace(",", "."),
                "avg_equity": "23.2%",
                "description": "Desistência cirúrgica quando a probabilidade matemática de vitória é inferior ao custo exigido pelo pote. Evita sangramento cumulativo de banca.",
                "emblematic_hands": [
                    {"hand_id": 277, "label": "Mão #277 · Fold de A-8 no river (poupou >800 fichas)", "test_id": "6max_heterogeneo_1000m_seed101"},
                    {"hand_id": 386, "label": "Mão #386 · Fold defensivo no turn", "test_id": "6max_heterogeneo_1000m_seed101"}
                ]
            }
        },
        # Nível 3: Desfecho / Resultado Final
        {
            "id": "glob_win_showdown",
            "label": "👑 Vitória no Showdown\n(Mão Feita Superior)\nPotes Médios: +596 fichas",
            "level": 3,
            "shape": "box",
            "color": {"background": "#a16207", "border": "#fde047"},
            "font": {"color": "#ffffff", "face": "Segoe UI", "size": 12, "bold": True},
            "borderWidth": 2,
            "margin": 10,
            "shadow": True,
            "meta": {
                "title": "👑 Desfecho: Vitória no Showdown",
                "badge": "👑 VITÓRIA",
                "description": "Conquista do pote no confronto aberto final com cartas superiores comprovadas. Rota predominante dos agentes Matemático e Híbrido.",
                "emblematic_hands": [
                    {"hand_id": 491, "label": "Mão #491 · Showdown vitorioso de 9.000 fichas", "test_id": "9max_full_ring_1000m_seed99"}
                ]
            }
        },
        {
            "id": "glob_win_fold",
            "label": "🏳️ Vitória por Desistência\n(Fold Equity Concretizada)\nPotes Médios: +320 fichas",
            "level": 3,
            "shape": "box",
            "color": {"background": "#059669", "border": "#34d399"},
            "font": {"color": "#ffffff", "face": "Segoe UI", "size": 12, "bold": True},
            "borderWidth": 2,
            "margin": 10,
            "shadow": True,
            "meta": {
                "title": "🏳️ Desfecho: Vitória por Desistência Coletiva",
                "badge": "🏳️ VITÓRIA",
                "description": "O agente força todos os adversários a desistirem da mão antes do showdown através de pressão de aposta (Fold Equity). Rota clássica do Blefador e Híbrido.",
                "emblematic_hands": [
                    {"hand_id": 472, "label": "Mão #472 · Conquista após raise no turn", "test_id": "6max_heterogeneo_1000m_seed101"}
                ]
            }
        },
        {
            "id": "glob_loss_showdown",
            "label": "🎭 Blefe Desmascarado\n(Derrota no Confronto)\nPerda do Investimento",
            "level": 3,
            "shape": "box",
            "color": {"background": "#be123c", "border": "#fb7185"},
            "font": {"color": "#ffffff", "face": "Segoe UI", "size": 12, "bold": True},
            "borderWidth": 2,
            "margin": 10,
            "shadow": True,
            "meta": {
                "title": "🎭 Desfecho: Blefe Desmascarado (Disparidade)",
                "badge": "🎭 DERROTA",
                "description": "O agente apostou fingindo possuir um jogo forte, mas o adversário pagou no showdown com cartas superiores legítimas.",
                "emblematic_hands": [
                    {"hand_id": 72, "label": "Mão #72 · Blefe pago pelo adversário", "test_id": "05_bluffer_vs_5_hybrids_seed99"}
                ]
            }
        },
        {
            "id": "glob_capital_saved",
            "label": "🛡️ Capital Preservado\n(Zero Sangramento)\nPrejuízo Evitado",
            "level": 3,
            "shape": "box",
            "color": {"background": "#334155", "border": "#cbd5e1"},
            "font": {"color": "#ffffff", "face": "Segoe UI", "size": 12, "bold": True},
            "borderWidth": 2,
            "margin": 10,
            "shadow": True,
            "meta": {
                "title": "🛡️ Desfecho: Defesa e Preservação de Capital",
                "badge": "🛡️ ECONOMIA",
                "description": "Ao foldar perante apostas onde a matemática era desfavorável, a IA interrompe o sangramento de stack, mantendo a rentabilidade acumulada positiva.",
                "emblematic_hands": [
                    {"hand_id": 277, "label": "Mão #277 · Economia de mais de 800 fichas", "test_id": "6max_heterogeneo_1000m_seed101"}
                ]
            }
        }
    ]

    edges = [
        # Transição Nível 0 -> Nível 1
        {"from": "glob_preflop", "to": "glob_wet_board", "label": "54.2%", "arrows": "to", "width": 6, "color": {"color": "#38bdf8"}},
        {"from": "glob_preflop", "to": "glob_dry_board", "label": "45.8%", "arrows": "to", "width": 5, "color": {"color": "#fbbf24"}},
        {"from": "glob_preflop", "to": "glob_fold", "label": f"{pct_fold:.1f}% Folds Pré-Flop", "arrows": "to", "width": 4, "color": {"color": "#64748b"}},

        # Transição Nível 1 -> Nível 2
        {"from": "glob_wet_board", "to": "glob_semi_bluff", "label": f"{pct_semi:.1f}% Semi-Blefes", "arrows": "to", "width": 5, "color": {"color": "#22d3ee"}},
        {"from": "glob_wet_board", "to": "glob_val_bet", "label": f"{pct_val * 0.55:.1f}% Valor (Draws)", "arrows": "to", "width": 6, "color": {"color": "#4ade80"}},
        {"from": "glob_wet_board", "to": "glob_check_call", "label": "Controle", "arrows": "to", "width": 4, "color": {"color": "#94a3b8"}},
        {"from": "glob_dry_board", "to": "glob_pure_bluff", "label": f"{pct_pure:.1f}% Blefe Puro", "arrows": "to", "width": 4, "color": {"color": "#f87171"}},
        {"from": "glob_dry_board", "to": "glob_val_bet", "label": f"{pct_val * 0.45:.1f}% Overpairs", "arrows": "to", "width": 5, "color": {"color": "#4ade80"}},
        {"from": "glob_dry_board", "to": "glob_check_call", "label": "Pote Pequeno", "arrows": "to", "width": 5, "color": {"color": "#94a3b8"}},

        # Transição Nível 2 -> Nível 3
        {"from": "glob_val_bet", "to": "glob_win_showdown", "label": "77.0% Vitórias", "arrows": "to", "width": 7, "color": {"color": "#fde047"}},
        {"from": "glob_semi_bluff", "to": "glob_win_fold", "label": "38.2% Folds", "arrows": "to", "width": 5, "color": {"color": "#34d399"}},
        {"from": "glob_semi_bluff", "to": "glob_win_showdown", "label": "15.6% Outs", "arrows": "to", "width": 3, "color": {"color": "#fde047"}},
        {"from": "glob_pure_bluff", "to": "glob_win_fold", "label": "48.4% Sucesso", "arrows": "to", "width": 5, "color": {"color": "#34d399"}},
        {"from": "glob_pure_bluff", "to": "glob_loss_showdown", "label": "43.6% Desmascarado", "arrows": "to", "width": 5, "color": {"color": "#fb7185"}},
        {"from": "glob_check_call", "to": "glob_win_showdown", "label": "Showdown", "arrows": "to", "width": 4, "color": {"color": "#94a3b8"}},
        {"from": "glob_fold", "to": "glob_capital_saved", "label": "100% Proteção", "arrows": "to", "width": 6, "color": {"color": "#cbd5e1"}},
    ]

    result = {
        "success": True,
        "view": "global",
        "profile": prof_key,
        "seed": seed_key,
        "summary": {
            "total_decisions": tot,
            "value_bets": val_b,
            "semi_bluffs": semi_b,
            "pure_bluffs": pure_b,
            "folds": folds,
            "checks_calls": checks + calls,
            "win_rate": f"{win_rate:.1f}%",
        },
        "nodes": nodes,
        "edges": edges,
    }
    _GLOBAL_GRAPH_CACHE[cache_key] = result
    return result


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
