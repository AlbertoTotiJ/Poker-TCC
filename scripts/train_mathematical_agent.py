"""Pipeline de treinamento, calibração e benchmark do Agente Matemático.

Simula partidas controladas de Texas Hold'em colocando o MathematicalAgent
contra adversários heurísticos de diversos arquétipos (Agressivo, Conservador,
Equilibrado) para calibrar hiperparâmetros e medir métricas de desempenho.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
import random
import sys
import time
from typing import Dict, List, Optional, Tuple

# Garante resolução dos módulos a partir da raiz do repositório
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.agents.base import BaseAgent  # noqa: E402
from src.agents.heuristic import AgentProfile, HeuristicAgent  # noqa: E402
from src.agents.mathematical_agent import MathematicalAgent  # noqa: E402
from src.engine.player import Player  # noqa: E402
from src.engine.table import Street, Table  # noqa: E402


@dataclass
class PerformanceMetrics:
    """Métricas consolidadas de desempenho estatístico do agente."""

    agent_name: str
    hands_played: int
    hands_won: int
    showdowns_participated: int
    showdowns_won: int
    initial_stack: int
    final_stack: int
    net_chips: int
    bb_per_100: float
    vpip_pct: float
    pfr_pct: float
    aggression_factor: float
    folds_count: int

    @property
    def win_rate(self) -> float:
        """Taxa percentual de mãos ganhas."""
        if not self.hands_played:
            return 0.0
        return (self.hands_won / self.hands_played) * 100.0

    @property
    def showdown_win_rate(self) -> float:
        """Taxa percentual de vitórias quando chega ao showdown."""
        if self.showdowns_participated == 0:
            return 0.0
        return (self.showdowns_won / self.showdowns_participated) * 100.0


class MathematicalAgentTrainer:
    """Orquestrador de simulação e calibração de parâmetros para o Agente Matemático."""

    def __init__(
        self,
        num_players: int = 4,
        starting_stack: int = 1000,
        small_blind: int = 10,
        big_blind: int = 20,
        seed: Optional[int] = 42,
    ) -> None:
        self.num_players: int = num_players
        self.starting_stack: int = starting_stack
        self.small_blind: int = small_blind
        self.big_blind: int = big_blind
        self.rng: random.Random = random.Random(seed)

    def run_benchmark(
        self,
        total_hands: int,
        math_agent: MathematicalAgent,
        reload_stacks_on_bust: bool = True,
    ) -> Tuple[PerformanceMetrics, Dict[str, int]]:
        """Executa bateria de mãos e extrai telemetria de desempenho."""
        math_id = math_agent.player_id
        players: List[Player] = [
            Player(player_id=math_id, name=math_agent.name, stack=self.starting_stack)
        ]
        agents: Dict[str, BaseAgent] = {math_id: math_agent}

        # Configura adversários com perfis complementares
        bot_profiles = [
            ("Bot_Agressivo", AgentProfile.AGGRESSIVE),
            ("Bot_Conservador", AgentProfile.CONSERVATIVE),
            ("Bot_Equilibrado", AgentProfile.BALANCED),
            ("Bot_Agressivo_2", AgentProfile.AGGRESSIVE),
            ("Bot_Conservador_2", AgentProfile.CONSERVATIVE),
            ("Bot_Equilibrado_2", AgentProfile.BALANCED),
        ]

        for i in range(self.num_players - 1):
            name, profile = bot_profiles[i % len(bot_profiles)]
            bot_id = f"bot_{i + 1}"
            players.append(
                Player(player_id=bot_id, name=name, stack=self.starting_stack)
            )
            agents[bot_id] = HeuristicAgent(
                player_id=bot_id,
                name=name,
                profile=profile,
                rng=random.Random(self.rng.randint(1, 1_000_000)),
            )

        hands_won = 0
        showdowns_participated = 0
        showdowns_won = 0
        button_idx = 0
        reloads_count: Dict[str, int] = {p.player_id: 0 for p in players}

        for hand_idx in range(1, total_hands + 1):
            if reload_stacks_on_bust:
                for p in players:
                    if p.stack < self.big_blind * 2:
                        p.stack = self.starting_stack
                        reloads_count[p.player_id] += 1

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

            while table.street not in (Street.FINISHED, Street.SHOWDOWN):
                actor = table.current_player
                if actor is None:
                    break
                agent = agents[actor.player_id]
                action = agent.decide_action(table)
                table.apply_action(action)

            button_idx = table.button_idx
            payouts = table.last_payouts

            if math_id in payouts and payouts[math_id] > 0:
                hands_won += 1

            if table.last_scores and math_id in table.last_scores:
                showdowns_participated += 1
                if math_id in payouts and payouts[math_id] > 0:
                    showdowns_won += 1

        math_player = next(p for p in players if p.player_id == math_id)
        total_reloaded = reloads_count[math_id] * self.starting_stack
        net_chips = (math_player.stack - self.starting_stack) - total_reloaded
        bb_100 = (
            ((net_chips / self.big_blind) / total_hands) * 100.0 if total_hands else 0.0
        )

        vpip = (
            (math_agent.vpip_actions / total_hands) * 100.0 if total_hands else 0.0
        )
        pfr = (
            (math_agent.pfr_actions / total_hands) * 100.0 if total_hands else 0.0
        )

        metrics = PerformanceMetrics(
            agent_name=math_agent.name,
            hands_played=total_hands,
            hands_won=hands_won,
            showdowns_participated=showdowns_participated,
            showdowns_won=showdowns_won,
            initial_stack=self.starting_stack,
            final_stack=math_player.stack,
            net_chips=net_chips,
            bb_per_100=round(bb_100, 2),
            vpip_pct=round(vpip, 1),
            pfr_pct=round(pfr, 1),
            aggression_factor=math_agent.aggression_factor,
            folds_count=math_agent.folds,
        )

        opponent_results: Dict[str, int] = {}
        for p in players:
            if p.player_id != math_id:
                opp_reloads = reloads_count[p.player_id] * self.starting_stack
                opp_net = (p.stack - self.starting_stack) - opp_reloads
                opponent_results[p.name] = opp_net

        return metrics, opponent_results

    def calibrate_hyperparameters(
        self,
        hands_per_config: int = 150,
    ) -> Tuple[MathematicalAgent, PerformanceMetrics]:
        """Testa hiperparâmetros para selecionar a configuração ótima."""
        print("\n" + "=" * 75)
        print("INICIANDO CALIBRAÇÃO DE HIPERPARÂMETROS (GRID SEARCH EXPERIMENTAL)")
        print("=" * 75)

        thresholds = [0.60, 0.65, 0.70]
        margins = [-0.02, 0.0, 0.02]

        best_agent: Optional[MathematicalAgent] = None
        best_metrics: Optional[PerformanceMetrics] = None
        best_bb100: float = -float("inf")

        config_idx = 1
        total_configs = len(thresholds) * len(margins)

        for th in thresholds:
            for mg in margins:
                candidate = MathematicalAgent(
                    player_id="candidate_math",
                    name=f"Math_Th{th}_Mg{mg}",
                    raise_equity_threshold=th,
                    call_ev_margin=mg,
                    num_simulations=120,
                    rng=random.Random(self.rng.randint(1, 1_000_000)),
                )

                metrics, _ = self.run_benchmark(
                    total_hands=hands_per_config,
                    math_agent=candidate,
                )

                print(
                    f"[{config_idx:02d}/{total_configs:02d}] "
                    f"Threshold: {th:.2f} | Margin: {mg:+.2f} -> "
                    f"WinRate: {metrics.win_rate:5.1f}% | "
                    f"Net: {metrics.net_chips:+6d} fichas | "
                    f"BB/100: {metrics.bb_per_100:+6.2f}"
                )

                if metrics.bb_per_100 > best_bb100:
                    best_bb100 = metrics.bb_per_100
                    best_metrics = metrics
                    best_agent = candidate

                config_idx += 1

        assert best_agent is not None and best_metrics is not None
        print("\nMelhor Configuração Encontrada:")
        print(f"  -> Raise Equity Threshold: {best_agent.raise_equity_threshold}")
        print(f"  -> Call EV Margin: {best_agent.call_ev_margin}")
        print(f"  -> BB/100 na calibração: {best_metrics.bb_per_100:+.2f}")
        return best_agent, best_metrics


def print_performance_report(
    metrics: PerformanceMetrics,
    opponents: Dict[str, int],
    elapsed_time: float,
) -> None:
    """Renderiza relatório formatado de desempenho e métricas estatísticas."""
    print("\n" + "=" * 75)
    header = "RELATÓRIO OFICIAL DE DESEMPENHO: AGENTE MATEMÁTICO"
    print(header.center(75, "="))
    print("=" * 75)

    print(f" Agente Analisado:             {metrics.agent_name}")
    print(f" Volume de Mãos Simuladas:     {metrics.hands_played}")
    print(f" Tempo Total de Execução:      {elapsed_time:.2f} segundos")
    wr_str = f"{metrics.hands_won} ({metrics.win_rate:.2f}%)"
    print(f" Mãos Ganhas (Win Rate):       {wr_str}")
    print(
        f" Showdown Participações:       {metrics.showdowns_participated} "
        f"(Vitórias: {metrics.showdowns_won} | {metrics.showdown_win_rate:.2f}%)"
    )

    print("\n--- RETORNO FINANCEIRO E LUCRATIVIDADE ---")
    print(f" Lucro Líquido em Fichas:      {metrics.net_chips:+d} fichas")
    print(f" Rentabilidade Padrão (BB/100):{metrics.bb_per_100:+.2f} BB por 100 mãos")

    print("\n--- MÉTRICAS COMPORTAMENTAIS & ESTILO DE JOGO ---")
    print(f" VPIP (% Entrou no Pote):      {metrics.vpip_pct:.1f}%")
    print(f" PFR (% Aumentou Pré-flop):    {metrics.pfr_pct:.1f}%")
    print(f" Fator de Agressão (AF):       {metrics.aggression_factor:.2f}")
    print(f" Folds Decididos por -EV:      {metrics.folds_count}")

    print("\n--- SALDO COMPARATIVO CONTRA ADVERSÁRIOS ---")
    for opp_name, opp_net in opponents.items():
        print(f"  vs {opp_name:24s}: {opp_net:+6d} fichas")

    print("=" * 75 + "\n")


def main() -> None:
    desc = "Treinamento, calibração e teste de desempenho do Agente Matemático."
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument(
        "--hands",
        "-n",
        type=int,
        default=500,
        help="Quantidade de mãos na simulação principal de benchmark (padrão: 500).",
    )
    parser.add_argument(
        "--players",
        "-p",
        type=int,
        default=4,
        help="Número total de jogadores na mesa (2 a 7, padrão: 4).",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Executa grade de busca de hiperparâmetros antes do benchmark principal.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Semente do gerador pseudoaleatório para reprodutibilidade.",
    )

    args = parser.parse_args()
    trainer = MathematicalAgentTrainer(
        num_players=args.players,
        seed=args.seed,
    )

    selected_agent = MathematicalAgent(
        player_id="math_hero",
        name="Agente Matemático (Calibrado)",
        raise_equity_threshold=0.65,
        call_ev_margin=0.0,
        bet_sizing_factor=0.75,
        num_simulations=150,
        rng=random.Random(args.seed),
    )

    if args.calibrate:
        best_agent, _ = trainer.calibrate_hyperparameters(hands_per_config=100)
        selected_agent.raise_equity_threshold = best_agent.raise_equity_threshold
        selected_agent.call_ev_margin = best_agent.call_ev_margin

    msg = f"\nIniciando Benchmark: {args.hands} mãos ({args.players} jogadores)..."
    print(msg)
    start_time = time.time()
    metrics, opponents = trainer.run_benchmark(
        total_hands=args.hands,
        math_agent=selected_agent,
    )
    elapsed = time.time() - start_time

    print_performance_report(metrics, opponents, elapsed)


if __name__ == "__main__":
    main()
