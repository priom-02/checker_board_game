"""Minimax search with Alpha-Beta Pruning.

Features
  * classic Minimax: the AI (MAX) picks the move with the best score, assuming
    the opponent (MIN) always answers with the move that is worst for the AI;
  * Alpha-Beta Pruning: branches that cannot change the decision are skipped;
  * configurable search depth, searched with iterative deepening (depth 1, 2,
    ... N) so the best move of the previous iteration is searched first;
  * move ordering: previous best move (transposition table), then the
    longest captures, then promotions - good ordering makes pruning effective;
  * capture extension (quiescence): at the depth limit, pending captures are
    still resolved so the heuristic is never applied mid-exchange (when
    capturing is optional, declining the capture is also considered);
  * repetition awareness: a position that already occurred in the game is
    scored as a draw, so the side that is ahead keeps making progress instead
    of drifting into a threefold-repetition draw.
"""

import random
import time

import config as C
from config import QUIESCENCE_DEPTH
from evaluation import WIN_SCORE, evaluate
from move_generator import apply_move, get_captures, get_legal_moves

INF = float("inf")
WIN_THRESHOLD = WIN_SCORE - 1000
EXACT, LOWER, UPPER = 0, 1, 2


class SearchAborted(Exception):
    """Raised inside a search when the caller asked it to stop."""


class MinimaxAgent:
    algorithm = "Minimax + Alpha-Beta"

    def __init__(self, depth, quiescence_depth=QUIESCENCE_DEPTH, randomize=True, seed=None):
        self.depth = depth
        self.quiescence_depth = quiescence_depth
        self.randomize = randomize
        self.rng = random.Random(seed)
        self.last_stats = {}

    @property
    def label(self):
        return f"Minimax α-β (depth {self.depth})"

    @property
    def short_label(self):
        return "Minimax"

    # ------------------------------------------------------------------
    def choose_move(self, squares, player, stop_event=None, history=None):
        """Return the best legal move for `player`, or None if there is none.

        `history` optionally maps (board tuple, side to move) -> occurrences
        in the game so far (GameState.position_counts)."""
        t0 = time.perf_counter()
        moves = get_legal_moves(squares, player)
        self.last_stats = {"nodes": 0, "depth": 0, "score": 0, "time": 0.0}
        if not moves:
            return None
        if len(moves) == 1:              # forced move: nothing to search
            self.last_stats.update(depth=0, time=time.perf_counter() - t0, forced=True)
            return moves[0]

        self.root_player = player
        self.stop_event = stop_event
        self.history = history or {}
        self.nodes = 0
        self.tt = {}

        root_moves = list(moves)
        if self.randomize:
            self.rng.shuffle(root_moves)     # vary play among equally good moves
        root_moves.sort(key=self._order_key, reverse=True)

        best_move, best_score, reached = root_moves[0], -INF, 0
        for depth in range(1, self.depth + 1):
            score, move = self._search_root(squares, player, depth, root_moves)
            best_move, best_score, reached = move, score, depth
            root_moves.remove(move)
            root_moves.insert(0, move)
            if abs(score) >= WIN_THRESHOLD:  # forced win/loss found
                break

        self.last_stats = {
            "nodes": self.nodes,
            "depth": reached,
            "score": best_score,
            "time": time.perf_counter() - t0,
        }
        return best_move

    # ------------------------------------------------------------------
    @staticmethod
    def _order_key(move):
        return (len(move.captures), move.promotes)

    def _search_root(self, squares, player, depth, moves):
        alpha, beta = -INF, INF
        best_score, best_move = -INF, moves[0]
        for move in moves:
            child = apply_move(squares, move)
            score = self._minimax(child, -player, depth - 1, alpha, beta, False, 1)
            if score > best_score:
                best_score, best_move = score, move
            alpha = max(alpha, score)
        return best_score, best_move

    def _check_stop(self):
        self.nodes += 1
        if self.nodes & 1023 == 0 and self.stop_event is not None and self.stop_event.is_set():
            raise SearchAborted()

    def _minimax(self, squares, to_move, depth, alpha, beta, maximizing, ply):
        """Value of the position for the root player (MAX)."""
        self._check_stop()

        if depth <= 0:
            return self._quiesce(squares, to_move, alpha, beta, maximizing, ply, self.quiescence_depth)

        key = (tuple(squares), to_move)
        if key in self.history:
            return 0                         # repeating an earlier position = draw
        entry = self.tt.get(key)
        tt_move = None
        if entry is not None:
            e_depth, e_value, e_flag, tt_move = entry
            if e_depth >= depth:
                value = self._from_tt(e_value, ply)
                if e_flag == EXACT:
                    return value
                if e_flag == LOWER and value >= beta:
                    return value
                if e_flag == UPPER and value <= alpha:
                    return value

        moves = get_legal_moves(squares, to_move)
        if not moves:
            # The side to move is stuck (or has no pieces) and loses.
            # Faster wins / slower losses are preferred via `ply`.
            return -WIN_SCORE + ply if to_move == self.root_player else WIN_SCORE - ply

        moves.sort(key=self._order_key, reverse=True)
        if tt_move is not None and tt_move in moves:
            moves.remove(tt_move)
            moves.insert(0, tt_move)

        alpha0, beta0 = alpha, beta
        best_move = moves[0]
        if maximizing:
            value = -INF
            for move in moves:
                score = self._minimax(apply_move(squares, move), -to_move, depth - 1,
                                      alpha, beta, False, ply + 1)
                if score > value:
                    value, best_move = score, move
                alpha = max(alpha, value)
                if alpha >= beta:
                    break                    # beta cut-off: MIN will avoid this branch
        else:
            value = INF
            for move in moves:
                score = self._minimax(apply_move(squares, move), -to_move, depth - 1,
                                      alpha, beta, True, ply + 1)
                if score < value:
                    value, best_move = score, move
                beta = min(beta, value)
                if alpha >= beta:
                    break                    # alpha cut-off: MAX will avoid this branch

        if value <= alpha0:
            flag = UPPER
        elif value >= beta0:
            flag = LOWER
        else:
            flag = EXACT
        self.tt[key] = (depth, self._to_tt(value, ply), flag, best_move)
        return value

    def _quiesce(self, squares, to_move, alpha, beta, maximizing, ply, qdepth):
        """At the horizon: keep resolving pending captures, then evaluate.

        When capturing is optional the side to move may also decline every
        capture, so the static score ("stand pat") is a valid option too."""
        captures = get_captures(squares, to_move) if qdepth > 0 else None
        if not captures:
            return evaluate(squares, self.root_player)
        captures.sort(key=self._order_key, reverse=True)
        stand_pat = None if C.MANDATORY_CAPTURE else evaluate(squares, self.root_player)
        if maximizing:
            value = -INF
            if stand_pat is not None:
                value = stand_pat
                alpha = max(alpha, value)
                if alpha >= beta:
                    return value
            for move in captures:
                self._check_stop()
                value = max(value, self._quiesce(apply_move(squares, move), -to_move,
                                                 alpha, beta, False, ply + 1, qdepth - 1))
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
        else:
            value = INF
            if stand_pat is not None:
                value = stand_pat
                beta = min(beta, value)
                if alpha >= beta:
                    return value
            for move in captures:
                self._check_stop()
                value = min(value, self._quiesce(apply_move(squares, move), -to_move,
                                                 alpha, beta, True, ply + 1, qdepth - 1))
                beta = min(beta, value)
                if alpha >= beta:
                    break
        return value

    # Win scores are stored relative to the node so they stay correct when the
    # same position is reached at a different distance from the root.
    @staticmethod
    def _to_tt(value, ply):
        if value >= WIN_THRESHOLD:
            return value + ply
        if value <= -WIN_THRESHOLD:
            return value - ply
        return value

    @staticmethod
    def _from_tt(value, ply):
        if value >= WIN_THRESHOLD:
            return value - ply
        if value <= -WIN_THRESHOLD:
            return value + ply
        return value
