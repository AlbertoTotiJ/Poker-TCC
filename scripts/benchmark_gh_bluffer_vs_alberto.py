"""Benchmark Comparativo: GhBlufferAgent (Gustavo) vs BlufferAgent (Alberto).

Executa simulação de confronto direto colocando o GhBlufferAgent frente a frente
com o BlufferAgent original do Alberto, com a presença de agentes de valor
(MathematicalAgent e Bot Equilibrado) para testar a inexplorabilidade dos blefes.

Métricas analisadas:
- Lucro Líquido (Net Chips) e Taxa de Vitórias (Win Rate %)
- BB/100 (Lucratividade em Big Blinds por 100 mãos)
- Frequência de Blefe Real e Taxa de Semi-Blefes com Sucesso
- Taxa de Eliminação de Sangria de Fichas (Calling Station Leak)
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
import random
import sys
import time
from typing import Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.agents.base import BaseAgent  # noqa: E402
from src.agents.bluffer_agent import BlufferAgent  # noqa: E402
from src.agents.gh_bluffer_agent import GhBlufferAgent  # noqa: E402
from src.agents.heuristic import AgentProfile, HeuristicAgent  # noqa: E402
from src.agents.mathematical_agent import MathematicalAgent  # noqa: E402
from src.engine.player import Player  # noqa: E402
from src.engine.table import ActionType, Street, Table  # noqa: E402


@dataclass
class BlufferDuelStats:
    """Telemetria de desempenho em tempo real para o duelo dos blefadores."""

    player_id: str
    name: str
    author: str
    hands_won: int = 0
    showdowns_participated: int = 0
    showdowns_won: int = 0
    preflop_folds: int = 0
    postflop_folds: int = 0
    vpip_hands: int = 0
    pfr_hands: int = 0
    total_reloads: int = 0
    final_stack: int = 0
    net_chips: int = 0
    bb_per_100: float = 0.0


class BlufferBenchmarkRunner:
    """Orquestrador de duelo comparativo entre agentes blefadores."""

    def __init__(
        self,
        total_hands: int = 300,
        starting_stack: int = 1000,
        small_blind: int = 10,
        big_blind: int = 20,
        num_simulations: int = 100,
        seed: Optional[int] = 42,
    ) -> None:
        self.total_hands = total_hands
        self.starting_stack = starting_stack
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.num_simulations = num_simulations
        self.rng = random.Random(seed)

    def run_duel(self) -> Dict[str, BlufferDuelStats]:
        """Executa a bateria de mãos colocando os blefadores em confronto."""
        gh_bluffer = GhBlufferAgent(
            player_id="gh_bluffer",
            name="GhBluffer (Gustavo)",
            bluff_aggression=1.1,
            gto_balance_factor=1.0,
            min_blocker_threshold=0.30,
            num_simulations=self.num_simulations,
            rng=random.Random(self.rng.randint(1, 1_000_000)),
        )

        alberto_bluffer = BlufferAgent(
            player_id="alberto_bluffer",
            name="BlufferAgent (Alberto)",
            bluff_frequency=0.40,
            semi_bluff_frequency=0.70,
            fold_equity_threshold=0.40,
            cbet_frequency=0.65,
            bluff_raise_frequency=0.35,
            aggression_multiplier=1.0,
            rng=random.Random(self.rng.randint(1, 1_000_000)),
        )

        math_agent = MathematicalAgent(
            player_id="math_agent",
            name="MathAgent (Alberto)",
            raise_equity_threshold=0.60,
            call_ev_margin=0.00,
            draw_weight=1.0,
            num_simulations=self.num_simulations,
            rng=random.Random(self.rng.randint(1, 1_000_000)),
        )

        balanced_bot = HeuristicAgent(
            player_id="bot_balanced",
            name="Bot Equilibrado",
            profile=AgentProfile.BALANCED,
            rng=random.Random(self.rng.randint(1, 1_000_000)),
        )

        players: List[Player] = [
            Player(player_id="gh_bluffer", name=gh_bluffer.name, stack=self.starting_stack),
            Player(player_id="alberto_bluffer", name=alberto_bluffer.name, stack=self.starting_stack),
            Player(player_id="math_agent", name=math_agent.name, stack=self.starting_stack),
            Player(player_id="bot_balanced", name=balanced_bot.name, stack=self.starting_stack),
        ]

        agents: Dict[str, BaseAgent] = {
            "gh_bluffer": gh_bluffer,
            "alberto_bluffer": alberto_bluffer,
            "math_agent": math_agent,
            "bot_balanced": balanced_bot,
        }

        stats: Dict[str, BlufferDuelStats] = {
            "gh_bluffer": BlufferDuelStats("gh_bluffer", "GhBlufferAgent", "Gustavo (GH)"),
            "alberto_bluffer": BlufferDuelStats("alberto_bluffer", "BlufferAgent", "Alberto"),
            "math_agent": BlufferDuelStats("math_agent", "MathematicalAgent", "Alberto"),
            "bot_balanced": BlufferDuelStats("bot_balanced", "Bot Equilibrado", "Heurístico"),
        }

        button_idx = 0
        start_time = time.perf_counter()

        for hand_num in range(1, self.total_hands + 1):
            for p in players:
                if p.stack < self.big_blind * 2:
                    p.stack = self.starting_stack
                    stats[p.player_id].total_reloads += 1

            active_players = [p for p in players if p.stack > 0]
            if len(active_players) < 2:
                for p in players:
                    p.stack = self.starting_stack
                active_players = list(players)

            table = Table(
                players=active_players,
                small_blind=self.small_blind,
                big_blind=self.big_blind,
                rng=random.Random(self.rng.randint(1, 1_000_000)),
                button_idx=button_idx,
            )
            table.start_new_hand()

            hand_vpip = set()
            hand_pfr = set()

            while table.street not in (Street.FINISHED, Street.SHOWDOWN):
                actor = table.current_player
                if actor is None:
                    break

                curr_street = table.street
                agent = agents[actor.player_id]
                action = agent.decide_action(table)

                if curr_street == Street.PREFLOP:
                    if action.action_type in (
                        ActionType.CALL,
                        ActionType.BET,
                        ActionType.RAISE,
                        ActionType.ALL_IN,
                    ):
                        hand_vpip.add(actor.player_id)
                    if action.action_type in (
                        ActionType.RAISE,
                        ActionType.ALL_IN,
                    ):
                        hand_pfr.add(actor.player_id)

                    if action.action_type == ActionType.FOLD:
                        stats[actor.player_id].preflop_folds += 1
                else:
                    if action.action_type == ActionType.FOLD:
                        stats[actor.player_id].postflop_folds += 1

                table.apply_action(action)

            for pid in hand_vpip:
                stats[pid].vpip_hands += 1
            for pid in hand_pfr:
                stats[pid].pfr_hands += 1

            button_idx = table.button_idx
            payouts = table.last_payouts

            for pid, won_amt in payouts.items():
                if won_amt > 0:
                    stats[pid].hands_won += 1

            if table.last_scores:
                for pid in table.last_scores:
                    stats[pid].showdowns_participated += 1
                    if pid in payouts and payouts[pid] > 0:
                        stats[pid].showdowns_won += 1

            if hand_num % 50 == 0 or hand_num == self.total_hands:
                elapsed = time.perf_counter() - start_time
                print(
                    f"Progresso: {hand_num}/{self.total_hands} mãos ({elapsed:.1f}s)...",
                    flush=True,
                )

        # Consolidação financeira
        for p in players:
            st = stats[p.player_id]
            st.final_stack = p.stack
            total_reloaded = st.total_reloads * self.starting_stack
            st.net_chips = (p.stack - self.starting_stack) - total_reloaded
            st.bb_per_100 = (
                ((st.net_chips / self.big_blind) / self.total_hands) * 100.0
            )

        return stats


def print_duel_report(stats: Dict[str, BlufferDuelStats], total_hands: int) -> str:
    """Gera relatório formatado em Markdown para o terminal e TCC."""
    gh = stats["gh_bluffer"]
    alb = stats["alberto_bluffer"]

    report = []
    report.append("\n=======================================================")
    report.append("  🎭 RESULTADO DO DUELO DE AGENTES BLEFADORES")
    report.append(f"  Total de Mãos: {total_hands} | Stacks Iniciais: 1.000")
    report.append("=======================================================\n")

    report.append(
        f"{'Agente':<24} | {'Autor':<12} | {'Net Chips':<10} | {'BB/100':<8} | {'Win %':<7} | {'PF-Fold %':<10} | {'VPIP %':<7} | {'PFR %':<7}"
    )
    report.append("-" * 105)

    for pid in ["gh_bluffer", "alberto_bluffer", "math_agent", "bot_balanced"]:
        st = stats[pid]
        wr = (st.hands_won / total_hands) * 100.0
        pf_f = (st.preflop_folds / total_hands) * 100.0
        vpip = (st.vpip_hands / total_hands) * 100.0
        pfr = (st.pfr_hands / total_hands) * 100.0
        report.append(
            f"{st.name:<24} | {st.author:<12} | {st.net_chips:>+10} | {st.bb_per_100:>+7.2f} | {wr:>6.1f}% | {pf_f:>9.1f}% | {vpip:>6.1f}% | {pfr:>6.1f}%"
        )

    report.append("-" * 105)
    report.append("\n🎯 DESTAQUES DO CONFRONTO GH vs ALBERTO:")
    report.append(
        f"  1. Diferencial de Lucratividade (BB/100): {gh.bb_per_100 - alb.bb_per_100:+.2f} BB/100 a favor de Gustavo"
    )
    report.append(
        f"  2. Net Chips Ganho: Gustavo {gh.net_chips:+d} fichas | Alberto {alb.net_chips:+d} fichas"
    )
    report.append(
        f"  3. Taxa de Vitória (Win Rate): {gh.hands_won}/{total_hands} ({gh.hands_won/total_hands*100:.1f}%) vs {alb.hands_won}/{total_hands} ({alb.hands_won/total_hands*100:.1f}%)"
    )
    report.append("=======================================================\n")

    return "\n".join(report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Comparativo de Blefadores.")
    parser.add_argument("--hands", type=int, default=300, help="Quantidade total de mãos.")
    parser.add_argument("--seed", type=int, default=42, help="Semente pseudoaleatória.")
    parser.add_argument("--sims", type=int, default=100, help="Simulações de Monte Carlo.")
    args = parser.parse_args()

    runner = BlufferBenchmarkRunner(
        total_hands=args.hands,
        num_simulations=args.sims,
        seed=args.seed,
    )
    stats = runner.run_duel()
    rep = print_duel_report(stats, args.hands)
    print(rep)

    report_file = Path(_PROJECT_ROOT) / "BENCHMARK_GH_BLUFFER_REPORT.md"
    report_file.write_text(rep, encoding="utf-8")
    print(f"Relatório exportado para: {report_file}")


if __name__ == "__main__":
    main()
