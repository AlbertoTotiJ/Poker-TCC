"""Benchmark Comparativo: GhMathAgent (Gustavo) vs MathematicalAgent (Alberto).

Executa simulação de alta precisão com ambos os agentes sentados na mesma mesa,
enfrentando as mesmas mãos e oponentes heurísticos (Agressivo, Equilibrado, Conservador).

Métricas analisadas:
- Lucro Líquido (Net Chips) e Taxa de Vitórias (Win Rate %)
- BB/100 (Lucratividade em Big Blinds por 100 mãos)
- Folds no Pré-Flop (Verificação da redução da passividade do agente original)
- VPIP % (Voluntarily Put in Pot) e PFR % (Pre-Flop Raise)
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
import random
import sys
import time
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.agents.base import BaseAgent  # noqa: E402
from src.agents.gh_math_agent import GhMathAgent  # noqa: E402
from src.agents.heuristic import AgentProfile, HeuristicAgent  # noqa: E402
from src.agents.mathematical_agent import MathematicalAgent  # noqa: E402
from src.engine.player import Player  # noqa: E402
from src.engine.table import ActionType, Street, Table  # noqa: E402


@dataclass
class AgentDuelStats:
    """Telemetria de desempenho em tempo real para o duelo."""

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


class GhBenchmarkRunner:
    """Orquestrador de duelo comparativo entre agentes de Poker."""

    def __init__(
        self,
        total_hands: int = 500,
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

    def run_duel(self) -> Dict[str, AgentDuelStats]:
        """Executa a bateria de mãos colocando os agentes em confronto direto."""
        gh_agent = GhMathAgent(
            player_id="gh_math",
            name="GhMath (Gustavo)",
            base_threshold=0.58,
            kelly_fraction_limit=0.25,
            num_simulations=self.num_simulations,
            rng=random.Random(self.rng.randint(1, 1_000_000)),
        )

        alberto_agent = MathematicalAgent(
            player_id="alberto_math",
            name="MathAgent (Alberto)",
            raise_equity_threshold=0.60,
            call_ev_margin=0.00,
            draw_weight=1.0,
            num_simulations=self.num_simulations,
            rng=random.Random(self.rng.randint(1, 1_000_000)),
        )

        # Mesa com 4 jogadores: GhMath + AlbertoMath + Bot Agressivo + Bot Equilibrado
        players: List[Player] = [
            Player(player_id="gh_math", name=gh_agent.name, stack=self.starting_stack),
            Player(
                player_id="alberto_math",
                name=alberto_agent.name,
                stack=self.starting_stack,
            ),
            Player(
                player_id="bot_aggro",
                name="Bot Agressivo",
                stack=self.starting_stack,
            ),
            Player(
                player_id="bot_balanced",
                name="Bot Equilibrado",
                stack=self.starting_stack,
            ),
        ]

        agents: Dict[str, BaseAgent] = {
            "gh_math": gh_agent,
            "alberto_math": alberto_agent,
            "bot_aggro": HeuristicAgent(
                "bot_aggro",
                "Bot Agressivo",
                AgentProfile.AGGRESSIVE,
                rng=random.Random(self.rng.randint(1, 1_000_000)),
            ),
            "bot_balanced": HeuristicAgent(
                "bot_balanced",
                "Bot Equilibrado",
                AgentProfile.BALANCED,
                rng=random.Random(self.rng.randint(1, 1_000_000)),
            ),
        }

        stats: Dict[str, AgentDuelStats] = {
            "gh_math": AgentDuelStats(
                "gh_math", "GhMathAgent", "Gustavo (GH)"
            ),
            "alberto_math": AgentDuelStats(
                "alberto_math", "MathematicalAgent", "Alberto"
            ),
            "bot_aggro": AgentDuelStats(
                "bot_aggro", "Bot Agressivo", "Heurístico"
            ),
            "bot_balanced": AgentDuelStats(
                "bot_balanced", "Bot Equilibrado", "Heurístico"
            ),
        }

        button_idx = 0
        start_time = time.perf_counter()

        for hand_num in range(1, self.total_hands + 1):
            # Recarrega stacks se jogadores caírem
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

                # Rastreamento de VPIP e PFR no pré-flop
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

            # Acumula VPIP/PFR por mão
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
                    f"Progresso: {hand_num}/{self.total_hands} mãos simuladas ({elapsed:.1f}s)...",
                    flush=True,
                )

        # Consolidação financeira final
        for p in players:
            st = stats[p.player_id]
            st.final_stack = p.stack
            total_reloaded = st.total_reloads * self.starting_stack
            st.net_chips = (p.stack - self.starting_stack) - total_reloaded
            st.bb_per_100 = (
                ((st.net_chips / self.big_blind) / self.total_hands) * 100.0
            )

        return stats


def print_duel_report(
    stats: Dict[str, AgentDuelStats], total_hands: int
) -> str:
    """Gera relatório formatado em Markdown para o terminal e documentação."""
    gh = stats["gh_math"]
    alb = stats["alberto_math"]

    gh_win_rate = (gh.hands_won / total_hands) * 100.0
    alb_win_rate = (alb.hands_won / total_hands) * 100.0

    gh_preflop_fold_pct = (gh.preflop_folds / total_hands) * 100.0
    alb_preflop_fold_pct = (alb.preflop_folds / total_hands) * 100.0

    fold_reduction_pct = (
        ((alb.preflop_folds - gh.preflop_folds) / alb.preflop_folds) * 100.0
        if alb.preflop_folds > 0
        else 0.0
    )

    gh_vpip = (gh.vpip_hands / total_hands) * 100.0
    alb_vpip = (alb.vpip_hands / total_hands) * 100.0

    gh_pfr = (gh.pfr_hands / total_hands) * 100.0
    alb_pfr = (alb.pfr_hands / total_hands) * 100.0

    report = []
    report.append("\n=======================================================")
    report.append("  🏆 RESULTADO DO BENCHMARK COMPARATIVO DE AGENTES")
    report.append(f"  Total de Mãos: {total_hands} | Stacks Iniciais: 1.000")
    report.append("=======================================================\n")

    report.append(
        f"{'Agente':<24} | {'Autor':<12} | {'Net Chips':<10} | {'BB/100':<8} | {'Win %':<7} | {'PF-Fold %':<10} | {'VPIP %':<7} | {'PFR %':<7}"
    )
    report.append("-" * 105)

    for pid in ["gh_math", "alberto_math", "bot_aggro", "bot_balanced"]:
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
        f"  1. Redução de Folds no Pré-Flop: {fold_reduction_pct:+.1f}% de melhoria"
    )
    report.append(
        f"     -> GhMath: {gh.preflop_folds} folds ({gh_preflop_fold_pct:.1f}%) | MathAgent: {alb.preflop_folds} folds ({alb_preflop_fold_pct:.1f}%)"
    )
    report.append(
        f"  2. Diferencial de Lucratividade (BB/100): {gh.bb_per_100 - alb.bb_per_100:+.2f} BB/100 a favor de Gustavo"
    )
    report.append(
        f"  3. Taxa de Vitória (Win Rate): {gh_win_rate:.1f}% (GH) vs {alb_win_rate:.1f}% (Alberto)"
    )
    report.append(
        f"  4. Agressividade Pré-Flop (VPIP/PFR): {gh_vpip:.1f}%/{gh_pfr:.1f}% (GH) vs {alb_vpip:.1f}%/{alb_pfr:.1f}% (Alberto)"
    )
    report.append("=======================================================\n")

    output = "\n".join(report)
    print(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark GhMathAgent vs MathematicalAgent"
    )
    parser.add_argument(
        "--hands",
        type=int,
        default=1000,
        help="Quantidade de mãos na simulação (padrão: 1000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed do gerador pseudoaleatório",
    )
    args = parser.parse_args()

    runner = GhBenchmarkRunner(total_hands=args.hands, seed=args.seed)
    stats = runner.run_duel()
    report_text = print_duel_report(stats, args.hands)

    report_path = Path(__file__).resolve().parent.parent / "BENCHMARK_GH_AGENT_REPORT.md"
    report_path.write_text(report_text, encoding="utf-8")
    print(f"Relatório salvo em: {report_path}", flush=True)


if __name__ == "__main__":
    main()
