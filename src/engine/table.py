from dataclasses import dataclass
from enum import Enum, auto
import random
from typing import Dict, List, Optional, Sequence, Set, Tuple

from src.engine.dealer import Dealer
from src.engine.deck import Card
from src.engine.hand_eval import HandScore, evaluate_hand
from src.engine.player import Player
from src.engine.pot import PotManager


class Street(Enum):
    PREFLOP = auto()
    FLOP = auto()
    TURN = auto()
    RIVER = auto()
    SHOWDOWN = auto()
    FINISHED = auto()


class ActionType(Enum):
    FOLD = "FOLD"
    CHECK = "CHECK"
    CALL = "CALL"
    BET = "BET"
    RAISE = "RAISE"
    ALL_IN = "ALL_IN"


@dataclass(frozen=True)
class Action:
    player_id: str
    action_type: ActionType
    amount: int = 0


@dataclass(frozen=True)
class TableState:
    """Snapshot imutável do estado observável da mesa."""

    street: Street
    community_cards: Tuple[Card, ...]
    pot_total: int
    current_highest_bet: int
    min_raise: int
    active_player_ids: Tuple[str, ...]
    dealer_button_idx: int
    current_player_id: Optional[str]


class Table:
    """Controlador central das regras de mesa, blinds e transições de rodada."""

    def __init__(
        self,
        players: Sequence[Player],
        small_blind: int,
        big_blind: int,
        rng: Optional[random.Random] = None,
        button_idx: int = 0,
    ) -> None:
        if len(players) < 2:
            raise ValueError("Uma mesa de Texas Hold'em exige no mínimo 2 jogadores.")
        if small_blind <= 0 or big_blind <= small_blind:
            raise ValueError("Blinds devem ser positivos com big_blind > small_blind.")

        self._players: List[Player] = list(players)
        self._small_blind: int = small_blind
        self._big_blind: int = big_blind
        self._dealer: Dealer = Dealer(rng=rng)
        self._pot_manager: PotManager = PotManager()

        self._button_idx: int = button_idx % len(self._players)
        self._street: Street = Street.PREFLOP
        self._current_player_idx: int = 0
        self._current_highest_bet: int = 0
        self._min_raise: int = big_blind
        self._last_aggressor_idx: Optional[int] = None
        self._acted_this_round: Set[str] = set()
        self._incomplete_raise_locked_players: Set[str] = set()
        self._last_payouts: Dict[str, int] = {}
        self._last_scores: Dict[str, HandScore] = {}

    @property
    def players(self) -> Tuple[Player, ...]:
        return tuple(self._players)

    @property
    def dealer(self) -> Dealer:
        return self._dealer

    @property
    def pot_manager(self) -> PotManager:
        return self._pot_manager

    @property
    def street(self) -> Street:
        return self._street

    @property
    def community_cards(self) -> Tuple[Card, ...]:
        return self._dealer.community_cards

    @property
    def current_highest_bet(self) -> int:
        return self._current_highest_bet

    @property
    def min_raise(self) -> int:
        return self._min_raise

    @property
    def button_idx(self) -> int:
        return self._button_idx

    @property
    def last_payouts(self) -> Dict[str, int]:
        return dict(self._last_payouts)

    @property
    def last_scores(self) -> Dict[str, HandScore]:
        return dict(self._last_scores)

    @property
    def current_player(self) -> Optional[Player]:
        if self._street in (Street.SHOWDOWN, Street.FINISHED):
            return None
        return self._players[self._current_player_idx]

    def _next_chip_player_idx(self, from_idx: int) -> int:
        """Localiza o próximo jogador em sentido horário que ainda possui fichas."""
        num = len(self._players)
        for step in range(1, num + 1):
            idx = (from_idx + step) % num
            if self._players[idx].stack > 0:
                return idx
        return from_idx

    def start_new_hand(self, rng: Optional[random.Random] = None) -> None:
        """Inicia uma nova mão: prepara stacks, posta blinds e distribui cartas."""
        active_with_chips = [p for p in self._players if p.stack > 0]
        if len(active_with_chips) < 2:
            raise RuntimeError(
                "Não há jogadores com fichas suficientes para iniciar nova mão."
            )

        for player in self._players:
            player.reset_for_hand()

        self._pot_manager.reset()
        self._dealer.start_new_hand(rng=rng)
        self._street = Street.PREFLOP
        self._acted_this_round.clear()
        self._incomplete_raise_locked_players.clear()
        self._last_payouts.clear()
        self._last_scores.clear()

        # Garante que o botão pertença a um jogador com fichas
        if self._players[self._button_idx].stack == 0:
            self._button_idx = self._next_chip_player_idx(self._button_idx)

        num_chip_players = len(active_with_chips)

        # Heads-up (2 jogadores com fichas): Dealer é Small Blind e age primeiro
        if num_chip_players == 2:
            sb_idx = self._button_idx
            bb_idx = self._next_chip_player_idx(self._button_idx)
            first_to_act_idx = sb_idx
        else:
            sb_idx = self._next_chip_player_idx(self._button_idx)
            bb_idx = self._next_chip_player_idx(sb_idx)
            first_to_act_idx = self._next_chip_player_idx(bb_idx)

        sb_player = self._players[sb_idx]
        posted_sb = sb_player.post_bet(self._small_blind)
        self._pot_manager.add_contribution(sb_player.player_id, posted_sb)

        bb_player = self._players[bb_idx]
        posted_bb = bb_player.post_bet(self._big_blind)
        self._pot_manager.add_contribution(bb_player.player_id, posted_bb)

        self._current_highest_bet = max(posted_sb, posted_bb)
        self._min_raise = self._big_blind
        self._last_aggressor_idx = bb_idx

        # Distribuição física pelo Dealer apenas para jogadores ativos
        active_ids = [p.player_id for p in self._players if p.is_active]
        hole_map = self._dealer.deal_hole_cards(active_ids)
        for player in self._players:
            if player.player_id in hole_map:
                player.hole_cards = hole_map[player.player_id]

        self._current_player_idx = first_to_act_idx
        self._ensure_valid_current_player()

    def get_legal_actions(self, player_id: str) -> List[ActionType]:
        """Calcula o conjunto de ações estritamente válidas para o jogador."""
        player = self._get_player_by_id(player_id)
        if not player.is_active or player.is_all_in:
            return []

        call_amount = self._current_highest_bet - player.current_bet
        actions: List[ActionType] = [ActionType.FOLD]

        if call_amount == 0:
            actions.append(ActionType.CHECK)
            if player.stack > 0:
                actions.append(ActionType.BET)
        else:
            if player.stack > call_amount:
                actions.append(ActionType.CALL)
                # Regra TDA 44 / Full Raise: Jogadores que já pagaram aposta prévia
                # e enfrentam apenas aumento incompleto não podem aumentar novamente
                if player_id not in self._incomplete_raise_locked_players:
                    actions.append(ActionType.RAISE)
            else:
                actions.append(ActionType.ALL_IN)

        return actions

    def apply_action(self, action: Action) -> None:
        """Processa a ação de aposta de um jogador e avança o estado da mesa."""
        player = self.current_player
        if player is None or player.player_id != action.player_id:
            raise ValueError(
                f"Ação fora da vez ou jogador inválido: {action.player_id}"
            )

        legal_types = self.get_legal_actions(player.player_id)
        if (
            action.action_type not in legal_types
            and action.action_type != ActionType.ALL_IN
        ):
            raise ValueError(
                f"Ação {action.action_type} ilegal. Ações permitidas: {legal_types}"
            )

        call_gap = self._current_highest_bet - player.current_bet

        if action.action_type == ActionType.FOLD:
            player.fold()

        elif action.action_type == ActionType.CHECK:
            if call_gap > 0:
                raise ValueError("Check ilegal com aposta pendente para pagar.")

        elif action.action_type == ActionType.CALL:
            posted = player.post_bet(call_gap)
            self._pot_manager.add_contribution(player.player_id, posted)

        elif action.action_type == ActionType.BET:
            if self._current_highest_bet > 0 and call_gap > 0:
                raise ValueError(
                    "Bet ilegal após abertura de aposta existente; use RAISE."
                )
            if action.amount < self._big_blind and action.amount < player.stack:
                raise ValueError(f"Bet mínimo é {self._big_blind}.")
            posted = player.post_bet(action.amount)
            self._pot_manager.add_contribution(player.player_id, posted)
            self._current_highest_bet = player.current_bet
            self._min_raise = max(posted, self._big_blind)
            self._last_aggressor_idx = self._current_player_idx
            self._incomplete_raise_locked_players.clear()
            self._acted_this_round.clear()

        elif action.action_type == ActionType.RAISE:
            min_required = self._current_highest_bet + self._min_raise
            if (
                action.amount < min_required
                and action.amount < player.current_bet + player.stack
            ):
                raise ValueError(
                    f"Aumento mínimo exigido é para o total de {min_required}."
                )
            prev_highest = self._current_highest_bet
            to_post = action.amount - player.current_bet
            posted = player.post_bet(to_post)
            self._pot_manager.add_contribution(player.player_id, posted)
            raise_size = player.current_bet - prev_highest

            if raise_size >= self._min_raise:
                self._min_raise = raise_size
                self._incomplete_raise_locked_players.clear()
                self._acted_this_round.clear()
            else:
                # Aumento incompleto (all-in menor que o raise mínimo)
                for p in self._players:
                    if (
                        p.is_active
                        and p.current_bet == prev_highest
                        and p.player_id != player.player_id
                    ):
                        self._incomplete_raise_locked_players.add(p.player_id)

            self._current_highest_bet = player.current_bet
            self._last_aggressor_idx = self._current_player_idx

        elif action.action_type == ActionType.ALL_IN:
            prev_highest = self._current_highest_bet
            posted = player.post_bet(player.stack)
            self._pot_manager.add_contribution(player.player_id, posted)
            if player.current_bet > prev_highest:
                raise_size = player.current_bet - prev_highest
                if raise_size >= self._min_raise:
                    self._min_raise = raise_size
                    self._incomplete_raise_locked_players.clear()
                    self._acted_this_round.clear()
                else:
                    # Aumento incompleto
                    for p in self._players:
                        if (
                            p.is_active
                            and p.current_bet == prev_highest
                            and p.player_id != player.player_id
                        ):
                            self._incomplete_raise_locked_players.add(p.player_id)
                self._current_highest_bet = player.current_bet
                self._last_aggressor_idx = self._current_player_idx

        self._acted_this_round.add(player.player_id)
        self._post_action_transition()

    def _post_action_transition(self) -> None:
        """Determina o avanço de jogador ou a transição para a próxima street."""
        active_players = [p for p in self._players if p.is_active]

        # Se resta apenas 1 jogador ativo, encerra com vitória imediata por fold
        if len(active_players) == 1:
            self._resolve_uncontested_pot(active_players[0])
            return

        players_can_act = [p for p in active_players if not p.is_all_in]

        # Concluído quando todos os aptos agiram e cobriram a maior aposta
        all_matched = all(
            p.current_bet == self._current_highest_bet for p in players_can_act
        )
        all_acted = all(p.player_id in self._acted_this_round for p in players_can_act)

        if (all_matched and all_acted) or len(players_can_act) <= 1:
            if len(players_can_act) <= 1 and all_matched:
                self._advance_street_or_runout()
            elif all_matched and all_acted:
                self._advance_street()
            else:
                self._advance_to_next_player()
        else:
            self._advance_to_next_player()

    def _advance_to_next_player(self) -> None:
        num_players = len(self._players)
        for step in range(1, num_players + 1):
            next_idx = (self._current_player_idx + step) % num_players
            candidate = self._players[next_idx]
            if candidate.is_active and not candidate.is_all_in:
                self._current_player_idx = next_idx
                return

    def _advance_street(self) -> None:
        """Avança para a próxima street distribuindo as cartas correspondentes."""
        for player in self._players:
            player.reset_street_bet()

        self._acted_this_round.clear()
        self._incomplete_raise_locked_players.clear()
        self._current_highest_bet = 0
        self._min_raise = self._big_blind
        self._last_aggressor_idx = None

        if self._street == Street.PREFLOP:
            self._dealer.deal_flop()
            self._street = Street.FLOP
        elif self._street == Street.FLOP:
            self._dealer.deal_turn()
            self._street = Street.TURN
        elif self._street == Street.TURN:
            self._dealer.deal_river()
            self._street = Street.RIVER
        elif self._street == Street.RIVER:
            self._street = Street.SHOWDOWN
            self._resolve_showdown()
            return

        # Pós-flop: Primeiro a falar é a primeira posição ativa à esquerda do botão
        self._current_player_idx = self._next_chip_player_idx(self._button_idx)
        self._ensure_valid_current_player()

    def _advance_street_or_runout(self) -> None:
        """Avança as cartas restantes quando jogadores estão all-in até o Showdown."""
        while self._street != Street.SHOWDOWN and self._street != Street.FINISHED:
            if self._street == Street.PREFLOP:
                self._dealer.deal_flop()
                self._street = Street.FLOP
            elif self._street == Street.FLOP:
                self._dealer.deal_turn()
                self._street = Street.TURN
            elif self._street == Street.TURN:
                self._dealer.deal_river()
                self._street = Street.RIVER
            elif self._street == Street.RIVER:
                self._street = Street.SHOWDOWN
                self._resolve_showdown()
                break

    def _ensure_valid_current_player(self) -> None:
        num_players = len(self._players)
        for _ in range(num_players):
            p = self._players[self._current_player_idx]
            if p.is_active and not p.is_all_in:
                return
            self._current_player_idx = (self._current_player_idx + 1) % num_players

    def _resolve_uncontested_pot(self, winner: Player) -> None:
        """Transfere todas as fichas ao único jogador remanescente após desistências."""
        total = self._pot_manager.total_pot
        winner.award(total)
        self._last_payouts = {winner.player_id: total}
        self._last_scores = {}
        self._street = Street.FINISHED
        self._button_idx = self._next_chip_player_idx(self._button_idx)

    def _resolve_showdown(self) -> Dict[str, int]:
        """Avalia mãos no Showdown e distribui potes principais e paralelos."""
        active_players = [p for p in self._players if p.is_active]
        non_folded_ids = {p.player_id for p in active_players}
        pots = self._pot_manager.build_pots(non_folded_ids)

        scores: Dict[str, HandScore] = {}
        for player in active_players:
            if player.hole_cards is not None:
                all_cards = list(player.hole_cards) + list(self._dealer.community_cards)
                scores[player.player_id] = evaluate_hand(all_cards)

        # Ordem horária de assentos para desempate do chip ímpar (odd chip)
        table_order = [
            self._players[(self._button_idx + 1 + i) % len(self._players)].player_id
            for i in range(len(self._players))
        ]
        payouts = self._pot_manager.payout(pots, scores, table_order=table_order)
        for player in active_players:
            if player.player_id in payouts:
                player.award(payouts[player.player_id])

        self._last_payouts = payouts
        self._last_scores = scores
        self._street = Street.FINISHED
        self._button_idx = self._next_chip_player_idx(self._button_idx)
        return payouts

    def _get_player_by_id(self, player_id: str) -> Player:
        for p in self._players:
            if p.player_id == player_id:
                return p
        raise KeyError(f"Jogador não encontrado: {player_id}")
