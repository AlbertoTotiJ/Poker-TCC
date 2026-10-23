"""Agente de Poker baseado em dinâmica de blefes, pressão e exploração de mesa.

Este módulo implementa o BlufferAgent conforme a especificação do Módulo de
Estratégia de Blefe (Bluff Engine). O agente é desacoplado e possui arquitetura
independente, permitindo execução isolada, calibragem de hiperparâmetros
e treinamento futuro por algoritmos de reforço ou busca heurística.
"""

from dataclasses import asdict, dataclass
from enum import Enum
import json
from pathlib import Path
import random
import sys
from typing import Any, Dict, Optional, Sequence, Tuple

# Garante resolução de 'src' ao executar o script diretamente
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.agents.base import BaseAgent  # noqa: E402
from src.engine.deck import Card, Rank  # noqa: E402
from src.engine.equity import (  # noqa: E402
    has_flush_draw,
    has_overcards,
    has_straight_draw,
)
from src.engine.hand_eval import evaluate_hand  # noqa: E402
from src.engine.table import Action, ActionType, Street, Table  # noqa: E402


class BluffTactic(str, Enum):
    """Classificação tática das manobras executadas pelo agente."""

    CBET_STEAL = "C-Bet Steal"
    SEMI_BLUFF = "Semi-Bluff"
    BLUFF_RAISE = "Bluff Raise"
    SCARE_CARD_BARREL = "Scare Card Barrel"
    RIVER_BLUFF = "River Pure Bluff"
    FLOAT_CALL = "Float Call"
    PREFLOP_STEAL = "Pre-Flop Steal"
    PREFLOP_DEFEND = "Pre-Flop Defend"
    PREFLOP_3BET = "Pre-Flop 3-Bet Bluff"
    VALUE_PLAY = "Value Play"
    FREE_CHECK = "Free Check"
    PRUDENT_FOLD = "Prudent Fold"
    CONTINGENCY = "Contingency"


@dataclass(frozen=True)
class BluffDecision:
    """Estrutura analítica contendo a fundamentação estratégica do blefe."""

    action_type: ActionType
    amount: int
    is_bluff: bool
    tactic: str
    fold_equity: float
    reason: str
    semi_bluff_outs: int = 0


@dataclass
class BlufferParameters:
    """Hiperparâmetros calibráveis que regem as decisões táticas do agente."""

    bluff_frequency: float = 0.40
    semi_bluff_frequency: float = 0.70
    fold_equity_threshold: float = 0.40
    cbet_frequency: float = 0.65
    bluff_raise_frequency: float = 0.35
    aggression_multiplier: float = 1.0
    scare_card_weight: float = 0.15
    dry_board_bonus: float = 0.10
    bet_sizing_factor: float = 0.40

    def to_dict(self) -> Dict[str, float]:
        """Converte hiperparâmetros em dicionário serializável."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlufferParameters":
        """Instancia hiperparâmetros a partir de dicionário."""
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered = {k: float(v) for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class BlufferAgent(BaseAgent):
    """Agente autônomo focado no Módulo de Estratégia de Blefe (Bluff Engine).

    Opera de forma desacoplada com base em:
    1. Fold Equity estimada dinâmica (número de adversários, streets e custos).
    2. Estratégia ativa de Pré-Flop para ver o Flop e roubar blinds.
    3. Análise de textura do bordo (dry boards, scare cards, flush draws).
    4. Semi-blefes com equidade oculta de evolução (outs no Flop e Turn).
    5. Blefes de continuação (C-Bet Steals) em potes abandonados.
    6. Re-aumentos desbalanceados (Bluff Raises) contra apostas de sondagem.
    7. Suporte completo a salvamento, carregamento e calibração de hiperparâmetros.
    """

    def __init__(
        self,
        player_id: str,
        name: str = "Agente Blefador",
        bluff_frequency: float = 0.40,
        semi_bluff_frequency: float = 0.70,
        fold_equity_threshold: float = 0.40,
        cbet_frequency: float = 0.65,
        bluff_raise_frequency: float = 0.35,
        aggression_multiplier: float = 1.0,
        scare_card_weight: float = 0.15,
        dry_board_bonus: float = 0.10,
        bet_sizing_factor: float = 0.40,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        self.params = BlufferParameters(
            bluff_frequency=max(0.05, min(0.95, bluff_frequency)),
            semi_bluff_frequency=max(0.10, min(1.0, semi_bluff_frequency)),
            fold_equity_threshold=max(0.10, min(0.90, fold_equity_threshold)),
            cbet_frequency=max(0.10, min(1.0, cbet_frequency)),
            bluff_raise_frequency=max(0.05, min(0.90, bluff_raise_frequency)),
            aggression_multiplier=max(0.50, min(2.50, aggression_multiplier)),
            scare_card_weight=max(0.00, min(0.40, scare_card_weight)),
            dry_board_bonus=max(0.00, min(0.30, dry_board_bonus)),
            bet_sizing_factor=max(0.25, min(1.20, bet_sizing_factor)),
        )
        self.rng: random.Random = rng if rng is not None else random.Random()

        # Telemetria acumulada para métricas estatísticas e treinamento
        self.hands_played: int = 0
        self.bluffs_attempted: int = 0
        self.pure_bluffs: int = 0
        self.semi_bluffs: int = 0
        self.cbet_steals: int = 0
        self.bluff_raises: int = 0
        self.vpip_actions: int = 0
        self.pfr_actions: int = 0
        self.bets_and_raises: int = 0
        self.calls: int = 0
        self.folds: int = 0

    # Propriedades de compatibilidade e acesso direto
    @property
    def bluff_frequency(self) -> float:
        return self.params.bluff_frequency

    @bluff_frequency.setter
    def bluff_frequency(self, value: float) -> None:
        self.params.bluff_frequency = max(0.05, min(0.95, float(value)))

    @property
    def aggression_multiplier(self) -> float:
        return self.params.aggression_multiplier

    @aggression_multiplier.setter
    def aggression_multiplier(self, value: float) -> None:
        self.params.aggression_multiplier = max(0.50, min(2.50, float(value)))

    @property
    def aggression_factor(self) -> float:
        """Razão clássica entre ações agressivas e passivas."""
        if self.calls == 0:
            return float(self.bets_and_raises)
        return round(self.bets_and_raises / self.calls, 2)

    @property
    def bluff_rate(self) -> float:
        """Percentual de ações ofensivas rotuladas como blefe."""
        if self.bets_and_raises == 0:
            return 0.0
        return round((self.bluffs_attempted / self.bets_and_raises) * 100.0, 1)

    def export_parameters(self) -> Dict[str, float]:
        """Exporta os hiperparâmetros atuais do agente para calibração/treino."""
        return self.params.to_dict()

    def load_parameters(self, params: Dict[str, Any]) -> None:
        """Aplica novos hiperparâmetros resultantes de rotinas de treino."""
        self.params = BlufferParameters.from_dict(params)

    def save_parameters(self, filepath: str | Path) -> None:
        """Persiste os hiperparâmetros treinados em arquivo JSON."""
        target = Path(filepath)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.export_parameters(), f, indent=2)

    def load_parameters_file(self, filepath: str | Path) -> None:
        """Carrega hiperparâmetros pré-treinados a partir de arquivo JSON."""
        target = Path(filepath)
        if not target.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {target}")
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load_parameters(data)

    def decide_action(self, table: Table) -> Action:
        """Executa a tomada de decisão conectado ao estado da mesa de poker."""
        legal_actions = table.get_legal_actions(self.player_id)
        if not legal_actions:
            return Action(self.player_id, ActionType.FOLD)

        player = next(p for p in table.players if p.player_id == self.player_id)
        if player.hole_cards is None:
            return Action(self.player_id, ActionType.FOLD)

        to_call = table.current_highest_bet - player.current_bet
        active_opponents = max(
            1,
            sum(
                1
                for p in table.players
                if p.is_active and p.player_id != self.player_id
            ),
        )

        decision = self.evaluate_state(
            hole_cards=player.hole_cards,
            community_cards=table.community_cards,
            pot_size=table.pot_manager.total_pot,
            to_call=to_call,
            player_stack=player.stack,
            player_current_bet=player.current_bet,
            current_highest_bet=table.current_highest_bet,
            min_raise=table.min_raise,
            big_blind=table.big_blind,
            num_opponents=active_opponents,
            legal_actions=legal_actions,
            street=table.street,
        )

        self._track_decision_telemetry(decision)
        return Action(
            player_id=self.player_id,
            action_type=decision.action_type,
            amount=decision.amount,
        )

    def _evaluate_preflop(
        self,
        hole_cards: Sequence[Card],
        pot_size: int,
        to_call: int,
        player_stack: int,
        player_current_bet: int,
        current_highest_bet: int,
        min_raise: int,
        big_blind: int,
        num_opponents: int,
        legal_actions: Sequence[ActionType],
    ) -> BluffDecision:
        """Avalia e decide a ação tática no Pré-Flop para o Agente Blefador.

        Garante que o blefador nunca desista de mãos jogáveis com custo baixo
        para ver o Flop e possa roubar blinds ou aplicar 3-bets pré-flop.
        """
        c1, c2 = hole_cards[0], hole_cards[1]
        is_pair = c1.rank.value == c2.rank.value
        is_suited = c1.suit == c2.suit
        high_rank = max(c1.rank.value, c2.rank.value)
        low_rank = min(c1.rank.value, c2.rank.value)
        gap = high_rank - low_rank

        # 1. Mãos Premium (TT+, AJ+, KQ) -> Valor legítimo pré-flop
        is_premium = (
            (is_pair and high_rank >= 10)
            or (high_rank == Rank.ACE.value and low_rank >= 11)
            or (high_rank == Rank.KING.value and low_rank == Rank.QUEEN.value)
        )

        if is_premium:
            return self._decide_value_play(
                pot_size=pot_size,
                to_call=to_call,
                player_stack=player_stack,
                player_current_bet=player_current_bet,
                current_highest_bet=current_highest_bet,
                min_raise=min_raise,
                big_blind=big_blind,
                legal_actions=legal_actions,
                hand_desc=f"{c1.rank.symbol}{c2.rank.symbol}",
            )

        # 2. Mãos Especulativas com alto potencial de blefe pós-flop
        # (Pares 22-99, cartas naipadas, conectores, broadways)
        is_speculative = (
            is_pair
            or is_suited
            or (gap <= 2 and low_rank >= 4)
            or (high_rank >= 10 and low_rank >= 8)
        )

        roll = self.rng.random()
        can_raise = ActionType.RAISE in legal_actions and player_stack > to_call

        # Cenário A: Custo Zero ou Limp / Cobrir o Big Blind (to_call <= big_blind)
        # O blefador NUNCA dá fold para ver o flop por um BB!
        if to_call <= big_blind:
            # Chance de aplicar Roubo de Blinds (Pre-Flop Steal calibrado para ~20%)
            wants_steal = roll < (self.params.cbet_frequency * 0.30)
            if can_raise and wants_steal:
                raise_amt = current_highest_bet + max(min_raise, big_blind * 2)
                max_pos = player_current_bet + player_stack
                raise_amt = min(max_pos, raise_amt)
                if raise_amt > current_highest_bet:
                    return BluffDecision(
                        action_type=ActionType.RAISE,
                        amount=raise_amt,
                        is_bluff=True,
                        tactic=BluffTactic.PREFLOP_STEAL.value,
                        fold_equity=0.55,
                        reason="Roubo de blinds pré-flop explorando mesa barata",
                    )

            if to_call == 0 and ActionType.CHECK in legal_actions:
                return BluffDecision(
                    action_type=ActionType.CHECK,
                    amount=0,
                    is_bluff=False,
                    tactic=BluffTactic.FREE_CHECK.value,
                    fold_equity=0.40,
                    reason="Check gratuito no Big Blind para ver o Flop",
                )

            if ActionType.CALL in legal_actions:
                return BluffDecision(
                    action_type=ActionType.CALL,
                    amount=0,
                    is_bluff=False,
                    tactic=BluffTactic.PREFLOP_DEFEND.value,
                    fold_equity=0.45,
                    reason="Pagamento do Big Blind para disputar o Flop em posição",
                )

        # Cenário B: Enfrentando aumento padrão pré-flop (to_call entre 1 e 3.5 BBs)
        is_standard_raise = to_call <= big_blind * 3.5
        if is_standard_raise:
            # Possibilidade moderada de 3-Bet Bluff para pressionar o agressor
            wants_3bet = roll < (self.params.bluff_raise_frequency * 0.30)
            if can_raise and wants_3bet and (is_speculative or roll < 0.15):
                raise_amt = current_highest_bet + max(min_raise, int(to_call * 2.4))
                max_pos = player_current_bet + player_stack
                raise_amt = min(max_pos, raise_amt)
                if raise_amt > current_highest_bet:
                    return BluffDecision(
                        action_type=ActionType.RAISE,
                        amount=raise_amt,
                        is_bluff=True,
                        tactic=BluffTactic.PREFLOP_3BET.value,
                        fold_equity=0.60,
                        reason=(
                            "Re-aumento 3-Bet de blefe pré-flop pressionando oponente"
                        ),
                    )

            # Com mão especulativa ou sorteio favorável, paga para ver o Flop
            wants_call = is_speculative or (roll < 0.70)
            if wants_call and ActionType.CALL in legal_actions:
                return BluffDecision(
                    action_type=ActionType.CALL,
                    amount=0,
                    is_bluff=False,
                    tactic=BluffTactic.PREFLOP_DEFEND.value,
                    fold_equity=0.40,
                    reason="Defesa pré-flop com mão especulativa para blefar pós-flop",
                )

        # Cenário C: Aumento pesado / 4-Bet / All-In (to_call > 3.5 BBs)
        # Desiste prudentemente se não tiver mão premium
        if ActionType.FOLD in legal_actions:
            return BluffDecision(
                action_type=ActionType.FOLD,
                amount=0,
                is_bluff=False,
                tactic=BluffTactic.PRUDENT_FOLD.value,
                fold_equity=0.20,
                reason="Desistência prudente pré-flop contra aposta massiva",
            )

        fallback = legal_actions[0] if legal_actions else ActionType.FOLD
        return BluffDecision(
            action_type=fallback,
            amount=0,
            is_bluff=False,
            tactic=BluffTactic.CONTINGENCY.value,
            fold_equity=0.20,
            reason="Ação de contingência pré-flop",
        )

    def evaluate_state(
        self,
        hole_cards: Sequence[Card],
        community_cards: Sequence[Card],
        pot_size: int,
        to_call: int,
        player_stack: int,
        player_current_bet: int,
        current_highest_bet: int,
        min_raise: int,
        big_blind: int,
        num_opponents: int,
        legal_actions: Sequence[ActionType],
        street: Street = Street.PREFLOP,
    ) -> BluffDecision:
        """Avalia de forma isolada e desacoplada o estado de mesa.

        Retorna a decisão ótima fundamentada no Bluff Engine, sem depender
        de infraestrutura ou conexões externas.
        """
        # Estratégia dedicada e ativa para o Pré-Flop (nunca dá fold por um BB)
        if street == Street.PREFLOP or len(community_cards) == 0:
            return self._evaluate_preflop(
                hole_cards=hole_cards,
                pot_size=pot_size,
                to_call=to_call,
                player_stack=player_stack,
                player_current_bet=player_current_bet,
                current_highest_bet=current_highest_bet,
                min_raise=min_raise,
                big_blind=big_blind,
                num_opponents=num_opponents,
                legal_actions=legal_actions,
            )

        all_cards = list(hole_cards) + list(community_cards)
        is_strong, hand_desc = self._classify_hand_strength(hole_cards, all_cards)

        # Análise das propriedades de textura da mesa
        is_dry, is_wet, is_scare = self.analyze_board_texture(community_cards)

        # Cálculo de Fold Equity esperada
        fold_equity = self.estimate_fold_equity(
            num_opponents=num_opponents,
            is_dry=is_dry,
            has_scare=is_scare,
            street=street,
            to_call=to_call,
            pot_size=pot_size,
        )

        # Identificação de potencial para semi-blefe (outs de evolução)
        semi_outs = self.detect_draw_outs(hole_cards, community_cards)

        # 1. Se possuir jogo consolidado: aposta por valor para balancear o range
        if is_strong:
            return self._decide_value_play(
                pot_size=pot_size,
                to_call=to_call,
                player_stack=player_stack,
                player_current_bet=player_current_bet,
                current_highest_bet=current_highest_bet,
                min_raise=min_raise,
                big_blind=big_blind,
                legal_actions=legal_actions,
                hand_desc=hand_desc,
            )

        # 2. Oportunidade de Semi-Blefe (draws no Flop e Turn)
        if semi_outs >= 4 and street in (Street.FLOP, Street.TURN):
            semi_decision = self._evaluate_semi_bluff(
                semi_outs=semi_outs,
                fold_equity=fold_equity,
                pot_size=pot_size,
                to_call=to_call,
                player_stack=player_stack,
                player_current_bet=player_current_bet,
                current_highest_bet=current_highest_bet,
                min_raise=min_raise,
                big_blind=big_blind,
                legal_actions=legal_actions,
            )
            if semi_decision is not None:
                return semi_decision

        # 3. Blefes Puros e Exploração de Fraqueza
        roll = self.rng.random()
        bluff_eligible = fold_equity >= self.params.fold_equity_threshold
        wants_bluff = roll < (self.params.bluff_frequency * (fold_equity / 0.50))

        # Cenário A: Mesa em Check (to_call == 0) -> C-Bet Steal / Pote Órfão
        if to_call == 0:
            can_bet = (
                ActionType.BET in legal_actions
                or ActionType.RAISE in legal_actions
            )
            if wants_bluff and bluff_eligible and can_bet:
                sizing = (
                    pot_size
                    * self.params.bet_sizing_factor
                    * self.params.aggression_multiplier
                )
                target_bet = int(sizing)
                target_bet = max(big_blind, target_bet)
                target_bet = min(player_stack, target_bet)

                tactic_name = (
                    BluffTactic.SCARE_CARD_BARREL.value
                    if is_scare and street in (Street.TURN, Street.RIVER)
                    else (
                        BluffTactic.RIVER_BLUFF.value
                        if street == Street.RIVER
                        else BluffTactic.CBET_STEAL.value
                    )
                )

                if ActionType.BET in legal_actions and target_bet > 0:
                    fe_desc = f"FE={fold_equity:.2f}"
                    return BluffDecision(
                        action_type=ActionType.BET,
                        amount=target_bet,
                        is_bluff=True,
                        tactic=tactic_name,
                        fold_equity=fold_equity,
                        reason=f"Agressão tática explorando passividade ({fe_desc})",
                        semi_bluff_outs=semi_outs,
                    )

            if ActionType.CHECK in legal_actions:
                return BluffDecision(
                    action_type=ActionType.CHECK,
                    amount=0,
                    is_bluff=False,
                    tactic=BluffTactic.FREE_CHECK.value,
                    fold_equity=fold_equity,
                    reason="Controle de pote sem investimento de fichas",
                    semi_bluff_outs=semi_outs,
                )

        # Cenário B: Enfrentando aposta (to_call > 0) -> Bluff Raise ou Float
        can_raise = ActionType.RAISE in legal_actions and player_stack > to_call
        is_probe_bet = to_call <= max(big_blind * 2, int(pot_size * 0.35))

        if (
            wants_bluff
            and can_raise
            and (is_probe_bet or is_scare)
            and roll < self.params.bluff_raise_frequency
        ):
            raise_amount = current_highest_bet + max(
                min_raise,
                int(to_call * 2.3 * self.params.aggression_multiplier),
            )
            max_possible = player_current_bet + player_stack
            raise_amount = min(max_possible, raise_amount)

            if raise_amount > current_highest_bet:
                raise_reason = (
                    f"Re-aumento contra aposta de sondagem fraca "
                    f"(FE={fold_equity:.2f})"
                )
                return BluffDecision(
                    action_type=ActionType.RAISE,
                    amount=raise_amount,
                    is_bluff=True,
                    tactic=BluffTactic.BLUFF_RAISE.value,
                    fold_equity=fold_equity,
                    reason=raise_reason,
                    semi_bluff_outs=semi_outs,
                )

        # Float Call: Pagar barato com perspectiva de roubar o pote depois
        if (
            ActionType.CALL in legal_actions
            and to_call <= big_blind * 2
            and street in (Street.PREFLOP, Street.FLOP)
            and roll < 0.30
        ):
            return BluffDecision(
                action_type=ActionType.CALL,
                amount=0,
                is_bluff=False,
                tactic=BluffTactic.FLOAT_CALL.value,
                fold_equity=fold_equity,
                reason="Call posicional de flutuação para blefar na street seguinte",
                semi_bluff_outs=semi_outs,
            )

        # Desistência Prudente (Prudent Fold) contra pressão alta sem valor
        if ActionType.FOLD in legal_actions:
            return BluffDecision(
                action_type=ActionType.FOLD,
                amount=0,
                is_bluff=False,
                tactic=BluffTactic.PRUDENT_FOLD.value,
                fold_equity=fold_equity,
                reason=(
                    "Desistência prudente preservando bankroll contra aposta adversária"
                ),
                semi_bluff_outs=semi_outs,
            )

        # Fallback defensivo seguro
        fallback = legal_actions[0] if legal_actions else ActionType.FOLD
        return BluffDecision(
            action_type=fallback,
            amount=0,
            is_bluff=False,
            tactic=BluffTactic.CONTINGENCY.value,
            fold_equity=fold_equity,
            reason="Ação de contingência das regras de mesa",
            semi_bluff_outs=semi_outs,
        )

    def analyze_board_texture(
        self, community_cards: Sequence[Card]
    ) -> Tuple[bool, bool, bool]:
        """Classifica características fundamentais da textura da mesa.

        Returns:
            Tupla (is_dry_board, is_wet_board, has_scare_card).
        """
        if len(community_cards) < 3:
            return False, False, False

        suits = [c.suit for c in community_cards]
        ranks = sorted([c.rank.value for c in community_cards])

        # Board Monótono ou Coordenado (Wet)
        suit_counts: Dict[Any, int] = {}
        for s in suits:
            suit_counts[s] = suit_counts.get(s, 0) + 1
        max_suit_repetition = max(suit_counts.values())
        has_flush_texture = max_suit_repetition >= 3

        # Conectividade de sequência
        connected_count = 0
        for i in range(len(ranks) - 1):
            if ranks[i + 1] - ranks[i] <= 2:
                connected_count += 1
        is_wet = has_flush_texture or connected_count >= 2

        # Board Seco (Dry): Rainbow e desconectado
        is_rainbow = len(set(suits[:3])) == 3
        gap = ranks[-1] - ranks[0] if len(ranks) >= 3 else 0
        is_dry = is_rainbow and gap >= 5 and not is_wet

        # Scare Cards (Presença de Ás, Rei ou cartas de perigo evidente)
        has_scare = any(c.rank in (Rank.ACE, Rank.KING) for c in community_cards)
        has_scare = has_scare or has_flush_texture

        return is_dry, is_wet, has_scare

    def estimate_fold_equity(
        self,
        num_opponents: int,
        is_dry: bool,
        has_scare: bool,
        street: Street,
        to_call: int,
        pot_size: int,
    ) -> float:
        """Estima a probabilidade acumulada dos adversários desistirem (Fold Equity)."""
        # Base decresce exponencialmente com cada jogador ativo adicional
        base_fe = max(0.12, 0.82 - (num_opponents * 0.15))

        if is_dry:
            base_fe += self.params.dry_board_bonus
        if has_scare and street in (Street.TURN, Street.RIVER):
            base_fe += self.params.scare_card_weight

        # Adversário demonstrando agressão pesada reduz drasticamente a fold equity
        if to_call > 0 and pot_size > 0:
            bet_pot_ratio = to_call / pot_size
            if bet_pot_ratio > 0.50:
                base_fe -= 0.20

        return max(0.05, min(0.92, base_fe))

    def detect_draw_outs(
        self, hole_cards: Sequence[Card], community_cards: Sequence[Card]
    ) -> int:
        """Detecta outs de evolução para compor oportunidades de semi-blefe."""
        if len(community_cards) < 3 or len(hole_cards) < 2:
            return 0

        combined = list(hole_cards) + list(community_cards)
        outs = 0

        if has_flush_draw(combined):
            outs += 9
        if has_straight_draw(combined):
            outs += 8

        h_tuple = (hole_cards[0], hole_cards[1])
        if has_overcards(h_tuple, community_cards):
            outs += 4

        return outs

    def _classify_hand_strength(
        self, hole_cards: Sequence[Card], all_cards: Sequence[Card]
    ) -> Tuple[bool, str]:
        """Classifica se a mão atual possui valor intrínseco consolidado."""
        if len(all_cards) >= 5:
            score = evaluate_hand(all_cards)
            # Dois pares ou melhor é tratado como jogo formado legítimo
            is_strong = score.hand_rank.value >= 3
            return is_strong, score.description

        if len(hole_cards) >= 2:
            c1, c2 = hole_cards[0], hole_cards[1]
            is_pair = c1.rank.value == c2.rank.value
            high_rank = max(c1.rank.value, c2.rank.value)
            is_strong = (is_pair and high_rank >= 10) or (
                high_rank == Rank.ACE.value and min(c1.rank.value, c2.rank.value) >= 11
            )
            return is_strong, f"Par/Carta Alta ({c1.rank.symbol}{c2.rank.symbol})"

        return False, "Desconhecida"

    def _evaluate_semi_bluff(
        self,
        semi_outs: int,
        fold_equity: float,
        pot_size: int,
        to_call: int,
        player_stack: int,
        player_current_bet: int,
        current_highest_bet: int,
        min_raise: int,
        big_blind: int,
        legal_actions: Sequence[ActionType],
    ) -> Optional[BluffDecision]:
        """Avalia e formata manobra de semi-blefe combinando equidade e FE."""
        if self.rng.random() >= self.params.semi_bluff_frequency:
            return None

        # Aposta de semi-blefe quando mesa der check
        if to_call == 0 and ActionType.BET in legal_actions:
            target_bet = int(pot_size * 0.65 * self.params.aggression_multiplier)
            target_bet = max(big_blind, min(player_stack, target_bet))
            if target_bet > 0:
                return BluffDecision(
                    action_type=ActionType.BET,
                    amount=target_bet,
                    is_bluff=True,
                    tactic=BluffTactic.SEMI_BLUFF.value,
                    fold_equity=fold_equity,
                    reason=f"Semi-blefe agressivo com {semi_outs} outs de evolução",
                    semi_bluff_outs=semi_outs,
                )

        # Semi-blefe de re-aumento contra aposta moderada
        can_raise = ActionType.RAISE in legal_actions and player_stack > to_call
        if to_call > 0 and can_raise and to_call <= pot_size * 0.40:
            raise_val = current_highest_bet + max(min_raise, int(to_call * 2.2))
            max_pos = player_current_bet + player_stack
            raise_val = min(max_pos, raise_val)
            if raise_val > current_highest_bet:
                return BluffDecision(
                    action_type=ActionType.RAISE,
                    amount=raise_val,
                    is_bluff=True,
                    tactic=BluffTactic.SEMI_BLUFF.value,
                    fold_equity=fold_equity,
                    reason=f"Semi-blefe raise aproveitando draws ({semi_outs} outs)",
                    semi_bluff_outs=semi_outs,
                )

        return None

    def _decide_value_play(
        self,
        pot_size: int,
        to_call: int,
        player_stack: int,
        player_current_bet: int,
        current_highest_bet: int,
        min_raise: int,
        big_blind: int,
        legal_actions: Sequence[ActionType],
        hand_desc: str,
    ) -> BluffDecision:
        """Executa aposta legítima por valor ao deter mão forte."""
        if ActionType.RAISE in legal_actions and player_stack > to_call:
            raise_val = current_highest_bet + max(
                min_raise, int(pot_size * 0.50 * self.params.aggression_multiplier)
            )
            max_pos = player_current_bet + player_stack
            raise_val = min(max_pos, raise_val)
            return BluffDecision(
                action_type=ActionType.RAISE,
                amount=raise_val,
                is_bluff=False,
                tactic=BluffTactic.VALUE_PLAY.value,
                fold_equity=0.25,
                reason=f"Aposta de valor legítimo com jogo formado ({hand_desc})",
            )

        if ActionType.BET in legal_actions:
            bet_val = max(big_blind, int(pot_size * 0.45))
            bet_val = min(player_stack, bet_val)
            return BluffDecision(
                action_type=ActionType.BET,
                amount=bet_val,
                is_bluff=False,
                tactic=BluffTactic.VALUE_PLAY.value,
                fold_equity=0.25,
                reason=f"Abertura por valor legítimo ({hand_desc})",
            )

        if ActionType.CALL in legal_actions:
            return BluffDecision(
                action_type=ActionType.CALL,
                amount=0,
                is_bluff=False,
                tactic=BluffTactic.VALUE_PLAY.value,
                fold_equity=0.25,
                reason=f"Call de valor ({hand_desc})",
            )

        if ActionType.CHECK in legal_actions:
            return BluffDecision(
                action_type=ActionType.CHECK,
                amount=0,
                is_bluff=False,
                tactic=BluffTactic.FREE_CHECK.value,
                fold_equity=0.25,
                reason="Check por controle de pote com mão formada",
            )

        return BluffDecision(
            action_type=ActionType.FOLD,
            amount=0,
            is_bluff=False,
            tactic=BluffTactic.CONTINGENCY.value,
            fold_equity=0.0,
            reason="Contingência",
        )

    def _track_decision_telemetry(self, decision: BluffDecision) -> None:
        """Atualiza a telemetria interna do agente."""
        if decision.is_bluff:
            self.bluffs_attempted += 1
            if decision.tactic == BluffTactic.SEMI_BLUFF.value:
                self.semi_bluffs += 1
            elif decision.tactic in (
                BluffTactic.CBET_STEAL.value,
                BluffTactic.PREFLOP_STEAL.value,
            ):
                self.cbet_steals += 1
            elif decision.tactic in (
                BluffTactic.BLUFF_RAISE.value,
                BluffTactic.PREFLOP_3BET.value,
            ):
                self.bluff_raises += 1
            else:
                self.pure_bluffs += 1

        if decision.action_type in (ActionType.BET, ActionType.RAISE):
            self.bets_and_raises += 1
            self.vpip_actions += 1
            self.pfr_actions += 1
        elif decision.action_type == ActionType.CALL:
            self.calls += 1
            self.vpip_actions += 1
        elif decision.action_type == ActionType.FOLD:
            self.folds += 1


def run_isolated_demo() -> None:
    """Demonstração de execução isolada do Agente Blefador em cenários canônicos."""
    agent = BlufferAgent(
        player_id="bluffer_demo",
        name="Agente Blefador (Isolado)",
        bluff_frequency=0.80,
        semi_bluff_frequency=0.90,
        rng=random.Random(42),
    )

    print("=" * 75)
    print("DEMONSTRAÇÃO DE EXECUÇÃO ISOLADA: AGENTE BLEFADOR (BLUFF ENGINE)")
    print("=" * 75)

    scenarios = [
        (
            "Cenário 0: Pré-Flop Defesa do Big Blind com Mão Especulativa (9s 8s)",
            (Card.from_str("9s"), Card.from_str("8s")),
            [],
            30,
            10,
            1000,
            3,
            [ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
            Street.PREFLOP,
        ),
        (
            "Cenário 1: C-Bet Steal no Flop em Mesa Seca (7d 2c em Ah 8s 3c)",
            (Card.from_str("7d"), Card.from_str("2c")),
            [Card.from_str("Ah"), Card.from_str("8s"), Card.from_str("3c")],
            100,
            0,
            1000,
            1,
            [ActionType.CHECK, ActionType.BET],
            Street.FLOP,
        ),
        (
            "Cenário 2: Semi-Blefe no Turn com Flush Draw (Kh Qh em Ah 8h 2c 4s)",
            (Card.from_str("Kh"), Card.from_str("Qh")),
            [
                Card.from_str("Ah"),
                Card.from_str("8h"),
                Card.from_str("2c"),
                Card.from_str("4s"),
            ],
            120,
            25,
            1000,
            1,
            [ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
            Street.TURN,
        ),
        (
            "Cenário 3: River Scare Barrel com Mão Fraca (Jd 10c em 2h 5d 8c Ks As)",
            (Card.from_str("Jd"), Card.from_str("10c")),
            [
                Card.from_str("2h"),
                Card.from_str("5d"),
                Card.from_str("8c"),
                Card.from_str("Ks"),
                Card.from_str("As"),
            ],
            150,
            0,
            1000,
            1,
            [ActionType.CHECK, ActionType.BET],
            Street.RIVER,
        ),
        (
            "Cenário 4: Bluff Raise contra aposta de sondagem fraca no Flop",
            (Card.from_str("6c"), Card.from_str("5c")),
            [Card.from_str("Kd"), Card.from_str("9s"), Card.from_str("2h")],
            120,
            20,
            1000,
            1,
            [ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
            Street.FLOP,
        ),
        (
            "Cenário 5: Desistência Prudente contra All-In Gigante sem equidade",
            (Card.from_str("4d"), Card.from_str("3s")),
            [
                Card.from_str("Kd"),
                Card.from_str("Qc"),
                Card.from_str("Js"),
                Card.from_str("10h"),
            ],
            200,
            600,
            1000,
            2,
            [ActionType.FOLD, ActionType.CALL],
            Street.TURN,
        ),
    ]

    for title, hole, board, pot, to_call, stack, opps, legals, street in scenarios:
        board_str = " ".join(str(c) for c in board) if board else "(Pré-Flop)"
        print(f"\n> {title}")
        print(
            f"  Mão: {hole[0]} {hole[1]} | Bordo: [{board_str}] | "
            f"Pote: {pot} | A pagar: {to_call}"
        )

        decision = agent.evaluate_state(
            hole_cards=hole,
            community_cards=board,
            pot_size=pot,
            to_call=to_call,
            player_stack=stack,
            player_current_bet=0,
            current_highest_bet=to_call,
            min_raise=20,
            big_blind=20,
            num_opponents=opps,
            legal_actions=legals,
            street=street,
        )

        amt_str = f" (Valor: {decision.amount})" if decision.amount > 0 else ""
        print(f"  -> Ação Decidida: {decision.action_type.name}{amt_str}")
        print(
            f"  -> Blefe?: {decision.is_bluff} | Tática: {decision.tactic} | "
            f"Fold Equity: {decision.fold_equity:.1%}"
        )
        print(f"  -> Motivação Estratégica: {decision.reason}")


if __name__ == "__main__":
    run_isolated_demo()
