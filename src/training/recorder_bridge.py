"""Ponte entre o sistema de treinamento e o gerador de datasets de partidas.

Permite que o sistema de treinamento grave todas as partidas disputadas durante a
avaliação e adaptação dos agentes, gerando datasets rotulados em formato JSONL
(e opcionalmente sincronizando com o banco Neon), contendo histórico completo de ações,
métricas cognitivas, detecção de blefe e metadados da geração evolutiva.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.database.recorder import (
    detect_hand_bluffs,
    get_record_file,
    save_hand_to_neon,
)
from src.engine.table import Table


class TrainingRecorderBridge:
    """Gerencia a persistência de rodadas simuladas durante o treinamento."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        output_file: Optional[Path] = None,
        append_to_main_dataset: bool = True,
        save_to_neon_db: bool = False,
    ) -> None:
        self.session_id: str = (
            session_id
            if session_id is not None
            else f"train_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        )
        self.append_to_main_dataset: bool = append_to_main_dataset
        self.save_to_neon_db: bool = save_to_neon_db

        project_root = Path(__file__).resolve().parent.parent.parent
        self.training_dir: Path = project_root / "data" / "training_sessions"
        self.training_dir.mkdir(parents=True, exist_ok=True)

        if output_file is not None:
            self.session_file: Path = Path(output_file)
        else:
            self.session_file = (
                self.training_dir / f"{self.session_id}.jsonl"
            )

        self.hands_recorded_count: int = 0
        self.total_actions_recorded: int = 0
        self.total_bluffs_recorded: int = 0

    def record_hand(
        self,
        table: Table,
        actions_log: List[Dict[str, Any]],
        profile_labels: Dict[str, str],
        generation: int,
        candidate_id: str,
        candidate_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Formata e persiste uma mão disputada durante o treino."""
        payouts = getattr(table, "last_payouts", {})
        pot_awards = getattr(table, "last_pot_awards", [])

        winning_ids: List[str] = []
        is_split = False
        winning_comb_desc = "Desistência dos adversários"

        if pot_awards:
            main_award = pot_awards[0]
            winning_ids = list(main_award.winning_player_ids)
            is_split = main_award.is_split
            if main_award.winning_score:
                winning_comb_desc = main_award.winning_score.description
        else:
            winning_ids = [
                pid for pid, amount in payouts.items() if amount > 0
            ]

        winners_data: List[Dict[str, Any]] = []
        for wid in winning_ids:
            p_obj = next((p for p in table.players if p.player_id == wid), None)
            winners_data.append({
                "player_id": wid,
                "player_name": p_obj.name if p_obj else wid,
                "profile": profile_labels.get(wid, "Desconhecido"),
                "amount_won": payouts.get(wid, 0),
            })

        # Detecção de blefe na mão
        bluffs_detected = detect_hand_bluffs(
            table=table,
            actions_log=actions_log,
            profile_labels=profile_labels,
            winners=winning_ids,
        )

        hand_record: Dict[str, Any] = {
            "hand_id": (
                f"{self.session_id}_g{generation}_{self.hands_recorded_count + 1}"
            ),
            "session_id": self.session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "training_engine",
            "generation": generation,
            "candidate_id": candidate_id,
            "candidate_params": candidate_params,
            "small_blind": table.small_blind,
            "big_blind": table.big_blind,
            "community_cards": [
                str(c) for c in table.community_cards
            ],
            "players": [
                {
                    "player_id": p.player_id,
                    "name": p.name,
                    "profile": profile_labels.get(p.player_id, ""),
                    "stack_before": p.stack + payouts.get(p.player_id, 0),
                    "stack_after": p.stack,
                    "hole_cards": (
                        [str(c) for c in p.hole_cards]
                        if p.hole_cards
                        else []
                    ),
                    "is_active": p.is_active,
                }
                for p in table.players
            ],
            "actions": actions_log,
            "winners": winners_data,
            "winning_combination": winning_comb_desc,
            "is_split": is_split,
            "bluffs_detected": bluffs_detected,
            "bluff_count": len(bluffs_detected),
        }

        # 1. Salva no arquivo dedicado da sessão
        with open(self.session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(hand_record, ensure_ascii=False) + "\n")

        # 2. Opcionalmente adiciona ao dataset principal de partidas
        if self.append_to_main_dataset:
            main_dataset_file = get_record_file()
            try:
                with open(main_dataset_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(hand_record, ensure_ascii=False) + "\n")
            except Exception:
                pass

        # 3. Opcionalmente sincroniza com o banco Neon
        if self.save_to_neon_db:
            try:
                save_hand_to_neon(hand_record)
            except Exception:
                pass

        self.hands_recorded_count += 1
        self.total_actions_recorded += len(actions_log)
        self.total_bluffs_recorded += len(bluffs_detected)

        return hand_record

    def get_summary(self) -> Dict[str, Any]:
        """Retorna o resumo estatístico do dataset gerado pelo treino."""
        file_size_bytes = (
            os.path.getsize(self.session_file)
            if self.session_file.exists()
            else 0
        )
        return {
            "session_id": self.session_id,
            "hands_recorded": self.hands_recorded_count,
            "actions_recorded": self.total_actions_recorded,
            "bluffs_recorded": self.total_bluffs_recorded,
            "session_file": str(self.session_file),
            "file_size_kb": round(file_size_bytes / 1024.0, 2),
        }
