import random
from typing import Dict, List, Optional, Sequence, Tuple, TypeVar

from src.engine.deck import Card, Deck

PlayerType = TypeVar("PlayerType")


class Dealer:
    """Gerencia a distribuição física das cartas, queimas e o bordo comunitário."""

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self._deck: Deck = Deck(rng=rng)
        self._community_cards: List[Card] = []
        self._burn_cards: List[Card] = []

    @property
    def community_cards(self) -> Tuple[Card, ...]:
        return tuple(self._community_cards)

    @property
    def burn_cards(self) -> Tuple[Card, ...]:
        return tuple(self._burn_cards)

    @property
    def deck(self) -> Deck:
        return self._deck

    def start_new_hand(self, rng: Optional[random.Random] = None) -> None:
        """Reinicia o baralho, esvazia o bordo e as cartas queimadas, e reembaralha."""
        self._deck.reset()
        self._deck.shuffle(rng=rng)
        self._community_cards.clear()
        self._burn_cards.clear()

    def deal_hole_cards(
        self, player_ids: Sequence[str]
    ) -> Dict[str, Tuple[Card, Card]]:
        """Distribui duas cartas fechadas para cada jogador alternando
        uma carta por rodada.

        Args:
            player_ids: Identificadores dos jogadores na ordem de ação da mesa.

        Returns:
            Mapeamento contendo o par ordenado de cartas fechadas de cada jogador.

        Raises:
            ValueError: Se a lista de jogadores for vazia.
        """
        if not player_ids:
            raise ValueError(
                "Ao menos um jogador deve ser fornecido para distribuição."
            )

        first_cards: Dict[str, Card] = {
            pid: self._deck.draw(1)[0] for pid in player_ids
        }
        second_cards: Dict[str, Card] = {
            pid: self._deck.draw(1)[0] for pid in player_ids
        }

        return {pid: (first_cards[pid], second_cards[pid]) for pid in player_ids}

    def deal_flop(self) -> Tuple[Card, Card, Card]:
        """Executa a queima de uma carta e abre as três cartas do Flop.

        Returns:
            Tupla contendo as três cartas abertas no Flop.

        Raises:
            RuntimeError: Se o Flop já tiver sido distribuído nesta mão.
        """
        if len(self._community_cards) != 0:
            raise RuntimeError(
                "O Flop só pode ser distribuído quando o bordo estiver vazio."
            )

        self._burn_cards.append(self._deck.burn())
        flop_cards = self._deck.draw(3)
        self._community_cards.extend(flop_cards)
        return (flop_cards[0], flop_cards[1], flop_cards[2])

    def deal_turn(self) -> Card:
        """Executa a queima de uma carta e abre a quarta carta comunitária (Turn).

        Returns:
            Instância da carta do Turn.

        Raises:
            RuntimeError: Se o Flop não tiver sido aberto ou o Turn já existir.
        """
        if len(self._community_cards) != 3:
            raise RuntimeError("O Turn exige exatamente 3 cartas comunitárias abertas.")

        self._burn_cards.append(self._deck.burn())
        turn_card = self._deck.draw(1)[0]
        self._community_cards.append(turn_card)
        return turn_card

    def deal_river(self) -> Card:
        """Executa a queima de uma carta e abre a quinta carta comunitária (River).

        Returns:
            Instância da carta do River.

        Raises:
            RuntimeError: Se o Turn não tiver sido aberto ou o River já existir.
        """
        if len(self._community_cards) != 4:
            raise RuntimeError(
                "O River exige exatamente 4 cartas comunitárias abertas."
            )

        self._burn_cards.append(self._deck.burn())
        river_card = self._deck.draw(1)[0]
        self._community_cards.append(river_card)
        return river_card
