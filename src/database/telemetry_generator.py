"""Módulo de Geração e Exportação de Telemetria Cognitiva e Análise de Blefes (TCC).

Produz duas tabelas relacionais fundamentais para a pesquisa:
1. `game_actions.csv`: Histórico cronológico das ações da mesa (Ações do jogo).
2. `decision_telemetry_and_bluffs.csv`: Motivação da IA (XAI), equidade, Pot Odds,
   Expected Value, detecção de blefe, classificação do tipo e rastreamento de como
   o blefe foi aceito (Fold do vilão) ou recusado (Call/Raise do vilão).
"""

import csv
from dataclasses import asdict, dataclass
from enum import Enum
import os
from pathlib import Path
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.agents.base import BaseAgent
from src.database.recorder import build_research_roster
from src.engine.deck import Card
from src.engine.equity import has_flush_draw, has_straight_draw
from src.engine.hand_eval import evaluate_hand
from src.engine.player import Player
from src.engine.table import Action, ActionType, Street, Table


class BluffType(str, Enum):
    """Classificação científica da intenção e mecânica do blefe."""

    NONE = "NONE"
    PURE_BLUFF = "PURE_BLUFF"
    SEMI_BLUFF = "SEMI_BLUFF"
    CBET_BLUFF = "CBET_BLUFF"
    STEAL_BLUFF = "STEAL_BLUFF"
    BLOCKER_BLUFF = "BLOCKER_BLUFF"


class OpponentResponse(str, Enum):
    """Reação dos adversários na mesa diante da aposta/aumento."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    ACCEPTED_ALL_FOLD = "ACCEPTED_ALL_FOLD"
    REFUSED_CALLED = "REFUSED_CALLED"
    REFUSED_RAISED = "REFUSED_RAISED"


class BluffOutcome(str, Enum):
    """Desfecho final da mão decorrente da tentativa de blefe."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    SUCCESS_UNCONTESTED = "SUCCESS_UNCONTESTED"
    SUCCESS_CONVERTED = "SUCCESS_CONVERTED"
    FAILED_FOLDED_LATER = "FAILED_FOLDED_LATER"
    FAILED_SHOWDOWN_LOST = "FAILED_SHOWDOWN_LOST"


@dataclass
class GameActionRecord:
    """Tabela 1: Registro de cada ação física executada na mesa."""

    action_id: str
    hand_id: int
    step_order: int
    street: str
    player_id: str
    player_name: str
    profile: str
    hole_cards: str
    community_cards: str
    action_type: str
    amount: int
    pot_before: int
    pot_after: int
    player_stack_before: int
    player_stack_after: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionTelemetryRecord:
    """Tabela 2: Telemetria cognitiva, explicabilidade (XAI) e desfecho de blefe."""

    action_id: str
    hand_id: int
    player_id: str
    player_name: str
    profile: str
    street: str
    action_taken: str
    amount: int
    decision_mode: str
    raw_equity: float
    pot_odds: float
    expected_value: float
    outs_count: int
    tactical_reason: str
    is_bluff: bool
    bluff_type: str
    opponent_response: str
    bluff_outcome: str
    net_bluff_chips: int
    hand_result: str
    showdown_occurred: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _format_cards(cards: Optional[Sequence[Card]]) -> str:
    """Formata lista de cartas para exibição tabular limpa."""
    if not cards:
        return ""
    return " ".join(str(c) for c in cards)


def _extract_cognitive_metrics(
    bot: BaseAgent,
    actor: Player,
    table: Table,
    action: Action,
    profile: str,
) -> Tuple[str, float, float, float, int, str, bool, Optional[str]]:
    """Extrai ou calcula as métricas cognitivas e de justificativa da decisão."""
    decision_mode = "STANDARD"
    raw_equity = 0.50
    pot_odds = 0.0
    expected_value = 0.0
    outs_count = 0
    tactical_reason = f"Ação heurística padrão ({action.action_type.value})"
    is_bluff_intent = False
    bluff_tactic_hint: Optional[str] = None

    highest_bet = getattr(table, "_current_highest_bet", 0)
    to_call = max(0, highest_bet - actor.current_bet)
    pot_total = table.pot_manager.total_pot
    if pot_total + to_call > 0:
        pot_odds = round(to_call / (pot_total + to_call), 4)

    # 1. Agente Híbrido
    if hasattr(bot, "last_decision") and bot.last_decision is not None:
        dec = bot.last_decision
        if hasattr(dec, "mode") and hasattr(dec, "is_deceptive"):
            decision_mode = str(dec.mode).upper()
            raw_equity = round(float(getattr(dec, "equity", 0.50)), 4)
            pot_odds = round(float(getattr(dec, "pot_odds", pot_odds)), 4)
            expected_value = round(float(getattr(dec, "expected_value", 0.0)), 2)
            outs_count = int(getattr(dec, "outs", 0))
            tactical_reason = str(getattr(dec, "reason", ""))
            is_bluff_intent = bool(dec.is_deceptive or dec.mode in ("semi_bluff", "pure_bluff"))
            if dec.mode == "semi_bluff":
                bluff_tactic_hint = "SEMI_BLUFF"
            elif dec.mode == "pure_bluff":
                bluff_tactic_hint = "PURE_BLUFF"
            return (
                decision_mode,
                raw_equity,
                pot_odds,
                expected_value,
                outs_count,
                tactical_reason,
                is_bluff_intent,
                bluff_tactic_hint,
            )

        # 2. Agente Blefador (BlufferAgent)
        if hasattr(dec, "is_bluff") and hasattr(dec, "tactic"):
            is_bluff_intent = bool(dec.is_bluff)
            decision_mode = str(dec.tactic).upper() if dec.tactic else ("BLUFF" if is_bluff_intent else "VALUE")
            raw_equity = round(float(getattr(dec, "equity", 0.35)), 4)
            pot_odds = round(float(getattr(dec, "pot_odds", pot_odds)), 4)
            expected_value = round(float(getattr(dec, "expected_value", 0.0)), 2)
            outs_count = int(getattr(dec, "outs", 0))
            tactical_reason = str(getattr(dec, "reason", ""))
            tactic_str = str(dec.tactic).lower()
            if "semi" in tactic_str:
                bluff_tactic_hint = "SEMI_BLUFF"
            elif "cbet" in tactic_str:
                bluff_tactic_hint = "CBET_BLUFF"
            elif "steal" in tactic_str:
                bluff_tactic_hint = "STEAL_BLUFF"
            elif is_bluff_intent:
                bluff_tactic_hint = "PURE_BLUFF"
            return (
                decision_mode,
                raw_equity,
                pot_odds,
                expected_value,
                outs_count,
                tactical_reason,
                is_bluff_intent,
                bluff_tactic_hint,
            )

        # 3. Agente com Telemetria Rica (GhMath / GhBluffer)
        if hasattr(dec, "metrics"):
            m = dec.metrics
            raw_equity = round(float(getattr(m, "raw_equity", 0.50)), 4)
            pot_odds = round(float(getattr(m, "direct_pot_odds", pot_odds)), 4)
            outs_count = int(getattr(m, "outs_count", 0))
            tactical_reason = str(getattr(m, "tactical_rationale", ""))
            expected_value = round(
                float(
                    getattr(m, "expected_value_raise", 0.0)
                    if action.action_type in (ActionType.BET, ActionType.RAISE)
                    else getattr(m, "expected_value_call", 0.0)
                ),
                2,
            )
            decision_mode = "XAI_METRIC"
            if raw_equity < 0.35 and action.action_type in (ActionType.BET, ActionType.RAISE):
                is_bluff_intent = True
                bluff_tactic_hint = "BLOCKER_BLUFF" if "blocker" in tactical_reason.lower() else "PURE_BLUFF"
            return (
                decision_mode,
                raw_equity,
                pot_odds,
                expected_value,
                outs_count,
                tactical_reason,
                is_bluff_intent,
                bluff_tactic_hint,
            )

        # 4. Agente Matemático Tradicional (MathematicalAgent)
        if hasattr(dec, "equity") and hasattr(dec, "reason"):
            raw_equity = round(float(getattr(dec, "equity", 0.50)), 4)
            pot_odds = round(float(getattr(dec, "pot_odds", pot_odds)), 4)
            expected_value = round(float(getattr(dec, "expected_value", 0.0)), 2)
            outs_count = int(getattr(dec, "outs", getattr(dec, "outs_count", 0)))
            tactical_reason = str(getattr(dec, "reason", ""))
            decision_mode = "MATHEMATICAL"
            return (
                decision_mode,
                raw_equity,
                pot_odds,
                expected_value,
                outs_count,
                tactical_reason,
                False,
                None,
            )

    # 5. Fallback para Bot Heurístico
    decision_mode = f"HEURISTIC_{profile.upper()}"
    if action.action_type == ActionType.FOLD:
        tactical_reason = "Desistência baseada no perfil heurístico conservador/equilibrado"
    elif action.action_type in (ActionType.BET, ActionType.RAISE):
        tactical_reason = f"Agressão heurística de aposta ({profile})"
        if "Agressivo" in profile and raw_equity < 0.38:
            is_bluff_intent = True
            bluff_tactic_hint = "PURE_BLUFF"
    elif action.action_type == ActionType.CHECK:
        tactical_reason = "Controle de pote heurístico sem aposta ativa"
    else:
        tactical_reason = "Pagamento heurístico para disputar a rodada"

    return (
        decision_mode,
        raw_equity,
        pot_odds,
        expected_value,
        outs_count,
        tactical_reason,
        is_bluff_intent,
        bluff_tactic_hint,
    )


def _classify_bluff(
    is_bluff_intent: bool,
    bluff_tactic_hint: Optional[str],
    action_type: ActionType,
    street: Street,
    actor: Player,
    table: Table,
    raw_equity: float,
    outs_count: int,
) -> Tuple[bool, BluffType]:
    """Classifica se uma ação foi blefe e determina sua taxonomia exata."""
    if action_type not in (ActionType.BET, ActionType.RAISE):
        return False, BluffType.NONE

    # Verifica se a mão atual é de força baixa
    all_cards = list(actor.hole_cards) + list(table.community_cards)
    is_weak_hand = True
    if len(all_cards) >= 5:
        score = evaluate_hand(all_cards)
        # Carta Alta (1) ou Par Baixo (2)
        is_weak_hand = score.hand_rank.value <= 2
    else:
        c1, c2 = actor.hole_cards[0], actor.hole_cards[1]
        is_weak_hand = (c1.rank.value != c2.rank.value) and (max(c1.rank.value, c2.rank.value) < 12)

    has_project = False
    if len(all_cards) >= 5:
        has_project = has_flush_draw(all_cards) or has_straight_draw(all_cards) or outs_count >= 8

    # Confirmação de Blefe
    if is_bluff_intent or (is_weak_hand and raw_equity < 0.42):
        if bluff_tactic_hint == "SEMI_BLUFF" or has_project:
            return True, BluffType.SEMI_BLUFF
        if bluff_tactic_hint == "CBET_BLUFF" or (street == Street.FLOP and is_weak_hand):
            return True, BluffType.CBET_BLUFF
        if bluff_tactic_hint == "STEAL_BLUFF" or (street == Street.PREFLOP and is_weak_hand):
            return True, BluffType.STEAL_BLUFF
        if bluff_tactic_hint == "BLOCKER_BLUFF":
            return True, BluffType.BLOCKER_BLUFF
        return True, BluffType.PURE_BLUFF

    return False, BluffType.NONE


def simulate_and_generate_telemetry(
    num_hands: int = 50,
    roster_mode: str = "tier_s_duelo",
    starting_stack: int = 1000,
    small_blind: int = 10,
    big_blind: int = 20,
    rng_seed: Optional[int] = 42,
    custom_seats: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
    test_id: Optional[str] = None,
) -> Tuple[List[GameActionRecord], List[DecisionTelemetryRecord], Dict[str, Any]]:
    """Simula rodadas e gera as duas tabelas completas de dados organizadas por ID de teste."""
    from datetime import datetime, timezone

    if not test_id:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_roster = roster_mode.replace(" ", "_").lower()
        test_id = f"test_{timestamp_str}_{clean_roster}"

    rng = random.Random(rng_seed)
    players, agents, profile_labels = build_research_roster(
        starting_stack=starting_stack,
        roster_mode=roster_mode,
        rng=rng,
        custom_seats=custom_seats,
    )

    all_action_records: List[GameActionRecord] = []
    all_telemetry_records: List[DecisionTelemetryRecord] = []

    button_idx = 0
    bluffs_summary: Dict[str, Any] = {
        "test_id": test_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "num_hands": num_hands,
        "roster_mode": roster_mode,
        "rng_seed": rng_seed,
        "total_bluffs": 0,
        "pure_bluffs": 0,
        "semi_bluffs": 0,
        "cbet_bluffs": 0,
        "steal_bluffs": 0,
        "blocker_bluffs": 0,
        "accepted_folds": 0,
        "refused_calls": 0,
        "refused_raises": 0,
        "successful_outcomes": 0,
        "failed_outcomes": 0,
    }

    for hand_idx in range(1, num_hands + 1):
        active_players = [p for p in players if p.stack > 0]
        if len(active_players) < 2:
            for p in players:
                p.stack = starting_stack
            active_players = players

        stacks_before_hand = {p.player_id: p.stack for p in active_players}

        table = Table(
            players=active_players,
            small_blind=small_blind,
            big_blind=big_blind,
            rng=rng,
            button_idx=button_idx,
        )
        table.start_new_hand(rng=rng)

        hand_actions: List[Tuple[GameActionRecord, Dict[str, Any]]] = []
        action_step = 1

        # Executa as ações na mesa
        while table.street not in (Street.FINISHED, Street.SHOWDOWN):
            actor = table.current_player
            if actor is None:
                break

            bot = agents[actor.player_id]
            pid = actor.player_id
            pname = actor.name
            profile = profile_labels.get(pid, "Desconhecido")
            street_name = table.street.name

            pot_before = table.pot_manager.total_pot
            stack_before = actor.stack

            # IA decide
            action = bot.decide_action(table)

            (
                decision_mode,
                raw_equity,
                pot_odds,
                ev,
                outs,
                tactical_reason,
                is_bluff_intent,
                bluff_hint,
            ) = _extract_cognitive_metrics(
                bot=bot,
                actor=actor,
                table=table,
                action=action,
                profile=profile,
            )

            is_bluff, bluff_type = _classify_bluff(
                is_bluff_intent=is_bluff_intent,
                bluff_tactic_hint=bluff_hint,
                action_type=action.action_type,
                street=table.street,
                actor=actor,
                table=table,
                raw_equity=raw_equity,
                outs_count=outs,
            )

            # Aplica a ação
            table.apply_action(action)

            pot_after = table.pot_manager.total_pot
            stack_after = actor.stack
            action_id = f"H{hand_idx:05d}_S{action_step:03d}_{pid}"

            action_rec = GameActionRecord(
                action_id=action_id,
                hand_id=hand_idx,
                step_order=action_step,
                street=street_name,
                player_id=pid,
                player_name=pname,
                profile=profile,
                hole_cards=_format_cards(actor.hole_cards),
                community_cards=_format_cards(table.community_cards),
                action_type=action.action_type.value,
                amount=action.amount,
                pot_before=pot_before,
                pot_after=pot_after,
                player_stack_before=stack_before,
                player_stack_after=stack_after,
            )

            meta = {
                "decision_mode": decision_mode,
                "raw_equity": raw_equity,
                "pot_odds": pot_odds,
                "expected_value": ev,
                "outs_count": outs,
                "tactical_reason": tactical_reason,
                "is_bluff": is_bluff,
                "bluff_type": bluff_type.value,
                "action_type": action.action_type,
                "amount": action.amount,
                "actor_id": pid,
            }

            hand_actions.append((action_rec, meta))
            action_step += 1

        # Fim da mão: determina os vencedores e o saldo
        button_idx = table.button_idx
        payouts = table.last_payouts
        winners = [pid for pid, amt in payouts.items() if amt > 0]
        showdown_occurred = table.street == Street.SHOWDOWN

        # Rastreia desfecho de cada ação e de cada blefe na mão
        for i, (act_rec, meta) in enumerate(hand_actions):
            is_bluff = meta["is_bluff"]
            bluff_type_str = meta["bluff_type"]
            actor_id = meta["actor_id"]

            opp_response = OpponentResponse.NOT_APPLICABLE.value
            outcome = BluffOutcome.NOT_APPLICABLE.value
            net_bluff_chips = 0

            # Determina resultado da mão para o jogador
            if actor_id in winners:
                hand_res = "WON_HAND" if len(winners) == 1 else "SPLIT_POT"
            else:
                hand_res = "LOST_HAND"

            if is_bluff:
                bluffs_summary["total_bluffs"] += 1
                if bluff_type_str == BluffType.PURE_BLUFF.value:
                    bluffs_summary["pure_bluffs"] += 1
                elif bluff_type_str == BluffType.SEMI_BLUFF.value:
                    bluffs_summary["semi_bluffs"] += 1
                elif bluff_type_str == BluffType.CBET_BLUFF.value:
                    bluffs_summary["cbet_bluffs"] += 1
                elif bluff_type_str == BluffType.STEAL_BLUFF.value:
                    bluffs_summary["steal_bluffs"] += 1
                elif bluff_type_str == BluffType.BLOCKER_BLUFF.value:
                    bluffs_summary["blocker_bluffs"] += 1

                # Avalia as reações subsequentes de outros jogadores na mão
                subsequent_actions = hand_actions[i + 1 :]
                sub_opp_actions = [
                    a for a, m in subsequent_actions if m["actor_id"] != actor_id
                ]

                has_raise = any(
                    a.action_type in ("RAISE", "ALL_IN") for a in sub_opp_actions
                )
                has_call = any(
                    a.action_type == "CALL" for a in sub_opp_actions
                )
                all_folded = (
                    len(sub_opp_actions) > 0
                    and all(a.action_type == "FOLD" for a in sub_opp_actions)
                )

                if has_raise:
                    opp_response = OpponentResponse.REFUSED_RAISED.value
                    bluffs_summary["refused_raises"] += 1
                    if actor_id not in winners:
                        outcome = BluffOutcome.FAILED_FOLDED_LATER.value
                        bluffs_summary["failed_outcomes"] += 1
                    else:
                        outcome = BluffOutcome.SUCCESS_CONVERTED.value
                        bluffs_summary["successful_outcomes"] += 1
                elif has_call:
                    opp_response = OpponentResponse.REFUSED_CALLED.value
                    bluffs_summary["refused_calls"] += 1
                    if actor_id in winners:
                        outcome = BluffOutcome.SUCCESS_CONVERTED.value
                        bluffs_summary["successful_outcomes"] += 1
                    else:
                        outcome = (
                            BluffOutcome.FAILED_SHOWDOWN_LOST.value
                            if showdown_occurred
                            else BluffOutcome.FAILED_FOLDED_LATER.value
                        )
                        bluffs_summary["failed_outcomes"] += 1
                else:
                    opp_response = OpponentResponse.ACCEPTED_ALL_FOLD.value
                    outcome = BluffOutcome.SUCCESS_UNCONTESTED.value
                    bluffs_summary["accepted_folds"] += 1
                    bluffs_summary["successful_outcomes"] += 1

                # Cálculo de fichas líquidas da mão para o jogador
                curr_p = next((p for p in table.players if p.player_id == actor_id), None)
                final_stack = curr_p.stack if curr_p is not None else stacks_before_hand.get(actor_id, 0)
                net_bluff_chips = final_stack - stacks_before_hand.get(actor_id, 0)

            telemetry_rec = DecisionTelemetryRecord(
                action_id=act_rec.action_id,
                hand_id=act_rec.hand_id,
                player_id=act_rec.player_id,
                player_name=act_rec.player_name,
                profile=act_rec.profile,
                street=act_rec.street,
                action_taken=act_rec.action_type,
                amount=act_rec.amount,
                decision_mode=meta["decision_mode"],
                raw_equity=meta["raw_equity"],
                pot_odds=meta["pot_odds"],
                expected_value=meta["expected_value"],
                outs_count=meta["outs_count"],
                tactical_reason=meta["tactical_reason"],
                is_bluff=is_bluff,
                bluff_type=bluff_type_str,
                opponent_response=opp_response,
                bluff_outcome=outcome,
                net_bluff_chips=net_bluff_chips,
                hand_result=hand_res,
                showdown_occurred=showdown_occurred,
            )

            all_action_records.append(act_rec)
            all_telemetry_records.append(telemetry_rec)

    # Exportação para CSV e JSON organizados pelo ID do teste
    if output_dir:
        import json

        base_path = Path(output_dir)
        test_dir = base_path if base_path.name == test_id else (base_path / test_id)
        test_dir.mkdir(parents=True, exist_ok=True)

        bluffs_summary["test_dir"] = str(test_dir)

        actions_csv = test_dir / "game_actions.csv"
        telemetry_csv = test_dir / "decision_telemetry_and_bluffs.csv"
        summary_json = test_dir / "summary.json"

        if all_action_records:
            fieldnames = list(all_action_records[0].to_dict().keys())
            with open(actions_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for rec in all_action_records:
                    writer.writerow(rec.to_dict())

            # Também atualiza na raiz para acesso rápido do último teste
            if base_path != test_dir:
                base_path.mkdir(parents=True, exist_ok=True)
                latest_actions_csv = base_path / "game_actions.csv"
                with open(latest_actions_csv, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for rec in all_action_records:
                        writer.writerow(rec.to_dict())

        if all_telemetry_records:
            fieldnames_tel = list(all_telemetry_records[0].to_dict().keys())
            with open(telemetry_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames_tel)
                writer.writeheader()
                for rec in all_telemetry_records:
                    writer.writerow(rec.to_dict())

            # Também atualiza na raiz para acesso rápido do último teste
            if base_path != test_dir:
                latest_telemetry_csv = base_path / "decision_telemetry_and_bluffs.csv"
                with open(latest_telemetry_csv, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames_tel)
                    writer.writeheader()
                    for rec in all_telemetry_records:
                        writer.writerow(rec.to_dict())

        with open(summary_json, "w", encoding="utf-8") as f:
            json.dump(bluffs_summary, f, indent=2, ensure_ascii=False)

    return all_action_records, all_telemetry_records, bluffs_summary


def ensure_telemetry_neon_schema(conn: Any) -> bool:
    """Garante que as tabelas de telemetria e ações existam no PostgreSQL / Neon."""
    schema_sql = """
    CREATE TABLE IF NOT EXISTS game_actions (
        action_id VARCHAR(64) PRIMARY KEY,
        hand_id INT,
        step_order INT,
        street VARCHAR(16),
        player_id VARCHAR(64),
        player_name VARCHAR(128),
        profile VARCHAR(64),
        hole_cards VARCHAR(32),
        community_cards VARCHAR(64),
        action_type VARCHAR(16),
        amount INT,
        pot_before INT,
        pot_after INT,
        player_stack_before INT,
        player_stack_after INT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS decision_telemetry_and_bluffs (
        action_id VARCHAR(64) PRIMARY KEY,
        hand_id INT,
        player_id VARCHAR(64),
        player_name VARCHAR(128),
        profile VARCHAR(64),
        street VARCHAR(16),
        action_taken VARCHAR(16),
        amount INT,
        decision_mode VARCHAR(64),
        raw_equity NUMERIC(6, 4),
        pot_odds NUMERIC(6, 4),
        expected_value NUMERIC(10, 2),
        outs_count INT,
        tactical_reason TEXT,
        is_bluff BOOLEAN,
        bluff_type VARCHAR(32),
        opponent_response VARCHAR(32),
        bluff_outcome VARCHAR(32),
        net_bluff_chips INT,
        hand_result VARCHAR(16),
        showdown_occurred BOOLEAN,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_telemetry_hand ON decision_telemetry_and_bluffs(hand_id);
    CREATE INDEX IF NOT EXISTS idx_telemetry_profile ON decision_telemetry_and_bluffs(profile);
    CREATE INDEX IF NOT EXISTS idx_telemetry_bluff ON decision_telemetry_and_bluffs(is_bluff, bluff_type);
    """
    cur = conn.cursor()
    try:
        cur.execute(schema_sql)
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


def save_telemetry_to_neon(
    actions: List[GameActionRecord],
    telemetry: List[DecisionTelemetryRecord],
    custom_url: Optional[str] = None,
) -> Tuple[bool, int, Optional[str]]:
    """Insere em lote os registros de ações e telemetria no Neon PostgreSQL."""
    from src.database.recorder import get_neon_connection

    conn = get_neon_connection(custom_url=custom_url)
    if conn is None:
        return False, 0, "Falha ao conectar ao banco de dados Neon. Verifique a DATABASE_URL."

    if not ensure_telemetry_neon_schema(conn):
        return False, 0, "Falha ao inicializar esquema das tabelas no Neon."

    cur = conn.cursor()
    inserted = 0
    try:
        # 1. Inserção de game_actions (upsert / ignore conflitos)
        insert_act_sql = """
        INSERT INTO game_actions (
            action_id, hand_id, step_order, street, player_id, player_name,
            profile, hole_cards, community_cards, action_type, amount,
            pot_before, pot_after, player_stack_before, player_stack_after
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON CONFLICT (action_id) DO NOTHING;
        """
        for a in actions:
            cur.execute(
                insert_act_sql,
                (
                    a.action_id,
                    a.hand_id,
                    a.step_order,
                    a.street,
                    a.player_id,
                    a.player_name,
                    a.profile,
                    a.hole_cards,
                    a.community_cards,
                    a.action_type,
                    a.amount,
                    a.pot_before,
                    a.pot_after,
                    a.player_stack_before,
                    a.player_stack_after,
                ),
            )

        # 2. Inserção de decision_telemetry_and_bluffs
        insert_tel_sql = """
        INSERT INTO decision_telemetry_and_bluffs (
            action_id, hand_id, player_id, player_name, profile, street,
            action_taken, amount, decision_mode, raw_equity, pot_odds,
            expected_value, outs_count, tactical_reason, is_bluff,
            bluff_type, opponent_response, bluff_outcome, net_bluff_chips,
            hand_result, showdown_occurred
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) ON CONFLICT (action_id) DO UPDATE SET
            opponent_response = EXCLUDED.opponent_response,
            bluff_outcome = EXCLUDED.bluff_outcome,
            net_bluff_chips = EXCLUDED.net_bluff_chips;
        """
        for t in telemetry:
            cur.execute(
                insert_tel_sql,
                (
                    t.action_id,
                    t.hand_id,
                    t.player_id,
                    t.player_name,
                    t.profile,
                    t.street,
                    t.action_taken,
                    t.amount,
                    t.decision_mode,
                    t.raw_equity,
                    t.pot_odds,
                    t.expected_value,
                    t.outs_count,
                    t.tactical_reason,
                    t.is_bluff,
                    t.bluff_type,
                    t.opponent_response,
                    t.bluff_outcome,
                    t.net_bluff_chips,
                    t.hand_result,
                    t.showdown_occurred,
                ),
            )
            inserted += 1

        conn.commit()
        return True, inserted, None
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, 0, f"Erro ao inserir dados no Neon: {str(e)}"
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


def get_neon_telemetry_stats(custom_url: Optional[str] = None) -> Dict[str, Any]:
    """Consulta e consolida as métricas de telemetria e blefes salvas no Neon PostgreSQL."""
    from src.database.recorder import get_neon_connection

    conn = get_neon_connection(custom_url=custom_url)
    if conn is None:
        return {
            "success": False,
            "connected": False,
            "error": "Não foi possível conectar ao banco de dados Neon. Verifique a DATABASE_URL.",
        }

    try:
        cur = conn.cursor()

        # Verifica quais tabelas existem no schema public
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_name IN ('game_actions', 'decision_telemetry_and_bluffs', 'hands');
        """)
        existing_tables = set(r[0] for r in cur.fetchall())

        actions_count = 0
        telemetry_count = 0
        hands_count = 0
        total_bluffs = 0
        bluffs_by_type: Dict[str, int] = {}
        responses: Dict[str, int] = {}
        outcomes: Dict[str, int] = {}
        wins_by_profile: Dict[str, int] = {}

        if "hands" in existing_tables:
            cur.execute("SELECT count(*) FROM hands;")
            row = cur.fetchone()
            if row:
                hands_count = int(row[0])

        if "game_actions" in existing_tables:
            cur.execute("SELECT count(*) FROM game_actions;")
            row = cur.fetchone()
            if row:
                actions_count = int(row[0])

        if "decision_telemetry_and_bluffs" in existing_tables:
            cur.execute("SELECT count(*) FROM decision_telemetry_and_bluffs;")
            row = cur.fetchone()
            if row:
                telemetry_count = int(row[0])

            cur.execute(
                "SELECT count(*) FROM decision_telemetry_and_bluffs WHERE is_bluff = TRUE;"
            )
            row = cur.fetchone()
            if row:
                total_bluffs = int(row[0])

            cur.execute("""
                SELECT bluff_type, count(*) 
                FROM decision_telemetry_and_bluffs 
                WHERE is_bluff = TRUE 
                GROUP BY bluff_type 
                ORDER BY count(*) DESC;
            """)
            bluffs_by_type = dict(cur.fetchall())

            cur.execute("""
                SELECT opponent_response, count(*) 
                FROM decision_telemetry_and_bluffs 
                WHERE is_bluff = TRUE 
                GROUP BY opponent_response 
                ORDER BY count(*) DESC;
            """)
            responses = dict(cur.fetchall())

            cur.execute("""
                SELECT bluff_outcome, count(*) 
                FROM decision_telemetry_and_bluffs 
                WHERE is_bluff = TRUE 
                GROUP BY bluff_outcome 
                ORDER BY count(*) DESC;
            """)
            outcomes = dict(cur.fetchall())

            cur.execute("""
                SELECT profile, count(DISTINCT hand_id)
                FROM decision_telemetry_and_bluffs
                WHERE hand_result IN ('WON_HAND', 'SPLIT_POT')
                GROUP BY profile
                ORDER BY count(DISTINCT hand_id) DESC;
            """)
            wins_by_profile = dict(cur.fetchall())

        cur.close()
        conn.close()

        return {
            "success": True,
            "connected": True,
            "tables_found": list(existing_tables),
            "hands_count": hands_count,
            "actions_count": actions_count,
            "telemetry_count": telemetry_count,
            "total_bluffs": total_bluffs,
            "bluffs_by_type": bluffs_by_type,
            "opponent_responses": responses,
            "bluff_outcomes": outcomes,
            "wins_by_profile": wins_by_profile,
        }
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {
            "success": False,
            "connected": True,
            "error": f"Erro ao consultar telemetria no Neon: {str(e)}",
        }


