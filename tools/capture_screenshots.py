"""Generate presentation screenshots of the game.

    python tools/capture_screenshots.py

Each scene is set up through the real game code (GameState, legal-move
generator, AI agents and the UI) and saved under screenshots/, grouped in the
same order as the project slides. Board-only crops are saved as well.
"""

import os
import sys
import time
import warnings

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"       # no sound while capturing
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

import config as C  # noqa: E402
import stats  # noqa: E402
import ui  # noqa: E402
from board import square_center  # noqa: E402
from move_generator import Move  # noqa: E402
from piece import BLACK, BLACK_KING, BLACK_MAN, RED, RED_KING, RED_MAN  # noqa: E402

OUT = os.path.join(ROOT, "screenshots")
BOARD_CROP = pygame.Rect(C.FRAME_X, C.FRAME_Y, C.FRAME_SIZE, C.FRAME_SIZE)
INDEX = []          # (folder, file, description) for the README


def sq(name):
    """'c3' -> board index (columns a-h, rank 8 at the top)."""
    return (8 - int(name[1])) * 8 + "abcdefgh".index(name[0])


def click(app, name):
    app.on_board_click(square_center(sq(name)))


def set_position(app, pieces, turn):
    """Put a custom position on the board of the current game."""
    g = app.game
    b = [0] * 64
    for name, p in pieces.items():
        b[sq(name)] = p
    g.board.squares = b
    g.turn = turn
    g._legal = None
    g.history.clear()
    g.position_counts.clear()
    g.position_counts[g.position_key()] += 1
    g.winner, g.is_draw, g.result_reason = None, False, ""
    g._check_game_over()
    app.selected_path = []
    app.anim = None


def save(app, folder, name, desc, board_crop=False):
    draw = {"menu": app.draw_menu, "setup": app.draw_setup, "game": app.draw_game}[app.screen_name]
    draw((-1, -1))
    path = os.path.join(OUT, folder)
    os.makedirs(path, exist_ok=True)
    pygame.image.save(app.screen, os.path.join(path, name))
    INDEX.append((folder, name, desc))
    if board_crop:
        if app.screen_name == "game" and app.game.over:
            # final position without the result box covering it
            app.renderer.draw(app.screen, app.game.squares, last_move=app.game.last_move)
        crop_name = f"{folder[:2]}_{name}"           # e.g. 04_01_single_capture.png
        crops = os.path.join(OUT, "09_board_only")
        os.makedirs(crops, exist_ok=True)
        pygame.image.save(app.screen.subsurface(BOARD_CROP), os.path.join(crops, crop_name))
        INDEX.append(("09_board_only", crop_name, f"Board only: {desc}"))
    print(f"  {folder}/{name}")


def finish_ai_wait(app, cond, timeout=120):
    t0 = time.time()
    while not cond() and time.time() - t0 < timeout:
        app.update_game()
        time.sleep(0.01)


def new_mode(app, mode, difficulty="Medium", color=BLACK):
    app.handle_action(("menu",))
    app.handle_action(("mode", mode))
    if mode != ui.HVH:
        app.handle_action(("difficulty", difficulty))
        app.handle_action(("color", color))
        app.handle_action(("start",))


def main():
    stats.append_record = lambda *a, **k: None   # demo games must not change the results file
    app = ui.App()

    # 01 - Menus ------------------------------------------------------------
    f = "01_menus"
    save(app, f, "01_main_menu.png", "Main menu with the three game modes")
    app.handle_action(("mode", ui.HVAI))
    app.handle_action(("difficulty", "Medium"))
    save(app, f, "02_human_vs_ai_setup.png", "Human vs AI setup: difficulty and colour choice")
    app.handle_action(("menu",))
    app.handle_action(("mode", ui.AIVAI))
    app.handle_action(("difficulty", "Hard"))
    save(app, f, "03_ai_vs_ai_setup.png", "AI vs AI setup: Minimax depth vs MCTS simulations")

    # 02 - Board ------------------------------------------------------------
    f = "02_board_and_pieces"
    new_mode(app, ui.HVH)
    save(app, f, "01_starting_position.png", "8x8 board, 12 pieces per player on dark squares", True)
    set_position(app, {"b8": RED_MAN, "f8": RED_KING, "c5": RED_MAN, "e3": BLACK_KING,
                       "b2": BLACK_MAN, "g3": BLACK_MAN}, BLACK)
    save(app, f, "02_ordinary_pieces_and_kings.png", "The two piece types: ordinary pieces and Kings (crowned)", True)

    # 03 - Movement ---------------------------------------------------------
    f = "03_movement"
    new_mode(app, ui.HVH)
    click(app, "c3")
    save(app, f, "01_ordinary_piece_moves_forward.png",
         "Selected ordinary piece: white rings show its diagonal forward moves", True)
    set_position(app, {"d4": BLACK_KING, "b8": RED_MAN, "h8": RED_MAN, "a1": BLACK_MAN}, BLACK)
    click(app, "d4")
    save(app, f, "02_king_moves_both_directions.png", "A King moves diagonally forward and backward", True)

    # 04 - Captures ---------------------------------------------------------
    f = "04_captures"
    set_position(app, {"c3": BLACK_MAN, "d4": RED_MAN, "g3": BLACK_MAN, "a1": BLACK_MAN,
                       "b8": RED_MAN, "f8": RED_MAN, "h6": RED_MAN}, BLACK)
    click(app, "c3")
    save(app, f, "01_single_capture_options.png",
         "Single capture: coral ring = jump target, X = piece that will be captured", True)
    g = app.game
    g.make_move(Move((sq("c3"), sq("e5")), (sq("d4"),)))
    save(app, f, "02_single_capture_done.png", "After the capture: the jumped piece is removed", True)

    set_position(app, {"a1": BLACK_MAN, "b2": RED_MAN, "d4": RED_MAN, "f6": RED_MAN,
                       "g1": BLACK_MAN, "b8": RED_MAN, "h8": RED_MAN}, BLACK)
    click(app, "a1")
    save(app, f, "03_multiple_capture_step1.png", "Multiple capture, step 1: first jump available", True)
    click(app, "c3")
    save(app, f, "04_multiple_capture_step2.png", "Multiple capture, step 2: the same piece must keep jumping", True)
    click(app, "e5")
    click(app, "g7")
    save(app, f, "05_multiple_capture_done.png", "Three pieces captured in one turn", True)

    set_position(app, {"e5": BLACK_KING, "d4": RED_MAN, "f6": RED_MAN, "b8": RED_MAN, "a1": BLACK_MAN}, BLACK)
    click(app, "e5")
    save(app, f, "06_king_captures_both_directions.png",
         "A King captures forward and backward", True)

    set_position(app, {"c3": BLACK_MAN, "d4": RED_MAN, "g3": BLACK_MAN, "a1": BLACK_MAN,
                       "b8": RED_MAN, "f8": RED_MAN}, BLACK)
    click(app, "g3")
    save(app, f, "07_capture_is_optional.png",
         "Capturing is optional: another piece can make a normal move instead", True)

    # 05 - King promotion ---------------------------------------------------
    f = "05_king_promotion"
    set_position(app, {"c7": BLACK_MAN, "f8": RED_MAN, "a3": BLACK_MAN, "e5": RED_MAN, "h6": RED_MAN}, BLACK)
    click(app, "c7")
    save(app, f, "01_before_promotion.png", "A piece about to reach the opponent's back row", True)
    click(app, "d8")
    save(app, f, "02_after_promotion.png", "Promoted to King on the back row", True)

    # 06 - Game modes -------------------------------------------------------
    f = "06_game_modes"
    new_mode(app, ui.HVH)
    for a, b in (("c3", "d4"), ("f6", "e5"), ("g3", "h4")):
        click(app, a)
        click(app, b)
    save(app, f, "01_human_vs_human.png", "Human vs Human: two players take turns with the mouse")

    new_mode(app, ui.HVAI, "Medium", BLACK)
    for a, b in (("c3", "d4"), ("g3", "f4")):
        click(app, a)
        click(app, b)
        finish_ai_wait(app, lambda: app.game.turn == BLACK and not app.anim and app.worker is None)
    save(app, f, "02_human_vs_ai.png", "Human vs AI (Minimax + Alpha-Beta, Medium)")

    new_mode(app, ui.AIVAI, "Hard", BLACK)
    app.handle_action(("toggle_run",))
    finish_ai_wait(app, lambda: len(app.game.history) >= 10 and app.worker is not None and not app.anim)
    save(app, f, "03_ai_vs_ai_thinking.png", "AI vs AI: Minimax vs MCTS, the active agent is thinking")
    app.handle_action(("toggle_run",))
    finish_ai_wait(app, lambda: app.worker is None or app.worker.done, timeout=20)
    save(app, f, "04_ai_vs_ai_paused.png", "AI vs AI paused (Resume / Reset controls)")
    app.handle_action(("toggle_run",))
    finish_ai_wait(app, lambda: app.game.over and not app.anim, timeout=900)
    app.update_game()
    save(app, f, "05_ai_vs_ai_finished.png", "AI vs AI finished: winner and session results")

    # 07 - Terminal states --------------------------------------------------
    f = "07_terminal_states"
    new_mode(app, ui.HVH)
    set_position(app, {"c3": BLACK_MAN, "d4": RED_MAN, "e1": BLACK_KING}, BLACK)
    app.game.make_move(Move((sq("c3"), sq("e5")), (sq("d4"),)))
    save(app, f, "01_win_all_pieces_captured.png", "Win: the opponent has lost all pieces", True)

    set_position(app, {"b8": RED_MAN, "a7": BLACK_MAN, "c7": BLACK_MAN, "e5": BLACK_MAN,
                       "c3": BLACK_MAN}, BLACK)
    app.game.make_move(Move((sq("e5"), sq("d6"))))
    save(app, f, "02_win_no_legal_moves.png", "Win: the opponent has no legal moves (blocked)", True)

    set_position(app, {"b8": RED_KING, "f6": RED_KING, "b2": BLACK_KING, "h2": BLACK_KING}, BLACK)
    for _ in range(2):
        for a, b in (("b2", "a3"), ("b8", "a7"), ("a3", "b2"), ("a7", "b8")):
            app.game.make_move(Move((sq(a), sq(b))))
    save(app, f, "03_draw_threefold_repetition.png", "Draw: the same position occurred three times", True)

    new_mode(app, ui.HVAI, "Easy", BLACK)
    set_position(app, {"c3": BLACK_MAN, "b4": RED_MAN, "h8": RED_MAN}, RED)
    app.game.make_move(Move((sq("b4"), sq("d2")), (sq("c3"),)))
    save(app, f, "04_human_vs_ai_you_lose.png", "Human vs AI: loss screen")

    new_mode(app, ui.HVAI, "Easy", BLACK)
    set_position(app, {"c3": BLACK_MAN, "d4": RED_MAN, "h8": BLACK_MAN}, BLACK)
    click(app, "c3")
    click(app, "e5")
    save(app, f, "05_human_vs_ai_you_win.png", "Human vs AI: win screen")

    # 08 - Results ----------------------------------------------------------
    draw_results_table(app)

    write_index()
    app._cancel_worker()
    pygame.quit()


def draw_results_table(app):
    """Render the measured AI vs AI statistics (from results/ai_vs_ai_games.csv)."""
    records = [r for r in stats.load_records()
               if r.get("source") == "benchmark" and r.get("capture_rule", "optional") == "optional"]
    summary = stats.summarize(records)
    if not summary:
        print("  (no AI vs AI results recorded - skipping results table)")
        return
    s = app.screen
    s.fill(C.BG_COLOR)
    ui.draw_decor(s)
    ui.draw_text(s, "AI vs AI Results", 40, C.TITLE_BLUE, (C.WINDOW_WIDTH // 2, 50), bold=True, anchor="midtop")
    ui.draw_text(s, "Minimax + Alpha-Beta vs Monte Carlo Tree Search (benchmark.py, completed games only)",
                 18, C.ACCENT_CORAL, (C.WINDOW_WIDTH // 2, 104), bold=True, anchor="midtop")
    headers = ["Difficulty", "Games", "Minimax win", "MCTS win", "Draw", "Minimax time", "MCTS time"]
    widths = [170, 90, 130, 110, 90, 140, 130]
    x0 = (C.WINDOW_WIDTH - sum(widths)) // 2
    y = 170
    row_h = 56

    def row(values, y, header=False):
        x = x0
        bg = C.BUTTON_BG if header else C.PANEL_BG
        pygame.draw.rect(s, bg, pygame.Rect(x0, y, sum(widths), row_h))
        pygame.draw.rect(s, C.PANEL_BORDER, pygame.Rect(x0, y, sum(widths), row_h), 1)
        for i, (v, w) in enumerate(zip(values, widths)):
            col = C.BUTTON_TEXT if header else C.TEXT_DARK
            cy = y + row_h // 2 - (8 if (i == 0 and not header) else 0)
            ui.draw_text(s, v, 18, col, (x + w // 2, cy), bold=True, anchor="center")
            x += w

    row(headers, y, header=True)
    for diff, st in summary.items():
        y += row_h
        cfg = C.AI_VS_AI[diff]
        row([f"{diff}", str(st["games"]), f"{st['minimax_win_rate']:.0%}", f"{st['mcts_win_rate']:.0%}",
             f"{st['draw_rate']:.0%}", f"{st['minimax_avg_time']:.3f} s", f"{st['mcts_avg_time']:.3f} s"], y)
        ui.draw_text(s, f"d{cfg['minimax_depth']} vs {cfg['mcts_simulations']:,} sims", 12, C.TEXT_MUTED,
                     (x0 + widths[0] // 2, y + row_h - 12), bold=True, anchor="center")
    total = sum(st["games"] for st in summary.values())
    ui.draw_text(s, f"{total} games in total, colours alternated every game. Times are average seconds per move.",
                 16, C.TEXT_MUTED, (C.WINDOW_WIDTH // 2, y + row_h + 30), bold=True, anchor="midtop")
    folder = "08_results"
    os.makedirs(os.path.join(OUT, folder), exist_ok=True)
    pygame.image.save(s, os.path.join(OUT, folder, "01_ai_vs_ai_results_table.png"))
    INDEX.append((folder, "01_ai_vs_ai_results_table.png", "Measured AI vs AI results table"))
    print(f"  {folder}/01_ai_vs_ai_results_table.png")


SECTION_TITLES = {
    "01_menus": "Menus and game setup",
    "02_board_and_pieces": "Board and pieces (slides 1-2)",
    "03_movement": "Movement of the pieces (slides 3, 7)",
    "04_captures": "Single and multiple captures (slides 4, 5, 8)",
    "05_king_promotion": "King promotion (slide 6)",
    "06_game_modes": "Game modes (slide 13)",
    "07_terminal_states": "Terminal states: win, loss, draw (slides 9-11)",
    "08_results": "AI vs AI results",
    "09_board_only": "Board-only crops (for placing next to slide text)",
}


def write_index():
    lines = ["# Game Screenshots", "",
             "Generated by `python tools/capture_screenshots.py` from the game code itself.",
             f"Full screenshots are {C.WINDOW_WIDTH}x{C.WINDOW_HEIGHT} px; "
             f"board-only crops are {C.FRAME_SIZE}x{C.FRAME_SIZE} px.", ""]
    current = None
    for folder, name, desc in INDEX:
        if folder != current:
            current = folder
            lines += ["", f"## {folder} - {SECTION_TITLES.get(folder, '')}", "",
                      "| File | Shows |", "|---|---|"]
        lines.append(f"| [{name}]({folder}/{name}) | {desc} |")
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    print(f"Saving screenshots to {OUT}")
    main()
    print("Done.")
