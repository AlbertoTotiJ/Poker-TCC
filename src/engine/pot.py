from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from src.engine.hand_eval import HandScore


@dataclass
class Pot:
    amount: int = 0
    eligible_players: Set[str] = field(default_factory=set)


@dataclass
class PotAward:
    """Detalhamento da distribuição de um pote individual (principal ou lateral)."""

    pot_index: int
    pot_type: str
    amount: int
    eligible_player_ids: List[str]
    winning_player_ids: List[str]
    winning_score: Optional[HandScore]
    payouts: Dict[str, int]
    is_split: bool
    odd_chip_awarded_to: Optional[str] = None


class PotManager:
    """Gerencia a acumulação de apostas e partição em potes e side pots."""

    def __init__(self) -> None:
        self._contributions: Dict[str, int] = {}

    @property
    def total_pot(self) -> int:
        return sum(self._contributions.values())

    @property
    def contributions(self) -> Dict[str, int]:
        return dict(self._contributions)

    def add_contribution(self, player_id: str, amount: int) -> None:
        """Acumula valor de aposta de um jogador.

        Args:
            player_id: Identificador do jogador.
            amount: Quantidade de fichas adicionadas.

        Raises:
            ValueError: Se o valor for negativo.
        """
        if amount < 0:
            raise ValueError(f"Aposta não pode ser negativa: {amount}")
        self._contributions[player_id] = self._contributions.get(player_id, 0) + amount

    def build_pots(self, non_folded_players: Set[str]) -> List[Pot]:
        """Calcula a partição em pote principal e side pots conforme all-ins.

        Args:
            non_folded_players: Conjunto de jogadores ativos que disputam a mão.

        Returns:
            Lista ordenada de instâncias de Pot (pote principal e eventuais side pots).
        """
        if not self._contributions:
            return []

        active_contributions = {
            pid: amt for pid, amt in self._contributions.items() if amt > 0
        }
        if not active_contributions:
            return []

        sorted_levels = sorted(set(active_contributions.values()))
        pots: List[Pot] = []
        previous_level = 0

        for level in sorted_levels:
            slice_per_player = level - previous_level
            current_slice_total = 0
            eligible_for_slice: Set[str] = set()

            for pid, amt in active_contributions.items():
                if amt >= level:
                    current_slice_total += slice_per_player
                    if pid in non_folded_players:
                        eligible_for_slice.add(pid)

            if current_slice_total > 0 and eligible_for_slice:
                pots.append(
                    Pot(amount=current_slice_total, eligible_players=eligible_for_slice)
                )
            elif current_slice_total > 0 and not eligible_for_slice:
                # Caso extremo onde todos que contribuíram até este nível foldaram
                if pots:
                    pots[-1].amount += current_slice_total

            previous_level = level

        # Mescla potes consecutivos que compartilham os mesmos jogadores elegíveis
        merged_pots: List[Pot] = []
        for pot in pots:
            if merged_pots and merged_pots[-1].eligible_players == pot.eligible_players:
                merged_pots[-1].amount += pot.amount
            else:
                merged_pots.append(pot)

        return merged_pots

    def resolve_pots(
        self,
        pots: List[Pot],
        player_scores: Dict[str, HandScore],
        table_order: Optional[Sequence[str]] = None,
    ) -> Tuple[Dict[str, int], List[PotAward]]:
        """Calcula a partição e premiação de cada pote (principal e side pots)."""
        winnings: Dict[str, int] = {pid: 0 for pid in player_scores}
        awards: List[PotAward] = []

        for idx, pot in enumerate(pots):
            contenders = [pid for pid in pot.eligible_players if pid in player_scores]
            pot_type = "Principal" if idx == 0 else f"Paralelo #{idx}"
            pot_payouts: Dict[str, int] = {}
            odd_chip_recipient = None

            if not contenders:
                fallback_recipients = [
                    pid for pid in pot.eligible_players if pid in winnings
                ] or list(winnings.keys())
                if fallback_recipients:
                    fb_share = pot.amount // len(fallback_recipients)
                    for pid in fallback_recipients:
                        winnings[pid] += fb_share
                        pot_payouts[pid] = fb_share
                awards.append(
                    PotAward(
                        pot_index=idx,
                        pot_type=pot_type,
                        amount=pot.amount,
                        eligible_player_ids=list(pot.eligible_players),
                        winning_player_ids=fallback_recipients,
                        winning_score=None,
                        payouts=pot_payouts,
                        is_split=len(fallback_recipients) > 1,
                    )
                )
                continue

            highest_score = max(player_scores[pid] for pid in contenders)
            winners = [pid for pid in contenders if player_scores[pid] == highest_score]

            if table_order:
                order_map = {pid: i for i, pid in enumerate(table_order)}
                winners.sort(key=lambda pid: order_map.get(pid, 9999))
            else:
                winners.sort()

            is_split = len(winners) > 1 and len(contenders) > 1
            share = pot.amount // len(winners)
            remainder = pot.amount % len(winners)

            for winner in winners:
                winnings[winner] += share
                pot_payouts[winner] = share

            if remainder > 0 and winners:
                odd_chip_recipient = winners[0]
                for i in range(remainder):
                    target = winners[i % len(winners)]
                    winnings[target] += 1
                    pot_payouts[target] = pot_payouts.get(target, 0) + 1

            awards.append(
                PotAward(
                    pot_index=idx,
                    pot_type=pot_type,
                    amount=pot.amount,
                    eligible_player_ids=list(pot.eligible_players),
                    winning_player_ids=winners,
                    winning_score=highest_score,
                    payouts=pot_payouts,
                    is_split=is_split,
                    odd_chip_awarded_to=odd_chip_recipient,
                )
            )

        return winnings, awards

    def payout(
        self,
        pots: List[Pot],
        player_scores: Dict[str, HandScore],
        table_order: Optional[Sequence[str]] = None,
    ) -> Dict[str, int]:
        """Distribui as fichas aos vencedores elegíveis por mérito de HandScore."""
        winnings, _ = self.resolve_pots(pots, player_scores, table_order=table_order)
        return winnings

    def reset(self) -> None:
        """Limpa as contribuições para início de nova mão."""
        self._contributions.clear()
