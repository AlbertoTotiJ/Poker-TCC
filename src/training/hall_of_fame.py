"""Galeria de Campeões (Hall of Fame) para co-evolução e adaptação contínua.

Armazena os agentes de elite produzidos em cada sessão de treinamento.
Garante que as novas gerações e novos treinamentos se adaptem aos agentes previamente
produzidos, enfrentando-os como adversários para prevenir overfitting contra bots fixos
e promover corrida armamentista estratégica (adversarial co-evolution).
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import random
from typing import Any, Dict, List, Optional

from src.agents.base import BaseAgent
from src.agents.heuristic import AgentProfile, HeuristicAgent
from src.training.parameters import instantiate_agent


@dataclass
class ChampionEntry:
    """Registro de um agente de elite produzido pelo sistema."""

    champion_id: str
    agent_type: str
    generation: int
    fitness_score: float
    qualification_tier: str
    parameters: Dict[str, Any]
    target_metric_focused: Optional[str]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChampionEntry":
        return cls(**data)


class HallOfFame:
    """Gerencia o repositório de agentes produzidos e a seleção de adversários."""

    def __init__(self, storage_file: Optional[Path] = None) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent
        default_storage = project_root / "models" / "hall_of_fame.json"
        target_file = storage_file if storage_file is not None else default_storage
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            test_file = target_file.parent / ".write_test"
            test_file.touch()
            test_file.unlink(missing_ok=True)
            self.default_file = target_file
        except Exception:
            fallback_file = Path("/tmp/models/hall_of_fame.json")
            try:
                fallback_file.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            self.default_file = fallback_file

        self.champions: List[ChampionEntry] = []
        self.load()

    def add_champion(
        self,
        agent_type: str,
        parameters: Dict[str, Any],
        fitness_score: float,
        qualification_tier: str,
        generation: int = 1,
        target_focus: Optional[str] = None,
    ) -> ChampionEntry:
        """Registra um novo agente de elite no Hall of Fame."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        champ_id = f"champ_{agent_type}_{ts}_g{generation}"
        entry = ChampionEntry(
            champion_id=champ_id,
            agent_type=agent_type,
            generation=generation,
            fitness_score=round(fitness_score, 2),
            qualification_tier=qualification_tier,
            parameters=parameters,
            target_metric_focused=target_focus,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.champions.append(entry)
        # Ordena do maior fitness para o menor
        self.champions.sort(key=lambda c: c.fitness_score, reverse=True)
        # Mantém até os 20 melhores campeões globais
        if len(self.champions) > 20:
            self.champions = self.champions[:20]
        self.save()
        return entry

    def get_top_champions(
        self, limit: int = 5, agent_type: Optional[str] = None
    ) -> List[ChampionEntry]:
        """Retorna os melhores campeões salvos, opcionalmente filtrados por tipo."""
        filtered = (
            [c for c in self.champions if c.agent_type == agent_type]
            if agent_type
            else self.champions
        )
        return filtered[:limit]

    def build_adaptive_opponents(
        self,
        candidate_agent_type: str,
        num_opponents: int = 5,
        rng: Optional[random.Random] = None,
    ) -> List[BaseAgent]:
        """Cria um pool de adversários adaptativo para testar o candidato.

        Inclui campeões produzidos em iterações anteriores combinados com
        perfis heurísticos fundamentais (Agressivo, Equilibrado, Conservador)
        para garantir avaliação robusta contra múltiplos estilos.
        """
        r = rng if rng is not None else random.Random()
        opponents: List[BaseAgent] = []

        # 1. Inclui até 2 campeões do Hall of Fame (adaptação a agentes produzidos)
        available_champs = list(self.champions)
        if available_champs:
            r.shuffle(available_champs)
            champs_to_include = available_champs[: min(2, num_opponents - 1)]
            for i, champ in enumerate(champs_to_include, 1):
                c_type = champ.agent_type.capitalize()
                agent_inst = instantiate_agent(
                    agent_type=champ.agent_type,
                    player_id=f"champ_{i}_{champ.champion_id[:12]}",
                    name=f"Campeão ({c_type} G{champ.generation})",
                    params=champ.parameters,
                    rng=r,
                )
                opponents.append(agent_inst)

        # 2. Completa com perfis padrão e heurísticos
        standard_profiles = [
            (AgentProfile.AGGRESSIVE, "Bot Agressivo"),
            (AgentProfile.BALANCED, "Bot Equilibrado"),
            (AgentProfile.CONSERVATIVE, "Bot Conservador"),
        ]
        r.shuffle(standard_profiles)

        counter = 1
        while len(opponents) < num_opponents:
            prof, prof_name = standard_profiles[
                (counter - 1) % len(standard_profiles)
            ]
            bot = HeuristicAgent(
                player_id=f"bot_opp_{counter}",
                name=f"{prof_name} #{counter}",
                profile=prof,
                rng=r,
            )
            opponents.append(bot)
            counter += 1

        return opponents

    def save(self, filepath: Optional[Path] = None) -> None:
        """Persiste a lista de campeões em JSON com fallback seguro."""
        target = filepath if filepath is not None else self.default_file
        data = [c.to_dict() for c in self.champions]
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError:
            try:
                fallback_file = Path("/tmp/models/hall_of_fame.json")
                fallback_file.parent.mkdir(parents=True, exist_ok=True)
                with open(fallback_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self.default_file = fallback_file
            except Exception:
                pass

    def load(self, filepath: Optional[Path] = None) -> None:
        """Carrega a lista de campeões do arquivo se existir."""
        target = filepath if filepath is not None else self.default_file
        if not target.exists():
            self.champions = []
            return
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.champions = [ChampionEntry.from_dict(item) for item in data]
        except Exception:
            self.champions = []
