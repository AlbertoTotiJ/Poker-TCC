"""Módulo de regras fundamentais e mecânicas do Texas Hold'em."""

from src.engine.dealer import Dealer
from src.engine.deck import Card, Deck, Rank, Suit
from src.engine.encoding import (
    card_to_id,
    cards_to_one_hot,
    hand_rank_to_one_hot,
    id_to_card,
    street_to_one_hot,
)
from src.engine.equity import (
    EquityResult,
    calculate_pot_odds,
    estimate_hand_equity,
    has_flush_draw,
    has_overcards,
    has_straight_draw,
    is_profitable_call,
)
from src.engine.hand_eval import (
    HandRank,
    HandScore,
    describe_hand,
    evaluate_hand,
    get_hand_rank_name_pt,
)
from src.engine.player import Player
from src.engine.pot import Pot, PotManager
from src.engine.rl_env import DiscreteAction, PokerEnv
from src.engine.table import Action, ActionType, Street, Table, TableState

__all__ = [
    "Card",
    "Deck",
    "Rank",
    "Suit",
    "Dealer",
    "HandRank",
    "HandScore",
    "evaluate_hand",
    "describe_hand",
    "get_hand_rank_name_pt",
    "Player",
    "Pot",
    "PotManager",
    "Action",
    "ActionType",
    "Street",
    "Table",
    "TableState",
    "card_to_id",
    "id_to_card",
    "cards_to_one_hot",
    "hand_rank_to_one_hot",
    "street_to_one_hot",
    "EquityResult",
    "estimate_hand_equity",
    "calculate_pot_odds",
    "is_profitable_call",
    "has_flush_draw",
    "has_straight_draw",
    "has_overcards",
    "DiscreteAction",
    "PokerEnv",
]
