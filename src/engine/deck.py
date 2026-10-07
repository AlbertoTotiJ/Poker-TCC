from dataclasses import dataclass
from enum import Enum, IntEnum
import random
from typing import Final, List, Optional, Tuple


class Suit(Enum):
    SPADES = "♠"
    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"

    @classmethod
    def from_symbol(cls, symbol: str) -> "Suit":
        """Converte caractere textual ou símbolo de naipe em instância de Suit.

        Args:
            symbol: Letra ('s', 'h', 'd', 'c') ou glifo ('♠', '♥', '♦', '♣').

        Returns:
            Instância correspondente de Suit.

        Raises:
            ValueError: Se o símbolo não corresponder a um naipe válido.
        """
        symbol_map: Final[dict[str, "Suit"]] = {
            "s": cls.SPADES,
            "♠": cls.SPADES,
            "h": cls.HEARTS,
            "♥": cls.HEARTS,
            "d": cls.DIAMONDS,
            "♦": cls.DIAMONDS,
            "c": cls.CLUBS,
            "♣": cls.CLUBS,
        }
        normalized = symbol.strip().lower()
        if normalized not in symbol_map:
            raise ValueError(f"Símbolo de naipe inválido: {symbol}")
        return symbol_map[normalized]


class Rank(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def symbol(self) -> str:
        symbol_map: Final[dict[int, str]] = {
            10: "T",
            11: "J",
            12: "Q",
            13: "K",
            14: "A",
        }
        return symbol_map.get(self.value, str(self.value))

    @classmethod
    def from_char(cls, char: str) -> "Rank":
        """Converte caractere textual em instância de Rank.

        Args:
            char: Caractere representando o ranque ('2'-'9', 'T', 'J', 'Q', 'K', 'A').

        Returns:
            Instância correspondente de Rank.

        Raises:
            ValueError: Se o caractere não corresponder a um ranque válido.
        """
        char_map: Final[dict[str, "Rank"]] = {
            "2": cls.TWO,
            "3": cls.THREE,
            "4": cls.FOUR,
            "5": cls.FIVE,
            "6": cls.SIX,
            "7": cls.SEVEN,
            "8": cls.EIGHT,
            "9": cls.NINE,
            "t": cls.TEN,
            "10": cls.TEN,
            "j": cls.JACK,
            "q": cls.QUEEN,
            "k": cls.KING,
            "a": cls.ACE,
        }
        normalized = char.strip().lower()
        if normalized not in char_map:
            raise ValueError(f"Caractere de ranque inválido: {char}")
        return char_map[normalized]


@dataclass(frozen=True, order=True)
class Card:
    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank.symbol}{self.suit.value}"

    def __repr__(self) -> str:
        return f"Card({self.rank.name}, {self.suit.name})"

    @classmethod
    def from_str(cls, text: str) -> "Card":
        """Instancia Card a partir de formato textual compacto (ex: 'As', 'Td').

        Args:
            text: String com ranque e naipe concatenados.

        Returns:
            Instância de Card.

        Raises:
            ValueError: Se o formato textual for incompatível com 2 caracteres válidos.
        """
        cleaned = text.strip()
        if len(cleaned) < 2:
            raise ValueError(f"String de carta com formato inválido: '{text}'")

        rank_part = cleaned[:-1]
        suit_part = cleaned[-1]
        return cls(rank=Rank.from_char(rank_part), suit=Suit.from_symbol(suit_part))


class Deck:
    """Baralho padrão de 52 cartas com suporte a semente determinística."""

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        self._rng: random.Random = rng if rng is not None else random.Random()
        self._cards: List[Card] = []
        self.reset()

    def reset(self) -> None:
        """Restaura as 52 cartas originais sem embaralhar."""
        self._cards = [Card(rank=rank, suit=suit) for suit in Suit for rank in Rank]

    def shuffle(self, rng: Optional[random.Random] = None) -> None:
        """Embaralha as cartas remanescentes in-place.

        Args:
            rng: Gerador de números pseudoaleatórios opcional para reprodutibilidade.
        """
        if rng is not None:
            self._rng = rng
        self._rng.shuffle(self._cards)

    def draw(self, count: int = 1) -> List[Card]:
        """Remove e retorna cartas do topo do baralho.

        Args:
            count: Quantidade de cartas a retirar.

        Returns:
            Lista de instâncias de Card retiradas.

        Raises:
            ValueError: Se a quantidade solicitada exceder as cartas disponíveis.
        """
        if count <= 0:
            raise ValueError(
                f"Quantidade de retirada deve ser positiva. Recebido: {count}"
            )
        if count > len(self._cards):
            raise ValueError(
                f"Cartas insuficientes. Solicitadas: {count}, "
                f"disponíveis: {len(self._cards)}"
            )

        drawn = self._cards[-count:]
        del self._cards[-count:]
        return list(reversed(drawn))

    def burn(self) -> Card:
        """Descarta a carta do topo seguindo o protocolo oficial de descarte.

        Returns:
            Instância da carta queimada.
        """
        drawn = self.draw(1)
        return drawn[0]

    def __len__(self) -> int:
        return len(self._cards)

    @property
    def remaining_cards(self) -> Tuple[Card, ...]:
        return tuple(self._cards)
