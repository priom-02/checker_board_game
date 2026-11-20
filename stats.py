"""Recording and summarising AI vs AI results.

Every completed AI vs AI game (from the GUI or from benchmark.py) is appended
to results/ai_vs_ai_games.csv. All summaries are computed from those rows,
so every reported number comes from games that were actually played.
"""

import csv
import os
import time
from collections import OrderedDict

import config as C

RESULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), C.RESULTS_DIR, "ai_vs_ai_games.csv")

FIELDS = [
    "timestamp", "source", "difficulty", "minimax_depth", "mcts_simulations",
    "capture_rule", "minimax_color", "winner", "reason", "plies",
    "minimax_moves", "minimax_total_time", "mcts_moves", "mcts_total_time",
]


def make_record(source, difficulty, minimax_agent, mcts_agent, minimax_color, game,
                minimax_times, mcts_times):
    if game.is_draw:
        winner = "draw"
    elif game.winner == minimax_color:
        winner = "minimax"
    else:
        winner = "mcts"
    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "difficulty": difficulty,
        "minimax_depth": minimax_agent.depth,
        "mcts_simulations": mcts_agent.simulations,
        "capture_rule": "mandatory" if C.MANDATORY_CAPTURE else "optional",
        "minimax_color": "black" if minimax_color == 1 else "red",
        "winner": winner,
        "reason": game.result_reason,
        "plies": len(game.history),
        "minimax_moves": len(minimax_times),
        "minimax_total_time": round(sum(minimax_times), 4),
        "mcts_moves": len(mcts_times),
        "mcts_total_time": round(sum(mcts_times), 4),
    }


def append_record(record, path=RESULTS_FILE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(record)


def load_records(path=RESULTS_FILE):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarize(records):
    """Aggregate rows into per-difficulty statistics."""
    groups = OrderedDict((d, []) for d in C.DIFFICULTIES)
    for row in records:
        groups.setdefault(row["difficulty"], []).append(row)
    out = OrderedDict()
    for diff, rows in groups.items():
        if not rows:
            continue
        n = len(rows)
        mm_w = sum(r["winner"] == "minimax" for r in rows)
        mc_w = sum(r["winner"] == "mcts" for r in rows)
        dr = sum(r["winner"] == "draw" for r in rows)
        mm_moves = sum(int(r["minimax_moves"]) for r in rows)
        mc_moves = sum(int(r["mcts_moves"]) for r in rows)
        mm_time = sum(float(r["minimax_total_time"]) for r in rows)
        mc_time = sum(float(r["mcts_total_time"]) for r in rows)
        out[diff] = {
            "games": n,
            "minimax_wins": mm_w,
            "mcts_wins": mc_w,
            "draws": dr,
            "minimax_win_rate": mm_w / n,
            "mcts_win_rate": mc_w / n,
            "draw_rate": dr / n,
            "minimax_avg_time": mm_time / mm_moves if mm_moves else 0.0,
            "mcts_avg_time": mc_time / mc_moves if mc_moves else 0.0,
            "avg_plies": sum(int(r["plies"]) for r in rows) / n,
            "settings": f"Minimax depth {rows[0]['minimax_depth']} vs MCTS {rows[0]['mcts_simulations']} sims",
        }
    return out


def format_table(summary):
    lines = [
        f"{'Difficulty':<10} {'Games':>5} {'Minimax win':>12} {'MCTS win':>9} {'Draw':>7} "
        f"{'Minimax avg t':>14} {'MCTS avg t':>11} {'Avg plies':>10}",
        "-" * 86,
    ]
    for diff, s in summary.items():
        lines.append(
            f"{diff:<10} {s['games']:>5} {s['minimax_win_rate']:>11.1%} {s['mcts_win_rate']:>9.1%} "
            f"{s['draw_rate']:>7.1%} {s['minimax_avg_time']:>13.3f}s {s['mcts_avg_time']:>10.3f}s "
            f"{s['avg_plies']:>10.1f}"
        )
    return "\n".join(lines)
