from dataclasses import dataclass
from typing import Optional, Tuple

from src.engine.deck import Card


@dataclass
class Player:
    """Representação de um jogador participante de uma mesa de poker."""

    player_id: str
    name: str
    stack: int
    hole_cards: Optional[Tuple[Card, Card]] = None
    is_active: bool = True
    is_all_in: bool = False
    current_bet: int = 0
    total_bet: int = 0

    def post_bet(self, amount: int) -> int:
        """Deduz valor do stack do jogador e acumula nas apostas da rodada e da mão.

        Args:
            amount: Valor desejado da aposta.

        Returns:
            Valor real postado (limitado pelo stack restante em caso de all-in).

        Raises:
            ValueError: Se o valor for negativo.
        """
        if amount < 0:
            raise ValueError(f"Valor de aposta inválido: {amount}")

        actual_amount = min(self.stack, amount)
        self.stack -= actual_amount
        self.current_bet += actual_amount
        self.total_bet += actual_amount

        if self.stack == 0 and actual_amount > 0:
            self.is_all_in = True

        return actual_amount

    def fold(self) -> None:
        """Marca o jogador como inativo na mão corrente."""
        self.is_active = False

    def reset_street_bet(self) -> None:
        """Zera a aposta local da street para início da próxima rodada de apostas."""
        self.current_bet = 0

    def reset_for_hand(self) -> None:
        """Restaura o estado do jogador para uma nova mão."""
        self.hole_cards = None
        self.is_active = self.stack > 0
        self.is_all_in = False
        self.current_bet = 0
        self.total_bet = 0

    def award(self, amount: int) -> None:
        """Adiciona fichas ao stack decorrentes de premiação de pote.

        Args:
            amount: Quantidade de fichas a creditar.
        """
        if amount < 0:
            raise ValueError(f"Premiação não pode ser negativa: {amount}")
        self.stack += amount
