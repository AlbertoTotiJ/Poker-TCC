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


def test_web_poker_session_agent_modes() -> None:
    # 1. Modo math: todos os bots são MathematicalAgent
    session_math = WebPokerSession(num_players=3, agent_mode="math")
    state_math = session_math.get_serialized_state()
    assert state_math["agent_mode"] == "math"
    bots = [p for p in state_math["players"] if p["id"] != session_math.human_id]
    for b in bots:
        assert b["agent_type"] == "math"
        assert "Matemático" in b["agent_label"]

    # 2. Modo mixed: alterna entre math e bot
    session_mixed = WebPokerSession(num_players=4, agent_mode="mixed")
    state_mixed = session_mixed.get_serialized_state()
    assert state_mixed["agent_mode"] == "mixed"
    bots_mixed = [
        p for p in state_mixed["players"] if p["id"] != session_mixed.human_id
    ]
    assert bots_mixed[0]["agent_type"] == "math"
    assert bots_mixed[1]["agent_type"] == "bot"

    # 3. Modo custom: assentos específicos
    session_custom = WebPokerSession(
        num_players=4,
        agent_mode="custom",
        custom_agents=["math", "aggressive", "conservative"],
    )
    state_custom = session_custom.get_serialized_state()
    assert state_custom["agent_mode"] == "custom"
    bots_custom = [
        p for p in state_custom["players"] if p["id"] != session_custom.human_id
    ]
    assert bots_custom[0]["agent_type"] == "math"
    assert bots_custom[1]["agent_type"] == "aggressive"
    assert bots_custom[2]["agent_type"] == "conservative"

    # 4. Modo bluffer: assentos com BlufferAgent
    session_bluffer = WebPokerSession(num_players=3, agent_mode="bluffer")
    state_bluffer = session_bluffer.get_serialized_state()
    assert state_bluffer["agent_mode"] == "bluffer"
    bots_bluffer = [
        p for p in state_bluffer["players"] if p["id"] != session_bluffer.human_id
    ]
    for b in bots_bluffer:
        assert b["agent_type"] == "bluffer"
        assert "Blefador" in b["agent_label"]

    # 5. Modo gh_bluffer: assentos com GhBlufferAgent (Gustavo)
    session_gh_bluffer = WebPokerSession(num_players=3, agent_mode="gh_bluffer")
    state_gh_bluffer = session_gh_bluffer.get_serialized_state()
    assert state_gh_bluffer["agent_mode"] == "gh_bluffer"
    bots_gh_bluffer = [
        p for p in state_gh_bluffer["players"] if p["id"] != session_gh_bluffer.human_id
    ]
    for b in bots_gh_bluffer:
        assert b["agent_type"] == "gh_bluffer"
        assert "GhBluffer" in b["agent_label"]


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


def test_agent_models_auto_discovery_and_import() -> None:
    import json
    import tempfile
    from pathlib import Path
    from src.training.agent_registry import AgentRegistry

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        catalog_path = tmp_path / "custom_trained_agents.json"
        
        # Cria um arquivo individual de agente treinado em models/
        agent_file = tmp_path / "hybrid_trained_test.json"
        agent_data = {
            "session_id": "test_auto_hybrid_123",
            "name": "Híbrido Teste Auto",
            "agent_type": "hybrid",
            "overall_fitness": 88.5,
            "overall_tier": "S (Elite)",
            "parameters": {
                "math_weight": 0.65,
                "bluff_frequency": 0.35,
            },
        }
        with open(agent_file, "w", encoding="utf-8") as f:
            json.dump(agent_data, f)

        reg = AgentRegistry(catalog_file=catalog_path)
        assert "test_auto_hybrid_123" in reg.custom_agents
        meta = reg.custom_agents["test_auto_hybrid_123"]
        assert meta.name == "Híbrido Teste Auto"
        assert meta.base_type == "hybrid"
        assert meta.parameters["math_weight"] == 0.65

        # Instanciação do agente auto-descoberto
        inst = reg.instantiate_agent_by_id("test_auto_hybrid_123", player_id="p1")
        assert inst is not None
        assert inst.name == "Híbrido Teste Auto"
