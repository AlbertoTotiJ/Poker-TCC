"""Motor de Treinamento Adaptativo e Qualificação Individual de Agentes de Poker.

Implementa um ciclo completo de otimização evolutiva (Algoritmos Genéticos com
Adaptação Adversarial via Hall of Fame), avaliação de métricas individuais,
qualificação com tiers acadêmicos e geração contínua de datasets de treino.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import time
from typing import Any, Callable, Dict, List, Optional

from src.agents.base import BaseAgent
from src.agents.bluffer_agent import BlufferAgent
from src.agents.heuristic import HeuristicAgent
from src.engine.player import Player
from src.engine.table import ActionType, Street, Table
from src.training.hall_of_fame import HallOfFame
from src.training.metrics import (
    AgentPerformanceMetrics,
    EvaluationMetric,
    FitnessEvaluator,
    MetricQualificationCard,
    MetricWeights,
)
from src.training.parameters import (
    crossover_parameters,
    generate_random_parameters,
    get_default_parameters,
    instantiate_agent,
    mutate_parameters,
)
from src.training.recorder_bridge import TrainingRecorderBridge


@dataclass
class GenerationSummary:
    """Resumo estatístico consolidado de uma geração de treinamento."""

    generation: int
    best_fitness: float
    average_fitness: float
    best_tier: str
    best_parameters: Dict[str, Any]
    best_metrics: Dict[str, Any]
    duration_seconds: float


@dataclass
class TrainingResult:
    """Resultado final da sessão de treinamento adaptativo."""

    agent_type: str
    session_id: str
    best_parameters: Dict[str, Any]
    baseline_parameters: Dict[str, Any]
    best_metrics: AgentPerformanceMetrics
    qualification_card: MetricQualificationCard
    generation_history: List[GenerationSummary]
    dataset_summary: Dict[str, Any]
    model_filepath: str
    report_markdown: str


class AdaptiveTrainer:
    """Treinador evolutivo adaptativo com qualificação de métricas individuais."""

    def __init__(
        self,
        agent_type: str = "bluffer",
        metric_weights: Optional[MetricWeights] = None,
        target_metric: Optional[EvaluationMetric | str] = None,
        generations: int = 4,
        population_size: int = 6,
        hands_per_eval: int = 25,
        num_players: int = 6,
        starting_stack: int = 1000,
        small_blind: int = 10,
        big_blind: int = 20,
        record_hands: bool = True,
        save_to_neon: bool = False,
        rng_seed: Optional[int] = None,
        models_dir: Optional[Path] = None,
    ) -> None:
        self.agent_type: str = agent_type.strip().lower()
        self.generations: int = max(1, generations)
        self.population_size: int = max(2, population_size)
        self.hands_per_eval: int = max(5, hands_per_eval)
        self.num_players: int = max(2, min(9, num_players))
        self.starting_stack: int = starting_stack
        self.small_blind: int = small_blind
        self.big_blind: int = big_blind
        self.record_hands: bool = record_hands
        self.save_to_neon: bool = save_to_neon
        self.rng: random.Random = random.Random(rng_seed)

        project_root = Path(__file__).resolve().parent.parent.parent
        default_models = project_root / "models"
        target_dir = models_dir if models_dir is not None else default_models
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            test_file = target_dir / ".write_test"
            test_file.touch()
            test_file.unlink(missing_ok=True)
            self.models_dir = target_dir
        except Exception:
            fallback_dir = Path("/tmp/models")
            try:
                fallback_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            self.models_dir = fallback_dir

        # Configuração de métricas individuais
        if target_metric is not None:
            self.metric_weights: MetricWeights = (
                MetricWeights.for_single_metric(target_metric)
            )
        elif metric_weights is not None:
            self.metric_weights = metric_weights
        else:
            if self.agent_type == "bluffer":
                self.metric_weights = MetricWeights.preset_bluff_specialist()
            else:
                self.metric_weights = MetricWeights.preset_balanced()

        self.evaluator: FitnessEvaluator = FitnessEvaluator(
            weights=self.metric_weights, num_players=self.num_players
        )
        self.hall_of_fame: HallOfFame = HallOfFame()
        now_ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        self.session_id: str = f"train_{self.agent_type}_{now_ts}"
        self.recorder_bridge: TrainingRecorderBridge = TrainingRecorderBridge(
            session_id=self.session_id,
            append_to_main_dataset=self.record_hands,
            save_to_neon_db=self.save_to_neon,
        )

    def _evaluate_candidate(
        self,
        candidate_params: Dict[str, Any],
        candidate_id: str,
        generation: int,
    ) -> tuple[AgentPerformanceMetrics, MetricQualificationCard]:
        """Avalia um candidato simulando rodadas contra oponentes adaptativos."""
        candidate_agent = instantiate_agent(
            agent_type=self.agent_type,
            player_id=candidate_id,
            name=f"Candidato {candidate_id}",
            params=candidate_params,
            rng=self.rng,
        )

        # Pool de oponentes adaptativos: campeões anteriores + bots heurísticos
        opponents = self.hall_of_fame.build_adaptive_opponents(
            candidate_agent_type=self.agent_type,
            num_opponents=self.num_players - 1,
            rng=self.rng,
        )

        players = [
            Player(
                player_id=candidate_id,
                name=f"Candidato ({self.agent_type.capitalize()})",
                stack=self.starting_stack,
            )
        ] + [
            Player(
                player_id=o.player_id,
                name=o.name,
                stack=self.starting_stack,
            )
            for o in opponents
        ]

        agents: Dict[str, BaseAgent] = {
            candidate_id: candidate_agent,
            **{o.player_id: o for o in opponents},
        }

        profile_labels: Dict[str, str] = {
            candidate_id: f"Candidato ({self.agent_type})",
            **{
                o.player_id: (
                    getattr(o, "profile", None).value
                    if isinstance(o, HeuristicAgent)
                    else o.name
                )
                for o in opponents
            },
        }

        hands_won = 0
        vpip_hands = 0
        pfr_hands = 0
        total_bets_raises = 0
        total_calls = 0
        showdowns_played = 0
        showdowns_won = 0
        total_reloads = 0
        bluffs_attempted = 0
        bluffs_won = 0
        fold_equity_opportunities = 0
        fold_equity_successes = 0

        button_idx = 0

        for hand_idx in range(1, self.hands_per_eval + 1):
            # Recarrega jogadores sem fichas
            active = [p for p in players if p.stack > 0]
            if len(active) < 2:
                for p in players:
                    if p.stack <= 0:
                        if p.player_id == candidate_id:
                            total_reloads += 1
                        p.stack = self.starting_stack
                active = players

            table = Table(
                players=active,
                small_blind=self.small_blind,
                big_blind=self.big_blind,
                rng=self.rng,
                button_idx=button_idx,
            )
            table.start_new_hand(rng=self.rng)

            actions_log: List[Dict[str, Any]] = []
            cand_acted_vpip = False
            cand_acted_pfr = False

            while table.street not in (Street.FINISHED, Street.SHOWDOWN):
                actor = table.current_player
                if actor is None:
                    break

                bot = agents[actor.player_id]
                action = bot.decide_action(table)

                pot_before = table.pot_manager.total_pot
                action_data = {
                    "street": table.street.name,
                    "player_id": actor.player_id,
                    "player_name": actor.name,
                    "profile": profile_labels.get(actor.player_id, ""),
                    "action_type": action.action_type.value,
                    "amount": action.amount,
                    "pot_before": pot_before,
                }
                actions_log.append(action_data)

                # Rastreamento específico do candidato
                if actor.player_id == candidate_id:
                    if table.street == Street.PREFLOP:
                        if action.action_type in (
                            ActionType.CALL,
                            ActionType.BET,
                            ActionType.RAISE,
                        ):
                            cand_acted_vpip = True
                        if action.action_type in (
                            ActionType.BET,
                            ActionType.RAISE,
                        ):
                            cand_acted_pfr = True

                    if action.action_type in (
                        ActionType.BET,
                        ActionType.RAISE,
                    ):
                        total_bets_raises += 1
                        fold_equity_opportunities += 1
                    elif action.action_type == ActionType.CALL:
                        total_calls += 1

                table.apply_action(action)

            button_idx = table.button_idx
            payouts = getattr(table, "last_payouts", {})

            if cand_acted_vpip:
                vpip_hands += 1
            if cand_acted_pfr:
                pfr_hands += 1

            cand_won = payouts.get(candidate_id, 0) > 0
            if cand_won:
                hands_won += 1

            # Showdown
            if candidate_id in table.last_scores:
                showdowns_played += 1
                if cand_won:
                    showdowns_won += 1

            # Avaliação de Blefes e Fold Equity para BlufferAgent
            if isinstance(candidate_agent, BlufferAgent):
                if hasattr(candidate_agent, "last_decision"):
                    ld = candidate_agent.last_decision
                    if ld and getattr(ld, "is_bluff", False):
                        bluffs_attempted += 1
                        if cand_won and candidate_id not in table.last_scores:
                            bluffs_won += 1
                            fold_equity_successes += 1
            else:
                # Caso genérico para outros agentes
                if (
                    cand_won
                    and candidate_id not in table.last_scores
                    and cand_acted_pfr
                ):
                    fold_equity_successes += 1

            # Grava a partida se habilitado
            if self.record_hands:
                self.recorder_bridge.record_hand(
                    table=table,
                    actions_log=actions_log,
                    profile_labels=profile_labels,
                    generation=generation,
                    candidate_id=candidate_id,
                    candidate_params=candidate_params,
                )

        # Consolidação estatística final
        cand_player = next(p for p in players if p.player_id == candidate_id)
        total_reloaded_chips = total_reloads * self.starting_stack
        net_chips = (cand_player.stack - self.starting_stack) - total_reloaded_chips
        bb_per_100 = (
            ((net_chips / self.big_blind) / self.hands_per_eval) * 100.0
        )
        win_rate = (hands_won / self.hands_per_eval) * 100.0
        vpip = (vpip_hands / self.hands_per_eval) * 100.0
        pfr = (pfr_hands / self.hands_per_eval) * 100.0
        aggression_factor = (
            round(total_bets_raises / total_calls, 2)
            if total_calls > 0
            else float(total_bets_raises)
        )
        bluff_success_rate = (
            round((bluffs_won / bluffs_attempted) * 100.0, 1)
            if bluffs_attempted > 0
            else 0.0
        )
        fe_ratio = (
            fold_equity_successes / max(1, fold_equity_opportunities)
        )
        fold_equity_realized = round(fe_ratio * 100.0, 1)
        showdown_win_rate = (
            round((showdowns_won / showdowns_played) * 100.0, 1)
            if showdowns_played > 0
            else 0.0
        )

        metrics = AgentPerformanceMetrics(
            hands_played=self.hands_per_eval,
            hands_won=hands_won,
            net_chips=net_chips,
            bb_per_100=round(bb_per_100, 2),
            win_rate=round(win_rate, 1),
            vpip=round(vpip, 1),
            pfr=round(pfr, 1),
            aggression_factor=aggression_factor,
            bluffs_attempted=bluffs_attempted,
            bluffs_won=bluffs_won,
            bluff_success_rate=bluff_success_rate,
            fold_equity_realized=fold_equity_realized,
            showdowns_played=showdowns_played,
            showdowns_won=showdowns_won,
            showdown_win_rate=showdown_win_rate,
        )

        card = self.evaluator.evaluate(metrics)
        return metrics, card

    def train(
        self,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> TrainingResult:
        """Executa o ciclo completo de treinamento evolutivo e adaptação."""
        baseline_params = get_default_parameters(self.agent_type)
        population: List[Dict[str, Any]] = [dict(baseline_params)]

        # Se houver campeões prévios no Hall of Fame, inclui o melhor genoma
        top_champs = self.hall_of_fame.get_top_champions(
            limit=1, agent_type=self.agent_type
        )
        if top_champs:
            population.append(dict(top_champs[0].parameters))

        # Completa a população inicial com variantes estocásticas
        while len(population) < self.population_size:
            population.append(
                generate_random_parameters(self.agent_type, rng=self.rng)
            )

        generation_history: List[GenerationSummary] = []
        overall_best_params = dict(baseline_params)
        overall_best_fitness = -1.0
        overall_best_metrics = AgentPerformanceMetrics()
        overall_best_card: Optional[MetricQualificationCard] = None

        start_time = time.perf_counter()

        for gen in range(1, self.generations + 1):
            gen_start = time.perf_counter()
            evaluated_candidates: List[
                tuple[
                    Dict[str, Any],
                    float,
                    AgentPerformanceMetrics,
                    MetricQualificationCard,
                ]
            ] = []

            for idx, candidate in enumerate(population):
                cand_id = f"g{gen}_c{idx}"
                metrics, card = self._evaluate_candidate(
                    candidate_params=candidate,
                    candidate_id=cand_id,
                    generation=gen,
                )
                evaluated_candidates.append(
                    (candidate, card.overall_fitness, metrics, card)
                )

            # Ordena por fitness decrescente
            evaluated_candidates.sort(key=lambda item: item[1], reverse=True)

            gen_best_params, gen_best_fit, gen_best_met, gen_best_c = (
                evaluated_candidates[0]
            )
            avg_fit = sum(c[1] for c in evaluated_candidates) / len(
                evaluated_candidates
            )
            gen_duration = time.perf_counter() - gen_start

            summary = GenerationSummary(
                generation=gen,
                best_fitness=round(gen_best_fit, 2),
                average_fitness=round(avg_fit, 2),
                best_tier=gen_best_c.overall_tier,
                best_parameters=gen_best_params,
                best_metrics=gen_best_met.to_dict(),
                duration_seconds=round(gen_duration, 2),
            )
            generation_history.append(summary)

            # Atualiza o melhor global se superado
            if gen_best_fit > overall_best_fitness:
                overall_best_fitness = gen_best_fit
                overall_best_params = dict(gen_best_params)
                overall_best_metrics = gen_best_met
                overall_best_card = gen_best_c

                # Adaptação do ambiente: registra novo campeão no Hall of Fame
                self.hall_of_fame.add_champion(
                    agent_type=self.agent_type,
                    parameters=gen_best_params,
                    fitness_score=gen_best_fit,
                    qualification_tier=gen_best_c.overall_tier,
                    generation=gen,
                    target_focus=gen_best_c.target_focus,
                )

            if progress_callback:
                progress_callback({
                    "generation": gen,
                    "total_generations": self.generations,
                    "best_fitness": round(gen_best_fit, 2),
                    "best_tier": gen_best_c.overall_tier,
                    "target_metric": gen_best_c.target_focus or "Balanced",
                    "hands_recorded": self.recorder_bridge.hands_recorded_count,
                    "duration": round(gen_duration, 2),
                })

            # Se não for a última geração, reproduz a próxima população
            if gen < self.generations:
                new_pop: List[Dict[str, Any]] = []

                # Elitismo: preserva os 2 melhores
                new_pop.append(dict(evaluated_candidates[0][0]))
                if len(evaluated_candidates) > 1:
                    new_pop.append(dict(evaluated_candidates[1][0]))

                # Decaimento adaptativo da escala de mutação ao longo das gerações
                decay = 1.0 - (gen / self.generations) * 0.5
                mutation_scale = max(0.06, 0.20 * decay)

                # Gera novos indivíduos por cruzamento e mutação
                while len(new_pop) < self.population_size:
                    # Seleção por torneio de tamanho 2
                    cand_a = self.rng.choice(evaluated_candidates[:4])[0]
                    cand_b = self.rng.choice(evaluated_candidates[:4])[0]

                    if self.rng.random() < 0.70:
                        child = crossover_parameters(
                            self.agent_type, cand_a, cand_b, rng=self.rng
                        )
                    else:
                        child = dict(cand_a)

                    mutated_child = mutate_parameters(
                        agent_type=self.agent_type,
                        params=child,
                        mutation_rate=0.30,
                        mutation_scale=mutation_scale,
                        rng=self.rng,
                    )
                    new_pop.append(mutated_child)

                population = new_pop

        if overall_best_card is None:
            overall_best_card = self.evaluator.evaluate(overall_best_metrics)

        # Salva o modelo treinado em JSON
        ts_model = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        model_filename = f"{self.agent_type}_trained_{ts_model}.json"
        model_path = self.models_dir / model_filename
        model_payload = {
            "session_id": self.session_id,
            "agent_type": self.agent_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "overall_fitness": overall_best_card.overall_fitness,
            "overall_tier": overall_best_card.overall_tier,
            "target_focus": overall_best_card.target_focus,
            "parameters": overall_best_params,
            "metrics": overall_best_metrics.to_dict(),
            "qualification": overall_best_card.to_dict(),
        }
        try:
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(model_payload, f, indent=2, ensure_ascii=False)
        except OSError:
            try:
                fallback_path = Path("/tmp/models") / model_filename
                fallback_path.parent.mkdir(parents=True, exist_ok=True)
                with open(fallback_path, "w", encoding="utf-8") as f:
                    json.dump(model_payload, f, indent=2, ensure_ascii=False)
                model_path = fallback_path
            except Exception:
                pass

        # Gera relatório em Markdown
        report_md = self._generate_markdown_report(
            baseline_params=baseline_params,
            best_params=overall_best_params,
            best_metrics=overall_best_metrics,
            card=overall_best_card,
            generation_history=generation_history,
            total_duration=time.perf_counter() - start_time,
            model_path=model_path,
        )

        return TrainingResult(
            agent_type=self.agent_type,
            session_id=self.session_id,
            best_parameters=overall_best_params,
            baseline_parameters=baseline_params,
            best_metrics=overall_best_metrics,
            qualification_card=overall_best_card,
            generation_history=generation_history,
            dataset_summary=self.recorder_bridge.get_summary(),
            model_filepath=str(model_path),
            report_markdown=report_md,
        )

    def _generate_markdown_report(
        self,
        baseline_params: Dict[str, Any],
        best_params: Dict[str, Any],
        best_metrics: AgentPerformanceMetrics,
        card: MetricQualificationCard,
        generation_history: List[GenerationSummary],
        total_duration: float,
        model_path: Path,
    ) -> str:
        """Gera documentação técnica formal da sessão de treino em Markdown."""
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        lines = [
            f"# Relatório de Treino: {self.agent_type.upper()}",
            f"**Sessão ID:** `{self.session_id}` | **Data:** {now_str}",
            f"**Tempo:** {total_duration:.2f}s | "
            f"**Gerações:** {self.generations} | "
            f"**População:** {self.population_size}",
            f"**Foco:** `{card.target_focus or 'Multi-Métrica Equilibrada'}`",
            "",
            "## 1. Boletim de Qualificação de Métricas Individuais",
            f"**Nota Geral (Fitness):** `{card.overall_fitness:.1f}/100.0` | "
            f"**Tier:** `{card.overall_tier}`",
            "",
            "| Métrica Individual | Valor Real | Nota (0-100) | Tier | "
            "Diagnóstico Estratégico |",
            "| :--- | :---: | :---: | :---: | :--- |",
        ]

        for _, m_score in card.individual_scores.items():
            lines.append(
                f"| **{m_score.metric.value}** | `{m_score.raw_value:.2f}` | "
                f"`{m_score.score:.1f}` | **{m_score.tier}** | "
                f"{m_score.description} |"
            )

        lines.extend([
            "",
            "## 2. Comparativo de Hiperparâmetros (Linha de Base vs Treinado)",
            "",
            "| Hiperparâmetro | Valor Inicial (Baseline) | "
            "Valor Otimizado (Treinado) | Variação Δ |",
            "| :--- | :---: | :---: | :---: |",
        ])

        for param_name, base_val in baseline_params.items():
            best_val = best_params.get(param_name, base_val)
            delta = (
                f"{best_val - base_val:+.4f}"
                if isinstance(base_val, float)
                else f"{best_val - base_val:+d}"
            )
            lines.append(
                f"| `{param_name}` | `{base_val}` | **`{best_val}`** | `{delta}` |"
            )

        lines.extend([
            "",
            "## 3. Evolução Geracional e Adaptação",
            "",
            "| Geração | Melhor Fitness | Média Fitness | Tier | Duração |",
            "| :---: | :---: | :---: | :---: | :---: |",
        ])

        for g in generation_history:
            lines.append(
                f"| G{g.generation} | `{g.best_fitness:.2f}` | "
                f"`{g.average_fitness:.2f}` | {g.best_tier} | "
                f"{g.duration_seconds:.2f}s |"
            )

        summary = self.recorder_bridge.get_summary()
        lines.extend([
            "",
            "## 4. Dataset de Treinamento Gerado",
            f"- **Partidas Gravadas:** {summary['hands_recorded']} mãos",
            f"- **Ações Registradas:** {summary['actions_recorded']} ações",
            f"- **Blefes Rotulados:** {summary['bluffs_recorded']} ocorrências",
            f"- **Arquivo Local:** `{summary['session_file']}` "
            f"({summary['file_size_kb']} KB)",
            f"- **Modelo Salvo em:** `{model_path}`",
            "",
            "> [!NOTE]",
            "> Este agente treinado já foi incorporado ao **Hall of Fame**.",
            "> Nas próximas sessões, novos candidatos enfrentarão esta",
            "> estratégia como contra-adversário no ciclo adaptativo.",
        ])

        return "\n".join(lines)
