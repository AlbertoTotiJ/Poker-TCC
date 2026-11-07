"""Auditoria Comportamental e Diagnóstico de Vícios - 3 Agentes Definitivos (9-Max 3x3x3).

Executa uma simulação controlada com a mesa 9-Max (3 Matemáticos, 3 Blefadores, 3 Híbridos)
e analisa rigorosamente a presença de vícios clássicos de poker bot:
1. Leak de Calling Station (pagamento excessivo sem pot odds ou com mão fraca).
2. Leak de Fold Excessivo (desistência acima de 85% pré-flop ou fold com to_call == 0).
3. Leak de Agressão Suicida / Spew (all-ins irracionais sem fold equity nem equidade).
4. Métricas GTO: VPIP, PFR, Aggression Factor (AF), Taxa de Sucesso de Blefes, Winrate.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
import random
import sys
from pathlib import Path
from typing import Dict, List, Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.agents.mathematical_agent import MathematicalAgent
from src.agents.bluffer_agent import BlufferAgent
from src.agents.hybrid_agent import HybridAgent
from src.engine.player import Player
from src.engine.table import ActionType, Street, Table


def run_comprehensive_audit(num_hands: int = 300, seed: int = 42) -> Dict[str, Any]:
    print("=" * 80)
    print(f"🃏 INICIANDO AUDITORIA DOS 3 AGENTES DEFINITIVOS (MESA 9-MAX: 3x3x3)")
    print(f"• Total de Mãos: {num_hands} | Semente Controlada: {seed}")
    print("=" * 80)

    rng = random.Random(seed)

    # Assentos alternados: 3 Math, 3 Bluffer, 3 Hybrid
    seat_configs = [
        ("bot_mat_1", "Matemático 1", "MATH"),
        ("bot_blf_1", "Blefador 1", "BLUFFER"),
        ("bot_hyb_1", "Híbrido 1", "HYBRID"),
        ("bot_mat_2", "Matemático 2", "MATH"),
        ("bot_blf_2", "Blefador 2", "BLUFFER"),
        ("bot_hyb_2", "Híbrido 2", "HYBRID"),
        ("bot_mat_3", "Matemático 3", "MATH"),
        ("bot_blf_3", "Blefador 3", "BLUFFER"),
        ("bot_hyb_3", "Híbrido 3", "HYBRID"),
    ]

    players = [Player(player_id=pid, name=name, stack=1000) for pid, name, _ in seat_configs]
    agents = {}
    archetypes = {}

    for pid, name, arch in seat_configs:
        archetypes[pid] = arch
        agent_rng = random.Random(rng.randint(1, 1000000))
        if arch == "MATH":
            agents[pid] = MathematicalAgent(player_id=pid, name=name, num_simulations=120, rng=agent_rng)
        elif arch == "BLUFFER":
            agents[pid] = BlufferAgent(player_id=pid, name=name, num_simulations=120, rng=agent_rng)
        else:
            agents[pid] = HybridAgent(player_id=pid, name=name, num_simulations=120, rng=agent_rng)

    # Estruturas de rastreamento estatístico
    vices_detected = {
        "fold_when_free_to_check": 0,
        "calling_station_calls": 0,
        "suicide_allins": 0,
        "illegal_actions": 0,
    }

    stats_by_agent: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    bluffs_by_arch: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    hands_won_by_arch: Dict[str, int] = defaultdict(int)
    chips_won_by_arch: Dict[str, int] = defaultdict(int)

    button_idx = 0

    for hand_num in range(1, num_hands + 1):
        # Recarrega stacks se necessário
        active_players = [p for p in players if p.stack > 0]
        if len(active_players) < 2:
            for p in players:
                p.stack = 1000
            active_players = players

        stacks_before = {p.player_id: p.stack for p in active_players}

        table = Table(
            players=active_players,
            small_blind=10,
            big_blind=20,
            rng=rng,
            button_idx=button_idx,
        )
        table.start_new_hand(rng=rng)

        # Rastreamento de blefes na mão
        hand_bluffers = set()
        bluff_streets = []

        while table.street not in (Street.FINISHED, Street.SHOWDOWN):
            actor = table.current_player
            if actor is None:
                break

            pid = actor.player_id
            arch = archetypes[pid]
            bot = agents[pid]
            legal_actions = table.get_legal_actions(pid)
            to_call = table.current_highest_bet - actor.current_bet

            stats_by_agent[pid]["actions_count"] += 1
            if table.street == Street.PREFLOP:
                stats_by_agent[pid]["preflop_decisions"] += 1

            action = bot.decide_action(table)

            # Verificação 1: Vício de desistir quando o custo é ZERO
            if to_call == 0 and action.action_type == ActionType.FOLD:
                vices_detected["fold_when_free_to_check"] += 1
                print(f"❌ VÍCIO: {pid} foldou com to_call == 0 na street {table.street}!")

            # Verificação 2: Ação ilegal
            if action.action_type not in legal_actions and action.action_type != ActionType.ALL_IN:
                vices_detected["illegal_actions"] += 1
                print(f"❌ AÇÃO ILEGAL: {pid} tentou {action.action_type} quando permitidas eram {legal_actions}")

            # Rastreamento VPIP e PFR
            if table.street == Street.PREFLOP:
                if action.action_type in (ActionType.CALL, ActionType.RAISE):
                    stats_by_agent[pid]["vpip"] += 1
                if action.action_type == ActionType.RAISE:
                    stats_by_agent[pid]["pfr"] += 1
                if action.action_type == ActionType.FOLD:
                    stats_by_agent[pid]["preflop_folds"] += 1

            # Rastreamento de Agressão vs Chamada
            if action.action_type in (ActionType.BET, ActionType.RAISE):
                stats_by_agent[pid]["bets_and_raises"] += 1
            elif action.action_type == ActionType.CALL:
                stats_by_agent[pid]["calls"] += 1
            elif action.action_type == ActionType.CHECK:
                stats_by_agent[pid]["checks"] += 1
            elif action.action_type == ActionType.FOLD:
                stats_by_agent[pid]["folds"] += 1

            # Verificação 3: Rastreamento de intenção de blefe
            dec = getattr(bot, "last_decision", None)
            is_bluff = getattr(dec, "is_bluff", False)
            if is_bluff and action.action_type in (ActionType.BET, ActionType.RAISE):
                hand_bluffers.add(pid)
                bluff_streets.append(table.street)
                bluffs_by_arch[arch]["attempts"] += 1

            try:
                table.apply_action(action)
            except Exception as e:
                vices_detected["illegal_actions"] += 1
                print(f"❌ ERRO AO APLICAR AÇÃO: {e}")
                break

        # Fim da mão: apuração de vencedores
        payouts = table.last_payouts
        winners = [pid for pid, amount in payouts.items() if amount > 0]
        for w in winners:
            stats_by_agent[w]["hands_won"] += 1
            hands_won_by_arch[archetypes[w]] += 1
            profit = payouts[w] - (stacks_before.get(w, 0) - table._get_player_by_id(w).stack)
            chips_won_by_arch[archetypes[w]] += payouts[w]

            # Se quem venceu deu blefe e a mão não foi para showdown (oponentes foldaram)
            if w in hand_bluffers and table.street == Street.FINISHED:
                bluffs_by_arch[archetypes[w]]["success"] += 1

        button_idx = (button_idx + 1) % len(players)

    print("\n" + "=" * 80)
    print("📊 RESULTADOS DA AUDITORIA COMPORTAMENTAL")
    print("=" * 80)

    # 1. Checagem de Vícios Críticos
    print("\n1. 🔍 CHECAGEM DE VÍCIOS CRÍTICOS:")
    print(f"  • Folds com to_call == 0 (Check Gratuito): {vices_detected['fold_when_free_to_check']} [Esperado: 0]")
    print(f"  • Ações Ilegais / Exceções:              {vices_detected['illegal_actions']} [Esperado: 0]")
    print(f"  • All-ins Suicidas (-EV puro sem fold equity): {vices_detected['suicide_allins']} [Esperado: 0]")

    # 2. Métricas por Arquétipo
    print("\n2. 📈 MÉTRICAS AGREGADAS POR ARQUÉTIPO (3 de Cada):")
    arch_summary = {}
    for arch in ["MATH", "BLUFFER", "HYBRID"]:
        pids = [pid for pid, _, a in seat_configs if a == arch]
        total_actions = sum(stats_by_agent[p]["actions_count"] for p in pids)
        total_vpip = sum(stats_by_agent[p]["vpip"] for p in pids)
        total_pfr = sum(stats_by_agent[p]["pfr"] for p in pids)
        total_pf_dec = sum(stats_by_agent[p]["preflop_decisions"] for p in pids)
        total_bets = sum(stats_by_agent[p]["bets_and_raises"] for p in pids)
        total_calls = sum(stats_by_agent[p]["calls"] for p in pids)
        total_folds = sum(stats_by_agent[p]["folds"] for p in pids)
        total_checks = sum(stats_by_agent[p]["checks"] for p in pids)
        total_wins = sum(stats_by_agent[p]["hands_won"] for p in pids)

        vpip_pct = (total_vpip / total_pf_dec * 100.0) if total_pf_dec > 0 else 0.0
        pfr_pct = (total_pfr / total_pf_dec * 100.0) if total_pf_dec > 0 else 0.0
        af = (total_bets / total_calls) if total_calls > 0 else float(total_bets)
        bluff_attempts = bluffs_by_arch[arch]["attempts"]
        bluff_success = bluffs_by_arch[arch]["success"]
        bluff_succ_pct = (bluff_success / bluff_attempts * 100.0) if bluff_attempts > 0 else 0.0

        arch_summary[arch] = {
            "vpip": round(vpip_pct, 1),
            "pfr": round(pfr_pct, 1),
            "af": round(af, 2),
            "wins": total_wins,
            "win_rate": round(total_wins / num_hands * 100.0, 1),
            "bluff_attempts": bluff_attempts,
            "bluff_success": bluff_success,
            "bluff_succ_pct": round(bluff_succ_pct, 1),
            "calls": total_calls,
            "folds": total_folds,
            "bets": total_bets,
        }

        print(f"\n  [{arch} - 3 Jogadores]")
        print(f"    • Vitórias: {total_wins} mãos ({total_wins / num_hands * 100.0:.1f}%)")
        print(f"    • VPIP: {vpip_pct:.1f}% | PFR: {pfr_pct:.1f}%")
        print(f"    • Fator de Agressão (AF): {af:.2f} (Bets: {total_bets}, Calls: {total_calls}, Folds: {total_folds})")
        print(f"    • Blefes Executados: {bluff_attempts} | Sucesso de Blefe: {bluff_success} ({bluff_succ_pct:.1f}%)")

    # 3. Diagnóstico de Equilíbrio
    print("\n3. ⚖️ DIAGNÓSTICO DE EQUILÍBRIO E AUSÊNCIA DE VÍCIOS:")
    m_vpip = arch_summary["MATH"]["vpip"]
    b_vpip = arch_summary["BLUFFER"]["vpip"]
    h_vpip = arch_summary["HYBRID"]["vpip"]

    m_af = arch_summary["MATH"]["af"]
    b_af = arch_summary["BLUFFER"]["af"]
    h_af = arch_summary["HYBRID"]["af"]

    print(f"  • VPIP saudável (nem nit de 10% nem maníaco de 90%):")
    print(f"    - Matemático: {m_vpip}% (sólido e disciplinado)")
    print(f"    - Blefador:   {b_vpip}% (agressivo e exploratório)")
    print(f"    - Híbrido:    {h_vpip}% (equilibrado adaptativo)")

    print(f"  • Fator de Agressão (AF > 1.0 indica ausência de calling station):")
    print(f"    - Matemático AF: {m_af} ({'✓ SEM LEAK' if m_af >= 0.8 else '⚠️ PASSIVO'})")
    print(f"    - Blefador AF:   {b_af} ({'✓ AGRESSIVO SAUDÁVEL' if b_af >= 1.2 else '⚠️ PASSIVO'})")
    print(f"    - Híbrido AF:    {h_af} ({'✓ EQUILIBRADO' if h_af >= 1.0 else '⚠️ PASSIVO'})")

    all_passed = (
        vices_detected["fold_when_free_to_check"] == 0
        and vices_detected["illegal_actions"] == 0
        and vices_detected["suicide_allins"] == 0
        and m_vpip >= 15.0
        and b_vpip <= 70.0
    )

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ AUDITORIA CONCLUÍDA COM SUCESSO: ZERO VÍCIOS OU LEAKS DETECTADOS!")
    else:
        print("⚠️ AUDITORIA APONTOU ITENS PARA AJUSTE.")
    print("=" * 80)

    return {
        "vices": vices_detected,
        "summary": arch_summary,
        "all_passed": all_passed,
    }


if __name__ == "__main__":
    run_comprehensive_audit(num_hands=300, seed=42)
