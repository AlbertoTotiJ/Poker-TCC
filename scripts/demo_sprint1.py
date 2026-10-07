"""Demonstração prática dos componentes desenvolvidos na Sprint 1 do Poker-TCC."""

from pathlib import Path
import random
import sys
from typing import List

# Garante a resolução correta dos módulos do projeto na execução direta
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.engine.dealer import Dealer  # noqa: E402
from src.engine.deck import Card, Deck  # noqa: E402
from src.engine.hand_eval import evaluate_hand  # noqa: E402
from src.engine.player import Player  # noqa: E402
from src.engine.table import Action, ActionType, Table  # noqa: E402


def demo_deck() -> None:
    print("=" * 60)
    print("1. DEMONSTRAÇÃO DO BARALHO (DECK & CARDS)")
    print("=" * 60)

    # Baralho com semente fixa para garantir determinismo na demonstração
    deck = Deck(rng=random.Random(42))
    print(f"Total de cartas no baralho recém-criado: {len(deck)}")

    deck.shuffle()
    print("Baralho embaralhado com sucesso.")

    sacadas = deck.draw(5)
    cartas_str = ", ".join(str(c) for c in sacadas)
    print(f"5 cartas retiradas do topo: [{cartas_str}]")

    queimada = deck.burn()
    print(f"Carta queimada oficialmente: {queimada}")
    print(f"Cartas restantes no baralho: {len(deck)}")
    print()


def demo_dealer() -> None:
    print("=" * 60)
    print("2. DEMONSTRAÇÃO DO DEALER OFICIAL")
    print("=" * 60)

    dealer = Dealer(rng=random.Random(100))
    dealer.start_new_hand()

    jogadores = ["Alice", "Bob"]
    maos = dealer.deal_hole_cards(jogadores)

    print("Cartas fechadas distribuídas pelo Dealer:")
    for jid, cartas in maos.items():
        print(f"  - {jid}: {cartas[0]} {cartas[1]}")

    flop = dealer.deal_flop()
    print(
        f"\n[FLOP]  (Queima: {dealer.burn_cards[0]}): {' '.join(str(c) for c in flop)}"
    )

    turn = dealer.deal_turn()
    print(f"[TURN]  (Queima: {dealer.burn_cards[1]}): {turn}")

    river = dealer.deal_river()
    print(f"[RIVER] (Queima: {dealer.burn_cards[2]}): {river}")

    bordo_str = " ".join(str(c) for c in dealer.community_cards)
    print(f"\nBordo completo final (5 cartas): [{bordo_str}]")
    print(f"Total de cartas queimadas pelo Dealer: {len(dealer.burn_cards)}")
    print(f"Cartas restantes no baralho do Dealer: {len(dealer.deck)}")
    print()


def demo_hand_evaluation() -> None:
    print("=" * 60)
    print("3. DEMONSTRAÇÃO DO AVALIADOR DE MÃOS (7 CARTAS)")
    print("=" * 60)

    # Cenário de demonstração com cartas comunitárias fixas
    bordo: List[Card] = [
        Card.from_str("Ks"),
        Card.from_str("Qc"),
        Card.from_str("Jd"),
        Card.from_str("7s"),
        Card.from_str("2h"),
    ]
    bordo_str = " ".join(str(c) for c in bordo)
    print(f"Bordo Comunitário: [{bordo_str}]\n")

    # Mão da Alice: Par de Áses
    alice_hole = (Card.from_str("Ah"), Card.from_str("As"))
    alice_total = list(alice_hole) + bordo
    alice_score = evaluate_hand(alice_total)

    print(f"Alice: {alice_hole[0]} {alice_hole[1]}")
    print(f"  Combinação: {alice_score.hand_rank.name}")
    print(f"  Melhores 5 cartas: {' '.join(str(c) for c in alice_score.cards)}")
    print(f"  Critérios de desempate: {alice_score.tiebreakers}")

    # Mão do Bob: Sequência de Ás a Dez (Broadway Straight)
    bob_hole = (Card.from_str("Ad"), Card.from_str("Ts"))
    bob_total = list(bob_hole) + bordo
    bob_score = evaluate_hand(bob_total)

    print(f"\nBob: {bob_hole[0]} {bob_hole[1]}")
    print(f"  Combinação: {bob_score.hand_rank.name}")
    print(f"  Melhores 5 cartas: {' '.join(str(c) for c in bob_score.cards)}")
    print(f"  Critérios de desempate: {bob_score.tiebreakers}")

    print("\nResultado do Confronto (Showdown):")
    if bob_score > alice_score:
        print("  -> Vencedor: BOB (Sequência vence Par de Áses)")
    elif alice_score > bob_score:
        print("  -> Vencedor: ALICE")
    else:
        print("  -> Empate matemático (Split pot)")
    print()


def demo_table_simulation() -> None:
    print("=" * 60)
    print("4. DEMONSTRAÇÃO DA MESA (SIMULAÇÃO COMPLETA DE MÃO)")
    print("=" * 60)

    alice = Player(player_id="p1", name="Alice", stack=1000)
    bob = Player(player_id="p2", name="Bob", stack=1000)

    # Inicialização da mesa com blinds 10/20
    table = Table(
        players=[alice, bob],
        small_blind=10,
        big_blind=20,
        rng=random.Random(7),
    )

    print(f"Stacks Iniciais: Alice = {alice.stack}, Bob = {bob.stack}")
    table.start_new_hand()

    print("\n[PRÉ-FLOP]")
    print(
        f"Blinds postados: Alice postou {alice.current_bet} (SB), "
        f"Bob postou {bob.current_bet} (BB)"
    )
    print(f"Pote acumulado: {table.pot_manager.total_pot}")
    print(f"Cartas de Alice: {alice.hole_cards[0]} {alice.hole_cards[1]}")
    print(f"Cartas de Bob:   {bob.hole_cards[0]} {bob.hole_cards[1]}")

    # Pré-flop: Alice paga o BB (+10), Bob dá Check
    print("Ação: Alice CALL (paga o Big Blind)")
    table.apply_action(Action("p1", ActionType.CALL))

    print("Ação: Bob CHECK")
    table.apply_action(Action("p2", ActionType.CHECK))

    print(f"\n[FLOP] Bordo: {' '.join(str(c) for c in table.community_cards)}")
    print(f"Pote no Flop: {table.pot_manager.total_pot}")

    # Flop: Bob aposta 40, Alice paga 40
    print("Ação: Bob BET 40")
    table.apply_action(Action("p2", ActionType.BET, amount=40))

    print("Ação: Alice CALL 40")
    table.apply_action(Action("p1", ActionType.CALL))

    print(f"\n[TURN] Bordo: {' '.join(str(c) for c in table.community_cards)}")
    print(f"Pote no Turn: {table.pot_manager.total_pot}")
    print("Ação: Bob CHECK")
    table.apply_action(Action("p2", ActionType.CHECK))
    print("Ação: Alice CHECK")
    table.apply_action(Action("p1", ActionType.CHECK))

    print(f"\n[RIVER] Bordo: {' '.join(str(c) for c in table.community_cards)}")
    print(f"Pote no River: {table.pot_manager.total_pot}")
    print("Ação: Bob CHECK")
    table.apply_action(Action("p2", ActionType.CHECK))
    print("Ação: Alice CHECK")
    table.apply_action(Action("p1", ActionType.CHECK))

    print("\n[SHOWDOWN & RESULTADO FINAL]")
    print(f"Status da Mesa: {table.street.name}")
    print(f"Stack final da Alice: {alice.stack}")
    print(f"Stack final do Bob:   {bob.stack}")
    print(f"Conservação total de fichas (deve ser 2000): {alice.stack + bob.stack}")
    print("=" * 60)


if __name__ == "__main__":
    demo_deck()
    demo_dealer()
    demo_hand_evaluation()
    demo_table_simulation()
