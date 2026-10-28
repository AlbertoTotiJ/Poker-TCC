"""Agente de Poker baseado estritamente na teoria das probabilidades e EV.

Este módulo implementa o MathematicalAgent conforme especificado no
documento de arquitetura dos agentes (read.me agents.md). Ele avalia
equidade da mão, probabilidades de draws (out rules), pot odds e
valor esperado (Expected Value - EV) sem vieses psicológicos.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import random
import sys
from typing import Any, Dict, Optional, Sequence, Tuple

# Garante resolucao de 'src' ao executar o script diretamente
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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


@dataclass(frozen=True)
class MathematicalDecision:
    """Estrutura analítica contendo os fundamentos matemáticos da decisão."""

    action_type: ActionType
    amount: int
    equity: float
    pot_odds: float
    expected_value: float
    outs: int
    reason: str


@dataclass
class MathematicalParameters:
    """Hiperparâmetros calibráveis que regem as decisões probabilísticas."""

    raise_equity_threshold: float = 0.65
    call_ev_margin: float = 0.04
    draw_weight: float = 1.0
    bet_sizing_factor: float = 0.50
    num_simulations: int = 200

    def to_dict(self) -> Dict[str, Any]:
        """Converte hiperparâmetros em dicionário serializável."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MathematicalParameters":
        """Instancia hiperparâmetros a partir de dicionário."""
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered: Dict[str, Any] = {}
        for k, v in data.items():
            if k in valid_keys:
                filtered[k] = int(v) if k == "num_simulations" else float(v)
        return cls(**filtered)


class MathematicalAgent(BaseAgent):
    """Agente autônomo estritamente probabilístico e analítico para Texas Hold'em.

    Toma decisões determinísticas fundamentadas em equidade de Monte Carlo,
    pot odds, valor esperado (EV) e outs de evolução no Flop/Turn.
    """

    def __init__(
        self,
        player_id: str,
        name: str = "Agente Matemático",
        raise_equity_threshold: float = 0.65,
        call_ev_margin: float = 0.04,
        draw_weight: float = 1.0,
        bet_sizing_factor: float = 0.50,
        num_simulations: int = 200,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)
        self.params = MathematicalParameters(
            raise_equity_threshold=max(0.40, min(0.90, raise_equity_threshold)),
            call_ev_margin=max(-0.10, min(0.20, call_ev_margin)),
            draw_weight=max(0.0, min(2.5, draw_weight)),
            bet_sizing_factor=max(0.20, min(1.5, bet_sizing_factor)),
            num_simulations=max(20, min(1000, num_simulations)),
        )
        self.rng: random.Random = rng if rng is not None else random.Random()

        # Telemetria acumulada de partidas
        self.hands_played: int = 0
        self.vpip_actions: int = 0
        self.pfr_actions: int = 0
        self.bets_and_raises: int = 0
        self.calls: int = 0
        self.folds: int = 0
        self.last_decision: Optional[MathematicalDecision] = None

    @property
    def raise_equity_threshold(self) -> float:
        return self.params.raise_equity_threshold

    @raise_equity_threshold.setter
    def raise_equity_threshold(self, value: float) -> None:
        self.params.raise_equity_threshold = max(0.40, min(0.90, float(value)))

    @property
    def call_ev_margin(self) -> float:
        return self.params.call_ev_margin

    @call_ev_margin.setter
    def call_ev_margin(self, value: float) -> None:
        self.params.call_ev_margin = max(-0.10, min(0.20, float(value)))

    @property
    def draw_weight(self) -> float:
        return self.params.draw_weight

    @draw_weight.setter
    def draw_weight(self, value: float) -> None:
        self.params.draw_weight = max(0.0, min(2.5, float(value)))

    @property
    def bet_sizing_factor(self) -> float:
        return self.params.bet_sizing_factor

    @bet_sizing_factor.setter
    def bet_sizing_factor(self, value: float) -> None:
        self.params.bet_sizing_factor = max(0.20, min(1.5, float(value)))

    @property
    def num_simulations(self) -> int:
        return self.params.num_simulations

    @num_simulations.setter
    def num_simulations(self, value: int) -> None:
        self.params.num_simulations = max(20, min(1000, int(value)))

    def export_parameters(self) -> Dict[str, Any]:
        """Exporta os hiperparâmetros atuais para calibração/treino."""
        return self.params.to_dict()

    def load_parameters(self, params: Dict[str, Any]) -> None:
        """Aplica novos hiperparâmetros resultantes de rotinas de treino."""
        self.params = MathematicalParameters.from_dict(params)

    def save_parameters(self, filepath: str | Path) -> None:
        """Persiste os hiperparâmetros em arquivo JSON."""
        target = Path(filepath)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.export_parameters(), f, indent=2)

    def load_parameters_file(self, filepath: str | Path) -> None:
        """Carrega hiperparâmetros pré-treinados de arquivo JSON."""
        target = Path(filepath)
        if not target.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {target}")
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load_parameters(data)

    def decide_action(self, table: Table) -> Action:
        """Determina a ação ótima na mesa com base em probabilidade e EV."""
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

        self._track_decision_telemetry(decision.action_type, table.street)
        self.last_decision = decision
        return Action(
            player_id=self.player_id,
            action_type=decision.action_type,
            amount=decision.amount,
        )

    def evaluate_state(
        self,
        hole_cards: Tuple[Card, Card],
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
    ) -> MathematicalDecision:
        """Calcula equidade, EV e retorna a decisão matemática estruturada."""
        is_preflop = len(community_cards) == 0 or street == Street.PREFLOP
        preflop_score = (
            self._evaluate_preflop_combinatorics(hole_cards)
            if is_preflop
            else 0.0
        )

        equity, outs = self.calculate_effective_equity(
            hole_cards=hole_cards,
            community_cards=community_cards,
            num_opponents=num_opponents,
        )

        fair_share = 1.0 / max(2, num_opponents + 1)

        if is_preflop and to_call > 0:
            # Implied odds aplicáveis a apostas moderadas (<= 3 * big_blind)
            if to_call <= 3 * big_blind:
                if preflop_score >= 0.50:
                    implied_mult = 2.5
                elif preflop_score >= 0.35:
                    implied_mult = 1.5
                else:
                    implied_mult = 0.0

                remaining_stack = max(0, player_stack - to_call)
                implied_pot = min(
                    remaining_stack,
                    int(big_blind * num_opponents * implied_mult),
                )
                contested_pot = max(
                    pot_size,
                    int(big_blind * (num_opponents + 1) * 0.75),
                )
                effective_pot = contested_pot + implied_pot
            else:
                # Contra aumentos pesados (> 3 BB), odds implícitas são nulas
                effective_pot = pot_size

            pot_odds = (
                to_call / (effective_pot + to_call)
                if (effective_pot + to_call) > 0
                else 0.0
            )
            expected_value = (equity * (effective_pot + to_call)) - to_call
        else:
            pot_odds = calculate_pot_odds(to_call=to_call, pot_size=pot_size)
            expected_value = (
                (equity * (pot_size + to_call)) - to_call if to_call > 0 else 0.0
            )

        all_cards = list(hole_cards) + list(community_cards)
        score = evaluate_hand(all_cards) if len(all_cards) >= 5 else None
        hand_rank_val = score.hand_rank.value if score else 1

        if to_call == 0:
            return self._decide_zero_cost(
                equity=equity,
                outs=outs,
                pot_size=pot_size,
                player_stack=player_stack,
                big_blind=big_blind,
                min_raise=min_raise,
                legal_actions=legal_actions,
                street=street,
                num_opponents=num_opponents,
                hand_rank_val=hand_rank_val,
            )

        return self._decide_facing_cost(
            equity=equity,
            pot_odds=pot_odds,
            expected_value=expected_value,
            outs=outs,
            pot_size=pot_size,
            to_call=to_call,
            player_stack=player_stack,
            player_current_bet=player_current_bet,
            current_highest_bet=current_highest_bet,
            min_raise=min_raise,
            legal_actions=legal_actions,
            is_preflop=is_preflop,
            preflop_score=preflop_score,
            fair_share=fair_share,
            big_blind=big_blind,
            street=street,
            num_opponents=num_opponents,
            hand_rank_val=hand_rank_val,
        )

    def calculate_effective_equity(
        self,
        hole_cards: Tuple[Card, Card],
        community_cards: Sequence[Card],
        num_opponents: int = 1,
    ) -> Tuple[float, int]:
        """Calcula a equidade ajustada incluindo Monte Carlo e outs de draws."""
        capped_opponents = min(3, max(1, num_opponents))
        sims = min(50, self.num_simulations)

        if not community_cards:
            preflop_score = self._evaluate_preflop_combinatorics(hole_cards)
            eq_res = estimate_hand_equity(
                hole_cards=hole_cards,
                community_cards=(),
                num_opponents=capped_opponents,
                num_simulations=sims,
                rng=self.rng,
            )
            blended_equity = (preflop_score * 0.40) + (eq_res.equity * 0.60)
            return blended_equity, 0

        eq_res = estimate_hand_equity(
            hole_cards=hole_cards,
            community_cards=community_cards,
            num_opponents=capped_opponents,
            num_simulations=sims,
            rng=self.rng,
        )

        outs = self._calculate_draw_outs(hole_cards, community_cards)

        # Regra de 4 e 2 para Texas Hold'em
        draw_prob = 0.0
        if len(community_cards) == 3:  # Flop (2 cartas por vir)
            draw_prob = min(0.65, outs * 0.04)
        elif len(community_cards) == 4:  # Turn (1 carta por vir)
            draw_prob = min(0.40, outs * 0.02)

        adjusted_equity = max(eq_res.equity, draw_prob * self.draw_weight)
        return adjusted_equity, outs

    def _decide_zero_cost(
        self,
        equity: float,
        outs: int,
        pot_size: int,
        player_stack: int,
        big_blind: int,
        min_raise: int,
        legal_actions: Sequence[ActionType],
        street: Optional[Street] = None,
        num_opponents: int = 1,
        hand_rank_val: int = 1,
    ) -> MathematicalDecision:
        """Determina se abre aposta por valor ou passa a vez gratuitamente."""
        # Se estiver no River em pote multiway (>= 2 oponentes):
        # Check de pot control para ver showdown
        if street == Street.RIVER and num_opponents >= 2:
            return MathematicalDecision(
                action_type=ActionType.CHECK,
                amount=0,
                equity=equity,
                pot_odds=0.0,
                expected_value=0.0,
                outs=outs,
                reason="Check por controle de pote multiway no River para showdown",
            )

        # Em multiway no Flop/Turn: só aposta com 2 pares ou melhor
        if (
            num_opponents >= 2
            and street in (Street.FLOP, Street.TURN)
            and hand_rank_val < 3
        ):
            return MathematicalDecision(
                action_type=ActionType.CHECK,
                amount=0,
                equity=equity,
                pot_odds=0.0,
                expected_value=0.0,
                outs=outs,
                reason="Check por controle de pote multiway no pós-flop",
            )

        if ActionType.BET in legal_actions and player_stack > 0:
            if equity >= self.raise_equity_threshold or hand_rank_val >= 3:
                target_fraction = min(
                    0.60, max(0.30, equity * self.bet_sizing_factor)
                )
                desired_bet = max(
                    big_blind, min_raise, int(pot_size * target_fraction)
                )
                bet_amount = min(player_stack, max(min_raise, desired_bet))
                return MathematicalDecision(
                    action_type=ActionType.BET,
                    amount=bet_amount,
                    equity=equity,
                    pot_odds=0.0,
                    expected_value=equity * pot_size,
                    outs=outs,
                    reason=f"Value bet com equidade de {equity:.1%}",
                )

        return MathematicalDecision(
            action_type=ActionType.CHECK,
            amount=0,
            equity=equity,
            pot_odds=0.0,
            expected_value=0.0,
            outs=outs,
            reason="Check gratuito preservando EV",
        )

    def _decide_facing_cost(
        self,
        equity: float,
        pot_odds: float,
        expected_value: float,
        outs: int,
        pot_size: int,
        to_call: int,
        player_stack: int,
        player_current_bet: int,
        current_highest_bet: int,
        min_raise: int,
        legal_actions: Sequence[ActionType],
        is_preflop: bool = False,
        preflop_score: float = 0.0,
        fair_share: float = 0.5,
        big_blind: int = 20,
        street: Optional[Street] = None,
        num_opponents: int = 1,
        hand_rank_val: int = 1,
    ) -> MathematicalDecision:
        """Determina se aumenta por valor puro, paga por EV positivo ou desiste."""
        if is_preflop:
            # No pré-flop:
            # 1. Com lixo puro (score < 0.30) diante de custo, é sempre -EV Fold
            if preflop_score < 0.30:
                is_profitable = False
            # 1b. Custo baixo (<= 1 BB) com mão jogável é sempre +EV Call
            elif to_call <= big_blind and preflop_score >= 0.30:
                is_profitable = True
            # 1c. Custo moderado (<= 2.5 BBs) com cartas boas/especulativas
            elif to_call <= int(big_blind * 2.5) and preflop_score >= 0.40:
                is_profitable = True
            # 2. Contra aposta pesada (> 3 BB), exige combinatória forte E equidade
            elif to_call > 3 * big_blind:
                is_profitable = (
                    preflop_score >= 0.70
                    and equity >= (pot_odds - self.call_ev_margin)
                )
            else:
                is_profitable = equity >= (pot_odds - self.call_ev_margin)

            # Vantagem dominante pré-flop: cartas premium ou edge sobre fair share
            strong_advantage = (
                preflop_score >= 0.75
                or (equity >= max(0.48, fair_share * 1.8))
                or (equity >= self.raise_equity_threshold + 0.08)
            )
        else:
            # Bluff Catcher e Tenacidade de Showdown no Pós-Flop
            has_pair = hand_rank_val >= 2
            is_mod_bet = to_call <= max(big_blind * 3, int(pot_size * 0.45))

            if has_pair and to_call <= max(big_blind * 5, int(pot_size * 0.65)):
                is_profitable = True
            elif is_mod_bet and (outs >= 4 or street == Street.RIVER):
                is_profitable = True
            else:
                bluff_catch_bonus = 0.12 if is_mod_bet else 0.05
                effective_margin = self.call_ev_margin + bluff_catch_bonus
                is_profitable = equity >= (pot_odds - effective_margin)

            strong_advantage = (
                equity >= (self.raise_equity_threshold + 0.15)
                and has_pair
                and num_opponents == 1
            )

        # Aumento por valor com vantagem significativa de equidade
        if (
            ActionType.RAISE in legal_actions
            and strong_advantage
            and player_stack > to_call
        ):
            min_required = current_highest_bet + min_raise
            if is_preflop:
                target_addition = max(
                    min_raise,
                    int(big_blind * 1.5),
                    int(pot_size * equity * self.bet_sizing_factor),
                )
            else:
                target_addition = max(
                    min_raise,
                    int(pot_size * equity * self.bet_sizing_factor),
                )

            total_target = current_highest_bet + target_addition
            raise_amount = min(
                player_current_bet + player_stack, max(min_required, total_target)
            )

            if raise_amount >= min_required:
                return MathematicalDecision(
                    action_type=ActionType.RAISE,
                    amount=raise_amount,
                    equity=equity,
                    pot_odds=pot_odds,
                    expected_value=expected_value,
                    outs=outs,
                    reason=f"Raise por valor com equidade dominante ({equity:.1%})",
                )

        if ActionType.CALL in legal_actions and is_profitable:
            call_amount = min(player_stack, to_call)
            return MathematicalDecision(
                action_type=ActionType.CALL,
                amount=call_amount,
                equity=equity,
                pot_odds=pot_odds,
                expected_value=expected_value,
                outs=outs,
                reason=f"+EV Call: Equidade {equity:.1%} >= Pot Odds {pot_odds:.1%}",
            )

        if ActionType.CHECK in legal_actions:
            return MathematicalDecision(
                action_type=ActionType.CHECK,
                amount=0,
                equity=equity,
                pot_odds=pot_odds,
                expected_value=expected_value,
                outs=outs,
                reason="Check legal viável",
            )

        return MathematicalDecision(
            action_type=ActionType.FOLD,
            amount=0,
            equity=equity,
            pot_odds=pot_odds,
            expected_value=expected_value,
            outs=outs,
            reason=f"-EV Fold: Equidade {equity:.1%} < Pot Odds {pot_odds:.1%}",
        )

    def _calculate_draw_outs(
        self, hole_cards: Tuple[Card, Card], community_cards: Sequence[Card]
    ) -> int:
        """Calcula a quantidade estimada de outs para evolução de mãos especulativas."""
        combined = list(hole_cards) + list(community_cards)
        outs = 0

        if has_flush_draw(combined):
            outs += 9

        if has_straight_draw(combined):
            outs += 8

        if has_overcards(hole_cards, community_cards):
            outs += 6

        return outs

    def _evaluate_preflop_combinatorics(self, hole_cards: Tuple[Card, Card]) -> float:
        """Calcula força pré-flop baseada em combinatória de pares e conectores."""
        c1, c2 = hole_cards
        high_r = max(c1.rank.value, c2.rank.value)
        low_r = min(c1.rank.value, c2.rank.value)
        is_pair = c1.rank == c2.rank
        is_suited = c1.suit == c2.suit
        gap = high_r - low_r

        if is_pair:
            return 0.52 + ((high_r / 14.0) * 0.40)

        base_score = ((high_r + (low_r * 0.60)) / 22.4) * 0.70
        if is_suited:
            base_score += 0.06
        if gap == 1:
            base_score += 0.05
        elif gap == 2:
            base_score += 0.03

        # Bônus para conectores do mesmo naipe (suited connectors)
        if is_suited and gap <= 2:
            base_score += 0.04

        if high_r == Rank.ACE.value:
            base_score += 0.06
        elif high_r == Rank.KING.value:
            base_score += 0.03

        return min(0.95, max(0.15, base_score))

    def _track_decision_telemetry(
        self, action_type: ActionType, street: Street
    ) -> None:
        """Atualiza contadores para métricas VPIP, PFR e Aggression Factor."""
        if street == Street.PREFLOP:
            if action_type in (
                ActionType.CALL,
                ActionType.BET,
                ActionType.RAISE,
                ActionType.ALL_IN,
            ):
                self.vpip_actions += 1
            if action_type in (ActionType.RAISE, ActionType.BET):
                self.pfr_actions += 1

        if action_type in (ActionType.BET, ActionType.RAISE):
            self.bets_and_raises += 1
        elif action_type == ActionType.CALL:
            self.calls += 1
        elif action_type == ActionType.FOLD:
            self.folds += 1

    @property
    def aggression_factor(self) -> float:
        """Calcula o Fator de Agressão clássico (AF = (Bets + Raises) / Calls)."""
        if self.calls == 0:
            return float(self.bets_and_raises)
        return round(self.bets_and_raises / self.calls, 2)


def run_isolated_demo() -> None:
    """Demonstração prática e isolada do Agente Matemático em cenários canônicos."""
    agent = MathematicalAgent(player_id="bot_math", name="Agente Matemático")
    print("=" * 75)
    print("DEMONSTRAÇÃO DE EXECUÇÃO ISOLADA: AGENTE MATEMÁTICO (EV & PROBABILIDADE)")
    print("=" * 75)

    c1 = "Cenário 1: Par de Ases Pré-flop (AA) contra bet de 20 em pote de 40"
    c2 = "Cenário 2: Nut Flush Draw no Flop (Kh Qh em Ah 8h 2c) bet 15 em pote 80"
    c3 = "Cenário 3: Mão fraca (7d 2c) no River contra bet de 100 em pote de 120"
    c4 = "Cenário 4: Trinca no Flop (Jh Jd em Jc 7s 2h) com check gratuito"

    scenarios = [
        (
            c1,
            (Card.from_str("As"), Card.from_str("Ah")),
            (),
            40,
            20,
            1000,
            1,
            [ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
        ),
        (
            c2,
            (Card.from_str("Kh"), Card.from_str("Qh")),
            [Card.from_str("Ah"), Card.from_str("8h"), Card.from_str("2c")],
            80,
            15,
            1000,
            1,
            [ActionType.FOLD, ActionType.CALL, ActionType.RAISE],
        ),
        (
            c3,
            (Card.from_str("7d"), Card.from_str("2c")),
            [
                Card.from_str("Kd"),
                Card.from_str("Js"),
                Card.from_str("4h"),
                Card.from_str("9c"),
                Card.from_str("3s"),
            ],
            120,
            100,
            1000,
            1,
            [ActionType.FOLD, ActionType.CALL],
        ),
        (
            c4,
            (Card.from_str("Jh"), Card.from_str("Jd")),
            [Card.from_str("Jc"), Card.from_str("7s"), Card.from_str("2h")],
            60,
            0,
            1000,
            2,
            [ActionType.CHECK, ActionType.BET],
        ),
    ]

    for title, hole, board, pot, to_call, stack, opps, legals in scenarios:
        board_str = " ".join(str(c) for c in board) if board else "(Pré-flop)"
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
        )

        amount_info = f" (Valor: {decision.amount})" if decision.amount > 0 else ""
        print(f"  -> Decisão: {decision.action_type.name}{amount_info}")
        print(
            f"  -> Equidade: {decision.equity:.1%} | "
            f"Pot Odds: {decision.pot_odds:.1%} | Outs: {decision.outs}"
        )
        print(
            f"  -> EV Esperado: {decision.expected_value:+.2f} fichas | "
            f"Justificativa: {decision.reason}"
        )


if __name__ == "__main__":
    run_isolated_demo()
