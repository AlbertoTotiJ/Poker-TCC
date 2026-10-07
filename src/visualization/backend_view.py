"""Módulo de renderização e observabilidade back-end no console para Texas Hold'em."""

from typing import Dict, List, Optional, Sequence

from src.engine.deck import Card
from src.engine.hand_eval import HandRank, HandScore
from src.engine.player import Player
from src.engine.table import Table

_RANK_NAMES: Dict[int, str] = {
    14: "Ás",
    13: "Rei",
    12: "Dama",
    11: "Valete",
    10: "10",
    9: "9",
    8: "8",
    7: "7",
    6: "6",
    5: "5",
    4: "4",
    3: "3",
    2: "2",
}


def _translate_rank(val: int) -> str:
    return _RANK_NAMES.get(val, str(val))


def format_card(card: Optional[Card], hidden: bool = False) -> str:
    """Formata uma carta individual com suporte a ocultação de adversários."""
    if hidden:
        return "[ ?? ]"
    if card is None:
        return "[ -- ]"
    return f"[{card.rank.symbol:>2}{card.suit.value}]"


def format_hand_combination(score: HandScore) -> str:
    """Converte um HandScore em descrição legível em português."""
    tb = score.tiebreakers
    hr = score.hand_rank

    if hr == HandRank.ROYAL_FLUSH:
        return "Royal Flush"
    if hr == HandRank.STRAIGHT_FLUSH:
        return f"Straight Flush ({_translate_rank(tb[0])} alto)"
    if hr == HandRank.FOUR_OF_A_KIND:
        return f"Quadra de {_translate_rank(tb[0])}"
    if hr == HandRank.FULL_HOUSE:
        return f"Full House ({_translate_rank(tb[0])} com {_translate_rank(tb[1])})"
    if hr == HandRank.FLUSH:
        return f"Flush ({_translate_rank(tb[0])} alto)"
    if hr == HandRank.STRAIGHT:
        return f"Sequência ({_translate_rank(tb[0])} alta)"
    if hr == HandRank.THREE_OF_A_KIND:
        return f"Trinca de {_translate_rank(tb[0])}"
    if hr == HandRank.TWO_PAIR:
        return f"Dois Pares ({_translate_rank(tb[0])} e {_translate_rank(tb[1])})"
    if hr == HandRank.ONE_PAIR:
        return f"Par de {_translate_rank(tb[0])}"
    return f"Carta Alta ({_translate_rank(tb[0])})"


def format_community_cards(cards: Sequence[Card]) -> str:
    """Formata o bordo comunitário com 5 posições (preenchidas ou vazias)."""
    slots: List[str] = []
    for i in range(5):
        if i < len(cards):
            slots.append(format_card(cards[i]))
        else:
            slots.append(format_card(None))
    return "  ".join(slots)


def get_position_label(player_idx: int, button_idx: int, total_players: int) -> str:
    """Retorna a sigla posicional padrão (D, SB, BB ou vazio)."""
    if total_players == 2:
        if player_idx == button_idx:
            return "D/SB"
        return "BB"

    sb_idx = (button_idx + 1) % total_players
    bb_idx = (button_idx + 2) % total_players

    if player_idx == button_idx:
        return "D"
    if player_idx == sb_idx:
        return "SB"
    if player_idx == bb_idx:
        return "BB"
    return "  "


class BackendView:
    """Renderizador do estado da mesa e telemetria de ações no console."""

    @staticmethod
    def render_table(
        table: Table,
        human_player_id: str,
        hand_number: int,
        event_log: Sequence[str],
        reveal_all: bool = False,
    ) -> None:
        """Renderiza o quadro completo de observabilidade da mesa."""
        num_players = len(table.players)
        b_idx = table.button_idx

        print("\n" + "=" * 80)
        print(f" TEXAS HOLD'EM - PAINEL BACK-END (MÃO #{hand_number}) ".center(80, "="))
        print("=" * 80)

        street_str = f"[{table.street.name}]"
        pot_str = f"{table.pot_manager.total_pot} fichas"
        bet_str = f"{table.current_highest_bet} fichas"
        summary = (
            f" Street: {street_str:<12} | "
            f"Pote Total: {pot_str:<14} | "
            f"Maior Aposta: {bet_str}"
        )
        print(summary)
        print("-" * 80)

        comm_str = format_community_cards(table.community_cards)
        print(f" BORDO COMUNITÁRIO:   {comm_str}")
        print("-" * 80)

        cols = f" {'POS':<5} {'NOME':<26} {'STACK':<8} {'APOSTA':<8}"
        print(f"{cols} {'STATUS':<9} {'CARTAS'}")
        print(" " + "-" * 78)

        for idx, player in enumerate(table.players):
            pos_label = get_position_label(idx, b_idx, num_players)
            is_turn = (
                table.current_player is not None
                and table.current_player.player_id == player.player_id
            )
            marker = ">>" if is_turn else "  "

            if not player.is_active:
                status = "Fold"
            elif player.is_all_in:
                status = "All-in"
            else:
                status = "Ativo"

            is_human = player.player_id == human_player_id
            hide_cards = not (is_human or reveal_all)

            if player.hole_cards is not None:
                c1_str = format_card(player.hole_cards[0], hidden=hide_cards)
                c2_str = format_card(player.hole_cards[1], hidden=hide_cards)
                cards_display = f"{c1_str} {c2_str}"
            else:
                cards_display = "[ -- ] [ -- ]"

            pos_formatted = f"{marker}[{pos_label:^4}]"
            name_display = player.name[:25]

            print(
                f"{pos_formatted:<8} {name_display:<24} "
                f"{player.stack:<8} {player.current_bet:<8} "
                f"{status:<9} {cards_display}"
            )

        print("=" * 80)
        if event_log:
            print(" TELEMETRIA RECENTE DO BACK-END:")
            recent = event_log[-5:]
            for event in recent:
                print(f"  • {event}")
            print("=" * 80)

    @staticmethod
    def render_showdown(
        scores: Dict[str, HandScore],
        payouts: Dict[str, int],
        players: Sequence[Player],
    ) -> None:
        """Renderiza o resumo analítico do Showdown pós-confronto."""
        print("\n" + "=" * 80)
        print(" RESULTADO DO SHOWDOWN ".center(80, "="))
        print("=" * 80)

        player_map = {p.player_id: p for p in players}

        for pid, score in scores.items():
            player = player_map.get(pid)
            if player is None or player.hole_cards is None:
                continue

            c1 = format_card(player.hole_cards[0])
            c2 = format_card(player.hole_cards[1])
            comb_desc = format_hand_combination(score)
            best_five = " ".join(format_card(c) for c in score.cards)
            won_chips = payouts.get(pid, 0)
            result_tag = f"VENCEDOR (+{won_chips} fichas)" if won_chips > 0 else ""

            print(f" • {player.name:<24} | Cartas: {c1} {c2}")
            print(f"   Combinação: {comb_desc:<25} | Melhores: {best_five}")
            if result_tag:
                print(f"   >>> {result_tag}")
            print("-" * 80)

    @staticmethod
    def render_uncontested_win(winner_name: str, amount: int) -> None:
        """Renderiza premiação por desistência de todos os adversários."""
        msg = f" VITÓRIA POR DESISTÊNCIA: {winner_name} recolhe {amount} fichas! "
        print("\n" + "=" * 80)
        print(msg.center(80))
        print("=" * 80 + "\n")

    @staticmethod
    def render_standings(
        players: Sequence[Player],
        eliminations: Sequence[Player],
    ) -> None:
        """Exibe o quadro de líderes e eliminações ocorridas."""
        print("\n" + "-" * 50)
        print(" CLASSIFICAÇÃO ATUALIZADA DE FICHAS ".center(50, "-"))
        sorted_players = sorted(players, key=lambda p: p.stack, reverse=True)
        for rank, p in enumerate(sorted_players, start=1):
            status = " (Eliminado)" if p.stack == 0 else ""
            print(f"  {rank}. {p.name:<25} : {p.stack:>6} fichas{status}")

        if eliminations:
            print("\n  [!] Jogadores eliminados nesta rodada:")
            for ep in eliminations:
                print(f"      - {ep.name}")
        print("-" * 50 + "\n")
