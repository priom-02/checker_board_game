"""Legal move generation shared by human players and both AI agents.

Boards are flat lists of 64 ints (index = row * 8 + col, row 0 at the top).
Only dark squares, where (row + col) is odd, are ever occupied.

Rules implemented (standard American checkers / English draughts):
  * men move one square diagonally forward, kings in all four diagonals;
  * captures jump an adjacent enemy piece into the empty square behind it;
  * capturing is optional by default; with config.MANDATORY_CAPTURE = True,
    only captures are legal whenever one exists;
  * a capture must be continued while the same piece can keep jumping
    (each returned capture Move is a complete multi-jump sequence);
  * a man reaching the opponent's back row is crowned, and that ends the move.
"""

import config as C
from piece import (
    EMPTY, BLACK, DIRECTIONS, is_king, move_directions, promote, promotion_row,
)

DARK_SQUARES = tuple(r * 8 + c for r in range(8) for c in range(8) if (r + c) % 2 == 1)

# STEP[i][d]: square one diagonal step from i in direction d (-1 if off-board)
# JUMP[i][d]: square two diagonal steps from i in direction d (-1 if off-board)
STEP = [[-1] * 4 for _ in range(64)]
JUMP = [[-1] * 4 for _ in range(64)]
for _sq in DARK_SQUARES:
    _r, _c = divmod(_sq, 8)
    for _d, (_dr, _dc) in enumerate(DIRECTIONS):
        if 0 <= _r + _dr < 8 and 0 <= _c + _dc < 8:
            STEP[_sq][_d] = (_r + _dr) * 8 + _c + _dc
        if 0 <= _r + 2 * _dr < 8 and 0 <= _c + 2 * _dc < 8:
            JUMP[_sq][_d] = (_r + 2 * _dr) * 8 + _c + 2 * _dc


def square_name(index):
    """Human readable square name, e.g. 'c3' (a-h left to right, 8-1 top to bottom)."""
    r, c = divmod(index, 8)
    return f"{'abcdefgh'[c]}{8 - r}"


class Move:
    """A complete move: the squares visited and the squares captured."""

    __slots__ = ("path", "captures", "promotes")

    def __init__(self, path, captures=(), promotes=False):
        self.path = tuple(path)
        self.captures = tuple(captures)
        self.promotes = promotes

    @property
    def start(self):
        return self.path[0]

    @property
    def end(self):
        return self.path[-1]

    @property
    def is_capture(self):
        return bool(self.captures)

    def __eq__(self, other):
        return isinstance(other, Move) and self.path == other.path and self.captures == other.captures

    def __hash__(self):
        return hash((self.path, self.captures))

    def __repr__(self):
        sep = "x" if self.captures else "-"
        return sep.join(square_name(s) for s in self.path)


# ---------------------------------------------------------------------------
# Capture generation
# ---------------------------------------------------------------------------
def _piece_jumps(squares, start, player):
    """All complete jump sequences for the piece on `start` (board unchanged on return)."""
    piece = squares[start]
    dirs = move_directions(piece)
    king = is_king(piece)
    crown_row = promotion_row(player)
    results = []
    path = [start]
    caps = []

    # Lift the piece so a king may pass back over its starting square.
    squares[start] = EMPTY

    def extend(pos):
        extended = False
        for d in dirs:
            land = JUMP[pos][d]
            if land < 0:
                continue
            mid = STEP[pos][d]
            if squares[mid] * player < 0 and squares[land] == EMPTY and mid not in caps:
                extended = True
                path.append(land)
                caps.append(mid)
                if not king and land >> 3 == crown_row:
                    # Crowning ends the move, even if more jumps would be possible.
                    results.append(Move(path, caps, True))
                else:
                    extend(land)
                path.pop()
                caps.pop()
        if not extended and len(path) > 1:
            results.append(Move(path, caps, False))

    try:
        extend(start)
    finally:
        squares[start] = piece
    return results


def _can_jump(squares, sq, player):
    piece = squares[sq]
    for d in move_directions(piece):
        land = JUMP[sq][d]
        if land >= 0 and squares[land] == EMPTY and squares[STEP[sq][d]] * player < 0:
            return True
    return False


def get_captures(squares, player):
    """All capture sequences available to `player` (empty list if none)."""
    moves = []
    for sq in DARK_SQUARES:
        if squares[sq] * player > 0 and _can_jump(squares, sq, player):
            moves.extend(_piece_jumps(squares, sq, player))
    return moves


def get_simple_moves(squares, player):
    """Non-capturing one-step moves."""
    moves = []
    crown_row = promotion_row(player)
    for sq in DARK_SQUARES:
        piece = squares[sq]
        if piece * player <= 0:
            continue
        king = is_king(piece)
        for d in move_directions(piece):
            to = STEP[sq][d]
            if to >= 0 and squares[to] == EMPTY:
                moves.append(Move((sq, to), (), (not king) and (to >> 3) == crown_row))
    return moves


def get_legal_moves(squares, player, mandatory_capture=None):
    """Every legal move for `player` (captures listed first).

    If capturing is mandatory (config.MANDATORY_CAPTURE, or the argument) and a
    capture exists, only captures are returned."""
    if mandatory_capture is None:
        mandatory_capture = C.MANDATORY_CAPTURE
    captures = get_captures(squares, player)
    if captures and mandatory_capture:
        return captures
    return captures + get_simple_moves(squares, player)


def apply_move(squares, move):
    """Return a new board with `move` played (the input board is not modified)."""
    board = list(squares)
    piece = board[move.path[0]]
    board[move.path[0]] = EMPTY
    for c in move.captures:
        board[c] = EMPTY
    board[move.path[-1]] = promote(piece) if move.promotes else piece
    return board


def apply_partial(squares, path):
    """Board after the first hops of a capture sequence (used to show a human's
    multi-jump in progress). `path` is a prefix of a capture Move's path."""
    board = list(squares)
    if len(path) < 2:
        return board
    piece = board[path[0]]
    board[path[0]] = EMPTY
    for a, b in zip(path, path[1:]):
        board[(a + b) // 2] = EMPTY      # jumped square is the midpoint
    board[path[-1]] = piece
    return board


def count_pieces(squares, player):
    return sum(1 for sq in DARK_SQUARES if squares[sq] * player > 0)


def initial_squares():
    """Red on rows 0-2 (top), Black on rows 5-7 (bottom), dark squares only."""
    board = [EMPTY] * 64
    for sq in DARK_SQUARES:
        r = sq >> 3
        if r <= 2:
            board[sq] = -1
        elif r >= 5:
            board[sq] = BLACK
    return board
