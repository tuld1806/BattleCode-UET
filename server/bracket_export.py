"""Excel-compatible (UTF-8-SIG CSV) bracket score export service.

Generates CSV reports with UTF-8 BOM for immediate compatibility with
Microsoft Excel and Google Sheets without Vietnamese character corruption.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from server.models import BracketMatch, GameProfile, Tournament, TournamentEnrollment, User
from server.tournament import calculate_final_scores


def _extract_bracket_standings_and_stages(
    db: Session,
) -> tuple[Dict[int, int], Dict[int, str]]:
    """Analyze completed bracket matches to determine placement rank and stage labels.

    Returns:
        (bracket_standings, stage_labels)
        bracket_standings maps user_id -> rank (1..16)
        stage_labels maps user_id -> Vietnamese stage description
    """
    standings: Dict[int, int] = {}
    stage_labels: Dict[int, str] = {}

    # 1. Final match
    final_match = (
        db.query(BracketMatch)
        .filter(BracketMatch.round_name.ilike("%final%"), BracketMatch.status == "completed")
        .order_by(BracketMatch.id.desc())
        .first()
    )
    if final_match and final_match.winner_id:
        champ_id = final_match.winner_id
        runner_up_id = (
            final_match.player2_id
            if final_match.player1_id == champ_id
            else final_match.player1_id
        )

        standings[champ_id] = 1
        stage_labels[champ_id] = "Vô địch (Champion)"

        if runner_up_id:
            standings[runner_up_id] = 2
            stage_labels[runner_up_id] = "Á quân (Finalist)"

    # 2. Semi-Final matches
    semi_matches = (
        db.query(BracketMatch)
        .filter(BracketMatch.round_name.ilike("%semi%"), BracketMatch.status == "completed")
        .all()
    )
    semi_rank = 3
    for sm in semi_matches:
        if sm.winner_id:
            loser_id = sm.player2_id if sm.player1_id == sm.winner_id else sm.player1_id
            if loser_id and loser_id not in standings:
                standings[loser_id] = semi_rank
                stage_labels[loser_id] = "Bán kết (Top 4)"
                semi_rank += 1

    # 3. Quarter-Final matches
    quarter_matches = (
        db.query(BracketMatch)
        .filter(BracketMatch.round_name.ilike("%quarter%"), BracketMatch.status == "completed")
        .all()
    )
    quarter_rank = 5
    for qm in quarter_matches:
        if qm.winner_id:
            loser_id = qm.player2_id if qm.player1_id == qm.winner_id else qm.player1_id
            if loser_id and loser_id not in standings:
                standings[loser_id] = quarter_rank
                stage_labels[loser_id] = "Tứ kết (Top 8)"
                quarter_rank += 1

    # 4. Round of 16 matches
    r16_matches = (
        db.query(BracketMatch)
        .filter(BracketMatch.round_name.ilike("%16%"), BracketMatch.status == "completed")
        .all()
    )
    r16_rank = 9
    for rm in r16_matches:
        if rm.winner_id:
            loser_id = rm.player2_id if rm.player1_id == rm.winner_id else rm.player1_id
            if loser_id and loser_id not in standings:
                standings[loser_id] = r16_rank
                stage_labels[loser_id] = "Vòng 16 (Top 16)"
                r16_rank += 1

    return standings, stage_labels


def generate_bracket_scores_csv(
    db: Session,
    tournament_id: Optional[int] = None,
) -> str:
    """Generate Excel-compatible UTF-8-SIG CSV string containing tournament final scores.

    Args:
        db: Active SQLAlchemy database session.
        tournament_id: Optional tournament identifier.

    Returns:
        CSV string prefixed with UTF-8 BOM (\\ufeff).
    """
    standings, stage_labels = _extract_bracket_standings_and_stages(db)

    users_data: List[Dict[str, Any]] = []

    if tournament_id is not None:
        tourney = db.query(Tournament).filter(Tournament.id == tournament_id).first()
        if tourney:
            enrollments = (
                db.query(TournamentEnrollment)
                .filter(TournamentEnrollment.tournament_id == tournament_id)
                .all()
            )
            enrolled_user_ids = [e.user_id for e in enrollments]

            # Query enrolled non-admin users
            users = (
                db.query(User)
                .filter(User.id.in_(enrolled_user_ids), User.is_admin == False)  # noqa: E712
                .all()
            )

            # Query per-game Elo for this tournament's game
            profiles = (
                db.query(GameProfile)
                .filter(
                    GameProfile.game_id == tourney.game_id,
                    GameProfile.user_id.in_([u.id for u in users]),
                )
                .all()
            )
            elo_map = {p.user_id: p.elo for p in profiles}

            for u in users:
                users_data.append({
                    "id": u.id,
                    "username": u.username,
                    "elo": elo_map.get(u.id, u.elo if u.elo else 1200),
                })
    else:
        # Global / Default bracket: include non-admin users
        users = (
            db.query(User)
            .filter(User.is_admin == False)  # noqa: E712
            .order_by(User.elo.desc(), User.id.asc())
            .all()
        )
        for u in users:
            users_data.append({
                "id": u.id,
                "username": u.username,
                "elo": u.elo,
            })

    # If users list is empty but we have bracket standings, populate from bracket
    if not users_data and standings:
        bracket_user_ids = list(standings.keys())
        users = db.query(User).filter(User.id.in_(bracket_user_ids)).all()
        for u in users:
            users_data.append({
                "id": u.id,
                "username": u.username,
                "elo": u.elo,
            })

    # Calculate 50% Elo + 50% Bracket composite scores
    final_scores = calculate_final_scores(users_data, standings)

    # Format into CSV buffer
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Thứ hạng",
        "Tên kỳ thủ",
        "Điểm Elo",
        "Điểm Elo chuẩn hóa",
        "Vòng đấu Bracket",
        "Điểm Bracket",
        "Tổng điểm chung cuộc",
    ])

    for row in final_scores:
        u_id = row.get("id")
        writer.writerow([
            row.get("rank", ""),
            row.get("username", ""),
            row.get("elo", 1200),
            f"{row.get('normalized_elo', 0.0):.1f}",
            stage_labels.get(u_id, "Vòng bảng / Tự do"),
            f"{row.get('bracket_score', 0.0):.1f}",
            f"{row.get('final_score', 0.0):.2f}",
        ])

    # Prepend UTF-8 BOM so Microsoft Excel opens it seamlessly without mojibake
    return "\ufeff" + output.getvalue()
