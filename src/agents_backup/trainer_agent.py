"""Agente Treinador e Mentor Especialista de IA para Texas Hold'em (Meta-Agent Coach).

Este módulo implementa o TrainerAgent, um meta-agente autônomo dedicado exclusivamente
a diagnosticar deficiências táticas e estatísticas, detectar vazamentos (leaks) de jogo,
planejar currículos de aprendizado progressivo, orquestrar a co-evolução adaptativa
e certificar/salvar novos agentes treinados sem sobrescrever ou descalibrar
os modelos originais de base.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import random
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

# Garante resolução de 'src' ao executar o script diretamente
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.agents.base import BaseAgent  # noqa: E402
from src.agents.mathematical_agent import MathematicalAgent  # noqa: E402
from src.engine.table import Action, Table  # noqa: E402
from src.training.adaptive_trainer import (  # noqa: E402
    AdaptiveTrainer,
    TrainingResult,
)
from src.training.agent_registry import (  # noqa: E402
    AgentRegistry,
    CustomAgentMetadata,
    global_registry,
)
from src.training.metrics import (  # noqa: E402
    AgentPerformanceMetrics,
    EvaluationMetric,
    MetricQualificationCard,
    MetricWeights,
)
from src.training.parameters import (  # noqa: E402
    BLUFFER_SPECS,
    GH_BLUFFER_SPECS,
    GH_MATH_SPECS,
    HYBRID_SPECS,
    MATHEMATICAL_SPECS,
    ParamSpec,
    get_default_parameters,
)


@dataclass
class AgentDiagnostic:
    """Diagnóstico prescritivo e analítico gerado pelo Agente Treinador."""

    target_agent: str
    strengths: List[str]
    vulnerabilities: List[str]
    recommended_metric: str
    recommended_focus_rationale: str
    suggested_curriculum: Dict[str, Any]
    detected_leaks: List[str] = field(default_factory=list)
    parameter_health: Dict[str, Any] = field(default_factory=dict)
    health_score: float = 100.0

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
        """Converte o diagnóstico para dicionário serializável."""
        d = asdict(self)
        d["agent_type"] = self.target_agent
        d["recommended_focus"] = self.recommended_metric
        d["prescription"] = self.recommended_focus_rationale
        return d


class TrainerAgent(BaseAgent):
    """Meta-agente orientador, auditor e supervisor de treinamento de IAs de Poker.

    Capacidades:
    1. Diagnóstico multidimensional com detecção ativa de vazamentos (leaks).
    2. Avaliação de sanidade estocástica de hiperparâmetros (Parameter Health Check).
    3. Prescrição adaptativa da métrica de fitness ótima para treino.
    4. Treino co-evolutivo e currículo em estágios (Curriculum Learning).
    5. Preservação estrita dos agentes originais com catalogação de novos modelos.
    6. Atuação em mesa como Sparring / Mentor Equilibrado de referência.
    """

    def __init__(
        self,
        player_id: str = "trainer_coach",
        name: str = "Agente Treinador (Mentor de IA)",
        registry: Optional[AgentRegistry] = None,
        rng: Optional[random.Random] = None,
        table_agent: Optional[BaseAgent] = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        self.registry: AgentRegistry = (
            registry if registry is not None else global_registry
        )
        self.rng: random.Random = rng if rng is not None else random.Random()

        # Configura o sparring para a mesa (preferência por postura equilibrada)
        if table_agent is not None:
            self._table_agent: BaseAgent = table_agent
        else:
            try:
                from src.agents.hybrid_agent import HybridAgent

                self._table_agent = HybridAgent(
                    player_id=player_id,
                    name=name,
                    math_weight=0.65,
                    raise_equity_threshold=0.60,
                    bluff_frequency=0.20,
                    rng=self.rng,
                )
            except Exception:
                self._table_agent = MathematicalAgent(
                    player_id=player_id,
                    name=name,
                    raise_equity_threshold=0.62,
                    call_ev_margin=0.01,
                    bet_sizing_factor=0.55,
                    num_simulations=100,
                    rng=self.rng,
                )

    def evaluate_parameter_health(
        self,
        agent_type: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Audita a integridade dos hiperparâmetros contra limites operacionais."""
        norm_type = agent_type.strip().lower()
        specs_map: Dict[str, List[ParamSpec]] = {
            "bluffer": BLUFFER_SPECS,
            "mathematical": MATHEMATICAL_SPECS,
            "gh_math": GH_MATH_SPECS,
            "gh_bluffer": GH_BLUFFER_SPECS,
            "hybrid": HYBRID_SPECS,
        }

        specs = specs_map.get(norm_type, [])
        if not specs:
            return {
                "overall_health_score": 100.0,
                "status": "HEALTHY",
                "parameter_details": {},
                "anomalies": [],
            }

        spec_dict = {s.name: s for s in specs}
        param_details: Dict[str, str] = {}
        anomalies: List[str] = []
        penalties = 0.0

        for key, val in params.items():
            if key not in spec_dict:
                continue
            spec = spec_dict[key]
            v = float(val)
            val_range = spec.max_val - spec.min_val

            if v < spec.min_val:
                param_details[key] = f"CRÍTICO: Abaixo do piso ({v} < {spec.min_val})"
                anomalies.append(
                    f"Parâmetro '{key}' ({v}) violou o piso mínimo ({spec.min_val})."
                )
                penalties += 35.0
            elif v > spec.max_val:
                param_details[key] = f"CRÍTICO: Acima do teto ({v} > {spec.max_val})"
                anomalies.append(
                    f"Parâmetro '{key}' ({v}) violou o teto máximo ({spec.max_val})."
                )
                penalties += 35.0
            elif v < spec.min_val + 0.08 * val_range:
                param_details[key] = f"AVISO: Próximo ao piso extremo ({v:.2f})"
                anomalies.append(f"Parâmetro '{key}' está em zona marginal inferior.")
                penalties += 10.0
            elif v > spec.max_val - 0.08 * val_range:
                param_details[key] = f"AVISO: Próximo ao teto extremo ({v:.2f})"
                anomalies.append(f"Parâmetro '{key}' está em zona marginal superior.")
                penalties += 10.0
            else:
                param_details[key] = "NOMINAL: Faixa operacional balanceada"

        score = max(0.0, min(100.0, 100.0 - penalties))
        status = (
            "HEALTHY"
            if score >= 80
            else ("WARNING" if score >= 50 else "CRITICAL")
        )

        return {
            "overall_health_score": round(score, 1),
            "status": status,
            "parameter_details": param_details,
            "anomalies": anomalies,
        }

    def _analyze_metrics_leaks(
        self,
        metrics: Dict[str, Any],
    ) -> Tuple[List[str], Optional[str]]:
        """Identifica vazamentos táticos objetivos a partir de telemetria de jogo."""
        leaks: List[str] = []
        priority_metric: Optional[str] = None

        vpip = float(metrics.get("vpip", 0.0))
        pfr = float(metrics.get("pfr", 0.0))
        af = float(metrics.get("aggression_factor", 0.0))
        bluff_rate = float(metrics.get("bluff_success_rate", 0.0))
        bluffs_att = int(metrics.get("bluffs_attempted", 0))
        bb_100 = float(metrics.get("bb_per_100", 0.0))
        sd_win = float(metrics.get("showdown_win_rate", 0.0))
        sd_played = int(metrics.get("showdowns_played", 0))

        if 0.0 < vpip < 0.16:
            leaks.append(
                f"Passividade crítica pré-flop: VPIP={vpip * 100:.1f}% "
                f"(esperado: 20-30%)."
            )
            if not priority_metric:
                priority_metric = EvaluationMetric.VPIP.value
        elif vpip > 0.45:
            leaks.append(
                f"Excesso de mãos voluntárias: VPIP={vpip * 100:.1f}%, jogando lixo."
            )

        if 0.0 < pfr < 0.08:
            leaks.append(
                f"Falta de agressão inicial: PFR={pfr * 100:.1f}%, apenas pagando."
            )

        if 0.0 < af < 1.0:
            leaks.append(
                f"Perfil Calling Station: AF={af:.2f} (<1.0), passivo pós-flop."
            )
            if not priority_metric:
                priority_metric = EvaluationMetric.AGGRESSION_FACTOR.value
        elif af > 4.5:
            leaks.append(
                f"Hiper-agressividade descontrolada: AF={af:.2f} (>4.5)."
            )

        if bluffs_att >= 4 and bluff_rate < 0.35:
            leaks.append(
                f"Blefes ineficientes: Sucesso de apenas {bluff_rate * 100:.1f}% "
                f"em {bluffs_att} tentativas."
            )
            priority_metric = EvaluationMetric.BLUFF_SUCCESS_RATE.value

        if bb_100 < -8.0:
            leaks.append(
                f"Sangria de bankroll: Retorno crítico de {bb_100:.1f} BB/100."
            )
            priority_metric = EvaluationMetric.BB_PER_100.value

        if sd_played >= 6 and sd_win < 0.40:
            leaks.append(
                f"Vício no Showdown: Apenas {sd_win * 100:.1f}% de vitórias "
                f"no showdown."
            )

        return leaks, priority_metric

    def diagnose_agent(
        self,
        agent_type: str,
        current_params: Optional[Dict[str, Any]] = None,
        performance_metrics: Optional[
            Union[Dict[str, Any], AgentPerformanceMetrics]
        ] = None,
    ) -> AgentDiagnostic:
        """Examina os parâmetros e telemetria atual e prescreve o treino."""
        norm_type = agent_type.strip().lower()
        try:
            params = (
                current_params
                if current_params is not None
                else get_default_parameters(norm_type)
            )
        except ValueError:
            params = current_params if current_params is not None else {}

        health = self.evaluate_parameter_health(norm_type, params)
        detected_leaks: List[str] = []
        metric_override: Optional[str] = None

        if performance_metrics is not None:
            m_dict = (
                performance_metrics.to_dict()
                if hasattr(performance_metrics, "to_dict")
                else dict(performance_metrics)
            )
            detected_leaks, metric_override = self._analyze_metrics_leaks(m_dict)

        if norm_type == "bluffer":
            fq = params.get("bluff_frequency", 0.40)
            fe = params.get("fold_equity_threshold", 0.40)
            cbet = params.get("cbet_frequency", 0.65)
            semi = params.get("semi_bluff_frequency", 0.70)
            sizing = params.get("bet_sizing_factor", 0.40)

            strengths = [
                f"Agressão ativa pré-flop com C-Bet em {cbet * 100:.0f}% dos flops.",
                "Capacidade de roubar potes secos e explorar scare cards.",
                f"Semi-blefes com equidade de draws calibrados em {semi * 100:.0f}%.",
            ]
            vulnerabilities = []
            if fq > 0.50:
                vulnerabilities.append(
                    "Frequência de blefe excessiva (>50%), vulnerável a catchers."
                )
            if fe < 0.35:
                vulnerabilities.append(
                    "Limiar de fold equity muito baixo, arriscando contra muitos."
                )
            if sizing < 0.35:
                vulnerabilities.append(
                    "Dimensionamento pequeno (<35%), concedendo odds favoráveis."
                )
            if semi < 0.45:
                vulnerabilities.append(
                    "Sub-utilização de semi-blefes, perdendo valor em draws."
                )
            if not vulnerabilities:
                vulnerabilities.append(
                    "Potencial de refinamento na precificação de apostas no river."
                )

            vulnerabilities.extend(detected_leaks)
            rec_metric = metric_override or EvaluationMetric.BLUFF_SUCCESS_RATE.value

            return AgentDiagnostic(
                target_agent="Agente Blefador",
                strengths=strengths,
                vulnerabilities=vulnerabilities,
                recommended_metric=rec_metric,
                recommended_focus_rationale=(
                    "Otimizar a Taxa de Sucesso de Blefe para garantir que cada "
                    "ficha arriscada sem a melhor mão tenha EV+ positivo."
                ),
                suggested_curriculum={
                    "generations": 4,
                    "population": 6,
                    "hands_per_eval": 25,
                    "target_metric": rec_metric,
                },
                detected_leaks=detected_leaks,
                parameter_health=health["parameter_details"],
                health_score=health["overall_health_score"],
            )

        elif norm_type == "gh_bluffer":
            agg = params.get("bluff_aggression", 1.10)
            gto_bal = params.get("gto_balance_factor", 1.00)
            blocker = params.get("min_blocker_threshold", 0.30)

            strengths = [
                "Blefes calibrados via Teoria dos Jogos (GTO B/(P+2B)).",
                "Detecção avançada de cartas de bloqueio (Blockers) dos nuts rivais.",
                "Folds disciplinados e semi-blefes táticos com draws agressivos.",
            ]
            vulnerabilities = []
            if blocker < 0.20:
                vulnerabilities.append(
                    "Exigência de blocker muito frouxa (<0.20), blefando sem remoção."
                )
            if agg > 1.60:
                vulnerabilities.append(
                    "Hiper-agressividade acima de Nash, explorável por defesas firmes."
                )
            if gto_bal < 0.75:
                vulnerabilities.append(
                    "Sub-ponderação do equilíbrio GTO, blefando menos do que o ideal."
                )
            if not vulnerabilities:
                vulnerabilities.append(
                    "Agressividade e blockers podem requerer sintonia contra stations."
                )

            vulnerabilities.extend(detected_leaks)
            rec_metric = metric_override or EvaluationMetric.BLUFF_SUCCESS_RATE.value

            return AgentDiagnostic(
                target_agent="GhBlufferAgent (Gustavo - Nash/Blockers)",
                strengths=strengths,
                vulnerabilities=vulnerabilities,
                recommended_metric=rec_metric,
                recommended_focus_rationale=(
                    "Otimizar a Taxa de Sucesso de Blefe refinando o equilíbrio "
                    "GTO e blockers."
                ),
                suggested_curriculum={
                    "generations": 4,
                    "population": 6,
                    "hands_per_eval": 25,
                    "target_metric": rec_metric,
                },
                detected_leaks=detected_leaks,
                parameter_health=health["parameter_details"],
                health_score=health["overall_health_score"],
            )

        elif norm_type == "gh_math":
            base_th = params.get("base_threshold", 0.58)
            kelly = params.get("kelly_fraction_limit", 0.25)

            strengths = [
                "Dimensionamento adaptativo via Critério de Kelly Fracionário.",
                "Odds implícitas ponderadas e eliminação de passividade pré-flop.",
                "Estruturação de ranges por posição de mesa (RFI).",
            ]
            vulnerabilities = []
            if kelly < 0.15:
                vulnerabilities.append(
                    "Teto de Kelly muito restritivo (<15%), subdimensionando apostas."
                )
            if kelly > 0.40:
                vulnerabilities.append(
                    "Fração de Kelly elevada (>40%), aumentando a exposição a risco."
                )
            if base_th > 0.70:
                vulnerabilities.append(
                    "Limiar base de equidade muito alto, induzindo passividade."
                )
            if not vulnerabilities:
                vulnerabilities.append(
                    "Sensibilidade a variações de threshold contra ultra-agressivos."
                )

            vulnerabilities.extend(detected_leaks)
            rec_metric = metric_override or EvaluationMetric.BB_PER_100.value

            return AgentDiagnostic(
                target_agent="GhMathAgent (Gustavo)",
                strengths=strengths,
                vulnerabilities=vulnerabilities,
                recommended_metric=rec_metric,
                recommended_focus_rationale=(
                    "Refinar limites de Kelly e threshold para maximizar "
                    "o retorno em BB/100 contra o Hall of Fame."
                ),
                suggested_curriculum={
                    "generations": 4,
                    "population": 6,
                    "hands_per_eval": 25,
                    "target_metric": rec_metric,
                },
                detected_leaks=detected_leaks,
                parameter_health=health["parameter_details"],
                health_score=health["overall_health_score"],
            )

        elif norm_type == "hybrid":
            math_w = params.get("math_weight", 0.50)
            slowplay = params.get("slowplay_prob", 0.20)

            strengths = [
                "Fusão tática entre rigor probabilístico e engano comportamental.",
                "Exploração oportunista de potes fracos mantendo piso matemático.",
                "Capacidade de armadilha (slow-play) e semi-blefes agressivos.",
            ]
            vulnerabilities = []
            if math_w > 0.75:
                vulnerabilities.append(
                    "Predomínio quase exclusivo matemático, suprimindo blefes."
                )
            elif math_w < 0.25:
                vulnerabilities.append(
                    "Piso probabilístico enfraquecido, assumindo riscos sem odds."
                )
            if slowplay > 0.35:
                vulnerabilities.append(
                    "Frequência de slow-play perigosa (>35%), concedendo cartas grátis."
                )
            if not vulnerabilities:
                vulnerabilities.append(
                    "Necessidade de calibração fina no equilíbrio das posturas."
                )

            vulnerabilities.extend(detected_leaks)
            rec_metric = metric_override or EvaluationMetric.BB_PER_100.value

            return AgentDiagnostic(
                target_agent="Agente Híbrido (Matemático + Blefador)",
                strengths=strengths,
                vulnerabilities=vulnerabilities,
                recommended_metric=rec_metric,
                recommended_focus_rationale=(
                    "Equilibrar os pesos matemáticos e de blefe para maximizar o "
                    "retorno em BB/100 sem expor fichas a riscos imprudentes."
                ),
                suggested_curriculum={
                    "generations": 5,
                    "population": 6,
                    "hands_per_eval": 35,
                    "target_metric": rec_metric,
                },
                detected_leaks=detected_leaks,
                parameter_health=health["parameter_details"],
                health_score=health["overall_health_score"],
            )

        elif norm_type == "heuristic":
            strengths = [
                "Execução rápida e de baixo custo computacional.",
                "Aderência a regras heurísticas consolidadas por perfil.",
            ]
            vulnerabilities = [
                "Ausência de cálculo de Pot Odds dinâmicas e equidade Monte Carlo.",
                "Bet sizing ultra-previsível facilitando exploração adversária.",
                "Incapacidade de adaptação estocástica sem calibração externa.",
            ]
            vulnerabilities.extend(detected_leaks)
            rec_metric = metric_override or EvaluationMetric.WIN_RATE.value

            return AgentDiagnostic(
                target_agent="Agente Heurístico (Base)",
                strengths=strengths,
                vulnerabilities=vulnerabilities,
                recommended_metric=rec_metric,
                recommended_focus_rationale=(
                    "Calibrar os limiares heurísticos para estabilizar a taxa "
                    "bruta de vitórias."
                ),
                suggested_curriculum={
                    "generations": 3,
                    "population": 4,
                    "hands_per_eval": 20,
                    "target_metric": rec_metric,
                },
                detected_leaks=detected_leaks,
                parameter_health=health["parameter_details"],
                health_score=health["overall_health_score"],
            )

        else:  # mathematical fallback
            thresh = params.get("raise_equity_threshold", 0.65)
            ev_margin = params.get("call_ev_margin", 0.04)
            sizing = params.get("bet_sizing_factor", 0.50)

            strengths = [
                "Decisões fundamentadas estritamente em Pot Odds e Monte Carlo.",
                "Ausência de vieses psicológicos ou frustração pós-derrota.",
                "Piso matemático que impede jogadas com Valor Esperado (EV) negativo.",
            ]
            vulnerabilities = []
            if thresh > 0.75:
                vulnerabilities.append(
                    "Limiar de raise excessivamente alto (>75%), perdendo valor."
                )
            if ev_margin > 0.08:
                vulnerabilities.append(
                    "Margem de EV de call muito conservadora (>0.08), foldando demais."
                )
            if sizing < 0.35:
                vulnerabilities.append(
                    "Apostas de valor subdimensionadas, falhando em proteger a mão."
                )
            if not vulnerabilities:
                vulnerabilities.append(
                    "Pode sofrer com excesso de folds pré-flop contra aumentos."
                )

            vulnerabilities.extend(detected_leaks)
            rec_metric = metric_override or EvaluationMetric.BB_PER_100.value

            return AgentDiagnostic(
                target_agent="Agente Matemático (Alberto)",
                strengths=strengths,
                vulnerabilities=vulnerabilities,
                recommended_metric=rec_metric,
                recommended_focus_rationale=(
                    "Ajustar a margem de EV de call e o threshold de raise por valor "
                    "para maximizar o saldo acumulado de Big Blinds."
                ),
                suggested_curriculum={
                    "generations": 4,
                    "population": 6,
                    "hands_per_eval": 25,
                    "target_metric": rec_metric,
                },
                detected_leaks=detected_leaks,
                parameter_health=health["parameter_details"],
                health_score=health["overall_health_score"],
            )

    def diagnose_all_agents(self) -> Dict[str, AgentDiagnostic]:
        """Gera um diagnóstico panorâmico para todos os agentes do ecossistema."""
        agent_keys = [
            "bluffer",
            "mathematical",
            "hybrid",
            "gh_bluffer",
            "gh_math",
            "heuristic",
        ]
        return {k: self.diagnose_agent(k) for k in agent_keys}

    def train_and_produce_agent(
        self,
        base_agent_type: str,
        new_agent_name: str,
        initial_parameters: Optional[Dict[str, Any]] = None,
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
        init_params = dict(initial_parameters) if initial_parameters else None

        # Se base_agent_type for um ID de agente já salvo no catálogo:
        if norm_type in self.registry.custom_agents:
            saved_meta = self.registry.custom_agents[norm_type]
            norm_type = saved_meta.base_type
            if init_params is None:
                init_params = dict(saved_meta.parameters)

        # Determina os pesos da métrica
        metric_weights: MetricWeights
        effective_target: Optional[str] = target_metric
        if target_metric and target_metric != "balanced":
            metric_weights = MetricWeights.for_single_metric(target_metric)
        else:
            effective_target = None
            if norm_type in ("bluffer", "gh_bluffer"):
                metric_weights = MetricWeights.preset_bluff_specialist()
            else:
                metric_weights = MetricWeights.preset_balanced()

        trainer = AdaptiveTrainer(
            agent_type=norm_type,
            initial_parameters=init_params,
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

    def train_curriculum(
        self,
        base_agent_type: str,
        new_agent_name: str,
        initial_parameters: Optional[Dict[str, Any]] = None,
        stages: Optional[List[Dict[str, Any]]] = None,
        record_hands: bool = False,
        rng_seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Executa um currículo progressivo de treinamento em múltiplos estágios."""
        norm_type = base_agent_type.strip().lower()
        current_params = dict(initial_parameters) if initial_parameters else None

        default_stages = [
            {
                "stage_name": "Estágio 1: Fundação de Valor",
                "target_metric": "bb_per_100",
                "generations": 2,
                "population_size": 4,
                "hands_per_eval": 15,
            },
            {
                "stage_name": "Estágio 2: Refinamento Tático",
                "target_metric": (
                    "bluff_success_rate"
                    if norm_type in ("bluffer", "gh_bluffer")
                    else "aggression_factor"
                ),
                "generations": 2,
                "population_size": 4,
                "hands_per_eval": 20,
            },
            {
                "stage_name": "Estágio 3: Equilíbrio Competitivo",
                "target_metric": "balanced",
                "generations": 2,
                "population_size": 4,
                "hands_per_eval": 25,
            },
        ]

        active_stages = stages if stages is not None else default_stages
        stage_history = []
        last_result: Optional[Dict[str, Any]] = None

        for idx, stage in enumerate(active_stages, 1):
            stage_name = stage.get("stage_name", f"Estágio {idx}")
            t_metric = stage.get("target_metric", "balanced")
            gens = int(stage.get("generations", 2))
            pop = int(stage.get("population_size", 4))
            hands = int(stage.get("hands_per_eval", 15))

            sub_name = f"{new_agent_name} - {stage_name}"
            stage_res = self.train_and_produce_agent(
                base_agent_type=norm_type,
                new_agent_name=sub_name,
                initial_parameters=current_params,
                target_metric=t_metric,
                generations=gens,
                population_size=pop,
                hands_per_eval=hands,
                record_hands=record_hands,
                rng_seed=rng_seed,
            )

            current_params = stage_res["best_parameters"]
            last_result = stage_res
            stage_history.append({
                "stage": stage_name,
                "target_metric": t_metric,
                "fitness": stage_res["qualification"].get(
                    "overall_fitness", 0.0
                ),
                "tier": stage_res["qualification"].get("overall_tier", ""),
                "best_parameters": current_params,
            })

        # Registra o agente final consolidado do currículo
        final_meta = self.registry.save_custom_agent(
            name=new_agent_name,
            base_type=norm_type,
            parameters=current_params,
            qualification=last_result["qualification"] if last_result else {},
            session_id=last_result.get("new_agent", {}).get("session_id", ""),
            description=(
                f"Formado com sucesso pelo Currículo Progressivo em "
                f"{len(active_stages)} estágios."
            ),
        )

        return {
            "success": True,
            "message": (
                f"Currículo de treinamento de {len(active_stages)} estágios "
                f"concluído com êxito!"
            ),
            "agent_name": new_agent_name,
            "new_agent": final_meta.to_dict(),
            "final_parameters": current_params,
            "stage_history": stage_history,
        }

    def decide_action(self, table: Table) -> Action:
        """Toma decisões na mesa atuando como jogador de referência/mentor."""
        if self._table_agent.player_id != self.player_id:
            self._table_agent.player_id = self.player_id
        return self._table_agent.decide_action(table)
