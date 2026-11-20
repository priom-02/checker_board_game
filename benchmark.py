"""Headless AI vs AI experiments: Minimax + Alpha-Beta vs MCTS.

Plays real games with the same rules engine as the GUI, alternating colours
every game, and reports win rate, draw rate, average decision time and number
of games. Each game is appended to results/ai_vs_ai_games.csv.

    python benchmark.py --games 20                 # all difficulties
    python benchmark.py --difficulty Hard --games 10
    python benchmark.py --summary                  # summarise every recorded game
"""

import argparse
import os
import sys
import time
import warnings

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
warnings.filterwarnings("ignore", category=UserWarning)

import config as C  # noqa: E402
import stats  # noqa: E402
from game import GameState  # noqa: E402
from mcts import MCTSAgent  # noqa: E402
from minimax import MinimaxAgent  # noqa: E402
from piece import BLACK, RED, opponent  # noqa: E402


def play_game(difficulty, minimax_color, seed):
    cfg = C.AI_VS_AI[difficulty]
    minimax = MinimaxAgent(cfg["minimax_depth"], seed=seed)
    mcts = MCTSAgent(cfg["mcts_simulations"], seed=seed)
    agents = {minimax_color: minimax, opponent(minimax_color): mcts}
    times = {BLACK: [], RED: []}

    game = GameState()
    while not game.over:
        player = game.turn
        t0 = time.perf_counter()
        move = agents[player].choose_move(list(game.squares), player, None, dict(game.position_counts))
        times[player].append(time.perf_counter() - t0)
        game.make_move(move)          # raises if an agent ever returns an illegal move

    return stats.make_record("benchmark", difficulty, minimax, mcts, minimax_color, game,
                             times[minimax_color], times[opponent(minimax_color)])


def keep_awake(enable):
    """Stop Windows from sleeping during a benchmark (a sleep would make the
    measured decision times meaningless). No effect on other systems."""
    if sys.platform != "win32":
        return
    import ctypes
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED if enable else ES_CONTINUOUS
    ctypes.windll.kernel32.SetThreadExecutionState(flags)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--difficulty", default="all", help="Easy, Medium, Hard or all")
    parser.add_argument("--games", type=int, default=10, help="games per difficulty")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-save", action="store_true", help="do not append to the results CSV")
    parser.add_argument("--summary", action="store_true", help="only summarise the results CSV")
    args = parser.parse_args()

    if args.summary:
        records = stats.load_records()
        if not records:
            print(f"No recorded games in {stats.RESULTS_FILE}")
            return
        print(f"All recorded AI vs AI games ({stats.RESULTS_FILE}):\n")
        print(stats.format_table(stats.summarize(records)))
        return

    if args.difficulty.lower() == "all":
        difficulties = C.DIFFICULTIES
    else:
        difficulties = [d for d in C.DIFFICULTIES if d.lower() == args.difficulty.lower()]
        if not difficulties:
            sys.exit(f"Unknown difficulty {args.difficulty!r}")

    keep_awake(True)
    try:
        run_records = run(difficulties, args)
    finally:
        keep_awake(False)

    print("\nResults of this run (computed from the games above):\n")
    print(stats.format_table(stats.summarize(run_records)))


def run(difficulties, args):
    run_records = []
    for diff in difficulties:
        cfg = C.AI_VS_AI[diff]
        print(f"\n== {diff}: Minimax depth {cfg['minimax_depth']} vs MCTS {cfg['mcts_simulations']} simulations ==")
        for i in range(args.games):
            minimax_color = BLACK if i % 2 == 0 else RED
            t0 = time.perf_counter()
            rec = play_game(diff, minimax_color, args.seed + i)
            run_records.append(rec)
            if not args.no_save:
                stats.append_record(rec)
            print(f"  game {i + 1:>3}: minimax={rec['minimax_color']:<5} winner={rec['winner']:<7} "
                  f"plies={rec['plies']:>3}  ({rec['reason']})  {time.perf_counter() - t0:.1f}s", flush=True)
    return run_records


if __name__ == "__main__":
    main()
