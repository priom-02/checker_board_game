"""Board representation and drawing.

`Board` is pure game data (no pygame).  `BoardRenderer` draws it in the style
of the board illustrations in the project slides: a wooden frame, pale maple
and dark walnut squares, flat red / black discs with a dark rim and an inner
ring, a crown on kings, and white rings for selections and destinations.
"""

import math
import os
import random

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

import config as C  # noqa: E402
import gfx  # noqa: E402
from move_generator import DARK_SQUARES, count_pieces, initial_squares  # noqa: E402
from piece import EMPTY, RED, is_king, owner  # noqa: E402


class Board:
    """An 8x8 checkers board stored as a flat list of 64 piece codes."""

    def __init__(self, squares=None):
        self.squares = list(squares) if squares is not None else initial_squares()

    def get(self, row, col):
        return self.squares[row * 8 + col]

    def count(self, player):
        return count_pieces(self.squares, player)

    def king_count(self, player):
        return sum(1 for sq in DARK_SQUARES if self.squares[sq] * player > 0 and is_king(self.squares[sq]))

    def key(self):
        return tuple(self.squares)

    def copy(self):
        return Board(self.squares)

    def __str__(self):
        sym = {0: ".", 1: "b", 2: "B", -1: "r", -2: "R"}
        rows = []
        for r in range(8):
            rows.append(" ".join(sym[self.squares[r * 8 + c]] if (r + c) % 2 else " " for c in range(8)))
        return "\n".join(rows)


# ---------------------------------------------------------------------------
# Drawing (positions are logical; gfx converts them to real pixels)
# ---------------------------------------------------------------------------
def square_rect(index):
    r, c = divmod(index, 8)
    return pygame.Rect(C.BOARD_X + c * C.SQUARE_SIZE, C.BOARD_Y + r * C.SQUARE_SIZE,
                       C.SQUARE_SIZE, C.SQUARE_SIZE)


def square_center(index):
    r, c = divmod(index, 8)
    return (C.BOARD_X + c * C.SQUARE_SIZE + C.SQUARE_SIZE // 2,
            C.BOARD_Y + r * C.SQUARE_SIZE + C.SQUARE_SIZE // 2)


def square_at(pos):
    """Board index under a logical position, or None."""
    x, y = int(pos[0]) - C.BOARD_X, int(pos[1]) - C.BOARD_Y
    if 0 <= x < C.BOARD_PIXELS and 0 <= y < C.BOARD_PIXELS:
        return (y // C.SQUARE_SIZE) * 8 + (x // C.SQUARE_SIZE)
    return None


def _wood(surface, rect, base, grain, rng, vertical=True, strength=1.0):
    """Fill a real-pixel `rect` with a simple procedural wood-grain texture."""
    old_clip = surface.get_clip()
    surface.set_clip(rect)
    surface.fill(base, rect)
    length = rect.height if vertical else rect.width
    across = rect.width if vertical else rect.height
    line_width = max(1, int(round(gfx.S)))
    step = max(4, int(4 * gfx.S))
    for _ in range(int(across / gfx.S * 0.55)):
        offset = rng.uniform(0, across)
        amp = rng.uniform(0.4, 1.6) * gfx.S
        freq = rng.uniform(0.01, 0.04) / gfx.S
        phase = rng.uniform(0, math.tau)
        mix = rng.uniform(0.15, 0.55) * strength
        col = tuple(int(base[i] + (grain[i] - base[i]) * mix) for i in range(3))
        pts = []
        for t in range(0, length + step, step):
            o = offset + amp * math.sin(t * freq + phase)
            pts.append((rect.x + o, rect.y + t) if vertical else (rect.x + t, rect.y + o))
        if len(pts) > 1:
            pygame.draw.lines(surface, col, False, pts, line_width)
    surface.set_clip(old_clip)


def draw_crown(surface, center, size, color):
    """Small three-pointed crown like the king markers in the slides."""
    cx, cy = center
    w = size
    h = size * 0.62
    left, right = cx - w / 2, cx + w / 2
    top, base = cy - h / 2, cy + h / 2
    pts = [
        (left, base), (left, top + h * 0.15), (cx - w * 0.25, top + h * 0.55),
        (cx, top), (cx + w * 0.25, top + h * 0.55), (right, top + h * 0.15), (right, base),
    ]
    pygame.draw.polygon(surface, color, pts)
    pygame.draw.rect(surface, color, pygame.Rect(left, base + h * 0.12, w, h * 0.22))
    for x in (left, cx, right):
        y = top + h * 0.15 if x != cx else top
        pygame.draw.circle(surface, color, (x, y), max(2, size * 0.08))


def draw_piece(surface, center, piece, radius=C.PIECE_RADIUS):
    """Flat disc with dark rim and an inner ring, as in the slide illustrations."""
    if piece == EMPTY:
        return
    if owner(piece) == RED:
        fill, rim, ring, crown = C.RED_PIECE, C.RED_RIM, C.RED_RING, C.RED_CROWN
    else:
        fill, rim, ring, crown = C.BLACK_PIECE, C.BLACK_RIM, C.BLACK_RING, C.BLACK_CROWN
    pad = radius + 6

    def paint(s, k):
        mid = pad * k
        pygame.draw.circle(s, (0, 0, 0, 70), (mid + k, mid + 2 * k), (radius + 1) * k)
        pygame.draw.circle(s, rim, (mid, mid), radius * k)
        pygame.draw.circle(s, fill, (mid, mid), (radius - 3) * k)
        pygame.draw.circle(s, ring, (mid, mid), radius * 0.74 * k, max(1, int(2 * k)))
        if is_king(piece):
            draw_crown(s, (mid, mid + k), radius * 0.95 * k, crown)

    gfx.vector(surface, ("piece", piece, radius), center[0] - pad, center[1] - pad, pad * 2, pad * 2, paint)


def draw_halo(surface, sq, color):
    """Soft glow around a piece that can be played."""
    cx, cy = square_center(sq)
    r = C.PIECE_RADIUS
    pad = r + 9

    def paint(s, k):
        mid = pad * k
        for i in range(8, 0, -1):
            alpha = 26 + (8 - i) * 26
            pygame.draw.circle(s, (*color, alpha), (mid, mid), (r + i) * k)

    gfx.vector(surface, ("halo", color), cx - pad, cy - pad, pad * 2, pad * 2, paint)


class BoardRenderer:
    """Draws the board, pieces and move indicators."""

    def __init__(self):
        self.background = self._build_background()

    @staticmethod
    def _build_background():
        surf = pygame.Surface(gfx.canvas_size(), pygame.SRCALPHA)
        rng = random.Random(2207048)  # fixed seed: the same wood every run
        frame = pygame.Rect(C.FRAME_X, C.FRAME_Y, C.FRAME_SIZE, C.FRAME_SIZE)
        _wood(surf, gfx.rect_px(frame), C.FRAME_COLOR, C.FRAME_GRAIN, rng, vertical=False, strength=1.2)
        for sq in range(64):
            rect = gfx.rect_px(square_rect(sq))
            if sq in DARK_SQUARES:
                _wood(surf, rect, C.DARK_SQUARE, C.DARK_GRAIN, rng, vertical=True, strength=0.9)
            else:
                _wood(surf, rect, C.LIGHT_SQUARE, C.LIGHT_GRAIN, rng, vertical=True, strength=1.0)
        grid = pygame.Rect(C.BOARD_X, C.BOARD_Y, C.BOARD_PIXELS, C.BOARD_PIXELS)
        gfx.rect(surf, C.FRAME_EDGE, grid.inflate(4, 4), 2)
        gfx.rect(surf, C.FRAME_EDGE, frame, 2)
        return surf

    def draw(self, surface, squares, hidden=(), selected=None, destinations=(),
             capture_targets=(), capture_destinations=(), movable=(), capturable=(), last_move=None):
        surface.blit(self.background, (0, 0))
        if last_move is not None:
            for sq in (last_move.path[0], last_move.path[-1]):
                gfx.shade(surface, square_rect(sq), (255, 255, 255, 50))

        for sq in movable:
            draw_halo(surface, sq, C.MOVABLE_GLOW)
        for sq in capturable:
            draw_halo(surface, sq, C.MUST_CAPTURE_RING)

        for sq in DARK_SQUARES:
            if squares[sq] != EMPTY and sq not in hidden:
                draw_piece(surface, square_center(sq), squares[sq])

        if last_move is not None:
            self._draw_last_move(surface, last_move)

        if selected is not None:
            gfx.circle(surface, C.SELECT_RING, square_center(selected), C.PIECE_RADIUS + 3, 3)

        for sq in capture_targets:
            self._draw_capture_mark(surface, sq)

        for sq in destinations:
            self._draw_destination(surface, sq, sq in capture_destinations)

    @staticmethod
    def _draw_destination(surface, sq, is_capture):
        center = square_center(sq)
        r = C.PIECE_RADIUS
        gfx.circle(surface, C.MOVE_FILL, center, r)
        gfx.circle(surface, C.CAPTURE_COLOR if is_capture else C.MOVE_RING, center, r, 3 if is_capture else 2)

    @staticmethod
    def _draw_capture_mark(surface, sq):
        cx, cy = square_center(sq)
        r = C.PIECE_RADIUS
        gfx.circle(surface, C.CAPTURE_COLOR, (cx, cy), r + 3, 3)
        d = r * 0.45
        size = d * 2 + 8

        def paint(s, k):
            a, b = 4 * k, (4 + d * 2) * k
            pygame.draw.line(s, C.CAPTURE_COLOR, (a, a), (b, b), max(1, int(4 * k)))
            pygame.draw.line(s, C.CAPTURE_COLOR, (a, b), (b, a), max(1, int(4 * k)))

        gfx.vector(surface, "capture_x", cx - d - 4, cy - d - 4, size, size, paint)

    @staticmethod
    def _draw_last_move(surface, move):
        """White curved arrow along the last move, like the arrows in the slides.
        Drawn over the pieces; it stops at the edge of the piece that moved."""
        pts_all = []
        for a, b in zip(move.path, move.path[1:]):
            (x1, y1), (x2, y2) = square_center(a), square_center(b)
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy) or 1
            bend = 0.18 * length
            cx, cy = mx - dy / length * bend, my + dx / length * bend
            for i in range(17):
                t = i / 16
                x = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * cx + t * t * x2
                y = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * cy + t * t * y2
                pts_all.append((x, y))
        end = square_center(move.path[-1])
        stop = C.PIECE_RADIUS + 3
        pts_all = [p for p in pts_all if math.hypot(p[0] - end[0], p[1] - end[1]) > stop]
        if len(pts_all) <= 2:
            return
        margin = 18
        left = min(p[0] for p in pts_all) - margin
        top = min(p[1] for p in pts_all) - margin
        w = max(p[0] for p in pts_all) - left + margin
        h = max(p[1] for p in pts_all) - top + margin
        (xa, ya), (xb, yb) = pts_all[-3], pts_all[-1]
        ang = math.atan2(yb - ya, xb - xa)
        tip = (xb + 8 * math.cos(ang), yb + 8 * math.sin(ang))

        def paint(s, k):
            col = C.LAST_MOVE_COLOR
            pts = [((x - left) * k, (y - top) * k) for x, y in pts_all]
            pygame.draw.lines(s, col, False, pts, max(1, int(3 * k)))
            for x, y in pts:
                pygame.draw.circle(s, col, (x, y), 1.5 * k)
            size = 14
            head = [(tip[0], tip[1]),
                    (tip[0] - size * math.cos(ang - 0.45), tip[1] - size * math.sin(ang - 0.45)),
                    (tip[0] - size * math.cos(ang + 0.45), tip[1] - size * math.sin(ang + 0.45))]
            pygame.draw.polygon(s, col, [((x - left) * k, (y - top) * k) for x, y in head])

        gfx.vector(surface, ("arrow", move.path), left, top, w, h, paint)
