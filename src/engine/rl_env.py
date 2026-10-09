"""Ambiente de Reinforcement Learning (Gymnasium-compatible) para Texas Hold'em."""

from enum import IntEnum
import random
from typing import Any, Dict, List, Optional, Tuple

from src.engine.encoding import cards_to_one_hot, street_to_one_hot
from src.engine.equity import calculate_pot_odds, estimate_hand_equity
from src.engine.player import Player
from src.engine.table import Action, ActionType, Street, Table


class DiscreteAction(IntEnum):
    """Espaço discreto de ações padronizado para treinamento de RL."""

    FOLD = 0
    CHECK_CALL = 1
    MIN_RAISE = 2
    HALF_POT = 3
    POT = 4
    ALL_IN = 5


class PokerEnv:
    """Ambiente de treinamento compatível com OpenAI Gym / Gymnasium.

    Permite treinar agentes de RL (PPO, DQN, A2C, SAC, CFR) enfrentando bots
    autônomos ou em regime de self-play.
    """

    def __init__(
        self,
        num_players: int = 2,
        starting_stack: int = 1000,
        small_blind: int = 10,
        big_blind: int = 20,
        hero_id: str = "hero",
        seed: Optional[int] = None,
    ) -> None:
        if not (2 <= num_players <= 9):
            raise ValueError("O número de jogadores deve estar entre 2 e 9.")

        self.num_players: int = num_players
        self.starting_stack: int = starting_stack
        self.small_blind: int = small_blind
        self.big_blind: int = big_blind
        self.hero_id: str = hero_id
        self.rng: random.Random = random.Random(seed)

        self._bots: Dict[str, Any] = {}
        self._table: Optional[Table] = None
        self._initial_hero_stack: int = starting_stack

    @property
    def table(self) -> Table:
        if self._table is None:
            raise RuntimeError("O ambiente precisa ser reiniciado via reset().")
        return self._table

    def reset(
        self, seed: Optional[int] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Reinicia o ambiente para o início de uma nova mão.

        Returns:
            Tupla (observation, info) seguindo o padrão do Gymnasium.
        """
        from src.agents.heuristic import AgentProfile, HeuristicAgent

        if seed is not None:
            self.rng = random.Random(seed)

        # Recria a mesa e jogadores
        players: List[Player] = [
            Player(player_id=self.hero_id, name="Hero", stack=self.starting_stack)
        ]
        self._bots.clear()

        profiles = [
            AgentProfile.BALANCED,
            AgentProfile.AGGRESSIVE,
            AgentProfile.CONSERVATIVE,
        ]

        for i in range(1, self.num_players):
            bot_id = f"bot_{i}"
            bot_profile = profiles[(i - 1) % len(profiles)]
            players.append(
                Player(
                    player_id=bot_id,
                    name=f"Bot_{i}",
                    stack=self.starting_stack,
                )
            )
            self._bots[bot_id] = HeuristicAgent(
                player_id=bot_id,
                name=f"Bot_{i}",
                profile=bot_profile,
                rng=self.rng,
            )

        self._table = Table(
            players=players,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            rng=self.rng,
        )
        self._table.start_new_hand(rng=self.rng)
        hero_p = self._get_hero_player()
        self._initial_hero_stack = hero_p.stack + hero_p.current_bet

        # Avança a vez dos bots até chegar no Hero ou finalizar a mão
        self._step_bots_until_hero_or_terminal()

        obs = self.get_observation(self.hero_id)
        info = {
            "action_mask": self.get_action_mask(self.hero_id),
            "street": self.table.street.name,
            "pot": self.table.pot_manager.total_pot,
        }
        return obs, info

    def get_action_mask(self, player_id: str) -> List[bool]:
        """Retorna a máscara booleana de 6 ações discretas legais (Action Masking)."""
        mask = [False] * 6
        if self.table.street in (Street.SHOWDOWN, Street.FINISHED):
            return mask

        current = self.table.current_player
        if current is None or current.player_id != player_id:
            return mask

        legal_types = self.table.get_legal_actions(player_id)
        if not legal_types:
            return mask

        # 0: FOLD
        mask[DiscreteAction.FOLD] = ActionType.FOLD in legal_types

        # 1: CHECK_CALL
        mask[DiscreteAction.CHECK_CALL] = (
            ActionType.CHECK in legal_types or ActionType.CALL in legal_types
        )

        can_bet_or_raise = (
            ActionType.BET in legal_types or ActionType.RAISE in legal_types
        )
        to_call = self.table.current_highest_bet - current.current_bet
        pot = self.table.pot_manager.total_pot

        # 2: MIN_RAISE
        mask[DiscreteAction.MIN_RAISE] = can_bet_or_raise

        # 3: HALF_POT
        half_pot_amount = current.current_bet + to_call + max(pot // 2, self.big_blind)
        min_required = self.table.current_highest_bet + self.table.min_raise
        mask[DiscreteAction.HALF_POT] = (
            can_bet_or_raise
            and half_pot_amount >= min_required
            and current.stack > to_call
        )

        # 4: POT
        pot_amount = current.current_bet + to_call + max(pot, self.big_blind)
        mask[DiscreteAction.POT] = (
            can_bet_or_raise
            and pot_amount >= min_required
            and current.stack > to_call
        )

        # 5: ALL_IN
        mask[DiscreteAction.ALL_IN] = current.stack > 0

        return mask

    def get_observation(self, player_id: str) -> Dict[str, Any]:
        """Retorna o dicionário de observação contendo o vetor numérico normalizado."""
        hero = next(p for p in self.table.players if p.player_id == player_id)
        hole_cards = hero.hole_cards if hero.hole_cards is not None else ()
        board_cards = self.table.community_cards

        # Vetores binários de cartas
        hole_vec = cards_to_one_hot(hole_cards)  # 52 dims
        board_vec = cards_to_one_hot(board_cards)  # 52 dims

        # Street one-hot (4 dims)
        street_idx_map = {
            Street.PREFLOP: 0,
            Street.FLOP: 1,
            Street.TURN: 2,
            Street.RIVER: 3,
        }
        s_idx = street_idx_map.get(self.table.street, 0)
        street_vec = street_to_one_hot(s_idx)

        # Escala de normalização (baseada no total de fichas em jogo)
        total_chips_in_game = max(1, self.starting_stack * self.num_players)
        to_call = max(0, self.table.current_highest_bet - hero.current_bet)
        pot = self.table.pot_manager.total_pot

        # Equidade aproximada via Monte Carlo
        equity = 0.5
        active_count = len([p for p in self.table.players if p.is_active])
        if len(hole_cards) == 2:
            eq_res = estimate_hand_equity(
                hole_cards=(hole_cards[0], hole_cards[1]),
                community_cards=board_cards,
                num_opponents=max(1, active_count - 1),
                num_simulations=50,
                rng=self.rng,
            )
            equity = eq_res.equity

        pot_odds = calculate_pot_odds(to_call=to_call, pot_size=pot)

        scalars = [
            hero.stack / total_chips_in_game,
            hero.current_bet / total_chips_in_game,
            to_call / total_chips_in_game,
            pot / total_chips_in_game,
            self.table.button_idx / float(self.num_players),
            active_count / float(self.num_players),
            equity,
            pot_odds,
        ]

        # Informações dos oponentes (máximo 8 oponentes * 2 features = 16 floats)
        opponent_features: List[float] = []
        for p in self.table.players:
            if p.player_id != player_id:
                opponent_features.append(p.stack / total_chips_in_game)
                opponent_features.append(p.current_bet / total_chips_in_game)

        # Padding caso haja menos de 8 oponentes
        while len(opponent_features) < 16:
            opponent_features.append(0.0)

        # Vetor consolidado (52 + 52 + 4 + 8 + 16 = 132 features numéricas)
        feature_vector = hole_vec + board_vec + street_vec + scalars + opponent_features

        return {
            "vector": feature_vector,
            "action_mask": self.get_action_mask(player_id),
            "equity": equity,
            "pot_odds": pot_odds,
        }

    def step(
        self, action_idx: int
    ) -> Tuple[Dict[str, Any], float, bool, bool, Dict[str, Any]]:
        """Executa a ação escolhida pelo Hero e simula o ambiente até a próxima decisão.

        Args:
            action_idx: Índice numérico da ação discreta (0..5).

        Returns:
            Tupla (observation, reward, terminated, truncated, info).
        """
        hero = self._get_hero_player()
        mask = self.get_action_mask(self.hero_id)

        # Valida ação pela máscara
        if not mask[action_idx]:
            # Punição e fallback seguro para check ou fold
            legal_types = self.table.get_legal_actions(self.hero_id)
            if ActionType.CHECK in legal_types:
                table_action = Action(self.hero_id, ActionType.CHECK)
            else:
                table_action = Action(self.hero_id, ActionType.FOLD)
        else:
            table_action = self._convert_discrete_action(action_idx, hero)

        is_bluff = self._check_if_bluff(hero, table_action)
        self.table.apply_action(table_action)

        # Avança a vez dos bots até o Hero poder agir novamente ou terminar a mão
        self._step_bots_until_hero_or_terminal()

        terminated = self.table.street in (Street.SHOWDOWN, Street.FINISHED)
        truncated = False

        reward = 0.0
        if terminated:
            # Recompensa em Big Blinds ganhos/perdidos na mão
            payout = self.table.last_payouts.get(self.hero_id, 0)
            net_chips = (hero.stack + payout) - self._initial_hero_stack
            reward = float(net_chips) / float(self.big_blind)

        obs = self.get_observation(self.hero_id)
        info = {
            "action_mask": self.get_action_mask(self.hero_id),
            "is_bluff": is_bluff,
            "street": self.table.street.name,
            "pot": self.table.pot_manager.total_pot,
            "last_payouts": self.table.last_payouts,
        }

        return obs, reward, terminated, truncated, info

    def _convert_discrete_action(
        self, action_idx: int, hero: Player
    ) -> Action:
        """Converte o índice da ação discreta em Action correspondente da Table."""
        legal = self.table.get_legal_actions(self.hero_id)
        to_call = self.table.current_highest_bet - hero.current_bet
        pot = self.table.pot_manager.total_pot
        min_required = self.table.current_highest_bet + self.table.min_raise

        if action_idx == DiscreteAction.FOLD:
            return Action(self.hero_id, ActionType.FOLD)

        if action_idx == DiscreteAction.CHECK_CALL:
            if ActionType.CHECK in legal:
                return Action(self.hero_id, ActionType.CHECK)
            if ActionType.CALL in legal:
                return Action(self.hero_id, ActionType.CALL)
            return Action(self.hero_id, ActionType.ALL_IN)

        if action_idx == DiscreteAction.MIN_RAISE:
            if ActionType.BET in legal:
                amount = min(hero.stack, self.big_blind)
                return Action(self.hero_id, ActionType.BET, amount=amount)
            if ActionType.RAISE in legal:
                amount = min(hero.current_bet + hero.stack, min_required)
                return Action(self.hero_id, ActionType.RAISE, amount=amount)

        if action_idx == DiscreteAction.HALF_POT:
            desired = hero.current_bet + to_call + max(pot // 2, self.big_blind)
            target = max(min_required, desired)
            target = min(hero.current_bet + hero.stack, target)
            if ActionType.BET in legal:
                return Action(self.hero_id, ActionType.BET, amount=target)
            return Action(self.hero_id, ActionType.RAISE, amount=target)

        if action_idx == DiscreteAction.POT:
            desired = hero.current_bet + to_call + max(pot, self.big_blind)
            target = max(min_required, desired)
            target = min(hero.current_bet + hero.stack, target)
            if ActionType.BET in legal:
                return Action(self.hero_id, ActionType.BET, amount=target)
            return Action(self.hero_id, ActionType.RAISE, amount=target)

        if action_idx == DiscreteAction.ALL_IN:
            return Action(self.hero_id, ActionType.ALL_IN)

        return Action(self.hero_id, ActionType.FOLD)

    def _step_bots_until_hero_or_terminal(self) -> None:
        """Executa automaticamente as decisões dos bots até a vez do Hero."""
        max_safety_steps = 100
        step_count = 0

        while (
            self.table.street not in (Street.SHOWDOWN, Street.FINISHED)
            and self.table.current_player is not None
            and self.table.current_player.player_id != self.hero_id
            and step_count < max_safety_steps
        ):
            bot_player = self.table.current_player
            bot_agent = self._bots.get(bot_player.player_id)
            if bot_agent is None:
                break
            action = bot_agent.decide_action(self.table)
            self.table.apply_action(action)
            step_count += 1

    def _check_if_bluff(self, player: Player, action: Action) -> bool:
        """Anota se uma aposta foi motivada por blefe (mão fraca < 35% equidade)."""
        agg_types = (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN)
        if action.action_type not in agg_types:
            return False
        if player.hole_cards is None:
            return False

        eq_res = estimate_hand_equity(
            hole_cards=player.hole_cards,
            community_cards=self.table.community_cards,
            num_opponents=1,
            num_simulations=40,
            rng=self.rng,
        )
        return eq_res.equity < 0.35

    def _get_hero_player(self) -> Player:
        return next(p for p in self.table.players if p.player_id == self.hero_id)
