"""Piece and King logic.

Pieces are stored as small integers so that the AI can copy and scan boards
quickly:

    0  empty square
    1  black man        2  black king
   -1  red man         -2  red king

The sign of a piece is its owner (BLACK = +1, RED = -1).
Black starts at the bottom of the board (rows 5-7) and moves up;
Red starts at the top (rows 0-2) and moves down.
"""

EMPTY = 0
BLACK = 1
RED = -1

BLACK_MAN = 1
BLACK_KING = 2
RED_MAN = -1
RED_KING = -2

PLAYER_NAMES = {BLACK: "Black", RED: "Red"}

# Diagonal directions, indexed 0..3 as (row delta, column delta).
DIRECTIONS = ((-1, -1), (-1, 1), (1, -1), (1, 1))
UP_DIRS = (0, 1)          # towards row 0  (forward for Black)
DOWN_DIRS = (2, 3)        # towards row 7  (forward for Red)
ALL_DIRS = (0, 1, 2, 3)   # kings move both forward and backward


def owner(piece):
    """Return BLACK, RED or EMPTY for a piece code."""
    if piece > 0:
        return BLACK
    if piece < 0:
        return RED
    return EMPTY


def opponent(player):
    return -player


def is_king(piece):
    return piece == BLACK_KING or piece == RED_KING


def man_of(player):
    return BLACK_MAN if player == BLACK else RED_MAN


def king_of(player):
    return BLACK_KING if player == BLACK else RED_KING


def promote(piece):
    """An ordinary piece that reaches the far row becomes a King."""
    if piece == BLACK_MAN:
        return BLACK_KING
    if piece == RED_MAN:
        return RED_KING
    return piece


def promotion_row(player):
    """The opponent's back row, where a man of `player` is crowned."""
    return 0 if player == BLACK else 7


def move_directions(piece):
    """Directions a piece may move or capture in."""
    if is_king(piece):
        return ALL_DIRS
    return UP_DIRS if piece > 0 else DOWN_DIRS


def describe(piece):
    if piece == EMPTY:
        return "empty"
    kind = "King" if is_king(piece) else "piece"
    return f"{PLAYER_NAMES[owner(piece)]} {kind}"
