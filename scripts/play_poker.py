"""Exemplo interativo de jogo Texas Hold'em contra a máquina.

Inclui visualização detalhada em console com telemetria do back-end.
"""

import argparse
from pathlib import Path
import random
import sys
import time
from typing import Dict, List, Optional, Sequence, Tuple

# Garante resolução dos módulos a partir da raiz do repositório
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.agents.heuristic import AgentProfile, HeuristicAgent  # noqa: E402
from src.engine.player import Player  # noqa: E402
from src.engine.table import Action, ActionType, Street, Table  # noqa: E402
from src.visualization.backend_view import BackendView  # noqa: E402

_BOT_PRESETS: List[Tuple[str, AgentProfile]] = [
    ("Bot Alpha (Agressivo)", AgentProfile.AGGRESSIVE),
    ("Bot Beta (Conservador)", AgentProfile.CONSERVATIVE),
    ("Bot Gamma (Equilibrado)", AgentProfile.BALANCED),
    ("Bot Delta (Agressivo)", AgentProfile.AGGRESSIVE),
    ("Bot Epsilon (Conservador)", AgentProfile.CONSERVATIVE),
    ("Bot Zeta (Equilibrado)", AgentProfile.BALANCED),
    ("Bot Eta (Agressivo)", AgentProfile.AGGRESSIVE),
    ("Bot Theta (Equilibrado)", AgentProfile.BALANCED),
]


class PokerGame:
    """Gerenciador da sessão interativa do jogo entre o usuário e as máquinas."""

    def __init__(
        self,
        num_players: int = 4,
        starting_stack: int = 1000,
        small_blind: int = 10,
        big_blind: int = 20,
        human_name: str = "Você (Humano)",
        rng: Optional[random.Random] = None,
        auto_mode: bool = False,
    ) -> None:
        if not (2 <= num_players <= 9):
            raise ValueError("A quantidade de jogadores deve ser entre 2 e 9.")

        self.human_id: str = "p_human"
        self.starting_stack: int = starting_stack
        self.small_blind: int = small_blind
        self.big_blind: int = big_blind
        self.rng: random.Random = rng if rng is not None else random.Random()
        self.auto_mode: bool = auto_mode

        self.players: List[Player] = [
            Player(player_id=self.human_id, name=human_name, stack=starting_stack)
        ]
        self.bot_agents: Dict[str, HeuristicAgent] = {}

        for i in range(num_players - 1):
            bot_id = f"p_bot_{i + 1}"
            bot_name, bot_profile = _BOT_PRESETS[i % len(_BOT_PRESETS)]
            self.players.append(
                Player(player_id=bot_id, name=bot_name, stack=starting_stack)
            )
            self.bot_agents[bot_id] = HeuristicAgent(
                player_id=bot_id,
                name=bot_name,
                profile=bot_profile,
                rng=random.Random(self.rng.randint(1, 1000000)),
            )

        self.hand_number: int = 0
        self.event_log: List[str] = []
        self._button_idx: int = 0

    def play(self, max_hands: int = 0) -> None:
        """Executa o loop principal de partidas até eliminação ou encerramento."""
        print("\n" + "=" * 80)
        print(" BEM-VINDO AO SIMULADOR DE TEXAS HOLD'EM (POKER-TCC) ".center(80, "="))
        print("=" * 80)
        print(f" Total de jogadores configurados: {len(self.players)}")
        print(f" Fichas iniciais por jogador: {self.starting_stack}")
        print(f" Estrutura de Blinds: {self.small_blind}/{self.big_blind}\n")

        while True:
            active_players = [p for p in self.players if p.stack > 0]
            if len(active_players) < 2:
                self._declare_champion(active_players)
                break

            human_player = next(
                (p for p in active_players if p.player_id == self.human_id), None
            )
            if human_player is None:
                print("\n[!] Você perdeu todas as fichas e foi eliminado. Fim de jogo!")
                break

            self.hand_number += 1
            if max_hands > 0 and self.hand_number > max_hands:
                print(f"\nLimite de {max_hands} mãos atingido.")
                break

            self._play_single_hand(active_players)

            new_active = [p for p in self.players if p.stack > 0]
            if len(new_active) < 2 or human_player.stack == 0:
                continue

            if not self.auto_mode:
                resposta = (
                    input("\nPressione [ENTER] para próxima mão (ou 's' para sair): ")
                    .strip()
                    .lower()
                )
                if resposta in ("s", "sair", "q", "quit"):
                    print("\nPartida encerrada pelo usuário.")
                    break

    def _play_single_hand(self, active_players: List[Player]) -> None:
        """Executa uma mão completa da distribuição das cartas ao showdown."""
        self.event_log.clear()
        table = Table(
            players=active_players,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            rng=self.rng,
            button_idx=self._button_idx,
        )

        table.start_new_hand(rng=self.rng)
        self.event_log.append("Nova mão iniciada. Blinds postados.")

        current_street = table.street
        while table.street not in (Street.FINISHED, Street.SHOWDOWN):
            if table.street != current_street:
                current_street = table.street
                bordo = " ".join(str(c) for c in table.community_cards)
                msg_street = f"Avanço para {current_street.name}. Bordo: {bordo}"
                self.event_log.append(msg_street)

            actor = table.current_player
            if actor is None:
                break

            if actor.player_id == self.human_id:
                action = self._prompt_human_action(table, actor)
            else:
                bot = self.bot_agents[actor.player_id]
                action = bot.decide_action(table)
                if not self.auto_mode:
                    time.sleep(0.4)

            self._log_action(actor, action)
            table.apply_action(action)

        self._button_idx = table.button_idx
        self._conclude_hand(table)

    def _prompt_human_action(self, table: Table, actor: Player) -> Action:
        """Exibe o estado e lê a decisão do usuário com validação de limites."""
        BackendView.render_table(
            table=table,
            human_player_id=self.human_id,
            hand_number=self.hand_number,
            event_log=self.event_log,
        )

        legal_actions = table.get_legal_actions(actor.player_id)
        if not legal_actions:
            return Action(actor.player_id, ActionType.FOLD)

        to_call = table.current_highest_bet - actor.current_bet

        if self.auto_mode:
            bot_fallback = HeuristicAgent(
                player_id=actor.player_id,
                name=actor.name,
                profile=AgentProfile.BALANCED,
                rng=self.rng,
            )
            return bot_fallback.decide_action(table)

        print("\n SUA VEZ DE AGIR! Escolha uma opção:")
        options_map: Dict[int, Tuple[ActionType, str]] = {}
        opt_idx = 1

        for act in legal_actions:
            if act == ActionType.FOLD:
                options_map[opt_idx] = (act, "Desistir (FOLD)")
            elif act == ActionType.CHECK:
                options_map[opt_idx] = (act, "Passar a vez (CHECK)")
            elif act == ActionType.CALL:
                options_map[opt_idx] = (act, f"Pagar aposta ({to_call} fichas) (CALL)")
            elif act == ActionType.BET:
                min_b = max(table.min_raise, self.big_blind)
                options_map[opt_idx] = (
                    act,
                    f"Apostar (BET) [Mín: {min_b}, Máx: {actor.stack}]",
                )
            elif act == ActionType.RAISE:
                min_r = table.current_highest_bet + table.min_raise
                max_r = actor.current_bet + actor.stack
                options_map[opt_idx] = (
                    act,
                    f"Aumentar (RAISE) [Mín: {min_r}, Máx: {max_r}]",
                )
            elif act == ActionType.ALL_IN:
                options_map[opt_idx] = (act, f"All-in ({actor.stack} fichas)")
            opt_idx += 1

        for num, (_, desc) in options_map.items():
            print(f"  [{num}] {desc}")

        while True:
            choice_str = input(f"\nDigite sua opção (1-{len(options_map)}): ").strip()
            if not choice_str.isdigit() or int(choice_str) not in options_map:
                print(f"Opção inválida! Escolha um número de 1 a {len(options_map)}.")
                continue

            chosen_act_type, _ = options_map[int(choice_str)]

            if chosen_act_type == ActionType.BET:
                min_b = max(table.min_raise, self.big_blind)
                max_b = actor.stack
                amt = self._ask_amount("Valor da aposta (BET): ", min_b, max_b)
                if amt == actor.stack:
                    return Action(actor.player_id, ActionType.ALL_IN)
                return Action(actor.player_id, ActionType.BET, amount=amt)

            if chosen_act_type == ActionType.RAISE:
                min_r = table.current_highest_bet + table.min_raise
                max_r = actor.current_bet + actor.stack
                amt = self._ask_amount("Valor total do aumento (RAISE): ", min_r, max_r)
                if amt == max_r:
                    return Action(actor.player_id, ActionType.ALL_IN)
                return Action(actor.player_id, ActionType.RAISE, amount=amt)

            return Action(actor.player_id, chosen_act_type)

    def _ask_amount(self, prompt_text: str, min_val: int, max_val: int) -> int:
        """Solicita valor numérico respeitando limites de aposta estabelecidos."""
        while True:
            val_str = input(f"{prompt_text} [{min_val} - {max_val}]: ").strip()
            if not val_str.isdigit():
                print("Por favor, digite apenas números inteiros positivos.")
                continue
            val = int(val_str)
            if min_val <= val <= max_val:
                return val
            print(f"Valor fora dos limites permitidos ({min_val} a {max_val}).")

    def _log_action(self, actor: Player, action: Action) -> None:
        """Registra a ação executada na telemetria do back-end."""
        act_type = action.action_type
        if act_type == ActionType.FOLD:
            msg = f"{actor.name} desistiu (FOLD)."
        elif act_type == ActionType.CHECK:
            msg = f"{actor.name} passou a vez (CHECK)."
        elif act_type == ActionType.CALL:
            msg = f"{actor.name} pagou a aposta (CALL)."
        elif act_type == ActionType.BET:
            msg = f"{actor.name} apostou {action.amount} fichas (BET)."
        elif act_type == ActionType.RAISE:
            msg = f"{actor.name} aumentou a aposta para {action.amount} fichas (RAISE)."
        elif act_type == ActionType.ALL_IN:
            msg = f"{actor.name} apostou tudo: ALL-IN ({actor.stack} fichas)!"
        else:
            msg = f"{actor.name} executou {act_type.value}."

        self.event_log.append(msg)

    def _conclude_hand(self, table: Table) -> None:
        """Processa a finalização da mão e exibe o balanço de fichas."""
        BackendView.render_table(
            table=table,
            human_player_id=self.human_id,
            hand_number=self.hand_number,
            event_log=self.event_log,
            reveal_all=True,
        )

        if table.last_scores:
            BackendView.render_showdown(
                scores=table.last_scores,
                payouts=table.last_payouts,
                players=table.players,
            )
        else:
            winner_id = next(iter(table.last_payouts.keys()), "")
            winner = next((p for p in table.players if p.player_id == winner_id), None)
            winner_name = winner.name if winner else "Desconhecido"
            pot_amount = table.last_payouts.get(winner_id, 0)
            BackendView.render_uncontested_win(winner_name, pot_amount)

        eliminations = [p for p in table.players if p.stack == 0]
        BackendView.render_standings(self.players, eliminations)

    def _declare_champion(self, active_players: Sequence[Player]) -> None:
        """Declara e renderiza o vencedor final do torneio."""
        print("\n" + "#" * 80)
        if len(active_players) == 1:
            champ = active_players[0]
            print(f" CAMPEÃO DO TORNEIO: {champ.name.upper()}! ".center(80, "#"))
            print(f" Total final acumulado: {champ.stack} fichas ".center(80))
        else:
            print(" TORNEIO ENCERRADO SEM VENCEDOR ÚNICO ".center(80, "#"))
        print("#" * 80 + "\n")


def parse_arguments() -> argparse.Namespace:
    """Configura e processa argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Simulador Texas Hold'em (Poker-TCC) com visualização back-end."
    )
    parser.add_argument(
        "--players",
        "-p",
        type=int,
        default=None,
        help="Quantidade total de jogadores na mesa (2 a 9).",
    )
    parser.add_argument(
        "--stack",
        "-s",
        type=int,
        default=1000,
        help="Stack inicial de fichas por jogador (Padrão: 1000).",
    )
    parser.add_argument(
        "--sb",
        type=int,
        default=10,
        help="Valor do Small Blind (Padrão: 10).",
    )
    parser.add_argument(
        "--bb",
        type=int,
        default=20,
        help="Valor do Big Blind (Padrão: 20).",
    )
    parser.add_argument(
        "--hands",
        type=int,
        default=0,
        help="Limite máximo de mãos (0 para ilimitado).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Semente determinística para simulação.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Modo automático para testes e demonstração sem bloqueio de stdin.",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Inicia a interface gráfica da mesa no navegador web.",
    )
    return parser.parse_args()


def prompt_number_of_players() -> int:
    """Solicita interativamente a quantidade de jogadores desejada pelo usuário."""
    print("=" * 60)
    print(" CONFIGURAÇÃO DA MESA DE TEXAS HOLD'EM ")
    print("=" * 60)
    while True:
        resp = input("Quantos jogadores na mesa (2 a 9)? [Padrão: 4]: ").strip()
        if not resp:
            return 4
        if resp.isdigit():
            val = int(resp)
            if 2 <= val <= 9:
                return val
        print("Entrada inválida! Escolha um valor entre 2 e 9.")


def main() -> None:
    args = parse_arguments()

    if args.web:
        import webbrowser
        from src.visualization.web_server import start_poker_web_server

        players_count = args.players if args.players is not None else 4
        httpd, port = start_poker_web_server(
            num_players=players_count,
            starting_stack=args.stack,
        )
        url = f"http://127.0.0.1:{port}"
        print("=" * 70)
        print(" MESA GRÁFICA VIRTUAL INICIADA NO NAVEGADOR! ".center(70, "="))
        print("=" * 70)
        print(f" Acesse: {url}")
        print(" Pressione Ctrl+C para encerrar o servidor.")
        print("=" * 70)
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor web finalizado.")
        finally:
            httpd.server_close()
        return

    if args.players is not None:
        num_players = args.players
    elif not args.auto:
        num_players = prompt_number_of_players()
    else:
        num_players = 4

    rng = random.Random(args.seed) if args.seed is not None else None

    game = PokerGame(
        num_players=num_players,
        starting_stack=args.stack,
        small_blind=args.sb,
        big_blind=args.bb,
        rng=rng,
        auto_mode=args.auto,
    )

    game.play(max_hands=args.hands)


if __name__ == "__main__":
    main()
