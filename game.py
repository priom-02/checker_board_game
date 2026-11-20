"""Game controller: rules state, turn management, end-of-game detection, and a
background worker so AI agents never freeze the interface."""

import threading
import time
from collections import Counter

import config as C
from board import Board
from minimax import SearchAborted
from move_generator import apply_move, get_legal_moves
from piece import BLACK, PLAYER_NAMES, RED, is_king, opponent


class GameState:
    """The authoritative state of one game.

    Human clicks and AI agents both go through `make_move`, which only accepts
    moves produced by the shared legal-move generator.
    """

    def __init__(self, first_player=None, move_limit=C.ENABLE_MOVE_LIMIT_DRAW):
        if first_player is None:
            first_player = BLACK if C.FIRST_PLAYER == "black" else RED
        self.board = Board()
        self.turn = first_player
        self.move_limit = move_limit
        self.history = []                       # list of (player, move)
        self.captured = {BLACK: 0, RED: 0}      # pieces captured BY each player
        self.position_counts = Counter()
        self.quiet_plies = 0                    # plies without capture or man move
        self.winner = None
        self.is_draw = False
        self.result_reason = ""
        self._legal = None
        self.position_counts[self.position_key()] += 1
        self._check_game_over()

    # ------------------------------------------------------------------
    @property
    def squares(self):
        return self.board.squares

    @property
    def over(self):
        return self.winner is not None or self.is_draw

    def position_key(self):
        """Board + side to move. Together these fully determine the legal moves,
        so equal keys mean the same position *and* the same legal-move situation."""
        return (self.board.key(), self.turn)

    def legal_moves(self):
        if self._legal is None:
            self._legal = get_legal_moves(self.board.squares, self.turn)
        return self._legal

    @property
    def last_move(self):
        return self.history[-1][1] if self.history else None

    # ------------------------------------------------------------------
    def make_move(self, move):
        if self.over:
            raise ValueError("The game is already over.")
        if move not in self.legal_moves():
            raise ValueError(f"Illegal move {move!r} for {PLAYER_NAMES[self.turn]}.")
        # use the generator's own instance (carries the promotion flag)
        move = self.legal_moves()[self.legal_moves().index(move)]

        mover_was_man = not is_king(self.board.squares[move.start])
        self.board.squares = apply_move(self.board.squares, move)
        self.captured[self.turn] += len(move.captures)
        self.history.append((self.turn, move))

        if move.captures or mover_was_man:
            self.quiet_plies = 0
        else:
            self.quiet_plies += 1

        self.turn = opponent(self.turn)
        self._legal = None
        self.position_counts[self.position_key()] += 1
        self._check_game_over()
        return move

    def _check_game_over(self):
        player = self.turn
        name = PLAYER_NAMES[player]
        if self.board.count(player) == 0:
            self.winner = opponent(player)
            self.result_reason = f"{name} has no pieces left"
        elif not self.legal_moves():
            self.winner = opponent(player)
            self.result_reason = f"{name} has no legal moves"
        elif self.position_counts[self.position_key()] >= C.REPETITION_LIMIT:
            self.is_draw = True
            self.result_reason = "Threefold repetition"
        elif self.move_limit and self.quiet_plies >= C.MOVE_LIMIT_PLIES:
            self.is_draw = True
            self.result_reason = f"{C.MOVE_LIMIT_PLIES // 2}-move rule (no capture or man move)"


class AIWorker:
    """Runs `agent.choose_move` on a background thread.

    The search gets a private copy of the board, so the GUI can keep drawing
    while the AI thinks. `cancel()` asks the search to stop early.
    """

    def __init__(self, agent, squares, player, history=None):
        self.agent = agent
        self.player = player
        self.move = None
        self.error = None
        self.elapsed = 0.0
        self.cancelled = False
        self.stop_event = threading.Event()
        self.started_at = time.perf_counter()
        self.history = dict(history or {})
        self.thread = threading.Thread(target=self._run, args=(list(squares),), daemon=True)
        self.thread.start()

    def _run(self, squares):
        t0 = time.perf_counter()
        try:
            self.move = self.agent.choose_move(squares, self.player, self.stop_event, self.history)
        except SearchAborted:
            self.cancelled = True
        except Exception as exc:  # surfaced in the GUI instead of killing the thread silently
            self.error = exc
        self.elapsed = time.perf_counter() - t0

    @property
    def done(self):
        return not self.thread.is_alive()

    def cancel(self):
        self.stop_event.set()
