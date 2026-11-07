"""Interface abstrata base para agentes de Texas Hold'em."""

from abc import ABC, abstractmethod

from src.engine.table import Action, Table


class BaseAgent(ABC):
    """Contrato abstrato que define a tomada de decisão de um agente na mesa."""

    def __init__(self, player_id: str, name: str) -> None:
        self.player_id: str = player_id
        self.name: str = name

    @abstractmethod
    def decide_action(self, table: Table) -> Action:
        """Determina e retorna a ação a ser executada na mesa.

        Args:
            table: Instância ativa da mesa contendo o estado atual do jogo.

        Returns:
            Ação escolhida pelo agente (Action com player_id, ActionType e valor).
        """
        pass
