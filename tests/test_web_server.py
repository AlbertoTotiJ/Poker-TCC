"""Testes unitários cobrindo a sessão e a API do servidor web de poker."""

import random
from src.engine.table import ActionType
from src.visualization.web_server import WebPokerSession, card_to_dict


def test_card_to_dict() -> None:
    assert card_to_dict(None) is None

    from src.engine.deck import Card

    c = Card.from_str("Ah")
    d = card_to_dict(c)
    assert d is not None
    assert d["rank"] == "A"
    assert d["suit"] == "♥"
    assert d["color"] == "red"


def test_web_poker_session_init_and_state() -> None:
    session = WebPokerSession(num_players=4, starting_stack=1000, rng=random.Random(42))
    state = session.get_serialized_state()

    assert state["active"] is True
    assert len(state["players"]) == 4
    assert state["pot_total"] >= 30
    assert state["hand_number"] == 1
    assert "community_cards" in state


def test_web_poker_session_bot_step_and_transitions() -> None:
    session = WebPokerSession(num_players=3, starting_stack=1000, rng=random.Random(10))

    # Avança ações de bots se houver algum na vez
    for _ in range(10):
        state = session.get_serialized_state()
        if state["is_human_turn"] or state["is_hand_finished"]:
            break
        desc = session.step_bot()
        assert desc is not None


def test_web_poker_session_human_action() -> None:
    session = WebPokerSession(num_players=2, starting_stack=1000, rng=random.Random(7))
    state = session.get_serialized_state()

    # Em heads-up, se for a vez do humano, testa a aplicação de ação válida
    if state["is_human_turn"]:
        legal = state["legal_actions"]
        action_to_try = ActionType.CHECK.value if "CHECK" in legal else "CALL"
        desc = session.apply_human_action(action_to_try)
        assert desc is not None
        new_state = session.get_serialized_state()
        assert new_state["active"] is True


def test_find_free_port_and_start_server() -> None:
    import threading
    import urllib.request
    import json
    from src.visualization.web_server import find_free_port, start_poker_web_server

    port = find_free_port(start_port=5200, host="127.0.0.1")
    assert port >= 5200

    httpd, chosen_port = start_poker_web_server(
        host="127.0.0.1",
        port=port,
        num_players=3,
        starting_stack=1000,
    )
    assert chosen_port == port

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    try:
        # Testa /api/health
        health_url = f"http://127.0.0.1:{chosen_port}/api/health"
        with urllib.request.urlopen(health_url) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "ok"

        # Testa /favicon.ico (204)
        fav_url = f"http://127.0.0.1:{chosen_port}/favicon.ico"
        req = urllib.request.Request(fav_url)
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 204

        # Testa / (HTML da mesa)
        root_url = f"http://127.0.0.1:{chosen_port}/"
        with urllib.request.urlopen(root_url) as resp:
            assert resp.status == 200
            content = resp.read().decode("utf-8")
            assert "Texas Hold'em Poker" in content

        # Testa /api/state
        state_url = f"http://127.0.0.1:{chosen_port}/api/state"
        with urllib.request.urlopen(state_url) as resp:
            assert resp.status == 200
            sdata = json.loads(resp.read().decode("utf-8"))
            assert sdata["active"] is True
            assert len(sdata["players"]) == 3
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_get_local_ip() -> None:
    from scripts.play_poker_web import get_local_ip
    ip = get_local_ip()
    assert isinstance(ip, str)
    assert len(ip) > 0
    # Verifica formato basico de IP (ex: 192.168.x.x ou 127.0.0.1)
    parts = ip.split(".")
    assert len(parts) == 4


def test_record_batch_and_vercel_routing() -> None:
    import json
    import threading
    import urllib.request
    from urllib.error import HTTPError
    from src.visualization.web_server import find_free_port, start_poker_web_server

    port = find_free_port(start_port=5300, host="127.0.0.1")
    httpd, chosen_port = start_poker_web_server(
        host="127.0.0.1",
        port=port,
        num_players=4,
        starting_stack=1000,
    )

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    try:
        base = f"http://127.0.0.1:{chosen_port}"
        payload = json.dumps({
            "auth_code": "TCC2026",
            "num_hands": 2,
            "num_players": 6,
        }).encode("utf-8")

        # 1. Rota direta /api/record_batch
        req1 = urllib.request.Request(
            f"{base}/api/record_batch",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req1) as r1:
            assert r1.status == 200
            d1 = json.loads(r1.read().decode("utf-8"))
            assert d1["success"] is True
            assert d1["hands_completed"] == 2

        # 2. Simulação de Rewrite da Vercel via query param ?__route__=record_batch
        req2 = urllib.request.Request(
            f"{base}/api/index.py?__route__=record_batch",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req2) as r2:
            assert r2.status == 200
            d2 = json.loads(r2.read().decode("utf-8"))
            assert d2["success"] is True

        # 3. Simulação de Rewrite da Vercel via cabeçalho x-forwarded-uri
        req3 = urllib.request.Request(
            f"{base}/api/index.py",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-forwarded-uri": "/api/record_batch",
            },
        )
        with urllib.request.urlopen(req3) as r3:
            assert r3.status == 200
            d3 = json.loads(r3.read().decode("utf-8"))
            assert d3["success"] is True

        # 4. Simulação de endpoint no próprio body JSON
        p_body = json.dumps({
            "endpoint": "record_batch",
            "auth_code": "TCC2026",
            "num_hands": 1,
            "num_players": 6,
        }).encode("utf-8")
        req4 = urllib.request.Request(
            f"{base}/api/index.py",
            data=p_body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req4) as r4:
            assert r4.status == 200
            d4 = json.loads(r4.read().decode("utf-8"))
            assert d4["success"] is True

        # 5. Garantir que erro 404 retorna JSON (e nunca HTML)
        try:
            urllib.request.urlopen(f"{base}/api/rota_inexistente")
            assert False, "Deveria ter retornado HTTP 404"
        except HTTPError as err:
            assert err.code == 404
            err_data = json.loads(err.read().decode("utf-8"))
            assert err_data["success"] is False
            assert "Rota GET não encontrada" in err_data["error"]
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_web_poker_session_split_pot_and_tie_resolution() -> None:
    from src.engine.deck import Card, Rank, Suit
    from src.visualization.web_server import WebPokerSession

    session = WebPokerSession(num_players=2, starting_stack=1000)
    assert session.table is not None

    # Injeta um bordo onde a mesa possui o Royal Flush (ambos empatam jogando a mesa)
    royal_board = [
        Card(Rank.ACE, Suit.SPADES),
        Card(Rank.KING, Suit.SPADES),
        Card(Rank.QUEEN, Suit.SPADES),
        Card(Rank.JACK, Suit.SPADES),
        Card(Rank.TEN, Suit.SPADES),
    ]
    session.table._dealer._community_cards = list(royal_board)

    # Força ambos os jogadores a irem ao showdown
    session.table._resolve_showdown()
    session._log_hand_conclusion()

    state = session.get_serialized_state()
    assert state["active"] is True
    assert state["is_hand_finished"] is True

    sd = state.get("showdown")
    assert sd is not None
    assert sd["is_split_pot"] is True
    assert len(sd["winner_names"]) == 2
    assert "🤝 Empate" in sd["summary_message"]
    assert sd["pot_awards"][0]["is_split"] is True

    # Verifica se o log de eventos registrou o empate detalhado
    assert any("🤝 Empate no Showdown" in ev for ev in session.event_log)
