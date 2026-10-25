"""Agente Blefador GH (GhBlufferAgent) para Texas Hold'em.

Desenvolvido por Gustavo (GH) para o Trabalho de Conclusão de Curso (TCC).
Incorpora os princípios matemáticos e algorítmicos do Libratus e Pluribus:
1. Razão Áurea GTO entre Valor e Blefe baseada no Princípio da Indiferença: B / (P + 2B)
2. Motor de Remoção de Cartas (Blocker Scoring Engine) para Nut Flush e Sequências
3. Semi-Blefes com alta retenção de equidade (Outs no Flop e Turn)
4. Dimensionamento Geométrico e Polarizado em boards secos e no River
5. Eliminação total do vício de "Calling Station" (folds disciplinados contra apostas sem odds)
6. Estratégias Mistas Estocásticas balanceadas e payload explicativo completo (XAI)
"""

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import random
import sys
from typing import List, Optional, Sequence, Tuple

# Garante resolução dos módulos a partir da raiz do repositório
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.agents.base import BaseAgent  # noqa: E402
from src.engine.deck import Card, Rank, Suit  # noqa: E402
from src.engine.equity import (  # noqa: E402
    calculate_pot_odds,
    estimate_hand_equity,
    has_flush_draw,
    has_overcards,
    has_straight_draw,
)
from src.engine.hand_eval import HandRank, evaluate_hand  # noqa: E402
from src.engine.table import Action, ActionType, Street, Table  # noqa: E402


class GhBluffTactic(str, Enum):
    """Classificação formal das manobras executadas pelo GhBlufferAgent."""

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


@dataclass(frozen=True)
class GhBluffDecision:
    """Estrutura formal e imutável da decisão tática tomada pelo agente."""

    action_type: ActionType
    amount: int
    metrics: GhBluffMetrics


class GhBlufferAgent(BaseAgent):
    """Agente Blefador com Indiferença de Nash, Remoção de Cartas e Semi-Blefes."""

    def __init__(
        self,
        player_id: str,
        name: str = "GhBlufferAgent",
        bluff_aggression: float = 1.0,
        gto_balance_factor: float = 1.0,
        min_blocker_threshold: float = 0.30,
        num_simulations: int = 250,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        self.bluff_aggression: float = max(0.5, min(2.0, float(bluff_aggression)))
        self.gto_balance_factor: float = max(0.5, min(1.8, float(gto_balance_factor)))
        self.min_blocker_threshold: float = max(0.10, min(0.70, float(min_blocker_threshold)))
        self.num_simulations: int = max(100, min(1000, int(num_simulations)))
        self.rng: random.Random = rng if rng is not None else random.Random()

        # Telemetria e auditoria estatística do agente
        self.hands_played: int = 0
        self.bluffs_attempted: int = 0
        self.pure_bluffs: int = 0
        self.semi_bluffs: int = 0
        self.cbet_steals: int = 0
        self.value_bets: int = 0
        self.calls: int = 0
        self.folds: int = 0
        self.checks: int = 0
        self.bets_and_raises: int = 0
        self.last_decision: Optional[GhBluffDecision] = None

    @property
    def aggression_factor(self) -> float:
        """Razão clássica entre ações agressivas (bets/raises) e passivas (calls)."""
        if self.calls == 0:
            return float(self.bets_and_raises)
        return round(self.bets_and_raises / self.calls, 2)

    @property
    def bluff_rate(self) -> float:
        """Percentual de ações ofensivas rotuladas como blefe legítimo."""
        if self.bets_and_raises == 0:
            return 0.0
        return round((self.bluffs_attempted / self.bets_and_raises) * 100.0, 1)

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

        # Verifica conectividade de sequências
        unique_ranks = sorted(set(ranks))
        has_connector = False
        for i in range(len(unique_ranks) - 1):
            if unique_ranks[i + 1] - unique_ranks[i] == 1:
                has_connector = True
                break

        # Wet Board: 3 cartas do mesmo naipe ou alta conectividade de broadways
        is_wet = max_suit_count >= 3 or (has_connector and len(unique_ranks) >= 3 and (max(unique_ranks) - min(unique_ranks) <= 4))

        # Dry Board: desconexo, sem pares no flop, no máximo 2 do mesmo naipe
        is_dry = (max_suit_count <= 2) and (not has_connector) and (len(unique_ranks) == len(community_cards))

        # Scare Card: presença de Ás, Rei ou cartas de coringa de borda
        has_scare = (Rank.ACE.value in ranks) or (Rank.KING.value in ranks) or (max_suit_count >= 4)

        return is_dry, is_wet, has_scare

    def evaluate_blockers(
        self,
        hole_cards: Sequence[Card],
        community_cards: Sequence[Card],
    ) -> float:
        """Avalia o Efeito de Remoção de Cartas (Card Removal / Blocker Score).

        Mede matematicamente o quanto as cartas na mão do herói reduzem
        os combos das melhores mãos no range do oponente.

        Returns:
            Pontuação normalizada entre 0.0 e 1.0.
        """
        if not community_cards:
            # No pré-flop: ter Ás ou Rei bloqueia AA, KK, AK no oponente
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
        # Se há 3 ou mais cartas de um naipe no bordo, segurar o Ás desse naipe
        # IMPEDE o adversário de ter o Nut Flush! (Conceito central do Pluribus)
        for suit, count in suit_counts.items():
            if count >= 3:
                has_ace_of_suit = any(c.rank == Rank.ACE and c.suit == suit for c in hole_cards)
                has_king_of_suit = any(c.rank == Rank.KING and c.suit == suit for c in hole_cards)
                if has_ace_of_suit:
                    score += 0.50
                elif has_king_of_suit and Rank.ACE.value in board_ranks:
                    score += 0.35

        # 2. Straight Blockers (Bloqueadores de Sequência)
        # Se o bordo tem cartas conectadas, segurar os conectores críticos remove combos de sequência
        unique_board_ranks = sorted(set(board_ranks))
        h_ranks = [c.rank.value for c in hole_cards]

        for hr in h_ranks:
            # Se a carta do herói se encaixa exatamente entre as cartas do bordo
            for br in unique_board_ranks:
                if abs(hr - br) == 1 or abs(hr - br) == 2:
                    score += 0.10

        # 3. Top Pair / Set Blocker em bordos secos com Ás ou Rei
        max_board_rank = max(board_ranks)
        if max_board_rank >= Rank.KING.value:
            if any(c.rank.value == max_board_rank for c in hole_cards):
                # Hero segura uma carta igual à maior do bordo (reduz combos de Top Pair do vilão)
                score += 0.25

        return min(1.0, score)

    def detect_draw_outs(
        self,
        hole_cards: Sequence[Card],
        community_cards: Sequence[Card],
    ) -> int:
        """Calcula o número de cartas restantes no baralho (outs) que completam o jogo."""
        if len(community_cards) < 3 or len(community_cards) > 4:
            return 0

        combined = list(hole_cards) + list(community_cards)
        outs = 0

        # 1. Flush Draw (4 cartas do mesmo naipe) -> 9 outs
        if has_flush_draw(combined):
            outs += 9

        # 2. Straight Draw (open-ended 8 outs, gutshot 4 outs)
        if has_straight_draw(combined):
            ranks = sorted({c.rank.value for c in combined})
            if 14 in ranks:
                ranks = [1] + ranks

            is_open_ended = False
            for i in range(len(ranks) - 3):
                window = ranks[i : i + 4]
                if window[3] - window[0] == 3:
                    # 4 cartas estritamente consecutivas (ex: 5-6-7-8)
                    is_open_ended = True
                    break

            if is_open_ended:
                outs += 8
            else:
                outs += 4

        # 3. Overcards em relação ao bordo (até 6 outs se desemparelhado)
        if outs == 0 and has_overcards((hole_cards[0], hole_cards[1]), community_cards):
            outs += 6

        return min(15, outs)

    def calculate_gto_bluff_ratio(self, bet_amount: int, pot_size: int) -> float:
        """Calcula a proporção ideal de blefe segundo o Teorema da Indiferença de Nash.

        Formula:
            Ratio = B / (P + 2B)
        """
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
    ) -> float:
        """Estima a probabilidade do oponente desistir baseada no contexto e dimensionamento."""
        # Multiway: Em potes com 3 ou mais jogadores, a Fold Equity desaba
        if num_opponents >= 3:
            return 0.15 if street in (Street.PREFLOP, Street.FLOP) else 0.05
        if num_opponents == 2:
            base_fe = 0.35 if street in (Street.PREFLOP, Street.FLOP) else 0.18
        else:
            base_fe = 0.52

        # Bordo seco favorece o agressor original
        if is_dry:
            base_fe += 0.12

        # Carta assustadora (Scare Card) no Turn ou River aumenta a pressão
        if has_scare and street in (Street.TURN, Street.RIVER):
            base_fe += 0.15

        # Bet Sizing: apostas maiores (75% a 100% do pote) geram mais fold equity
        if pot_size > 0:
            ratio = bet_size / pot_size
            if ratio >= 0.75:
                base_fe += 0.10
            elif ratio <= 0.40:
                base_fe -= 0.10

        return max(0.05, min(0.85, base_fe))

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
    ) -> GhBluffDecision:
        """Executa aposta ou aumento por valor legítimo para balancear o range do agente."""
        can_raise = ActionType.RAISE in legal_actions and player_stack > to_call
        can_bet = ActionType.BET in legal_actions and player_stack > 0

        # Dimensionamento por valor: 65% a 75% do pote no pós-flop, ou all-in se stack curto
        target_fraction = 0.75 if street in (Street.TURN, Street.RIVER) else 0.65
        bet_amt = int(max(big_blind, pot_size * target_fraction))
        bet_amt = min(player_stack, bet_amt)

        if to_call == 0 and can_bet and bet_amt > 0:
            return GhBluffDecision(
                action_type=ActionType.BET,
                amount=bet_amt,
                metrics=GhBluffMetrics(
                    raw_equity=equity,
                    adjusted_equity=equity,
                    pot_odds=0.0,
                    gto_bluff_threshold=0.0,
                    random_roll=0.0,
                    blocker_score=0.0,
                    semi_bluff_outs=0,
                    is_bluff=False,
                    tactic=GhBluffTactic.VALUE_PLAY.value,
                    tactical_rationale="Aposta por valor para proteção de range e extração máxima",
                    formula_reference="Value Bet: Sizing = 0.65-0.75 * Pot",
                ),
            )

        if to_call > 0 and can_raise and equity >= 0.75:
            raise_amt = current_highest_bet + max(min_raise, int(to_call * 2.5))
            max_pos = player_current_bet + player_stack
            raise_amt = min(max_pos, raise_amt)
            if raise_amt > current_highest_bet:
                return GhBluffDecision(
                    action_type=ActionType.RAISE,
                    amount=raise_amt,
                    metrics=GhBluffMetrics(
                        raw_equity=equity,
                        adjusted_equity=equity,
                        pot_odds=calculate_pot_odds(to_call, pot_size),
                        gto_bluff_threshold=0.0,
                        random_roll=0.0,
                        blocker_score=0.0,
                        semi_bluff_outs=0,
                        is_bluff=False,
                        tactic=GhBluffTactic.VALUE_PLAY.value,
                        tactical_rationale="Aumento por valor com equidade dominante",
                        formula_reference="Value Raise: Eq >= 0.75",
                    ),
                )

        if to_call > 0 and ActionType.CALL in legal_actions:
            return GhBluffDecision(
                action_type=ActionType.CALL,
                amount=0,
                metrics=GhBluffMetrics(
                    raw_equity=equity,
                    adjusted_equity=equity,
                    pot_odds=calculate_pot_odds(to_call, pot_size),
                    gto_bluff_threshold=0.0,
                    random_roll=0.0,
                    blocker_score=0.0,
                    semi_bluff_outs=0,
                    is_bluff=False,
                    tactic=GhBluffTactic.VALUE_PLAY.value,
                    tactical_rationale="Pagamento com valor legítimo e perspectiva de showdown",
                    formula_reference="Value Call: Eq >= PotOdds",
                ),
            )

        if to_call == 0 and ActionType.CHECK in legal_actions:
            return GhBluffDecision(
                action_type=ActionType.CHECK,
                amount=0,
                metrics=GhBluffMetrics(
                    raw_equity=equity,
                    adjusted_equity=equity,
                    pot_odds=0.0,
                    gto_bluff_threshold=0.0,
                    random_roll=0.0,
                    blocker_score=0.0,
                    semi_bluff_outs=0,
                    is_bluff=False,
                    tactic=GhBluffTactic.FREE_CHECK.value,
                    tactical_rationale="Check por controle de pote com mão sólida",
                    formula_reference="Value Check",
                ),
            )

        fallback = legal_actions[0] if legal_actions else ActionType.FOLD
        return GhBluffDecision(
            action_type=fallback,
            amount=0,
            metrics=GhBluffMetrics(
                raw_equity=equity,
                adjusted_equity=equity,
                pot_odds=0.0,
                gto_bluff_threshold=0.0,
                random_roll=0.0,
                blocker_score=0.0,
                semi_bluff_outs=0,
                is_bluff=False,
                tactic=GhBluffTactic.CONTINGENCY.value,
                tactical_rationale="Ação de contingência para valor",
                formula_reference="Fallback",
            ),
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
    ) -> GhBluffDecision:
        """Avalia com rigor de Teoria dos Jogos as decisões pré-flop."""
        c1, c2 = hole_cards[0], hole_cards[1]
        is_pair = c1.rank.value == c2.rank.value
        is_suited = c1.suit == c2.suit
        high_rank = max(c1.rank.value, c2.rank.value)
        low_rank = min(c1.rank.value, c2.rank.value)
        gap = high_rank - low_rank

        can_raise = ActionType.RAISE in legal_actions and player_stack > to_call
        roll = self.rng.random()

        # 1. Mãos Premium (AA, KK, QQ, JJ, TT, AKs, AKo, AQs)
        is_premium = (
            (is_pair and high_rank >= 10)
            or (high_rank == Rank.ACE.value and low_rank >= 11)
            or (high_rank == Rank.KING.value and low_rank == Rank.QUEEN.value and is_suited)
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
                equity=0.80,
                street=Street.PREFLOP,
            )

        # 2. Polarized 3-Bet Bluffs (A5s, A4s, A3s, K9s, QTs)
        # Ases naipados fracos têm o Nut Blocker (removem AA/AK do vilão) e alta jogabilidade
        is_wheel_ace_suited = (high_rank == Rank.ACE.value and low_rank in (2, 3, 4, 5) and is_suited)
        is_suited_broadway = (high_rank in (Rank.KING.value, Rank.QUEEN.value) and low_rank >= 9 and is_suited)
        is_3bet_bluff_candidate = is_wheel_ace_suited or is_suited_broadway

        if to_call > 0 and to_call <= big_blind * 3.5 and can_raise and is_3bet_bluff_candidate:
            threshold_3bet = 0.28 * self.bluff_aggression
            if roll < threshold_3bet:
                raise_amount = current_highest_bet + max(min_raise, int(to_call * 2.8))
                max_pos = player_current_bet + player_stack
                raise_amount = min(max_pos, raise_amount)
                if raise_amount > current_highest_bet:
                    return GhBluffDecision(
                        action_type=ActionType.RAISE,
                        amount=raise_amount,
                        metrics=GhBluffMetrics(
                            raw_equity=0.45,
                            adjusted_equity=0.55,
                            pot_odds=calculate_pot_odds(to_call, pot_size),
                            gto_bluff_threshold=threshold_3bet,
                            random_roll=roll,
                            blocker_score=0.45,
                            semi_bluff_outs=0,
                            is_bluff=True,
                            tactic=GhBluffTactic.PREFLOP_3BET_BLUFF.value,
                            tactical_rationale="3-Bet de blefe polarizada explorando o Ás de bloqueador e equidade de wheel",
                            formula_reference="Polarized 3-Bet: Nut Blocker A-x suited",
                        ),
                    )

        # 3. Pote sem aumento ou cobrir Big Blind (to_call <= big_blind)
        # O agente JAMAIS folda quando o check é gratuito!
        if to_call == 0 and ActionType.CHECK in legal_actions:
            return GhBluffDecision(
                action_type=ActionType.CHECK,
                amount=0,
                metrics=GhBluffMetrics(
                    raw_equity=0.40,
                    adjusted_equity=0.40,
                    pot_odds=0.0,
                    gto_bluff_threshold=0.0,
                    random_roll=roll,
                    blocker_score=0.0,
                    semi_bluff_outs=0,
                    is_bluff=False,
                    tactic=GhBluffTactic.FREE_CHECK.value,
                    tactical_rationale="Check gratuito no Big Blind para ver o flop sem custo",
                    formula_reference="Free Check Rule",
                ),
            )

        if to_call <= big_blind and ActionType.CALL in legal_actions:
            # Completa o blind com mãos que tenham potencial
            return GhBluffDecision(
                action_type=ActionType.CALL,
                amount=0,
                metrics=GhBluffMetrics(
                    raw_equity=0.42,
                    adjusted_equity=0.42,
                    pot_odds=calculate_pot_odds(to_call, pot_size),
                    gto_bluff_threshold=0.0,
                    random_roll=roll,
                    blocker_score=0.0,
                    semi_bluff_outs=0,
                    is_bluff=False,
                    tactic=GhBluffTactic.PROBE_DEFEND.value,
                    tactical_rationale="Defesa de Big Blind por custo mínimo",
                    formula_reference="Limp/Blind Defend",
                ),
            )

        # 4. Enfrentando aumento padrão (to_call <= 3.5 BBs)
        # Defende apenas com mãos que possuem implied odds e jogabilidade pós-flop
        is_speculative = is_pair or is_suited or (gap <= 2 and low_rank >= 5)
        has_implied_odds = player_stack >= to_call * 8

        if to_call <= big_blind * 3.5 and is_speculative and has_implied_odds and ActionType.CALL in legal_actions:
            return GhBluffDecision(
                action_type=ActionType.CALL,
                amount=0,
                metrics=GhBluffMetrics(
                    raw_equity=0.46,
                    adjusted_equity=0.46,
                    pot_odds=calculate_pot_odds(to_call, pot_size),
                    gto_bluff_threshold=0.0,
                    random_roll=roll,
                    blocker_score=0.0,
                    semi_bluff_outs=0,
                    is_bluff=False,
                    tactic=GhBluffTactic.PROBE_DEFEND.value,
                    tactical_rationale="Defesa pré-flop com implied odds em conector/par",
                    formula_reference="Implied Odds Call: Stack >= 8 * to_call",
                ),
            )

        # 5. Desistência Disciplinada contra pressão ou lixo (sem sangria de fichas)
        # Corrige o vazamento do Alberto que dava call em 60% das vezes às cegas!
        if ActionType.FOLD in legal_actions:
            return GhBluffDecision(
                action_type=ActionType.FOLD,
                amount=0,
                metrics=GhBluffMetrics(
                    raw_equity=0.25,
                    adjusted_equity=0.25,
                    pot_odds=calculate_pot_odds(to_call, pot_size),
                    gto_bluff_threshold=0.0,
                    random_roll=roll,
                    blocker_score=0.0,
                    semi_bluff_outs=0,
                    is_bluff=False,
                    tactic=GhBluffTactic.DISCIPLINED_FOLD.value,
                    tactical_rationale="Desistência disciplinada contra aumento sem odds matemáticas",
                    formula_reference="Strict Fold: Equity < PotOdds & No Implied Odds",
                ),
            )

        fallback = legal_actions[0] if legal_actions else ActionType.FOLD
        return GhBluffDecision(
            action_type=fallback,
            amount=0,
            metrics=GhBluffMetrics(
                raw_equity=0.20,
                adjusted_equity=0.20,
                pot_odds=0.0,
                gto_bluff_threshold=0.0,
                random_roll=roll,
                blocker_score=0.0,
                semi_bluff_outs=0,
                is_bluff=False,
                tactic=GhBluffTactic.CONTINGENCY.value,
                tactical_rationale="Ação de contingência pré-flop",
                formula_reference="Fallback",
            ),
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
    ) -> GhBluffDecision:
        """Avalia de forma desacoplada o estado completo da mesa."""
        # 1. Roteamento Pré-Flop dedicado
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

        # 2. Avaliação de Equidade e Estrutura da Mesa
        equity_res = estimate_hand_equity(
            hole_cards=(hole_cards[0], hole_cards[1]),
            community_cards=community_cards,
            num_opponents=num_opponents,
            num_simulations=self.num_simulations,
            rng=self.rng,
        )
        raw_equity = equity_res.equity
        is_dry, is_wet, has_scare = self.analyze_board_texture(community_cards)
        blocker_score = self.evaluate_blockers(hole_cards, community_cards)
        outs = self.detect_draw_outs(hole_cards, community_cards)

        # Ajuste de Equidade por Outs no Flop e Turn
        out_mult = 0.035 if street == Street.FLOP else 0.020
        adjusted_equity = min(0.99, raw_equity + (outs * out_mult))
        pot_odds = calculate_pot_odds(to_call, pot_size)
        roll = self.rng.random()

        can_bet = ActionType.BET in legal_actions and player_stack > 0
        can_raise = ActionType.RAISE in legal_actions and player_stack > to_call
        can_call = ActionType.CALL in legal_actions
        can_check = ActionType.CHECK in legal_actions

        # 3. FILTRO 1: Jogo Consolidado (Valor Real vs. Semi-Blefe)
        # Identifica se a mão atual já é um jogo feito ou apenas um draw com outs
        all_cards = list(hole_cards) + list(community_cards)
        made_score = evaluate_hand(all_cards) if len(all_cards) >= 5 else None

        is_strong_made_hand = False
        if made_score is not None:
            if made_score.hand_rank >= HandRank.TWO_PAIR:
                is_strong_made_hand = True
            elif made_score.hand_rank == HandRank.ONE_PAIR and raw_equity >= 0.60:
                is_strong_made_hand = True

        value_threshold = 0.70 if street == Street.RIVER else 0.65
        # Se for um jogo feito sólido e equidade alta, ou se não houver draws e a equidade for alta:
        if (is_strong_made_hand and adjusted_equity >= value_threshold) or (outs < 4 and adjusted_equity >= value_threshold):
            return self._decide_value_play(
                pot_size=pot_size,
                to_call=to_call,
                player_stack=player_stack,
                player_current_bet=player_current_bet,
                current_highest_bet=current_highest_bet,
                min_raise=min_raise,
                big_blind=big_blind,
                legal_actions=legal_actions,
                equity=adjusted_equity,
                street=street,
            )

        # 4. FILTRO 2: Semi-Blefes com Retenção de Equidade (Flop e Turn com Outs >= 4)
        if street in (Street.FLOP, Street.TURN) and outs >= 4:
            # Combo Draw (12+ outs) -> Agressão máxima
            if outs >= 12:
                target_sizing = int(max(big_blind, pot_size * 0.85))
                target_sizing = min(player_stack, target_sizing)
                if to_call == 0 and can_bet and target_sizing > 0:
                    return GhBluffDecision(
                        action_type=ActionType.BET,
                        amount=target_sizing,
                        metrics=GhBluffMetrics(
                            raw_equity=raw_equity,
                            adjusted_equity=adjusted_equity,
                            pot_odds=pot_odds,
                            gto_bluff_threshold=0.85,
                            random_roll=roll,
                            blocker_score=blocker_score,
                            semi_bluff_outs=outs,
                            is_bluff=True,
                            tactic=GhBluffTactic.SEMI_BLUFF_DRAW.value,
                            tactical_rationale=f"Aposta pesada em combo draw monstro ({outs} outs) com fold equity massiva",
                            formula_reference="Combo Semi-Bluff: Outs >= 12, Sizing = 0.85 * Pot",
                        ),
                    )
                if to_call > 0 and can_raise and roll < 0.60 * self.bluff_aggression:
                    raise_amt = current_highest_bet + max(min_raise, int(to_call * 2.6))
                    max_pos = player_current_bet + player_stack
                    raise_amt = min(max_pos, raise_amt)
                    if raise_amt > current_highest_bet:
                        return GhBluffDecision(
                            action_type=ActionType.RAISE,
                            amount=raise_amt,
                            metrics=GhBluffMetrics(
                                raw_equity=raw_equity,
                                adjusted_equity=adjusted_equity,
                                pot_odds=pot_odds,
                                gto_bluff_threshold=0.60,
                                random_roll=roll,
                                blocker_score=blocker_score,
                                semi_bluff_outs=outs,
                                is_bluff=True,
                                tactic=GhBluffTactic.SEMI_BLUFF_DRAW.value,
                                tactical_rationale=f"Re-aumento de semi-blefe com combo draw ({outs} outs)",
                                formula_reference="Semi-Bluff Raise: Outs >= 12",
                            ),
                        )

            # Draw Padrão (8 a 11 outs - Flush ou Open-Ended Straight)
            if to_call == 0 and can_bet:
                semi_threshold = 0.55 * self.bluff_aggression
                if roll < semi_threshold:
                    target_bet = int(max(big_blind, pot_size * 0.65))
                    target_bet = min(player_stack, target_bet)
                    return GhBluffDecision(
                        action_type=ActionType.BET,
                        amount=target_bet,
                        metrics=GhBluffMetrics(
                            raw_equity=raw_equity,
                            adjusted_equity=adjusted_equity,
                            pot_odds=0.0,
                            gto_bluff_threshold=semi_threshold,
                            random_roll=roll,
                            blocker_score=blocker_score,
                            semi_bluff_outs=outs,
                            is_bluff=True,
                            tactic=GhBluffTactic.SEMI_BLUFF_DRAW.value,
                            tactical_rationale=f"Aposta de semi-blefe com draw forte ({outs} outs)",
                            formula_reference="Semi-Bluff Bet: 8-11 outs, Sizing = 0.65 * Pot",
                        ),
                    )

            # Enfrentando aposta com draw: Pagar se tiver Pot Odds ou Implied Odds
            draw_prob = outs * (0.04 if street == Street.FLOP else 0.02)
            if to_call > 0 and can_call and (draw_prob >= pot_odds or player_stack >= to_call * 6):
                return GhBluffDecision(
                    action_type=ActionType.CALL,
                    amount=0,
                    metrics=GhBluffMetrics(
                        raw_equity=raw_equity,
                        adjusted_equity=adjusted_equity,
                        pot_odds=pot_odds,
                        gto_bluff_threshold=0.0,
                        random_roll=roll,
                        blocker_score=blocker_score,
                        semi_bluff_outs=outs,
                        is_bluff=False,
                        tactic=GhBluffTactic.PROBE_DEFEND.value,
                        tactical_rationale=f"Call matemático com draw ({outs} outs) respaldado por pot/implied odds",
                        formula_reference="Draw Call: DrawProb >= PotOdds || Implied Odds",
                    ),
                )

        # 5. FILTRO 3: Blefes no River Baseados em Bloqueadores e Teorema de Nash
        if street == Street.RIVER:
            # Em potes multiway (3+ jogadores no River), blefar puro é suicídio estatístico
            if num_opponents >= 2:
                if to_call == 0 and can_check:
                    return GhBluffDecision(
                        action_type=ActionType.CHECK,
                        amount=0,
                        metrics=GhBluffMetrics(
                            raw_equity=raw_equity,
                            adjusted_equity=adjusted_equity,
                            pot_odds=0.0,
                            gto_bluff_threshold=0.0,
                            random_roll=roll,
                            blocker_score=blocker_score,
                            semi_bluff_outs=0,
                            is_bluff=False,
                            tactic=GhBluffTactic.FREE_CHECK.value,
                            tactical_rationale="Check em river multiway: fold equity insuficiente para blefe puro",
                            formula_reference="Multiway River Rule: No pure bluffs with 3+ players",
                        ),
                    )
                if to_call > 0 and ActionType.FOLD in legal_actions:
                    return GhBluffDecision(
                        action_type=ActionType.FOLD,
                        amount=0,
                        metrics=GhBluffMetrics(
                            raw_equity=raw_equity,
                            adjusted_equity=adjusted_equity,
                            pot_odds=pot_odds,
                            gto_bluff_threshold=0.0,
                            random_roll=roll,
                            blocker_score=blocker_score,
                            semi_bluff_outs=0,
                            is_bluff=False,
                            tactic=GhBluffTactic.DISCIPLINED_FOLD.value,
                            tactical_rationale="Fold disciplinado em river multiway contra aposta",
                            formula_reference="Multiway Fold",
                        ),
                    )

            # Heads-Up no River com mão fraca (sem showdown value): Janela de Blefe GTO
            if raw_equity < 0.40 and blocker_score >= self.min_blocker_threshold:
                # Sizing polarizado: 75% a 100% do pote
                target_sizing = int(max(big_blind, pot_size * 0.85))
                target_sizing = min(player_stack, target_sizing)

                # Razão de Indiferença GTO: B / (P + 2B)
                gto_ratio = self.calculate_gto_bluff_ratio(target_sizing, pot_size)
                # Pondera a probabilidade pelo blocker score
                bluff_threshold = gto_ratio * (blocker_score / 0.40) * self.gto_balance_factor

                if to_call == 0 and can_bet and target_sizing > 0 and roll < bluff_threshold:
                    tactic_name = (
                        GhBluffTactic.NUT_BLOCKER_BLUFF.value
                        if blocker_score >= 0.45
                        else GhBluffTactic.POLARIZED_RIVER_BLUFF.value
                    )
                    return GhBluffDecision(
                        action_type=ActionType.BET,
                        amount=target_sizing,
                        metrics=GhBluffMetrics(
                            raw_equity=raw_equity,
                            adjusted_equity=adjusted_equity,
                            pot_odds=0.0,
                            gto_bluff_threshold=bluff_threshold,
                            random_roll=roll,
                            blocker_score=blocker_score,
                            semi_bluff_outs=0,
                            is_bluff=True,
                            tactic=tactic_name,
                            tactical_rationale=(
                                f"Blefe polarizado no River ativado por bloqueador "
                                f"(Blocker={blocker_score:.2f}) sob frequência de Nash ({bluff_threshold:.2f})"
                            ),
                            formula_reference="Nash Indifference: Ratio = B / (P + 2B) * BlockerWeight",
                        ),
                    )

            # River Showdown Value (40% a 70% de equidade): Mão média que vence blefes
            if raw_equity >= 0.40 and raw_equity < value_threshold:
                if to_call == 0 and can_check:
                    return GhBluffDecision(
                        action_type=ActionType.CHECK,
                        amount=0,
                        metrics=GhBluffMetrics(
                            raw_equity=raw_equity,
                            adjusted_equity=adjusted_equity,
                            pot_odds=0.0,
                            gto_bluff_threshold=0.0,
                            random_roll=roll,
                            blocker_score=blocker_score,
                            semi_bluff_outs=0,
                            is_bluff=False,
                            tactic=GhBluffTactic.FREE_CHECK.value,
                            tactical_rationale="Check para showdown value com mão média (não transforma valor em blefe)",
                            formula_reference="Showdown Value Preservation",
                        ),
                    )
                if to_call > 0 and can_call and raw_equity >= pot_odds + 0.05:
                    return GhBluffDecision(
                        action_type=ActionType.CALL,
                        amount=0,
                        metrics=GhBluffMetrics(
                            raw_equity=raw_equity,
                            adjusted_equity=adjusted_equity,
                            pot_odds=pot_odds,
                            gto_bluff_threshold=0.0,
                            random_roll=roll,
                            blocker_score=blocker_score,
                            semi_bluff_outs=0,
                            is_bluff=False,
                            tactic=GhBluffTactic.PROBE_DEFEND.value,
                            tactical_rationale="Call de Bluff-Catcher no river amparado por equidade > pot odds",
                            formula_reference="Bluff Catcher Call: Equity >= PotOdds + 0.05",
                        ),
                    )

        # 6. FILTRO 4: C-Bet Steal em Pote Órfão (Flop e Turn)
        if to_call == 0 and can_bet and is_dry and num_opponents == 1 and street in (Street.FLOP, Street.TURN):
            cbet_threshold = 0.45 * self.bluff_aggression
            if roll < cbet_threshold:
                target_bet = int(max(big_blind, pot_size * 0.45))
                target_bet = min(player_stack, target_bet)
                return GhBluffDecision(
                    action_type=ActionType.BET,
                    amount=target_bet,
                    metrics=GhBluffMetrics(
                        raw_equity=raw_equity,
                        adjusted_equity=adjusted_equity,
                        pot_odds=0.0,
                        gto_bluff_threshold=cbet_threshold,
                        random_roll=roll,
                        blocker_score=blocker_score,
                        semi_bluff_outs=outs,
                        is_bluff=True,
                        tactic=GhBluffTactic.CBET_STEAL.value,
                        tactical_rationale="C-Bet de roubo explorando bordo seco e fraqueza do oponente",
                        formula_reference="Dry Board C-Bet Steal: Sizing = 0.45 * Pot",
                    ),
                )

        # 7. FILTRO 5: Check Gratuito Obrigatório
        # Nunca dá fold quando to_call == 0!
        if to_call == 0 and can_check:
            return GhBluffDecision(
                action_type=ActionType.CHECK,
                amount=0,
                metrics=GhBluffMetrics(
                    raw_equity=raw_equity,
                    adjusted_equity=adjusted_equity,
                    pot_odds=0.0,
                    gto_bluff_threshold=0.0,
                    random_roll=roll,
                    blocker_score=blocker_score,
                    semi_bluff_outs=outs,
                    is_bluff=False,
                    tactic=GhBluffTactic.FREE_CHECK.value,
                    tactical_rationale="Check gratuito para controle de pote",
                    formula_reference="Free Check Rule",
                ),
            )

        # 8. FILTRO 6: Desistência Disciplinada contra Aposta (Anti-Calling Station)
        if ActionType.FOLD in legal_actions:
            return GhBluffDecision(
                action_type=ActionType.FOLD,
                amount=0,
                metrics=GhBluffMetrics(
                    raw_equity=raw_equity,
                    adjusted_equity=adjusted_equity,
                    pot_odds=pot_odds,
                    gto_bluff_threshold=0.0,
                    random_roll=roll,
                    blocker_score=blocker_score,
                    semi_bluff_outs=outs,
                    is_bluff=False,
                    tactic=GhBluffTactic.DISCIPLINED_FOLD.value,
                    tactical_rationale="Desistência disciplinada: mão sem odds suficientes e sem blockers para blefe",
                    formula_reference="Disciplined Fold: Equity < PotOdds",
                ),
            )

        fallback = legal_actions[0] if legal_actions else ActionType.FOLD
        return GhBluffDecision(
            action_type=fallback,
            amount=0,
            metrics=GhBluffMetrics(
                raw_equity=raw_equity,
                adjusted_equity=adjusted_equity,
                pot_odds=pot_odds,
                gto_bluff_threshold=0.0,
                random_roll=roll,
                blocker_score=blocker_score,
                semi_bluff_outs=outs,
                is_bluff=False,
                tactic=GhBluffTactic.CONTINGENCY.value,
                tactical_rationale="Ação de contingência pós-flop",
                formula_reference="Fallback",
            ),
        )

    def _track_decision_telemetry(self, decision: GhBluffDecision) -> None:
        """Atualiza os contadores estatísticos do agente para relatórios e benchmarks."""
        self.last_decision = decision
        if decision.action_type in (ActionType.BET, ActionType.RAISE):
            self.bets_and_raises += 1
            if decision.metrics.is_bluff:
                self.bluffs_attempted += 1
                if decision.metrics.tactic in (
                    GhBluffTactic.POLARIZED_RIVER_BLUFF.value,
                    GhBluffTactic.NUT_BLOCKER_BLUFF.value,
                ):
                    self.pure_bluffs += 1
                elif decision.metrics.tactic == GhBluffTactic.SEMI_BLUFF_DRAW.value:
                    self.semi_bluffs += 1
                elif decision.metrics.tactic == GhBluffTactic.CBET_STEAL.value:
                    self.cbet_steals += 1
            else:
                self.value_bets += 1
        elif decision.action_type == ActionType.CALL:
            self.calls += 1
        elif decision.action_type == ActionType.CHECK:
            self.checks += 1
        elif decision.action_type == ActionType.FOLD:
            self.folds += 1

    def decide_action(self, table: Table) -> Action:
        """Executa a tomada de decisão conectado ao estado de mesa de poker."""
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
