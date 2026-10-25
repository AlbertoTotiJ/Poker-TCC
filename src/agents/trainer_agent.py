"""Agente Treinador e Mentor Especialista de IA para Texas Hold'em (Meta-Agent Coach).

Este módulo implementa o TrainerAgent, um agente autônomo dedicado exclusivamente
a diagnosticar fraquezas, planejar regimes de treino, orquestrar a co-evolução
adaptativa e certificar/salvar 'novos agentes' treinados sem sobrescrever ou perder
os agentes originais da linha de base.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import random
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.agents.mathematical_agent import MathematicalAgent
from src.engine.table import Action, Table
from src.training.adaptive_trainer import AdaptiveTrainer, TrainingResult
from src.training.agent_registry import (
    AgentRegistry,
    CustomAgentMetadata,
    global_registry,
)
from src.training.metrics import (
    EvaluationMetric,
    MetricQualificationCard,
    MetricWeights,
)
from src.training.parameters import get_default_parameters


@dataclass
class AgentDiagnostic:
    """Diagnóstico prescritivo gerado pelo Agente Treinador."""

    target_agent: str
    strengths: List[str]
    vulnerabilities: List[str]
    recommended_metric: str
    recommended_focus_rationale: str
    suggested_curriculum: Dict[str, Any]

    @property
    def agent_type(self) -> str:
        """Alias de conveniência para target_agent."""
        return self.target_agent

    @property
    def recommended_focus(self) -> str:
        """Alias de conveniência para recommended_metric."""
        return self.recommended_metric

    @property
    def prescription(self) -> str:
        """Alias de conveniência para recommended_focus_rationale."""
        return self.recommended_focus_rationale

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["agent_type"] = self.target_agent
        d["recommended_focus"] = self.recommended_metric
        d["prescription"] = self.recommended_focus_rationale
        return d


class TrainerAgent(BaseAgent):
    """Meta-agente orientador e supervisor de treinamento de inteligências artificiais.

    Capacidades:
    1. Diagnosticar deficiências táticas de agentes matemáticos e blefadores.
    2. Prescrever a métrica individual ótima para maximizar o aprendizado.
    3. Executar o ciclo de treinamento adaptativo co-evolutivo.
    4. Salvar o novo agente treinado preservando a integridade do agente original.
    5. Atuar na mesa como um jogador equilibrado de referência (Mentor).
    """

    def __init__(
        self,
        player_id: str = "trainer_coach",
        name: str = "Agente Treinador (Mentor de IA)",
        registry: Optional[AgentRegistry] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        self.registry: AgentRegistry = (
            registry if registry is not None else global_registry
        )
        self.rng: random.Random = rng if rng is not None else random.Random()
        # Fallback para atuação em mesa caso jogue
        self._table_agent = MathematicalAgent(
            player_id=player_id,
            name=name,
            raise_equity_threshold=0.62,
            call_ev_margin=0.01,
            bet_sizing_factor=0.55,
            num_simulations=100,
            rng=self.rng,
        )

    def diagnose_agent(
        self,
        agent_type: str,
        current_params: Optional[Dict[str, Any]] = None,
    ) -> AgentDiagnostic:
        """Examina os parâmetros atuais do agente e prescreve o regime de treino."""
        norm_type = agent_type.strip().lower()
        params = (
            current_params
            if current_params is not None
            else get_default_parameters(norm_type)
        )

        if norm_type == "bluffer":
            fq = params.get("bluff_frequency", 0.40)
            fe = params.get("fold_equity_threshold", 0.40)
            cbet = params.get("cbet_frequency", 0.65)

            strengths = [
                f"Agressão ativa pré-flop com C-Bet em {cbet * 100:.0f}% dos flops.",
                "Capacidade de roubar potes secos e explorar scare cards.",
            ]
            vulnerabilities = []
            if fq > 0.50:
                vulnerabilities.append(
                    "Frequência de blefe excessiva (>50%), "
                    "vulnerável a 'bluff catchers'."
                )
            if fe < 0.35:
                vulnerabilities.append(
                    "Limiar de fold equity muito baixo, arriscando fichas "
                    "contra múltiplos oponentes."
                )
            if not vulnerabilities:
                vulnerabilities.append(
                    "Potencial de refinamento na precificação de apostas e "
                    "semi-blefes no river."
                )

            return AgentDiagnostic(
                target_agent="Agente Blefador",
                strengths=strengths,
                vulnerabilities=vulnerabilities,
                recommended_metric=EvaluationMetric.BLUFF_SUCCESS_RATE.value,
                recommended_focus_rationale=(
                    "Otimizar a Taxa de Sucesso de Blefe para garantir que cada "
                    "ficha arriscada sem a melhor mão tenha EV+ positivo."
                ),
                suggested_curriculum={
                    "generations": 4,
                    "population": 6,
                    "hands_per_eval": 25,
                    "target_metric": "bluff_success_rate",
                },
            )

        elif norm_type == "gh_bluffer":
            return AgentDiagnostic(
                target_agent="GhBlufferAgent (Gustavo - Nash/Blockers)",
                strengths=[
                    "Blefes matematicamente calibrados via Teoria dos Jogos (GTO B/(P+2B)).",
                    "Detecção avançada de cartas de bloqueio (Blockers) dos nuts dos oponentes.",
                    "Folds disciplinados e semi-blefes táticos com draws agressivos.",
                ],
                vulnerabilities=[
                    "Agressividade e limiar de blockers podem requerer sintonia contra calling stations.",
                ],
                recommended_metric=EvaluationMetric.BLUFF_SUCCESS_RATE.value,
                recommended_focus_rationale=(
                    "Otimizar a Taxa de Sucesso de Blefe refinando o equilíbrio GTO e limiar de blockers."
                ),
                suggested_curriculum={
                    "generations": 4,
                    "population": 6,
                    "hands_per_eval": 25,
                    "target_metric": "bluff_success_rate",
                },
            )

        elif norm_type == "gh_math":
            return AgentDiagnostic(
                target_agent="GhMathAgent (Gustavo)",
                strengths=[
                    "Dimensionamento adaptativo via Critério de Kelly Fracionário.",
                    "Odds implícitas ponderadas e eliminação de passividade pré-flop.",
                ],
                vulnerabilities=[
                    "Sensibilidade a variações de threshold contra "
                    "oponentes ultra-agressivos.",
                ],
                recommended_metric=EvaluationMetric.BB_PER_100.value,
                recommended_focus_rationale=(
                    "Refinar limites de Kelly e threshold para maximizar "
                    "o retorno em BB/100 contra o Hall of Fame."
                ),
                suggested_curriculum={
                    "generations": 4,
                    "population": 6,
                    "hands_per_eval": 25,
                    "target_metric": "bb_per_100",
                },
            )

        else:  # mathematical
            return AgentDiagnostic(
                target_agent="Agente Matemático (Alberto)",
                strengths=[
                    "Decisões fundamentadas estritamente em Pot Odds e "
                    "Equidade Monte Carlo.",
                    "Ausência de vieses psicológicos ou frustração pós-derrota.",
                ],
                vulnerabilities=[
                    "Pode sofrer com excesso de folds pré-flop contra "
                    "aumentos moderados.",
                ],
                recommended_metric=EvaluationMetric.BB_PER_100.value,
                recommended_focus_rationale=(
                    "Ajustar a margem de EV de call e o threshold de raise por valor "
                    "para maximizar o saldo acumulado de Big Blinds."
                ),
                suggested_curriculum={
                    "generations": 4,
                    "population": 6,
                    "hands_per_eval": 25,
                    "target_metric": "bb_per_100",
                },
            )

    def train_and_produce_agent(
        self,
        base_agent_type: str,
        new_agent_name: str,
        target_metric: Optional[str] = None,
        generations: int = 3,
        population_size: int = 4,
        hands_per_eval: int = 20,
        record_hands: bool = True,
        save_to_neon: bool = False,
        rng_seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Supervisiona o treino e registra o NOVO agente, preservando o original."""
        norm_type = base_agent_type.strip().lower()

        # Determina os pesos da métrica
        metric_weights: MetricWeights
        effective_target: Optional[str] = target_metric
        if target_metric and target_metric != "balanced":
            metric_weights = MetricWeights.for_single_metric(target_metric)
        else:
            effective_target = None
            if norm_type == "bluffer":
                metric_weights = MetricWeights.preset_bluff_specialist()
            else:
                metric_weights = MetricWeights.preset_balanced()

        trainer = AdaptiveTrainer(
            agent_type=norm_type,
            metric_weights=metric_weights,
            target_metric=effective_target,
            generations=generations,
            population_size=population_size,
            hands_per_eval=hands_per_eval,
            record_hands=record_hands,
            save_to_neon=save_to_neon,
            rng_seed=rng_seed,
        )

        training_result: TrainingResult = trainer.train()

        # Salva o NOVO agente no catálogo preservando o original
        custom_name = (
            new_agent_name.strip()
            if new_agent_name and new_agent_name.strip()
            else (
                f"{norm_type.capitalize()} Treinado "
                f"({datetime.now(timezone.utc).strftime('%d/%m %H:%M')})"
            )
        )

        card: MetricQualificationCard = training_result.qualification_card
        new_entry: CustomAgentMetadata = self.registry.save_custom_agent(
            name=custom_name,
            base_type=norm_type,
            parameters=training_result.best_parameters,
            qualification=card.to_dict(),
            session_id=training_result.session_id,
            description=(
                f"Treinado sob supervisão do TrainerAgent. "
                f"Fitness: {card.overall_fitness:.1f} ({card.overall_tier})."
            ),
        )

        return {
            "success": True,
            "message": (
                f"Treinamento concluído com sucesso! O novo agente '{custom_name}' "
                f"foi salvo e está pronto para jogar. O agente original '{norm_type}' "
                f"permaneceu 100% preservado."
            ),
            "new_agent": new_entry.to_dict(),
            "original_agent_preserved": True,
            "base_type": norm_type,
            "qualification": card.to_dict(),
            "best_parameters": training_result.best_parameters,
            "baseline_parameters": training_result.baseline_parameters,
            "best_metrics": training_result.best_metrics.to_dict(),
            "dataset_summary": training_result.dataset_summary,
            "model_filepath": training_result.model_filepath,
            "report_markdown": training_result.report_markdown,
        }

    def decide_action(self, table: Table) -> Action:
        """Toma decisões na mesa atuando como jogador de referência/mentor."""
        if self._table_agent.player_id != self.player_id:
            self._table_agent.player_id = self.player_id
        return self._table_agent.decide_action(table)
