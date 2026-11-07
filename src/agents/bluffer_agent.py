"""Agente Blefador Definitivo para Texas Hold'em.

Unifica e aprimora a versão tática/exploratória clássica (Alberto) e a versão
baseada em Teoria dos Jogos GTO e Remoção de Cartas (Gustavo - GH):
1. Razão Áurea GTO entre Valor e Blefe pelo Princípio da Indiferença: B / (P + 2B).
2. Motor de Remoção de Cartas (Nut Blocker & Card Removal Engine).
3. Dinâmica avançada de Fold Equity (textura de bordo, scare cards, posição e multiway).
4. Arsenal tático completo: C-Bet Steal, Semi-Bluff com Outs, Polarized River Bluff,
   Nut Blocker Bluff, Scare Card Barrel, Preflop 3-Bet Bluff e Float Call.
5. Eliminação definitiva de vícios: fold disciplinado contra apostas pesadas sem odds,
   evitando completamente o leak clássico de "Calling Station" ou blefes suicidas.
6. Payload explicativo e auditável (XAI) para Quartz e telemetria de pesquisa.
"""

from collections import Counter
from dataclasses import asdict, dataclass
from enum import Enum
import json
from pathlib import Path
import random
import sys
from typing import Any, Dict, Optional, Sequence, Tuple

# Garante resolução dos módulos a partir da raiz do repositório
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.agents.base import BaseAgent  # noqa: E402
from src.engine.deck import Card, Rank  # noqa: E402
from src.engine.equity import (  # noqa: E402
    calculate_pot_odds,
    estimate_hand_equity,
    has_flush_draw,
    has_overcards,
    has_straight_draw,
)
from src.engine.hand_eval import evaluate_hand  # noqa: E402
from src.engine.table import Action, ActionType, Street, Table  # noqa: E402


class BluffTactic(str, Enum):
    """Classificação tática clássica das manobras executadas pelo agente."""

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


class GhBluffTactic(str, Enum):
    """Classificação formal GTO das manobras executadas pelo GhBlufferAgent."""

    POLARIZED_RIVER_BLUFF = "Polarized River Bluff (GTO Blocker)"
    NUT_BLOCKER_BLUFF = "Nut Blocker Bluff"
    SEMI_BLUFF_DRAW = "Semi-Bluff Draw (Outs Pressure)"
    CBET_STEAL = "C-Bet Steal (Dry Board Float)"
    PREFLOP_3BET_BLUFF = "Preflop Polarized 3-Bet Bluff"
    VALUE_PLAY = "Value Play (Range Protection)"
    FREE_CHECK = "Free Check (Pot Control)"
    DISCIPLINED_FOLD = "Disciplined Fold (Anti-Leak)"
    PROBE_DEFEND = "Pot-Odds Defend (Implied Call)"
    CONTINGENCY = "Contingency Fallback"


@dataclass(frozen=True)
class GhBluffMetrics:
    """Payload cognitivo explicável para inspeção de IA e apresentação do TCC."""

    raw_equity: float
    adjusted_equity: float
    pot_odds: float
    gto_bluff_threshold: float
    random_roll: float
    blocker_score: float
    semi_bluff_outs: int
    is_bluff: bool
    tactic: str
    tactical_rationale: str
    formula_reference: str

    @property
    def direct_pot_odds(self) -> float:
        return self.pot_odds

    @property
    def implied_odds(self) -> float:
        return self.pot_odds

    @property
    def expected_value_call(self) -> float:
        return 0.0

    @property
    def expected_value_raise(self) -> float:
        return 0.0

    @property
    def kelly_fraction(self) -> float:
        return 0.0

    @property
    def outs_count(self) -> int:
        return self.semi_bluff_outs

    @property
    def position_name(self) -> str:
        return "Middle"


@dataclass(frozen=True)
class BluffDecision:
    """Estrutura formal e imutável da decisão tática tomada pelo agente."""

    action_type: ActionType
    amount: int
    is_bluff: bool
    tactic: str
    fold_equity: float
    reason: str
    semi_bluff_outs: int = 0
    equity: float = 0.0
    pot_odds: float = 0.0
    expected_value: float = 0.0
    metrics: Optional[GhBluffMetrics] = None


# Alias para 100% de compatibilidade com o ecossistema GH
GhBluffDecision = BluffDecision


@dataclass
class BlufferParameters:
    """Hiperparâmetros calibráveis que regem as decisões táticas e GTO do agente."""

    bluff_frequency: float = 0.40
    semi_bluff_frequency: float = 0.70
    fold_equity_threshold: float = 0.40
    cbet_frequency: float = 0.65
    bluff_raise_frequency: float = 0.35
    aggression_multiplier: float = 1.0
    scare_card_weight: float = 0.15
    dry_board_bonus: float = 0.10
    bet_sizing_factor: float = 0.40
    min_blocker_threshold: float = 0.30
    gto_balance_factor: float = 1.0
    num_simulations: int = 250

    def to_dict(self) -> Dict[str, Any]:
        """Converte hiperparâmetros em dicionário serializável."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlufferParameters":
        """Instancia hiperparâmetros a partir de dicionário com validação e clamping."""
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered: Dict[str, Any] = {}
        for k, v in data.items():
            if k == "bluff_aggression":
                filtered["aggression_multiplier"] = float(v)
            elif k in valid_keys:
                filtered[k] = int(v) if k == "num_simulations" else float(v)
        return cls(**filtered)


GhBlufferParameters = BlufferParameters


class BlufferAgent(BaseAgent):
    """Agente Blefador Definitivo.

    Integra o motor de Fold Equity e táticas dinâmicas de Alberto com a indiferença
    de Nash Libratus/Pluribus e a remoção de cartas (Blockers) de Gustavo (GH).
    """

    def __init__(
        self,
        player_id: str,
        name: str = "Agente Blefador Definitivo",
        bluff_frequency: float = 0.40,
        semi_bluff_frequency: float = 0.70,
        fold_equity_threshold: float = 0.40,
        cbet_frequency: float = 0.65,
        bluff_raise_frequency: float = 0.35,
        aggression_multiplier: float = 1.0,
        scare_card_weight: float = 0.15,
        dry_board_bonus: float = 0.10,
        bet_sizing_factor: float = 0.40,
        bluff_aggression: Optional[float] = None,
        gto_balance_factor: float = 1.0,
        min_blocker_threshold: float = 0.30,
        num_simulations: int = 250,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        eff_agg = bluff_aggression if bluff_aggression is not None else aggression_multiplier
        self.params = BlufferParameters(
            bluff_frequency=max(0.05, min(0.95, float(bluff_frequency))),
            semi_bluff_frequency=max(0.10, min(1.0, float(semi_bluff_frequency))),
            fold_equity_threshold=max(0.10, min(0.90, float(fold_equity_threshold))),
            cbet_frequency=max(0.10, min(1.0, float(cbet_frequency))),
            bluff_raise_frequency=max(0.05, min(0.90, float(bluff_raise_frequency))),
            aggression_multiplier=max(0.50, min(2.0, float(eff_agg))),
            scare_card_weight=max(0.00, min(0.40, float(scare_card_weight))),
            dry_board_bonus=max(0.00, min(0.30, float(dry_board_bonus))),
            bet_sizing_factor=max(0.25, min(1.20, float(bet_sizing_factor))),
            min_blocker_threshold=max(0.10, min(0.70, float(min_blocker_threshold))),
            gto_balance_factor=max(0.50, min(1.80, float(gto_balance_factor))),
            num_simulations=max(100, min(1000, int(num_simulations))),
        )
        self.rng: random.Random = rng if rng is not None else random.Random()

        # Telemetria acumulada para métricas estatísticas e treinamento
        self.hands_played: int = 0
        self.bluffs_attempted: int = 0
        self.pure_bluffs: int = 0
        self.semi_bluffs: int = 0
        self.cbet_steals: int = 0
        self.bluff_raises: int = 0
        self.value_bets: int = 0
        self.vpip_actions: int = 0
        self.pfr_actions: int = 0
        self.bets_and_raises: int = 0
        self.calls: int = 0
        self.folds: int = 0
        self.checks: int = 0
        self.last_decision: Optional[BluffDecision] = None

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
    def bluff_aggression(self) -> float:
        return self.params.aggression_multiplier

    @bluff_aggression.setter
    def bluff_aggression(self, value: float) -> None:
        self.params.aggression_multiplier = max(0.50, min(2.0, float(value)))

    @property
    def gto_balance_factor(self) -> float:
        return self.params.gto_balance_factor

    @gto_balance_factor.setter
    def gto_balance_factor(self, value: float) -> None:
        self.params.gto_balance_factor = max(0.50, min(1.80, float(value)))

    @property
    def min_blocker_threshold(self) -> float:
        return self.params.min_blocker_threshold

    @min_blocker_threshold.setter
    def min_blocker_threshold(self, value: float) -> None:
        self.params.min_blocker_threshold = max(0.10, min(0.70, float(value)))

    @property
    def num_simulations(self) -> int:
        return self.params.num_simulations

    @num_simulations.setter
    def num_simulations(self, value: int) -> None:
        self.params.num_simulations = max(100, min(1000, int(value)))

    @property
    def aggression_factor(self) -> float:
        """Razão clássica entre ações agressivas (bets/raises) e passivas (calls)."""
        if self.calls == 0:
            return float(self.bets_and_raises)
        return round(self.bets_and_raises / self.calls, 2)

    @property
    def bluff_rate(self) -> float:
        """Percentual de ações ofensivas rotuladas como blefe."""
        if self.bets_and_raises == 0:
            return 0.0
        return round((self.bluffs_attempted / self.bets_and_raises) * 100.0, 1)

    def export_parameters(self) -> Dict[str, Any]:
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

        self.last_decision = decision
        self._track_decision_telemetry(decision)
        return Action(
            player_id=self.player_id,
            action_type=decision.action_type,
            amount=decision.amount,
        )

    def evaluate_cognitive_state(self, table: Table) -> BluffDecision:
        """Endpoint para interface visual Quartz (XAI Micro Vision)."""
        self.decide_action(table)
        assert self.last_decision is not None
        return self.last_decision

    def analyze_board_texture(
        self, community_cards: Sequence[Card]
    ) -> Tuple[bool, bool, bool]:
        """Classifica as propriedades estruturais da mesa (Board Texture).

        Retorna:
            (is_dry, is_wet, has_scare)
        """
        if len(community_cards) < 3:
            return False, False, False

        ranks = [c.rank.value for c in community_cards]
        suits = [c.suit for c in community_cards]
        max_suit_count = max(Counter(suits).values()) if suits else 0

        unique_ranks = sorted(set(ranks))
        has_connector = False
        for i in range(len(unique_ranks) - 1):
            if unique_ranks[i + 1] - unique_ranks[i] == 1:
                has_connector = True
                break

        # Wet Board: 3 cartas do mesmo naipe ou conectores broadway
        is_wet = max_suit_count >= 3 or (
            has_connector and len(unique_ranks) >= 3 and (max(unique_ranks) - min(unique_ranks) <= 4)
        )

        # Dry Board: desconexo, sem pares no flop, no máximo 2 do mesmo naipe
        is_dry = (
            (max_suit_count <= 2)
            and (not has_connector)
            and (len(unique_ranks) == len(community_cards))
        )

        # Scare Card: presença de Ás, Rei ou cartas de coringa de borda
        has_scare = (
            (Rank.ACE.value in ranks)
            or (Rank.KING.value in ranks)
            or (max_suit_count >= 4)
        )

        return is_dry, is_wet, has_scare

    def evaluate_blockers(
        self,
        hole_cards: Sequence[Card],
        community_cards: Sequence[Card],
    ) -> float:
        """Avalia o Efeito de Remoção de Cartas (Card Removal / Blocker Score)."""
        if not community_cards:
            h_ranks = [c.rank.value for c in hole_cards]
            score = 0.0
            if Rank.ACE.value in h_ranks:
                score += 0.35
            if Rank.KING.value in h_ranks:
                score += 0.20
            return min(1.0, score)

        score = 0.0
        board_suits = [c.suit for c in community_cards]
        suit_counts = Counter(board_suits)
        board_ranks = [c.rank.value for c in community_cards]

        # 1. Nut Flush Blocker
        for suit, count in suit_counts.items():
            if count >= 3:
                has_ace_of_suit = any(c.rank == Rank.ACE and c.suit == suit for c in hole_cards)
                has_king_of_suit = any(c.rank == Rank.KING and c.suit == suit for c in hole_cards)
                if has_ace_of_suit:
                    score += 0.50
                elif has_king_of_suit and Rank.ACE.value in board_ranks:
                    score += 0.35

        # 2. Straight Blockers
        unique_board_ranks = sorted(set(board_ranks))
        h_ranks = [c.rank.value for c in hole_cards]
        for hr in h_ranks:
            for br in unique_board_ranks:
                if abs(hr - br) in (1, 2):
                    score += 0.10

        # 3. Top Pair / Set Blocker
        max_board_rank = max(board_ranks)
        if max_board_rank >= Rank.KING.value:
            if any(c.rank.value == max_board_rank for c in hole_cards):
                score += 0.25

        return min(1.0, score)

    def detect_draw_outs(
        self,
        hole_cards: Sequence[Card],
        community_cards: Sequence[Card],
    ) -> int:
        """Calcula o número de outs que completam o jogo."""
        if len(community_cards) < 3 or len(hole_cards) < 2:
            return 0

        combined = list(hole_cards) + list(community_cards)
        outs = 0

        if has_flush_draw(combined):
            outs += 9

        if has_straight_draw(combined):
            ranks = sorted({c.rank.value for c in combined})
            if 14 in ranks:
                ranks = [1] + ranks

            is_open_ended = False
            for i in range(len(ranks) - 3):
                window = ranks[i : i + 4]
                if window[3] - window[0] == 3:
                    is_open_ended = True
                    break

            outs += 8 if is_open_ended else 4

        if outs == 0 and has_overcards((hole_cards[0], hole_cards[1]), community_cards):
            outs += 6

        return min(15, outs)

    def calculate_gto_bluff_ratio(self, bet_amount: int, pot_size: int) -> float:
        """Calcula a proporção ideal de blefe segundo o Teorema da Indiferença de Nash: B / (P + 2B)."""
        if bet_amount <= 0 or pot_size <= 0:
            return 0.20
        ratio = bet_amount / (pot_size + 2 * bet_amount)
        return max(0.15, min(0.40, ratio))

    def estimate_fold_equity(
        self,
        num_opponents: int,
        is_dry: bool,
        has_scare: bool,
        street: Street,
        pot_size: int,
        bet_size: int,
        to_call: int = 0,
    ) -> float:
        """Estima a probabilidade do oponente desistir baseada no contexto e dimensionamento."""
        # Base clássica de Fold Equity
        base_fe = max(0.12, 0.82 - (num_opponents * 0.15))

        if is_dry:
            base_fe += self.params.dry_board_bonus + 0.05

        if has_scare and street in (Street.TURN, Street.RIVER):
            base_fe += self.params.scare_card_weight + 0.05

        # Bet Sizing: apostas maiores aumentam fold equity
        if pot_size > 0 and bet_size > 0:
            ratio = bet_size / pot_size
            if ratio >= 0.70:
                base_fe += 0.08
            elif ratio <= 0.35:
                base_fe -= 0.08

        # Adversário demonstrando agressão pesada reduz a fold equity
        if to_call > 0 and pot_size > 0:
            bet_pot_ratio = to_call / pot_size
            if bet_pot_ratio > 0.50:
                base_fe -= 0.20

        return max(0.05, min(0.92, base_fe))

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
        equity: float,
        street: Street,
        comb_desc: str = "",
        hand_desc: str = "",
    ) -> BluffDecision:
        """Executa aposta ou aumento por valor legítimo para balancear o range."""
        can_raise = ActionType.RAISE in legal_actions and player_stack > to_call
        can_bet = ActionType.BET in legal_actions and player_stack > 0

        target_fraction = 0.75 if street in (Street.TURN, Street.RIVER) else 0.65
        bet_amt = int(max(big_blind, pot_size * target_fraction))
        bet_amt = min(player_stack, bet_amt)

        desc = f" ({comb_desc or hand_desc})" if (comb_desc or hand_desc) else ""

        if to_call == 0 and can_bet and bet_amt > 0:
            metrics = GhBluffMetrics(
                raw_equity=equity,
                adjusted_equity=equity,
                pot_odds=0.0,
                gto_bluff_threshold=0.0,
                random_roll=0.0,
                blocker_score=0.0,
                semi_bluff_outs=0,
                is_bluff=False,
                tactic=GhBluffTactic.VALUE_PLAY.value,
                tactical_rationale=f"Aposta por valor para proteção de range{desc}",
                formula_reference="Value Bet: Sizing = 0.65-0.75 * Pot",
            )
            return BluffDecision(
                action_type=ActionType.BET,
                amount=bet_amt,
                is_bluff=False,
                tactic=BluffTactic.VALUE_PLAY.value,
                fold_equity=0.10,
                reason=f"Aposta de valor legítimo{desc} com equidade sólida de {equity:.1%}",
                semi_bluff_outs=0,
                equity=equity,
                pot_odds=0.0,
                expected_value=equity * pot_size,
                metrics=metrics,
            )

        if to_call > 0 and can_raise and equity >= 0.70:
            raise_amt = current_highest_bet + max(min_raise, int(to_call * 2.5))
            max_pos = player_current_bet + player_stack
            raise_amt = min(max_pos, raise_amt)
            if raise_amt > current_highest_bet:
                metrics = GhBluffMetrics(
                    raw_equity=equity,
                    adjusted_equity=equity,
                    pot_odds=to_call / max(1, pot_size + to_call),
                    gto_bluff_threshold=0.0,
                    random_roll=0.0,
                    blocker_score=0.0,
                    semi_bluff_outs=0,
                    is_bluff=False,
                    tactic=GhBluffTactic.VALUE_PLAY.value,
                    tactical_rationale=f"Re-aumento de valor para punir apostas adversárias{desc}",
                    formula_reference="Value 3-Bet/Raise: Equity >= 0.70",
                )
                return BluffDecision(
                    action_type=ActionType.RAISE,
                    amount=raise_amt,
                    is_bluff=False,
                    tactic=BluffTactic.VALUE_PLAY.value,
                    fold_equity=0.15,
                    reason=f"Re-aumento de valor dominante{desc} ({equity:.1%})",
                    semi_bluff_outs=0,
                    equity=equity,
                    pot_odds=to_call / max(1, pot_size + to_call),
                    expected_value=(equity * (pot_size + to_call)) - to_call,
                    metrics=metrics,
                )

        can_pay = ActionType.CALL in legal_actions or ActionType.ALL_IN in legal_actions
        if to_call > 0 and can_pay:
            pay_act = ActionType.CALL if ActionType.CALL in legal_actions else ActionType.ALL_IN
            gh_m = GhBluffMetrics(
                raw_equity=equity,
                adjusted_equity=equity,
                pot_odds=to_call / max(1, pot_size + to_call),
                gto_bluff_threshold=0.0,
                random_roll=0.0,
                blocker_score=0.0,
                semi_bluff_outs=0,
                is_bluff=False,
                tactic=GhBluffTactic.PROBE_DEFEND.value,
                tactical_rationale=f"Call de valor para showdown seguro{desc}",
                formula_reference="Showdown Value Call",
            )
            return BluffDecision(
                action_type=pay_act,
                amount=to_call if pay_act == ActionType.CALL else player_stack,
                is_bluff=False,
                tactic=BluffTactic.VALUE_PLAY.value,
                fold_equity=0.05,
                reason=f"Call de valor para showdown seguro{desc}",
                semi_bluff_outs=0,
                equity=equity,
                pot_odds=to_call / max(1, pot_size + to_call),
                expected_value=(equity * (pot_size + to_call)) - to_call,
                metrics=gh_m,
            )

        if ActionType.CHECK in legal_actions:
            gh_m = GhBluffMetrics(
                raw_equity=equity,
                adjusted_equity=equity,
                pot_odds=0.0,
                gto_bluff_threshold=0.0,
                random_roll=0.0,
                blocker_score=0.0,
                semi_bluff_outs=0,
                is_bluff=False,
                tactic=GhBluffTactic.FREE_CHECK.value,
                tactical_rationale=f"Check de controle de valor{desc}",
                formula_reference="Value Pot Control",
            )
            return BluffDecision(
                action_type=ActionType.CHECK,
                amount=0,
                is_bluff=False,
                tactic=BluffTactic.FREE_CHECK.value,
                fold_equity=0.0,
                reason=f"Check de controle de valor{desc}",
                semi_bluff_outs=0,
                equity=equity,
                pot_odds=0.0,
                expected_value=0.0,
                metrics=gh_m,
            )

        # Fallback de segurança FOLD
        return BluffDecision(
            action_type=ActionType.FOLD,
            amount=0,
            is_bluff=False,
            tactic=BluffTactic.PRUDENT_FOLD.value,
            fold_equity=0.0,
            reason="Fold de segurança",
            semi_bluff_outs=0,
            equity=equity,
            pot_odds=0.0,
            expected_value=0.0,
            metrics=None,
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
        """Determina a ação tática no Pré-Flop para o Agente Blefador."""
        c1, c2 = hole_cards[0], hole_cards[1]
        is_pair = c1.rank.value == c2.rank.value
        is_suited = c1.suit == c2.suit
        high_rank = max(c1.rank.value, c2.rank.value)
        low_rank = min(c1.rank.value, c2.rank.value)
        gap = high_rank - low_rank

        can_raise = ActionType.RAISE in legal_actions and player_stack > to_call
        can_call = ActionType.CALL in legal_actions
        can_check = ActionType.CHECK in legal_actions

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
                equity=0.82,
                street=Street.PREFLOP,
                comb_desc=f"{c1.rank.symbol}{c2.rank.symbol}",
            )

        # 2. Mãos Especulativas (Pares 22-99, cartas naipadas, conectores, broadways)
        is_speculative = (
            is_pair
            or is_suited
            or (gap <= 2 and low_rank >= 4)
            or (high_rank >= 10 and low_rank >= 8)
        )
        is_wheel_ace = is_suited and high_rank == Rank.ACE.value and low_rank in (2, 3, 4, 5)

        roll = self.rng.random()

        # =========================================================================
        # Cenário A: Custo Zero ou Cobrir Big Blind (to_call <= big_blind)
        # O blefador NUNCA dá fold para ver o flop por um BB!
        # =========================================================================
        if to_call <= big_blind:
            # Roubo de Blinds pré-flop pontual (8%) se em posição para roubar
            wants_steal = roll < 0.08
            if can_raise and wants_steal and to_call == 0:
                steal_amt = min(player_stack, current_highest_bet + max(min_raise, big_blind * 2))
                metrics = GhBluffMetrics(
                    raw_equity=0.38,
                    adjusted_equity=0.40,
                    pot_odds=0.0,
                    gto_bluff_threshold=0.10,
                    random_roll=roll,
                    blocker_score=0.25,
                    semi_bluff_outs=0,
                    is_bluff=True,
                    tactic=GhBluffTactic.CBET_STEAL.value,
                    tactical_rationale="Roubo tático de blinds pré-flop",
                    formula_reference="Preflop Blind Steal",
                )
                return BluffDecision(
                    action_type=ActionType.RAISE,
                    amount=steal_amt,
                    is_bluff=True,
                    tactic=BluffTactic.PREFLOP_STEAL.value,
                    fold_equity=0.55,
                    reason="Roubo de blinds pré-flop explorando mesa barata",
                    semi_bluff_outs=0,
                    equity=0.38,
                    pot_odds=0.0,
                    expected_value=float(big_blind),
                    metrics=metrics,
                )

            if to_call == 0 and can_check:
                metrics = GhBluffMetrics(
                    raw_equity=0.30,
                    adjusted_equity=0.30,
                    pot_odds=0.0,
                    gto_bluff_threshold=0.0,
                    random_roll=roll,
                    blocker_score=0.0,
                    semi_bluff_outs=0,
                    is_bluff=False,
                    tactic=GhBluffTactic.FREE_CHECK.value,
                    tactical_rationale="Check gratuito no Big Blind para ver o Flop",
                    formula_reference="Free Check Preflop",
                )
                return BluffDecision(
                    action_type=ActionType.CHECK,
                    amount=0,
                    is_bluff=False,
                    tactic=BluffTactic.FREE_CHECK.value,
                    fold_equity=0.40,
                    reason="Check gratuito no Big Blind para ver o Flop",
                    semi_bluff_outs=0,
                    equity=0.30,
                    pot_odds=0.0,
                    expected_value=0.0,
                    metrics=metrics,
                )

            # Cobrir ou completar o Big Blind pré-flop: SEMPRE defende
            if can_call:
                metrics = GhBluffMetrics(
                    raw_equity=0.35,
                    adjusted_equity=0.35,
                    pot_odds=to_call / max(1, pot_size + to_call),
                    gto_bluff_threshold=0.0,
                    random_roll=roll,
                    blocker_score=0.15,
                    semi_bluff_outs=0,
                    is_bluff=False,
                    tactic=GhBluffTactic.PROBE_DEFEND.value,
                    tactical_rationale="Pagamento do Big Blind para disputar o Flop em posição",
                    formula_reference="Preflop Big Blind Defense",
                )
                return BluffDecision(
                    action_type=ActionType.CALL,
                    amount=to_call,
                    is_bluff=False,
                    tactic=BluffTactic.PREFLOP_DEFEND.value,
                    fold_equity=0.45,
                    reason="Pagamento do Big Blind para disputar o Flop em posição",
                    semi_bluff_outs=0,
                    equity=0.35,
                    pot_odds=to_call / max(1, pot_size + to_call),
                    expected_value=5.0,
                    metrics=metrics,
                )

        # =========================================================================
        # Cenário B: Enfrentando aumento pré-flop (to_call > big_blind)
        # =========================================================================
        # 3-Bet Polarizada de Blefe com Wheel Aces (A5s/A4s)
        threshold_3bet = 0.35 * self.params.aggression_multiplier
        if can_raise and is_wheel_ace and to_call > 0 and roll < threshold_3bet:
            raise_target = current_highest_bet + max(min_raise, int(to_call * 2.8))
            max_pos = player_current_bet + player_stack
            raise_amount = min(max_pos, max(current_highest_bet + min_raise, raise_target))
            metrics = GhBluffMetrics(
                raw_equity=0.42,
                adjusted_equity=0.45,
                pot_odds=to_call / max(1, pot_size + to_call),
                gto_bluff_threshold=threshold_3bet,
                random_roll=roll,
                blocker_score=0.40,
                semi_bluff_outs=0,
                is_bluff=True,
                tactic=GhBluffTactic.PREFLOP_3BET_BLUFF.value,
                tactical_rationale="3-Bet de blefe polarizada pré-flop com Ás do naipe",
                formula_reference="Polarized Preflop 3-Bet: Blocker + Fold Equity",
            )
            return BluffDecision(
                action_type=ActionType.RAISE,
                amount=raise_amount,
                is_bluff=True,
                tactic=BluffTactic.PREFLOP_3BET.value,
                fold_equity=0.55,
                reason="Preflop 3-Bet Polarized Bluff com Ás bloqueador",
                semi_bluff_outs=0,
                equity=0.42,
                pot_odds=to_call / max(1, pot_size + to_call),
                expected_value=15.0,
                metrics=metrics,
            )

        # Aumento padrão pré-flop (to_call <= big_blind * 3.5)
        is_standard_raise = to_call <= big_blind * 3.5
        if is_standard_raise and is_speculative:
            wants_3bet = can_raise and (roll < 0.20 * self.params.aggression_multiplier)
            if wants_3bet:
                raise_target = current_highest_bet + max(min_raise, int(to_call * 2.5))
                max_pos = player_current_bet + player_stack
                raise_amount = min(max_pos, max(current_highest_bet + min_raise, raise_target))
                metrics = GhBluffMetrics(
                    raw_equity=0.40,
                    adjusted_equity=0.42,
                    pot_odds=to_call / max(1, pot_size + to_call),
                    gto_bluff_threshold=0.20,
                    random_roll=roll,
                    blocker_score=0.25,
                    semi_bluff_outs=0,
                    is_bluff=True,
                    tactic=GhBluffTactic.PREFLOP_3BET_BLUFF.value,
                    tactical_rationale="Re-aumento de blefe tático pré-flop com mão especulativa",
                    formula_reference="Preflop Speculative 3-Bet",
                )
                return BluffDecision(
                    action_type=ActionType.RAISE,
                    amount=raise_amount,
                    is_bluff=True,
                    tactic=BluffTactic.PREFLOP_3BET.value,
                    fold_equity=0.50,
                    reason="Re-aumento de blefe tático pré-flop com mão especulativa",
                    semi_bluff_outs=0,
                    equity=0.40,
                    pot_odds=to_call / max(1, pot_size + to_call),
                    expected_value=10.0,
                    metrics=metrics,
                )

            if can_call:
                metrics = GhBluffMetrics(
                    raw_equity=0.38,
                    adjusted_equity=0.40,
                    pot_odds=to_call / max(1, pot_size + to_call),
                    gto_bluff_threshold=0.0,
                    random_roll=roll,
                    blocker_score=0.20,
                    semi_bluff_outs=0,
                    is_bluff=False,
                    tactic=GhBluffTactic.PROBE_DEFEND.value,
                    tactical_rationale="Defesa pré-flop com mão especulativa para disputar o Flop",
                    formula_reference="Preflop Speculative Defend",
                )
                return BluffDecision(
                    action_type=ActionType.CALL,
                    amount=to_call,
                    is_bluff=False,
                    tactic=BluffTactic.PREFLOP_DEFEND.value,
                    fold_equity=0.35,
                    reason="Defesa pré-flop com mão especulativa para disputar o Flop",
                    semi_bluff_outs=0,
                    equity=0.38,
                    pot_odds=to_call / max(1, pot_size + to_call),
                    expected_value=8.0,
                    metrics=metrics,
                )

        # Se não for especulativo ou enfrentar overbet absurda: FOLD DISCIPLINADO
        metrics = GhBluffMetrics(
            raw_equity=0.20,
            adjusted_equity=0.20,
            pot_odds=to_call / max(1, pot_size + to_call),
            gto_bluff_threshold=0.0,
            random_roll=roll,
            blocker_score=0.0,
            semi_bluff_outs=0,
            is_bluff=False,
            tactic=GhBluffTactic.DISCIPLINED_FOLD.value,
            tactical_rationale="Desistência disciplinada pré-flop sem pot odds",
            formula_reference="Disciplined Fold Preflop",
        )
        return BluffDecision(
            action_type=ActionType.FOLD,
            amount=0,
            is_bluff=False,
            tactic=BluffTactic.PRUDENT_FOLD.value,
            fold_equity=0.0,
            reason="Fold pré-flop disciplinado sem odds",
            semi_bluff_outs=0,
            equity=0.20,
            pot_odds=to_call / max(1, pot_size + to_call),
            expected_value=-float(to_call),
            metrics=metrics,
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
        street: Optional[Street] = None,
        **kwargs: Any,
    ) -> BluffDecision:
        """Determina e dimensiona o blefe ótimo ou aposta de valor com base em GTO e Blockers."""
        actual_street = street if street is not None else (
            Street.PREFLOP if not community_cards else (
                Street.FLOP if len(community_cards) == 3 else (
                    Street.TURN if len(community_cards) == 4 else Street.RIVER
                )
            )
        )

        # Rota de Pré-Flop
        if actual_street == Street.PREFLOP or not community_cards:
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

        can_check = ActionType.CHECK in legal_actions
        can_bet = ActionType.BET in legal_actions
        can_raise = ActionType.RAISE in legal_actions
        can_call = ActionType.CALL in legal_actions

        # Textura do bordo, blockers e outs
        is_dry, is_wet, has_scare = self.analyze_board_texture(community_cards)
        blocker_score = self.evaluate_blockers(hole_cards, community_cards)
        outs = self.detect_draw_outs(hole_cards, community_cards)

        # Avaliação de jogo formado
        all_cards = list(hole_cards) + list(community_cards)
        score = evaluate_hand(all_cards) if len(all_cards) >= 5 else None
        hand_rank_val = score.hand_rank.value if score else 1
        comb_desc = score.description if score else ""

        # Mãos Fortes (Dois pares, Trinca, Sequência, Full House) -> Valor Puro
        if hand_rank_val >= 3:
            return self._decide_value_play(
                pot_size=pot_size,
                to_call=to_call,
                player_stack=player_stack,
                player_current_bet=player_current_bet,
                current_highest_bet=current_highest_bet,
                min_raise=min_raise,
                big_blind=big_blind,
                legal_actions=legal_actions,
                equity=0.85,
                street=actual_street,
                comb_desc=comb_desc,
            )

        # Dimensionamento de aposta/blefe base
        target_bet = int(pot_size * self.params.bet_sizing_factor * self.params.aggression_multiplier)
        bet_amount = min(player_stack, max(big_blind, min_raise, target_bet))

        # Fold Equity estimada dinâmica
        fold_equity = self.estimate_fold_equity(
            num_opponents=num_opponents,
            is_dry=is_dry,
            has_scare=has_scare,
            street=actual_street,
            pot_size=pot_size,
            bet_size=bet_amount,
            to_call=to_call,
        )

        # Teorema da Indiferença GTO de Nash: B / (P + 2B)
        gto_bluff_threshold = self.calculate_gto_bluff_ratio(bet_amount, pot_size) * self.params.gto_balance_factor
        roll = self.rng.random()

        # =========================================================================
        # CENÁRIO 1: CUSTO ZERO (to_call == 0) -> Avalia C-Bet, Semi-Blefe ou River Bluff
        # =========================================================================
        if to_call == 0:
            # 1A. Semi-Blefe no Flop ou Turn com Outs (>= 8 outs)
            if outs >= 8 and actual_street in (Street.FLOP, Street.TURN) and can_bet and bet_amount > 0:
                roll_semi = self.rng.random()
                if roll_semi <= self.params.semi_bluff_frequency:
                    metrics = GhBluffMetrics(
                        raw_equity=0.45,
                        adjusted_equity=0.55,
                        pot_odds=0.0,
                        gto_bluff_threshold=gto_bluff_threshold,
                        random_roll=roll_semi,
                        blocker_score=blocker_score,
                        semi_bluff_outs=outs,
                        is_bluff=True,
                        tactic=GhBluffTactic.SEMI_BLUFF_DRAW.value,
                        tactical_rationale=f"Semi-blefe agressivo com {outs} outs de evolução",
                        formula_reference="Semi-Bluff Draw Pressure: Outs >= 8",
                    )
                    return BluffDecision(
                        action_type=ActionType.BET,
                        amount=bet_amount,
                        is_bluff=True,
                        tactic=BluffTactic.SEMI_BLUFF.value,
                        fold_equity=fold_equity,
                        reason=f"Semi-blefe agressivo ({outs} outs) com fold equity de {fold_equity:.0%}",
                        semi_bluff_outs=outs,
                        equity=0.45,
                        pot_odds=0.0,
                        expected_value=25.0,
                        metrics=metrics,
                    )

            # 1B. Blefe de River Polarizado com Nut Blocker
            if actual_street == Street.RIVER and can_bet and num_opponents <= 2 and bet_amount > 0:
                has_nut_blocker = blocker_score >= self.params.min_blocker_threshold
                if has_nut_blocker and (roll <= gto_bluff_threshold or roll < self.params.bluff_frequency):
                    polarized_bet = min(player_stack, max(min_raise, int(pot_size * 0.70)))
                    metrics = GhBluffMetrics(
                        raw_equity=0.20,
                        adjusted_equity=0.20,
                        pot_odds=0.0,
                        gto_bluff_threshold=gto_bluff_threshold,
                        random_roll=roll,
                        blocker_score=blocker_score,
                        semi_bluff_outs=0,
                        is_bluff=True,
                        tactic=GhBluffTactic.NUT_BLOCKER_BLUFF.value,
                        tactical_rationale="Blefe polarizado no river sustentado por Nut Blocker",
                        formula_reference="GTO Nash Indifference Polarized Bluff: B / (P + 2B)",
                    )
                    return BluffDecision(
                        action_type=ActionType.BET,
                        amount=polarized_bet,
                        is_bluff=True,
                        tactic=BluffTactic.RIVER_BLUFF.value,
                        fold_equity=fold_equity + 0.15,
                        reason="Blefe polarizado no river sustentado por Nut Blocker",
                        semi_bluff_outs=0,
                        equity=0.20,
                        pot_odds=0.0,
                        expected_value=20.0,
                        metrics=metrics,
                    )

            # 1C. Agressão em Scare Card no Turn/River ou C-Bet Steal em Bordo Seco
            if can_bet and bet_amount > 0 and num_opponents <= 2:
                cbet_eligible = (is_dry or has_scare or fold_equity >= self.params.fold_equity_threshold)
                if cbet_eligible and (roll <= self.params.cbet_frequency or roll <= self.params.bluff_frequency):
                    if has_scare and actual_street in (Street.TURN, Street.RIVER):
                        tactic_str = BluffTactic.SCARE_CARD_BARREL.value
                        gh_tactic_str = GhBluffTactic.CBET_STEAL.value
                        rationale = "Agressão em Scare Card no Turn/River explorando range favorável"
                    elif actual_street == Street.RIVER:
                        tactic_str = BluffTactic.RIVER_BLUFF.value
                        gh_tactic_str = GhBluffTactic.POLARIZED_RIVER_BLUFF.value
                        rationale = "Blefe no River explorando mesa abandonada"
                    else:
                        tactic_str = BluffTactic.CBET_STEAL.value
                        gh_tactic_str = GhBluffTactic.CBET_STEAL.value
                        rationale = "C-Bet Steal em bordo seco explorando fraqueza"

                    metrics = GhBluffMetrics(
                        raw_equity=0.30,
                        adjusted_equity=0.35,
                        pot_odds=0.0,
                        gto_bluff_threshold=gto_bluff_threshold,
                        random_roll=roll,
                        blocker_score=blocker_score,
                        semi_bluff_outs=outs,
                        is_bluff=True,
                        tactic=gh_tactic_str,
                        tactical_rationale=rationale,
                        formula_reference="C-Bet Steal / Scare Barrel",
                    )
                    return BluffDecision(
                        action_type=ActionType.BET,
                        amount=bet_amount,
                        is_bluff=True,
                        tactic=tactic_str,
                        fold_equity=fold_equity,
                        reason=f"{tactic_str} (FE={fold_equity:.2f})",
                        semi_bluff_outs=outs,
                        equity=0.30,
                        pot_odds=0.0,
                        expected_value=18.0,
                        metrics=metrics,
                    )

            # 1D. Check Gratuito (Preservação de Fichas)
            metrics = GhBluffMetrics(
                raw_equity=0.30,
                adjusted_equity=0.30,
                pot_odds=0.0,
                gto_bluff_threshold=gto_bluff_threshold,
                random_roll=roll,
                blocker_score=blocker_score,
                semi_bluff_outs=outs,
                is_bluff=False,
                tactic=GhBluffTactic.FREE_CHECK.value,
                tactical_rationale="Check gratuito para controle de pote",
                formula_reference="Free Check: Pot Control",
            )
            return BluffDecision(
                action_type=ActionType.CHECK,
                amount=0,
                is_bluff=False,
                tactic=BluffTactic.FREE_CHECK.value,
                fold_equity=fold_equity,
                reason="Check gratuito para controle de pote",
                semi_bluff_outs=outs,
                equity=0.30,
                pot_odds=0.0,
                expected_value=0.0,
                metrics=metrics,
            )

        # =========================================================================
        # CENÁRIO 2: ENFRENTANDO APOSTA (to_call > 0)
        # =========================================================================
        pot_odds = to_call / max(1, pot_size + to_call)

        # 2A. Semi-Blefe Raise com Alto Draw (>= 8 outs)
        if outs >= 8 and actual_street in (Street.FLOP, Street.TURN) and can_raise:
            raise_target = current_highest_bet + max(min_raise, int(to_call * 2.2))
            max_pos = player_current_bet + player_stack
            raise_amount = min(max_pos, max(current_highest_bet + min_raise, raise_target))
            metrics = GhBluffMetrics(
                raw_equity=0.45,
                adjusted_equity=0.55,
                pot_odds=pot_odds,
                gto_bluff_threshold=gto_bluff_threshold,
                random_roll=roll,
                blocker_score=blocker_score,
                semi_bluff_outs=outs,
                is_bluff=True,
                tactic=GhBluffTactic.SEMI_BLUFF_DRAW.value,
                tactical_rationale=f"Semi-blefe raise contra aposta com {outs} outs",
                formula_reference="Semi-Bluff Raise Pressure",
            )
            return BluffDecision(
                action_type=ActionType.RAISE,
                amount=raise_amount,
                is_bluff=True,
                tactic=BluffTactic.SEMI_BLUFF.value,
                fold_equity=fold_equity,
                reason=f"Semi-blefe raise agressivo com {outs} outs",
                semi_bluff_outs=outs,
                equity=0.45,
                pot_odds=pot_odds,
                expected_value=22.0,
                metrics=metrics,
            )

        # 2B. Call de Defesa / Implied Odds com Draw
        if outs >= 8 and can_call and to_call <= max(big_blind * 4, int(pot_size * 0.45)):
            metrics = GhBluffMetrics(
                raw_equity=0.40,
                adjusted_equity=0.48,
                pot_odds=pot_odds,
                gto_bluff_threshold=gto_bluff_threshold,
                random_roll=roll,
                blocker_score=blocker_score,
                semi_bluff_outs=outs,
                is_bluff=False,
                tactic=GhBluffTactic.PROBE_DEFEND.value,
                tactical_rationale=f"Call por implied odds com {outs} outs para o draw",
                formula_reference="Implied Draw Call",
            )
            return BluffDecision(
                action_type=ActionType.CALL,
                amount=to_call,
                is_bluff=False,
                tactic=BluffTactic.FLOAT_CALL.value,
                fold_equity=fold_equity,
                reason=f"Call com {outs} outs sustentado por odds implícitas",
                semi_bluff_outs=outs,
                equity=0.40,
                pot_odds=pot_odds,
                expected_value=10.0,
                metrics=metrics,
            )

        # 2C. Fallback Check se legal
        if can_check:
            metrics = GhBluffMetrics(
                raw_equity=0.25,
                adjusted_equity=0.25,
                pot_odds=pot_odds,
                gto_bluff_threshold=gto_bluff_threshold,
                random_roll=roll,
                blocker_score=blocker_score,
                semi_bluff_outs=outs,
                is_bluff=False,
                tactic=GhBluffTactic.FREE_CHECK.value,
                tactical_rationale="Check de segurança legal",
                formula_reference="Fallback Check",
            )
            return BluffDecision(
                action_type=ActionType.CHECK,
                amount=0,
                is_bluff=False,
                tactic=BluffTactic.FREE_CHECK.value,
                fold_equity=fold_equity,
                reason="Check de segurança legal",
                semi_bluff_outs=outs,
                equity=0.25,
                pot_odds=pot_odds,
                expected_value=0.0,
                metrics=metrics,
            )

        # 2D. Desistência Disciplinada (ANTI-CALLING-STATION LEAK-FIX)
        metrics = GhBluffMetrics(
            raw_equity=0.20,
            adjusted_equity=0.20,
            pot_odds=pot_odds,
            gto_bluff_threshold=gto_bluff_threshold,
            random_roll=roll,
            blocker_score=blocker_score,
            semi_bluff_outs=outs,
            is_bluff=False,
            tactic=GhBluffTactic.DISCIPLINED_FOLD.value,
            tactical_rationale="Desistência disciplinada contra aposta sem odds nem blockers",
            formula_reference="Anti-Leak Disciplined Fold: No Equity, No Blockers",
        )
        return BluffDecision(
            action_type=ActionType.FOLD,
            amount=0,
            is_bluff=False,
            tactic=BluffTactic.PRUDENT_FOLD.value,
            fold_equity=0.0,
            reason="Fold prudente disciplinado contra aposta sem odds",
            semi_bluff_outs=outs,
            equity=0.20,
            pot_odds=pot_odds,
            expected_value=-float(to_call),
            metrics=metrics,
        )

    def _track_decision_telemetry(self, decision: BluffDecision) -> None:
        """Atualiza telemetria de tomada de decisão do agente."""
        self.hands_played += 1
        if decision.action_type in (ActionType.BET, ActionType.RAISE):
            self.bets_and_raises += 1
            if decision.is_bluff:
                self.bluffs_attempted += 1
                if decision.semi_bluff_outs > 0:
                    self.semi_bluffs += 1
                else:
                    self.pure_bluffs += 1
            else:
                self.value_bets += 1
        elif decision.action_type == ActionType.CALL:
            self.calls += 1
        elif decision.action_type == ActionType.CHECK:
            self.checks += 1
        elif decision.action_type == ActionType.FOLD:
            self.folds += 1


GhBlufferAgent = BlufferAgent
