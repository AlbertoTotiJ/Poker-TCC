"""Testes unitários cobrindo o gravador seguro de partidas e autenticação da equipe."""

from src.database.recorder import (
    build_research_roster,
    run_recording_batch,
    verify_auth_code,
)


def test_auth_code_verification() -> None:
    assert verify_auth_code("TCC2026") is True
    assert verify_auth_code("  TCC2026  ") is True
    assert verify_auth_code("CODIGO_ERRADO") is False
    assert verify_auth_code("") is False


def test_build_research_roster_6_players() -> None:
    players, agents, profile_labels = build_research_roster(num_players=6)
    assert len(players) == 6
    assert len(agents) == 6

    # 2 Matemáticos, 2 Agressivos, 2 Conservadores
    profiles = list(profile_labels.values())
    assert profiles.count("Matemático") == 2
    assert profiles.count("Agressivo") == 2
    assert profiles.count("Conservador") == 2


def test_build_research_roster_9_players() -> None:
    players, agents, profile_labels = build_research_roster(num_players=9)
    assert len(players) == 9
    profiles = list(profile_labels.values())
    assert profiles.count("Matemático") == 3
    assert profiles.count("Agressivo") == 3
    assert profiles.count("Conservador") == 3


def test_build_research_roster_custom_modes() -> None:
    # 1. Duelo: Matemáticos vs Bots
    _, _, p_mvb = build_research_roster(roster_mode="math_vs_bots")
    assert list(p_mvb.values()).count("Matemático") == 3
    assert list(p_mvb.values()).count("Agressivo") == 1
    assert list(p_mvb.values()).count("Conservador") == 1
    assert list(p_mvb.values()).count("Equilibrado") == 1

    # 2. Torneio Completo de IAs
    _, _, p_ai = build_research_roster(roster_mode="full_ai_tournament")
    assert list(p_ai.values()).count("Matemático") == 2
    assert list(p_ai.values()).count("Blefador") == 2
    assert list(p_ai.values()).count("Híbrido") == 2

    # 3. Desafio de Blefe
    _, _, p_blf = build_research_roster(roster_mode="bluff_challenge")
    assert list(p_blf.values()).count("Blefador") == 2
    assert list(p_blf.values()).count("Matemático") == 2
    assert list(p_blf.values()).count("Conservador") == 2

    # 4. Multimodelo 9-Max
    players_9, _, p_all9 = build_research_roster(roster_mode="all_models_9")
    assert len(players_9) == 9
    assert "Blefador" in p_all9.values()
    assert "Híbrido" in p_all9.values()
    assert "Matemático" in p_all9.values()


def test_run_recording_batch_simulation() -> None:
    res = run_recording_batch(
        auth_code="TCC2026",
        num_hands=3,
        num_players=6,
        rng_seed=42,
    )
    assert res["success"] is True
    assert res["hands_completed"] == 3
    assert "wins_by_profile" in res
    assert "total_bluffs_detected" in res
    assert "champion" in res
    assert "best_combination" in res
    assert "leaderboard" in res
    assert res["file_saved_count"] >= 3


def test_run_recording_batch_full_ai_tournament() -> None:
    res = run_recording_batch(
        auth_code="TCC2026",
        num_hands=2,
        roster_mode="full_ai_tournament",
        rng_seed=42,
    )
    assert res["success"] is True
    assert res["roster_mode"] == "full_ai_tournament"
    assert "Blefador" in res["wins_by_profile"]
    assert "Híbrido" in res["wins_by_profile"]
    assert "Matemático" in res["wins_by_profile"]


def test_sync_functions_invalid_auth() -> None:
    from src.database.recorder import (
        save_dataset_to_github,
        save_dataset_to_neon,
    )

    res_gh = save_dataset_to_github(auth_code="ERRADO")
    assert res_gh["success"] is False
    assert "inválido" in res_gh["error"].lower()

    res_neon = save_dataset_to_neon(auth_code="ERRADO")
    assert res_neon["success"] is False
    assert "inválido" in res_neon["error"].lower()


def test_build_research_roster_tcc_experiment_9() -> None:
    players, agents, profile_labels = build_research_roster(
        roster_mode="tcc_experiment_9"
    )
    assert len(players) == 9
    assert len(agents) == 9
    profiles = list(profile_labels.values())
    assert profiles.count("Matemático") == 4
    assert profiles.count("Blefador") == 5
    # Cadeira do 9º agente deve ter a indicação de substituto
    names = [p.name for p in players]
    assert any("9º Agente" in n for n in names)


def test_build_research_roster_gh_bluffer_showdown() -> None:
    players, agents, profile_labels = build_research_roster(
        roster_mode="gh_bluffer_showdown"
    )
    assert len(players) == 6
    assert len(agents) == 6
    profiles = list(profile_labels.values())
    assert profiles.count("GhBluffer (Gustavo)") == 2
    assert profiles.count("Blefador (Alberto)") == 2


def test_build_research_roster_custom_seats_9_max() -> None:
    custom_seats = [
        "gh_math", "math", "bluffer", "hybrid",
        "aggressive", "conservative", "balanced", "math", "bluffer"
    ]
    players, agents, profile_labels = build_research_roster(
        custom_seats=custom_seats
    )
    assert len(players) == 9
    assert len(agents) == 9
    # O 9º jogador deve estar configurado como agente de IA autônomo
    player_9 = players[8]
    assert "9º Agente" in player_9.name
    assert profile_labels[player_9.player_id] == "Blefador"


def test_run_recording_batch_custom_seats() -> None:
    custom_seats = [
        "math", "bluffer", "gh_math", "hybrid",
        "aggressive", "conservative", "balanced", "math", "bluffer"
    ]
    res = run_recording_batch(
        auth_code="TCC2026",
        num_hands=2,
        custom_seats=custom_seats,
        rng_seed=123,
    )
    assert res["success"] is True
    assert res["roster_mode"] == "custom"
    assert res["hands_completed"] == 2
    # Leaderboard contém os 9 agentes, incluindo o 9º agente
    leaderboard_names = [p["name"] for p in res["leaderboard"]]
    assert len(leaderboard_names) == 9
    assert any("9º Agente" in n for n in leaderboard_names)


def test_build_research_roster_tier_s_presets() -> None:
    # 1. Duelo Campeões Tier S (3 Blefadores vs 3 Matemáticos)
    players_s, _, p_s = build_research_roster(roster_mode="tier_s_duelo")
    assert len(players_s) == 6
    assert list(p_s.values()).count("Blefador Treinado (Tier S)") == 3
    assert list(p_s.values()).count("Matemático Treinado (Tier S)") == 3

    # 2. Torneio Híbrido vs Campeões Tier S
    players_h, _, p_h = build_research_roster(roster_mode="hybrid_vs_champions")
    assert len(players_h) == 6
    assert list(p_h.values()).count("Híbrido") == 2
    assert list(p_h.values()).count("Blefador Treinado (Tier S)") == 2
    assert list(p_h.values()).count("Matemático Treinado (Tier S)") == 2

    # 3. Grande Torneio TCC Tier S & Híbridos 9-Max
    players_9, _, p_9 = build_research_roster(roster_mode="tcc_champions_9")
    assert len(players_9) == 9
    assert list(p_9.values()).count("Matemático Treinado (Tier S)") == 3
    assert list(p_9.values()).count("Blefador Treinado (Tier S)") == 3
    assert list(p_9.values()).count("Híbrido") == 3
    assert any("9º Agente" in p.name for p in players_9)


def test_run_recording_batch_tier_s_and_hybrid() -> None:
    # Simula rodada gravada no modo tier_s_duelo
    res_duelo = run_recording_batch(
        auth_code="TCC2026",
        num_hands=2,
        roster_mode="tier_s_duelo",
        rng_seed=999,
    )
    assert res_duelo["success"] is True
    assert res_duelo["hands_completed"] == 2
    assert "Blefador Treinado (Tier S)" in res_duelo["wins_by_profile"]
    assert "Matemático Treinado (Tier S)" in res_duelo["wins_by_profile"]

    # Simula rodada gravada com custom_seats contendo os agentes Tier S e o Híbrido
    custom_seats = [
        "trained_bluffer", "trained_math", "hybrid",
        "trained_bluffer", "trained_math", "hybrid"
    ]
    res_custom = run_recording_batch(
        auth_code="TCC2026",
        num_hands=2,
        custom_seats=custom_seats,
        rng_seed=888,
    )
    assert res_custom["success"] is True
    assert res_custom["roster_mode"] == "custom"
    assert res_custom["hands_completed"] == 2
    assert len(res_custom["leaderboard"]) == 6
