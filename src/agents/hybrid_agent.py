"""Agente Híbrido integrando rigor probabilístico e engano comportamental.

Este módulo implementa o HybridAgent, unificando a base matemática
(Monte Carlo, pot odds e EV) com adaptações táticas dinâmicas
(blefes oportunos, semi-blefes em draws e armadilhas de slow-play).
O agente é totalmente treinável pelo motor evolutivo (AdaptiveTrainer)
e capaz de herdar e fundir parâmetros pré-treinados do Agente Matemático
e do Agente Blefador.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import random
import sys
from typing import Any, Dict, Optional, Sequence

# Garante resolução de 'src' ao executar o script diretamente
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.agents.base import BaseAgent  # noqa: E402
from src.engine.deck import Card  # noqa: E402
from src.engine.equity import (  # noqa: E402
    calculate_pot_odds,
    estimate_hand_equity,
    has_flush_draw,
    has_straight_draw,
)
from src.engine.table import Action, ActionType, Street, Table  # noqa: E402


@dataclass(frozen=True)
class HybridDecision:
    """Estrutura representativa da decisão integrada do Agente Híbrido."""

    action_type: ActionType
    amount: int
    mode: str
    equity: float
    pot_odds: float
    is_deceptive: bool
    reason: str
    expected_value: float = 0.0
    outs: int = 0


@dataclass
class HybridParameters:
    """Hiperparâmetros calibráveis que regem as decisões táticas e matemáticas do Híbrido."""

    math_weight: float = 0.50            # Peso atribuído ao rigor matemático vs oportunismo de blefe (0.10 a 0.90)
    raise_equity_threshold: float = 0.60 # Equidade mínima para apostar ou aumentar por valor (0.45 a 0.85)
    call_ev_margin: float = 0.02         # Margem de tolerância de EV para aceitar calls (-0.05 a 0.15)
    bluff_frequency: float = 0.25        # Frequência base de blefe oportuno em potes abandonados (0.05 a 0.60)
    semi_bluff_frequency: float = 0.50   # Frequência de semi-blefe agressivo com draws (0.10 a 0.85)
    fold_equity_threshold: float = 0.35  # Limiar estimado de fold equity para autorizar blefes (0.15 a 0.80)
    slowplay_prob: float = 0.20          # Probabilidade de armadilha (slow-play) com mãos monstro (0.05 a 0.50)
    bet_sizing_factor: float = 0.55      # Fração do pote utilizada para dimensionar apostas (0.25 a 1.20)
    num_simulations: int = 150           # Quantidade de iterações Monte Carlo para equidade (50 a 300)

    def to_dict(self) -> Dict[str, Any]:
        """Converte hiperparâmetros em dicionário serializável."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HybridParameters":
        """Instancia hiperparâmetros a partir de dicionário com validação de chaves."""
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered: Dict[str, Any] = {}
        for k, v in data.items():
            if k in valid_keys:
                filtered[k] = int(v) if k == "num_simulations" else float(v)
        return cls(**filtered)

    @classmethod
    def from_parents(
        cls,
        math_params: Optional[Dict[str, Any]] = None,
        bluffer_params: Optional[Dict[str, Any]] = None,
        math_weight: float = 0.50,
    ) -> "HybridParameters":
        """Funde parâmetros calibrados do Agente Matemático e do Blefador."""
        hybrid = cls(math_weight=max(0.10, min(0.90, math_weight)))
        if math_params:
            if "raise_equity_threshold" in math_params:
                hybrid.raise_equity_threshold = float(math_params["raise_equity_threshold"])
            elif "base_threshold" in math_params:
                hybrid.raise_equity_threshold = float(math_params["base_threshold"])
            if "call_ev_margin" in math_params:
                hybrid.call_ev_margin = float(math_params["call_ev_margin"])
            if "num_simulations" in math_params:
                hybrid.num_simulations = int(math_params["num_simulations"])

        if bluffer_params:
            if "bluff_frequency" in bluffer_params:
                hybrid.bluff_frequency = float(bluffer_params["bluff_frequency"])
            if "semi_bluff_frequency" in bluffer_params:
                hybrid.semi_bluff_frequency = float(bluffer_params["semi_bluff_frequency"])
            if "fold_equity_threshold" in bluffer_params:
                hybrid.fold_equity_threshold = float(bluffer_params["fold_equity_threshold"])
            if "bet_sizing_factor" in bluffer_params:
                hybrid.bet_sizing_factor = float(bluffer_params["bet_sizing_factor"])

        return hybrid


class HybridAgent(BaseAgent):
    """Agente que mescla o modelo matemático rigoroso com heurísticas táticas de blefe.

    Opera com piso probabilístico estrito para evitar jogadas de EV negativo,
    mas introduz variabilidade estratégica através de semi-blefes,
    blefes em potes fracos e desaceleração (*slow-play*) com mãos dominantes.
    É totalmente compatível com o sistema de treinamento evolutivo.
    """

    def __init__(
        self,
        player_id: str,
        name: str = "Agente Híbrido",
        math_weight: float = 0.50,
        raise_equity_threshold: float = 0.60,
        call_ev_margin: float = 0.02,
        bluff_frequency: float = 0.25,
        semi_bluff_frequency: float = 0.50,
        fold_equity_threshold: float = 0.35,
        slowplay_prob: float = 0.20,
        bet_sizing_factor: float = 0.55,
        num_simulations: int = 150,
        # Argumentos legados para retrocompatibilidade
        math_threshold: Optional[float] = None,
        bluff_prob: Optional[float] = None,
        rng: Optional[random.Random] = None,
    ) -> None:
        super().__init__(player_id=player_id, name=name)

        eff_equity_th = (
            math_threshold if math_threshold is not None else raise_equity_threshold
        )
        eff_bluff_freq = (
            bluff_prob if bluff_prob is not None else bluff_frequency
        )

        self.params = HybridParameters(
            math_weight=max(0.10, min(0.90, math_weight)),
            raise_equity_threshold=max(0.40, min(0.90, eff_equity_th)),
            call_ev_margin=max(-0.10, min(0.20, call_ev_margin)),
            bluff_frequency=max(0.05, min(0.65, eff_bluff_freq)),
            semi_bluff_frequency=max(0.10, min(0.90, semi_bluff_frequency)),
            fold_equity_threshold=max(0.15, min(0.85, fold_equity_threshold)),
            slowplay_prob=max(0.05, min(0.50, slowplay_prob)),
            bet_sizing_factor=max(0.20, min(1.30, bet_sizing_factor)),
            num_simulations=max(30, min(500, num_simulations)),
        )

        self.rng: random.Random = rng if rng is not None else random.Random()

        # Telemetria analítica de partidas
        self.hands_played: int = 0
        self.bluffs_attempted: int = 0
        self.bluffs_won: int = 0
        self.traps_attempted: int = 0
        self.vpip_actions: int = 0
        self.pfr_actions: int = 0
        self.bets_and_raises: int = 0
        self.calls: int = 0
        self.folds: int = 0
        self.last_decision: Optional[HybridDecision] = None

    # --- Propriedades de compatibilidade ---
    @property
    def math_threshold(self) -> float:
        return self.params.raise_equity_threshold

    @math_threshold.setter
    def math_threshold(self, val: float) -> None:
        self.params.raise_equity_threshold = max(0.40, min(0.90, val))

    @property
    def bluff_prob(self) -> float:
        return self.params.bluff_frequency

    @bluff_prob.setter
    def bluff_prob(self, val: float) -> None:
        self.params.bluff_frequency = max(0.05, min(0.65, val))

    @property
    def slowplay_prob(self) -> float:
        return self.params.slowplay_prob

    @slowplay_prob.setter
    def slowplay_prob(self, val: float) -> None:
        self.params.slowplay_prob = max(0.05, min(0.50, val))

    @property
    def num_simulations(self) -> int:
        return self.params.num_simulations

    @num_simulations.setter
    def num_simulations(self, val: int) -> None:
        self.params.num_simulations = max(30, min(500, val))

    # --- Métodos de exportação, importação e persistência ---
    def export_parameters(self) -> Dict[str, Any]:
        """Exporta os hiperparâmetros atuais do agente para calibração ou treino."""
        return self.params.to_dict()

    def load_parameters(self, params: Dict[str, Any]) -> None:
        """Aplica novos hiperparâmetros resultantes de rotinas de treinamento."""
        self.params = HybridParameters.from_dict(params)

    def save_parameters(self, filepath: str | Path) -> None:
        """Persiste os hiperparâmetros em arquivo JSON."""
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

    def adapt_to_parents(
        self,
        math_params: Optional[Dict[str, Any]] = None,
        bluffer_params: Optional[Dict[str, Any]] = None,
        math_weight: float = 0.50,
    ) -> None:
        """Herda parâmetros de agentes matemáticos e blefadores já treinados."""
        self.params = HybridParameters.from_parents(
            math_params=math_params,
            bluffer_params=bluffer_params,
            math_weight=math_weight,
        )

    # --- Decisão e Lógica ---
    def decide_action(self, table: Table) -> Action:
        """Determina a ação na mesa combinando matemática e oportunismo tático."""
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
        self.last_decision = decision

        return Action(
            player_id=self.player_id,
            action_type=decision.action_type,
            amount=decision.amount,
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
        street: Street,
    ) -> HybridDecision:
        """Calcula equidade via Monte Carlo e balanceia rigor matemático com blefe."""
        eq_res = estimate_hand_equity(
            hole_cards=hole_cards,
            community_cards=community_cards,
            num_opponents=num_opponents,
            num_simulations=self.params.num_simulations,
            rng=self.rng,
        )
        equity = eq_res.equity
        pot_odds = calculate_pot_odds(to_call=to_call, pot_size=pot_size)

        # Detecção de Draws (Flush / Straight) no Flop e Turn
        is_draw = False
        if street in (Street.FLOP, Street.TURN) and len(community_cards) >= 3:
            all_cards = list(hole_cards) + list(community_cards)
            is_draw = has_flush_draw(all_cards) or has_straight_draw(all_cards)

        roll = self.rng.random()

        # Cenário 1: Mão Monstro (Equity >= 0.80) -> Valor vs Armadilha (Slow-Play)
        if equity >= 0.80:
            if roll < self.params.slowplay_prob and street != Street.RIVER:
                if ActionType.CHECK in legal_actions:
                    return HybridDecision(
                        action_type=ActionType.CHECK,
                        amount=0,
                        mode="SLOW_PLAY",
                        equity=equity,
                        pot_odds=pot_odds,
                        is_deceptive=True,
                        reason=f"Slow-play com mão monstro (Eq={equity:.2%})",
                    )
                if ActionType.CALL in legal_actions and to_call <= big_blind * 4:
                    return HybridDecision(
                        action_type=ActionType.CALL,
                        amount=0,
                        mode="SLOW_PLAY",
                        equity=equity,
                        pot_odds=pot_odds,
                        is_deceptive=True,
                        reason=f"Call de armadilha com mão monstro (Eq={equity:.2%})",
                    )

            return self._build_value_action(
                equity=equity,
                pot_odds=pot_odds,
                pot_size=pot_size,
                player_stack=player_stack,
                player_current_bet=player_current_bet,
                current_highest_bet=current_highest_bet,
                min_raise=min_raise,
                big_blind=big_blind,
                legal_actions=legal_actions,
            )

        # Cenário 2: Equidade Alta por Valor (Equity >= raise_equity_threshold)
        if equity >= self.params.raise_equity_threshold:
            return self._build_value_action(
                equity=equity,
                pot_odds=pot_odds,
                pot_size=pot_size,
                player_stack=player_stack,
                player_current_bet=player_current_bet,
                current_highest_bet=current_highest_bet,
                min_raise=min_raise,
                big_blind=big_blind,
                legal_actions=legal_actions,
            )

        # Cenário 3: Semi-Blefe Tático (Draws ou Equidade Moderada 0.38-0.59)
        # O peso de blefe (1.0 - math_weight) expande ou restringe essa probabilidade
        semi_bluff_threshold = self.params.semi_bluff_frequency * (1.3 - 0.6 * self.params.math_weight)
        if (is_draw or equity >= 0.38) and roll < semi_bluff_threshold:
            if ActionType.BET in legal_actions:
                bet_amt = min(
                    player_stack,
                    max(big_blind, int(pot_size * self.params.bet_sizing_factor)),
                )
                return HybridDecision(
                    action_type=ActionType.BET,
                    amount=bet_amt,
                    mode="SEMI_BLUFF",
                    equity=equity,
                    pot_odds=pot_odds,
                    is_deceptive=True,
                    reason=f"Semi-blefe agressivo com draw/equidade (Eq={equity:.2%})",
                )
            if ActionType.RAISE in legal_actions and to_call <= big_blind * 3:
                raise_amt = current_highest_bet + max(min_raise, to_call * 2)
                max_pos = player_current_bet + player_stack
                raise_amt = min(max_pos, raise_amt)
                return HybridDecision(
                    action_type=ActionType.RAISE,
                    amount=raise_amt,
                    mode="SEMI_BLUFF",
                    equity=equity,
                    pot_odds=pot_odds,
                    is_deceptive=True,
                    reason=f"Raise de semi-blefe aplicando fold equity (Eq={equity:.2%})",
                )

        # Cenário 4: Blefe Oportunista (Potes abandonados onde a mesa deu check)
        bluff_threshold = self.params.bluff_frequency * (1.3 - 0.6 * self.params.math_weight)
        if to_call == 0:
            if roll < bluff_threshold and num_opponents <= 3:
                if ActionType.BET in legal_actions:
                    steal_amt = min(
                        player_stack,
                        max(big_blind, int(pot_size * self.params.bet_sizing_factor)),
                    )
                    return HybridDecision(
                        action_type=ActionType.BET,
                        amount=steal_amt,
                        mode="PURE_BLUFF",
                        equity=equity,
                        pot_odds=pot_odds,
                        is_deceptive=True,
                        reason=f"Blefe oportuno em mesa passiva (Eq={equity:.2%})",
                    )
            if ActionType.CHECK in legal_actions:
                return HybridDecision(
                    action_type=ActionType.CHECK,
                    amount=0,
                    mode="PASSIVE_CHECK",
                    equity=equity,
                    pot_odds=pot_odds,
                    is_deceptive=False,
                    reason="Check gratuito preservando fichas",
                )

        # Cenário 5: Enfrentando aposta -> Avaliação de Pot Odds e EV com margem
        if to_call > 0:
            # Se a equidade supera as pot odds menos a margem de EV tolerada
            if equity >= (pot_odds - self.params.call_ev_margin) and ActionType.CALL in legal_actions:
                return HybridDecision(
                    action_type=ActionType.CALL,
                    amount=0,
                    mode="EV_CALL",
                    equity=equity,
                    pot_odds=pot_odds,
                    is_deceptive=False,
                    reason=(
                        f"Call justificado por Pot Odds e EV "
                        f"(Eq={equity:.2%} >= Odds={pot_odds:.2%})"
                    ),
                )

            # Floating barato se a aposta for ínfima (<= 0.5 * BB)
            if to_call <= big_blind // 2 and ActionType.CALL in legal_actions:
                return HybridDecision(
                    action_type=ActionType.CALL,
                    amount=0,
                    mode="CHEAP_CALL",
                    equity=equity,
                    pot_odds=pot_odds,
                    is_deceptive=False,
                    reason="Call de valor marginal quase gratuito",
                )

        # Cenário 6: Desistência disciplinada (EV Negativo e sem justificativa de blefe)
        if ActionType.FOLD in legal_actions:
            return HybridDecision(
                action_type=ActionType.FOLD,
                amount=0,
                mode="DISCIPLINED_FOLD",
                equity=equity,
                pot_odds=pot_odds,
                is_deceptive=False,
                reason=(
                    f"Fold disciplinado por EV negativo "
                    f"(Eq={equity:.2%} < Odds={pot_odds:.2%})"
                ),
            )

        fallback = legal_actions[0] if legal_actions else ActionType.FOLD
        return HybridDecision(
            action_type=fallback,
            amount=0,
            mode="FALLBACK",
            equity=equity,
            pot_odds=pot_odds,
            is_deceptive=False,
            reason="Ação de segurança",
        )

    def _build_value_action(
        self,
        equity: float,
        pot_odds: float,
        pot_size: int,
        player_stack: int,
        player_current_bet: int,
        current_highest_bet: int,
        min_raise: int,
        big_blind: int,
        legal_actions: Sequence[ActionType],
    ) -> HybridDecision:
        """Gera ação de aposta por valor proporcional à equidade e bet sizing."""
        if ActionType.RAISE in legal_actions and player_stack > 0:
            raise_size = current_highest_bet + max(
                min_raise, int(pot_size * self.params.bet_sizing_factor * 1.25)
            )
            max_pos = player_current_bet + player_stack
            raise_size = min(max_pos, raise_size)
            return HybridDecision(
                action_type=ActionType.RAISE,
                amount=raise_size,
                mode="VALUE_RAISE",
                equity=equity,
                pot_odds=pot_odds,
                is_deceptive=False,
                reason=f"Aumento por valor com vantagem de equidade ({equity:.2%})",
            )

        if ActionType.BET in legal_actions:
            bet_size = min(
                player_stack,
                max(big_blind, int(pot_size * self.params.bet_sizing_factor)),
            )
            return HybridDecision(
                action_type=ActionType.BET,
                amount=bet_size,
                mode="VALUE_BET",
                equity=equity,
                pot_odds=pot_odds,
                is_deceptive=False,
                reason=f"Aposta por valor proporcional ao pote ({equity:.2%})",
            )

        if ActionType.CALL in legal_actions:
            return HybridDecision(
                action_type=ActionType.CALL,
                amount=0,
                mode="VALUE_CALL",
                equity=equity,
                pot_odds=pot_odds,
                is_deceptive=False,
                reason=f"Call com forte equidade ({equity:.2%})",
            )

        if ActionType.CHECK in legal_actions:
            return HybridDecision(
                action_type=ActionType.CHECK,
                amount=0,
                mode="VALUE_CHECK",
                equity=equity,
                pot_odds=pot_odds,
                is_deceptive=False,
                reason="Check mantendo a mão ativa",
            )

        return HybridDecision(
            action_type=ActionType.FOLD,
            amount=0,
            mode="FALLBACK",
            equity=equity,
            pot_odds=pot_odds,
            is_deceptive=False,
            reason="Contingência",
        )

    def _track_decision_telemetry(self, decision: HybridDecision) -> None:
        """Registra telemetria das jogadas realizadas."""
        if decision.mode in ("SEMI_BLUFF", "PURE_BLUFF"):
            self.bluffs_attempted += 1
        elif decision.mode == "SLOW_PLAY":
            self.traps_attempted += 1

        if decision.action_type in (ActionType.BET, ActionType.RAISE):
            self.bets_and_raises += 1
            self.vpip_actions += 1
            self.pfr_actions += 1
        elif decision.action_type == ActionType.CALL:
            self.calls += 1
            self.vpip_actions += 1
        elif decision.action_type == ActionType.FOLD:
            self.folds += 1


if __name__ == "__main__":
    agent = HybridAgent(
        player_id="hybrid_test",
        name="Híbrido Teste",
        math_weight=0.50,
        raise_equity_threshold=0.55,
        bluff_frequency=0.30,
        rng=random.Random(42),
    )
    hole = [Card.from_str("Ks"), Card.from_str("Qs")]
    board = [Card.from_str("Js"), Card.from_str("10s"), Card.from_str("2c")]

    dec = agent.evaluate_state(
        hole_cards=hole,
        community_cards=board,
        pot_size=160,
        to_call=0,
        player_stack=950,
        player_current_bet=0,
        current_highest_bet=0,
        min_raise=20,
        big_blind=20,
        num_opponents=2,
        legal_actions=[ActionType.CHECK, ActionType.BET],
        street=Street.FLOP,
    )
    print("Decisão isolada do Agente Híbrido:")
    print(f"  Ação: {dec.action_type.value}")
    print(f"  Quantia: {dec.amount}")
    print(f"  Modo: {dec.mode}")
    print(f"  Equidade: {dec.equity:.2%}")
    print(f"  Enganoso? {dec.is_deceptive}")
    print(f"  Razão: {dec.reason}")
