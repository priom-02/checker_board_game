"""Heuristic evaluation of a checkers position.

The score combines:
  * material      - ordinary pieces and (more valuable) kings;
  * position      - advancement of men, keeping the back row guarded,
                    centre control, safe edge squares, central kings;
  * endgame terms - the side that is ahead is encouraged to trade pieces and
                    to bring its kings towards the remaining enemy pieces.

`evaluate(squares, player)` is positive when `player` is better.
"""

from move_generator import DARK_SQUARES
from piece import BLACK, BLACK_MAN, BLACK_KING, RED_MAN, RED_KING

MAN_VALUE = 100
KING_VALUE = 160
WIN_SCORE = 100_000


def _build_tables():
    black_man = [0] * 64
    red_man = [0] * 64
    king = [0] * 64
    for sq in DARK_SQUARES:
        r, c = divmod(sq, 8)
        central = 2 <= r <= 5 and 2 <= c <= 5
        edge = c in (0, 7)

        # Black men advance towards row 0.
        v = 3 * (7 - r)
        if r == 7:
            v += 8              # back-row guard stops enemy promotion
        if central:
            v += 4
        if edge:
            v += 2              # edge pieces cannot be jumped
        black_man[sq] = v

        # Mirror for Red men (they advance towards row 7).
        v = 3 * r
        if r == 0:
            v += 8
        if central:
            v += 4
        if edge:
            v += 2
        red_man[sq] = v

        # Kings are strongest in the centre and weak on the rim.
        if central:
            king[sq] = 8
        elif edge or r in (0, 7):
            king[sq] = -4
    return black_man, red_man, king


PST_BLACK_MAN, PST_RED_MAN, PST_KING = _build_tables()


def evaluate(squares, player):
    """Static score of `squares` from `player`'s point of view."""
    black_score = 0
    red_score = 0
    black_n = red_n = 0
    black_kings = []
    red_kings = []
    black_pos = []
    red_pos = []

    for sq in DARK_SQUARES:
        p = squares[sq]
        if p == 0:
            continue
        if p == BLACK_MAN:
            black_score += MAN_VALUE + PST_BLACK_MAN[sq]
            black_n += 1
            black_pos.append(sq)
        elif p == RED_MAN:
            red_score += MAN_VALUE + PST_RED_MAN[sq]
            red_n += 1
            red_pos.append(sq)
        elif p == BLACK_KING:
            black_score += KING_VALUE + PST_KING[sq]
            black_n += 1
            black_kings.append(sq)
            black_pos.append(sq)
        elif p == RED_KING:
            red_score += KING_VALUE + PST_KING[sq]
            red_n += 1
            red_kings.append(sq)
            red_pos.append(sq)

    if black_n == 0:
        return -WIN_SCORE if player == BLACK else WIN_SCORE
    if red_n == 0:
        return WIN_SCORE if player == BLACK else -WIN_SCORE

    score = black_score - red_score
    total = black_n + red_n

    # Endgame: when ahead, trading down and chasing with kings wins faster.
    if total <= 12 and score != 0:
        lead = 1 if score > 0 else -1
        score += lead * (24 - total) * 4
        hunters, prey = (black_kings, red_pos) if lead > 0 else (red_kings, black_pos)
        if hunters and prey:
            dist = 0
            for h in hunters:
                hr, hc = divmod(h, 8)
                dist += min(max(abs(hr - (q >> 3)), abs(hc - (q & 7))) for q in prey)
            score -= lead * dist * 2

    return score if player == BLACK else -score
