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
