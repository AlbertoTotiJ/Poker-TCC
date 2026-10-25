"""Catálogo e registro persistente de agentes de IA (Originais e Treinados).

Garante que novos agentes resultantes de treinamento sejam salvos e versionados
como entidades independentes, sem substituir ou corromper os agentes originais
da linha de base.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import random
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.agents.bluffer_agent import BlufferAgent
from src.agents.gh_bluffer_agent import GhBlufferAgent
from src.agents.gh_math_agent import GhMathAgent
from src.agents.heuristic import AgentProfile, HeuristicAgent
from src.agents.hybrid_agent import HybridAgent
from src.agents.mathematical_agent import MathematicalAgent
from src.training.parameters import clamp_parameters


@dataclass
class CustomAgentMetadata:
    """Metadados de um novo agente produzido via treinamento."""

    agent_id: str
    name: str
    base_type: str
    created_at: str
    parameters: Dict[str, Any]
    qualification: Dict[str, Any]
    session_id: Optional[str] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CustomAgentMetadata":
        return cls(**data)


STANDARD_AGENTS: List[Dict[str, Any]] = [
    {
        "agent_id": "gh_bluffer",
        "name": "GhBlufferAgent (Gustavo - Nash/Blockers)",
        "base_type": "gh_bluffer",
        "is_custom": False,
        "description": (
            "Agente blefador avançado baseado em Nash GTO e efeito de remoção de cartas (Blockers)."
        ),
        "badge": "Original",
    },
    {
        "agent_id": "gh_math",
        "name": "GhMathAgent (Gustavo - Kelly/XAI)",
        "base_type": "gh_math",
        "is_custom": False,
        "description": (
            "Agente analítico com Implied Odds e Critério de Kelly."
        ),
        "badge": "Original",
    },
    {
        "agent_id": "math",
        "name": "Agente Matemático (Alberto - EV)",
        "base_type": "mathematical",
        "is_custom": False,
        "description": (
            "Agente probabilístico baseado em Monte Carlo e Pot Odds."
        ),
        "badge": "Original",
    },
    {
        "agent_id": "bluffer",
        "name": "Agente Blefador (Bluff Engine)",
        "base_type": "bluffer",
        "is_custom": False,
        "description": (
            "Agente tático exploratório com foco em Fold Equity."
        ),
        "badge": "Original",
    },
    {
        "agent_id": "trainer",
        "name": "Agente Treinador & Mentor (Meta-Agent)",
        "base_type": "trainer",
        "is_custom": False,
        "description": "Meta-agente especialista em calibrar e evoluir IAs de poker.",
        "badge": "Mentor",
    },
    {
        "agent_id": "hybrid",
        "name": "Agente Híbrido",
        "base_type": "hybrid",
        "is_custom": False,
        "description": "Combinação entre regras matemáticas e heurística tática.",
        "badge": "Original",
    },
    {
        "agent_id": "aggressive",
        "name": "Bot Agressivo",
        "base_type": "heuristic",
        "is_custom": False,
        "description": "Perfil heurístico clássico focado em pressão e apostas altas.",
        "badge": "Bot",
    },
    {
        "agent_id": "conservative",
        "name": "Bot Conservador",
        "base_type": "heuristic",
        "is_custom": False,
        "description": "Perfil heurístico focado em proteção e pouca exposição.",
        "badge": "Bot",
    },
    {
        "agent_id": "balanced",
        "name": "Bot Equilibrado",
        "base_type": "heuristic",
        "is_custom": False,
        "description": "Perfil heurístico balanceado padrão de mesa.",
        "badge": "Bot",
    },
]


class AgentRegistry:
    """Gerenciador central de catálogo de agentes para mesas e simulações."""

    def __init__(self, catalog_file: Optional[Path] = None) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent
        default_catalog = project_root / "models" / "custom_trained_agents.json"
        target_file = catalog_file if catalog_file is not None else default_catalog
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            test_file = target_file.parent / ".write_test"
            test_file.touch()
            test_file.unlink(missing_ok=True)
            self.catalog_file = target_file
        except Exception:
            fallback_file = Path("/tmp/models/custom_trained_agents.json")
            try:
                fallback_file.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            self.catalog_file = fallback_file

        self.custom_agents: Dict[str, CustomAgentMetadata] = {}
        self.load()

    def list_available_agents(self) -> List[Dict[str, Any]]:
        """Retorna todos os agentes: originais da linha de base + novos treinados."""
        result: List[Dict[str, Any]] = list(STANDARD_AGENTS)

        for meta in sorted(
            self.custom_agents.values(), key=lambda a: a.created_at, reverse=True
        ):
            tier = meta.qualification.get("overall_tier", "Treinado")
            fit = meta.qualification.get("overall_fitness", 0.0)
            result.append({
                "agent_id": meta.agent_id,
                "name": f"⭐ {meta.name} [{tier} - {fit:.1f}pts]",
                "base_type": meta.base_type,
                "is_custom": True,
                "created_at": meta.created_at,
                "description": (
                    f"Agente {meta.base_type.capitalize()} customizado e treinado. "
                    f"Tier: {tier} ({fit:.1f} pts)."
                ),
                "badge": "Treinado",
                "parameters": meta.parameters,
                "qualification": meta.qualification,
            })

        return result

    def save_custom_agent(
        self,
        name: str,
        base_type: str,
        parameters: Dict[str, Any],
        qualification: Dict[str, Any],
        session_id: Optional[str] = None,
        description: str = "",
    ) -> CustomAgentMetadata:
        """Salva um NOVO agente treinado no catálogo sem alterar o original."""
        normalized_type = base_type.strip().lower()
        clamped_params = clamp_parameters(normalized_type, parameters)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        slug = name.strip().lower().replace(" ", "_")[:18]
        agent_id = f"custom_{normalized_type}_{slug}_{ts}"

        entry = CustomAgentMetadata(
            agent_id=agent_id,
            name=name.strip(),
            base_type=normalized_type,
            created_at=datetime.now(timezone.utc).isoformat(),
            parameters=clamped_params,
            qualification=qualification,
            session_id=session_id,
            description=description or f"Agente treinado em {ts}",
        )

        self.custom_agents[agent_id] = entry
        self.save()
        return entry

    def register_trained_agent(
        self,
        name: str,
        base_type: str,
        parameters: Dict[str, Any],
        qualification: Dict[str, Any],
        target_metric: Optional[str] = None,
        session_id: Optional[str] = None,
        description: str = "",
    ) -> CustomAgentMetadata:
        """Alias de conveniência para save_custom_agent com suporte a target_metric."""
        desc = description or (
            f"Agente treinado com foco em {target_metric}"
            if target_metric
            else ""
        )
        return self.save_custom_agent(
            name=name,
            base_type=base_type,
            parameters=parameters,
            qualification=qualification,
            session_id=session_id,
            description=desc,
        )

    def get_agent_info(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Busca metadados de um agente pelo identificador."""
        for std in STANDARD_AGENTS:
            if std["agent_id"] == agent_id:
                return dict(std)
        if agent_id in self.custom_agents:
            meta = self.custom_agents[agent_id]
            return {
                "agent_id": meta.agent_id,
                "name": meta.name,
                "base_type": meta.base_type,
                "is_custom": True,
                "created_at": meta.created_at,
                "parameters": meta.parameters,
                "qualification": meta.qualification,
                "description": meta.description,
            }
        return None

    def delete_custom_agent(self, agent_id: str) -> bool:
        """Exclui um agente customizado (os originais não podem ser excluídos)."""
        if agent_id in self.custom_agents:
            del self.custom_agents[agent_id]
            self.save()
            return True
        return False

    def instantiate_agent_by_id(
        self,
        agent_id: str,
        player_id: str,
        name: Optional[str] = None,
        rng: Optional[random.Random] = None,
    ) -> BaseAgent:
        """Instancia o agente correto (seja original de base ou novo treinado)."""
        local_rng = rng if rng is not None else random.Random()
        agent_key = (agent_id or "math").strip().lower()

        # 1. Caso seja um agente customizado salvo
        if agent_key in self.custom_agents:
            meta = self.custom_agents[agent_key]
            effective_name = name or meta.name
            if meta.base_type == "gh_bluffer":
                return GhBlufferAgent(
                    player_id=player_id,
                    name=effective_name,
                    rng=local_rng,
                    **meta.parameters,
                )
            elif meta.base_type == "bluffer":
                return BlufferAgent(
                    player_id=player_id,
                    name=effective_name,
                    rng=local_rng,
                    **meta.parameters,
                )
            elif meta.base_type == "gh_math":
                return GhMathAgent(
                    player_id=player_id,
                    name=effective_name,
                    rng=local_rng,
                    **meta.parameters,
                )
            else:  # mathematical
                return MathematicalAgent(
                    player_id=player_id,
                    name=effective_name,
                    rng=local_rng,
                    **meta.parameters,
                )

        # 2. Caso seja o Agente Treinador
        if agent_key == "trainer":
            from src.agents.trainer_agent import TrainerAgent
            return TrainerAgent(
                player_id=player_id,
                name=name or "Agente Treinador",
                rng=local_rng,
            )

        # 3. Agentes originais da linha de base
        if agent_key == "gh_bluffer":
            return GhBlufferAgent(
                player_id=player_id,
                name=name or "GhBlufferAgent (Original)",
                rng=local_rng,
            )
        elif agent_key == "gh_math":
            return GhMathAgent(
                player_id=player_id,
                name=name or "GhMathAgent (Original)",
                rng=local_rng,
            )
        elif agent_key == "bluffer":
            return BlufferAgent(
                player_id=player_id,
                name=name or "Agente Blefador (Original)",
                rng=local_rng,
            )
        elif agent_key == "hybrid":
            return HybridAgent(
                player_id=player_id,
                name=name or "Agente Híbrido (Original)",
                rng=local_rng,
            )
        elif agent_key == "aggressive":
            return HeuristicAgent(
                player_id=player_id,
                name=name or "Bot Agressivo",
                profile=AgentProfile.AGGRESSIVE,
                rng=local_rng,
            )
        elif agent_key == "conservative":
            return HeuristicAgent(
                player_id=player_id,
                name=name or "Bot Conservador",
                profile=AgentProfile.CONSERVATIVE,
                rng=local_rng,
            )
        elif agent_key == "balanced":
            return HeuristicAgent(
                player_id=player_id,
                name=name or "Bot Equilibrado",
                profile=AgentProfile.BALANCED,
                rng=local_rng,
            )
        else:  # default 'math'
            return MathematicalAgent(
                player_id=player_id,
                name=name or "Agente Matemático (Original)",
                rng=local_rng,
            )

    def save(self) -> None:
        """Persiste os agentes customizados em JSON com fallback seguro."""
        data = {aid: meta.to_dict() for aid, meta in self.custom_agents.items()}
        try:
            self.catalog_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.catalog_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError:
            try:
                fallback_file = Path("/tmp/models/custom_trained_agents.json")
                fallback_file.parent.mkdir(parents=True, exist_ok=True)
                with open(fallback_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self.catalog_file = fallback_file
            except Exception:
                pass

    def load(self) -> None:
        """Carrega agentes customizados pré-salvos."""
        if not self.catalog_file.exists():
            self.custom_agents = {}
            return
        try:
            with open(self.catalog_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.custom_agents = {
                aid: CustomAgentMetadata.from_dict(item)
                for aid, item in data.items()
            }
        except Exception:
            self.custom_agents = {}


# Instância global reutilizável
global_registry = AgentRegistry()
