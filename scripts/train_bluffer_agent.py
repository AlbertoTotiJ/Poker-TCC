"""Pipeline de treinamento, calibração e benchmark do Agente Blefador.

Simula partidas controladas de Texas Hold'em colocando o BlufferAgent
contra adversários heurísticos e matemáticos para calibrar hiperparâmetros
do Bluff Engine e mensurar rentabilidade, frequência de blefes e fold equity.
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
from src.agents.bluffer_agent import BlufferAgent  # noqa: E402
from src.agents.heuristic import AgentProfile, HeuristicAgent  # noqa: E402
from src.agents.mathematical_agent import MathematicalAgent  # noqa: E402
from src.engine.player import Player  # noqa: E402
from src.engine.table import Street, Table  # noqa: E402


@dataclass
class BlufferPerformanceMetrics:
    """Métricas estatísticas consolidadas de desempenho do Agente Blefador."""

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
    bluffs_attempted: int
    pure_bluffs: int
    semi_bluffs: int
    cbet_steals: int
    bluff_raises: int
    bluff_rate: float

    @property
    def win_rate(self) -> float:
        """Taxa percentual de mãos ganhas."""
        if not self.hands_played:
            return 0.0
        return (self.hands_won / self.hands_played) * 100.0

    @property
    def showdown_win_rate(self) -> float:
        """Taxa percentual de vitórias ao atingir o showdown."""
        if self.showdowns_participated == 0:
            return 0.0
        return (self.showdowns_won / self.showdowns_participated) * 100.0


class BlufferAgentTrainer:
    """Orquestrador de simulação, treino e calibração de hiperparâmetros do Blefador."""

    def __init__(
        self,
        num_players: int = 4,
        starting_stack: int = 1000,
        small_blind: int = 10,
        big_blind: int = 20,
        seed: Optional[int] = 42,
    ) -> None:
        self.num_players: int = max(2, min(9, num_players))
        self.starting_stack: int = starting_stack
        self.small_blind: int = small_blind
        self.big_blind: int = big_blind
        self.rng: random.Random = random.Random(seed)

    def run_benchmark(
        self,
        total_hands: int,
        bluffer_agent: BlufferAgent,
        reload_stacks_on_bust: bool = True,
    ) -> Tuple[BlufferPerformanceMetrics, Dict[str, int]]:
        """Executa bateria de mãos e extrai telemetria analítica de desempenho."""
        bluff_id = bluffer_agent.player_id
        players: List[Player] = [
            Player(
                player_id=bluff_id,
                name=bluffer_agent.name,
                stack=self.starting_stack,
            )
        ]
        agents: Dict[str, BaseAgent] = {bluff_id: bluffer_agent}

        # Configura adversários com perfis complementares
        opp_candidates: List[Tuple[str, BaseAgent]] = [
            (
                "Bot_Matematico",
                MathematicalAgent(
                    player_id="bot_math",
                    name="Bot_Matematico",
                    raise_equity_threshold=0.65,
                    call_ev_margin=0.0,
                    rng=random.Random(self.rng.randint(1, 1_000_000)),
                ),
            ),
            (
                "Bot_Conservador",
                HeuristicAgent(
                    player_id="bot_con",
                    name="Bot_Conservador",
                    profile=AgentProfile.CONSERVATIVE,
                    rng=random.Random(self.rng.randint(1, 1_000_000)),
                ),
            ),
            (
                "Bot_Equilibrado",
                HeuristicAgent(
                    player_id="bot_bal",
                    name="Bot_Equilibrado",
                    profile=AgentProfile.BALANCED,
                    rng=random.Random(self.rng.randint(1, 1_000_000)),
                ),
            ),
            (
                "Bot_Agressivo",
                HeuristicAgent(
                    player_id="bot_agr",
                    name="Bot_Agressivo",
                    profile=AgentProfile.AGGRESSIVE,
                    rng=random.Random(self.rng.randint(1, 1_000_000)),
                ),
            ),
            (
                "Bot_Conservador_2",
                HeuristicAgent(
                    player_id="bot_con2",
                    name="Bot_Conservador_2",
                    profile=AgentProfile.CONSERVATIVE,
                    rng=random.Random(self.rng.randint(1, 1_000_000)),
                ),
            ),
        ]

        for i in range(self.num_players - 1):
            name, agent_instance = opp_candidates[i % len(opp_candidates)]
            bot_id = f"bot_{i + 1}"
            agent_instance.player_id = bot_id
            players.append(
                Player(player_id=bot_id, name=name, stack=self.starting_stack)
            )
            agents[bot_id] = agent_instance

        hands_won = 0
        showdowns_participated = 0
        showdowns_won = 0
        button_idx = 0
        reloads_count: Dict[str, int] = {p.player_id: 0 for p in players}

        for _ in range(total_hands):
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

            if bluff_id in payouts and payouts[bluff_id] > 0:
                hands_won += 1

            if table.last_scores and bluff_id in table.last_scores:
                showdowns_participated += 1
                if bluff_id in payouts and payouts[bluff_id] > 0:
                    showdowns_won += 1

        bluff_player = next(p for p in players if p.player_id == bluff_id)
        total_reloaded = reloads_count[bluff_id] * self.starting_stack
        net_chips = (bluff_player.stack - self.starting_stack) - total_reloaded
        bb_100 = (
            ((net_chips / self.big_blind) / total_hands) * 100.0 if total_hands else 0.0
        )

        vpip = (
            (bluffer_agent.vpip_actions / total_hands) * 100.0 if total_hands else 0.0
        )
        pfr = (
            (bluffer_agent.pfr_actions / total_hands) * 100.0 if total_hands else 0.0
        )

        metrics = BlufferPerformanceMetrics(
            agent_name=bluffer_agent.name,
            hands_played=total_hands,
            hands_won=hands_won,
            showdowns_participated=showdowns_participated,
            showdowns_won=showdowns_won,
            initial_stack=self.starting_stack,
            final_stack=bluff_player.stack,
            net_chips=net_chips,
            bb_per_100=round(bb_100, 2),
            vpip_pct=round(vpip, 1),
            pfr_pct=round(pfr, 1),
            aggression_factor=bluffer_agent.aggression_factor,
            folds_count=bluffer_agent.folds,
            bluffs_attempted=bluffer_agent.bluffs_attempted,
            pure_bluffs=bluffer_agent.pure_bluffs,
            semi_bluffs=bluffer_agent.semi_bluffs,
            cbet_steals=bluffer_agent.cbet_steals,
            bluff_raises=bluffer_agent.bluff_raises,
            bluff_rate=bluffer_agent.bluff_rate,
        )

        opponent_results: Dict[str, int] = {}
        for p in players:
            if p.player_id != bluff_id:
                opp_reloads = reloads_count[p.player_id] * self.starting_stack
                opp_net = (p.stack - self.starting_stack) - opp_reloads
                opponent_results[p.name] = opp_net

        return metrics, opponent_results

    def calibrate_hyperparameters(
        self,
        hands_per_config: int = 100,
    ) -> Tuple[BlufferAgent, BlufferPerformanceMetrics]:
        """Executa busca em grade para selecionar a parametrização ótima."""
        print("\n" + "=" * 75)
        print("INICIANDO CALIBRAÇÃO DE HIPERPARÂMETROS (BLUFF ENGINE GRID SEARCH)")
        print("=" * 75)

        bluff_freqs = [0.30, 0.45, 0.60]
        agg_mults = [0.85, 1.00, 1.25]

        best_agent: Optional[BlufferAgent] = None
        best_metrics: Optional[BlufferPerformanceMetrics] = None
        best_bb100: float = -float("inf")

        config_idx = 1
        total_configs = len(bluff_freqs) * len(agg_mults)

        for bf in bluff_freqs:
            for am in agg_mults:
                candidate = BlufferAgent(
                    player_id="candidate_bluffer",
                    name=f"Bluff_Bf{bf}_Am{am}",
                    bluff_frequency=bf,
                    aggression_multiplier=am,
                    semi_bluff_frequency=0.75,
                    rng=random.Random(self.rng.randint(1, 1_000_000)),
                )

                metrics, _ = self.run_benchmark(
                    total_hands=hands_per_config,
                    bluffer_agent=candidate,
                )

                print(
                    f"[{config_idx:02d}/{total_configs:02d}] "
                    f"BluffFreq: {bf:.2f} | AggMult: {am:.2f} -> "
                    f"WinRate: {metrics.win_rate:5.1f}% | "
                    f"Net: {metrics.net_chips:+6d} fichas | "
                    f"BB/100: {metrics.bb_per_100:+6.2f} | "
                    f"Blefes: {metrics.bluffs_attempted:3d}"
                )

                if metrics.bb_per_100 > best_bb100:
                    best_bb100 = metrics.bb_per_100
                    best_metrics = metrics
                    best_agent = candidate

                config_idx += 1

        assert best_agent is not None and best_metrics is not None
        print("\nMelhor Configuração do Agente Blefador Encontrada:")
        print(f"  -> Bluff Frequency: {best_agent.params.bluff_frequency}")
        print(f"  -> Aggression Multiplier: {best_agent.params.aggression_multiplier}")
        print(f"  -> BB/100 na calibração: {best_metrics.bb_per_100:+.2f}")
        return best_agent, best_metrics


def print_performance_report(
    metrics: BlufferPerformanceMetrics,
    opponents: Dict[str, int],
    elapsed_time: float,
) -> None:
    """Renderiza relatório formatado de desempenho e métricas estatísticas."""
    print("\n" + "=" * 75)
    header = "RELATÓRIO OFICIAL DE DESEMPENHO: AGENTE BLEFADOR (BLUFF ENGINE)"
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
    print(f" Total de Folds:               {metrics.folds_count}")

    print("\n--- AUDITORIA DO BLUFF ENGINE ---")
    print(f" Total de Blefes Disparados:   {metrics.bluffs_attempted}")
    print(f" Taxa de Blefe nas Agressões:  {metrics.bluff_rate:.1f}%")
    print(f"  - C-Bet Steals (Potes Vazios): {metrics.cbet_steals}")
    print(f"  - Semi-Blefes (Draws de Out):  {metrics.semi_bluffs}")
    print(f"  - Bluff Raises (Re-aumentos):  {metrics.bluff_raises}")
    print(f"  - Blefes Puros / Scare Barrels: {metrics.pure_bluffs}")

    print("\n--- SALDO COMPARATIVO CONTRA ADVERSÁRIOS ---")
    for opp_name, opp_net in opponents.items():
        print(f"  vs {opp_name:24s}: {opp_net:+6d} fichas")

    print("=" * 75 + "\n")


def main() -> None:
    desc = "Treinamento, calibração e teste de desempenho do Agente Blefador."
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument(
        "--hands",
        "-n",
        type=int,
        default=300,
        help="Quantidade de mãos na simulação principal de benchmark (padrão: 300).",
    )
    parser.add_argument(
        "--players",
        "-p",
        type=int,
        default=4,
        help="Número total de jogadores na mesa (2 a 6, padrão: 4).",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Executa grade de busca de hiperparâmetros antes do benchmark principal.",
    )
    parser.add_argument(
        "--save-params",
        type=str,
        default="models/bluffer_agent_calibrated.json",
        help="Caminho para salvar os hiperparâmetros calibrados.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Semente do gerador pseudoaleatório para reprodutibilidade.",
    )

    args = parser.parse_args()
    trainer = BlufferAgentTrainer(
        num_players=args.players,
        seed=args.seed,
    )

    selected_agent = BlufferAgent(
        player_id="bluffer_hero",
        name="Agente Blefador (Calibrado)",
        bluff_frequency=0.45,
        semi_bluff_frequency=0.75,
        fold_equity_threshold=0.40,
        aggression_multiplier=1.05,
        rng=random.Random(args.seed),
    )

    if args.calibrate:
        best_agent, _ = trainer.calibrate_hyperparameters(hands_per_config=80)
        selected_agent.load_parameters(best_agent.export_parameters())
        if args.save_params:
            selected_agent.save_parameters(args.save_params)
            print(f"Hiperparâmetros salvos com sucesso em: {args.save_params}")

    msg = f"\nIniciando Benchmark: {args.hands} mãos ({args.players} jogadores)..."
    print(msg)
    start_time = time.time()
    metrics, opponents = trainer.run_benchmark(
        total_hands=args.hands,
        bluffer_agent=selected_agent,
    )
    elapsed = time.time() - start_time

    print_performance_report(metrics, opponents, elapsed)


if __name__ == "__main__":
    main()
