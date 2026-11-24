"""Resolution-independent, anti-aliased drawing.

The interface is laid out in fixed "logical" coordinates (config.WINDOW_WIDTH x
WINDOW_HEIGHT). These helpers convert them to real pixels for the current
window size, so everything is redrawn sharply instead of being stretched.
Curved shapes are drawn oversized, smoothed down and cached.
"""

import math
import os
import sys

import pygame

import config as C

S = 1.0             # real pixels per logical unit
_cache = {}


def set_scale(scale):
    global S
    S = scale
    _cache.clear()


def px(value):
    return int(round(value * S))


def rect_px(rect):
    x, y, w, h = rect
    left, top = px(x), px(y)
    return pygame.Rect(left, top, px(x + w) - left, px(y + h) - top)


def canvas_size():
    return px(C.WINDOW_WIDTH), px(C.WINDOW_HEIGHT)


def enable_dpi_awareness():
    """Stop Windows from bitmap-stretching the window on scaled displays."""
    if sys.platform == "win32" and os.environ.get("SDL_VIDEODRIVER") != "dummy":
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def initial_window_size():
    """Comfortable starting size that respects display scaling and fits the screen."""
    if os.environ.get("SDL_VIDEODRIVER") == "dummy":
        return C.WINDOW_WIDTH, C.WINDOW_HEIGHT
    dpi = 1.0
    if sys.platform == "win32":
        try:
            import ctypes
            dpi = ctypes.windll.user32.GetDpiForSystem() / 96
        except (AttributeError, OSError):
            pass
    desk_w, desk_h = pygame.display.get_desktop_sizes()[0]
    scale = min(dpi, desk_w * 0.92 / C.WINDOW_WIDTH, desk_h * 0.86 / C.WINDOW_HEIGHT)
    return int(C.WINDOW_WIDTH * scale), int(C.WINDOW_HEIGHT * scale)


def _sprite(key, w, h, paint):
    sprite = _cache.get(key)
    if sprite is None:
        if len(_cache) > 800:
            _cache.clear()
        ss = 4 if max(w, h) <= 512 else 2
        big = pygame.Surface((w * ss, h * ss), pygame.SRCALPHA)
        paint(big, ss)
        sprite = pygame.transform.smoothscale(big.premul_alpha(), (w, h))
        _cache[key] = sprite
    return sprite


def _blit(surface, sprite, pos):
    surface.blit(sprite, pos, special_flags=pygame.BLEND_PREMULTIPLIED)


def rect(surface, color, area, width=0, border_radius=0):
    r = rect_px(area)
    stroke = max(1, px(width)) if width else 0
    if not border_radius:
        pygame.draw.rect(surface, color, r, stroke)
        return
    radius = px(border_radius)
    key = ("rect", r.w, r.h, tuple(color), stroke, radius)

    def paint(s, ss):
        pygame.draw.rect(s, color, (0, 0, r.w * ss, r.h * ss), stroke * ss, border_radius=radius * ss)

    _blit(surface, _sprite(key, r.w, r.h, paint), r.topleft)


def circle(surface, color, center, radius, width=0):
    real_r = radius * S
    stroke = max(1, px(width)) if width else 0
    size = math.ceil(real_r * 2) + 4
    key = ("circle", size, tuple(color), round(real_r, 2), stroke)

    def paint(s, ss):
        mid = size * ss / 2
        pygame.draw.circle(s, color, (mid, mid), real_r * ss, stroke * ss)

    pos = (int(round(center[0] * S - size / 2)), int(round(center[1] * S - size / 2)))
    _blit(surface, _sprite(key, size, size, paint), pos)


def vector(surface, key, x, y, w, h, paint):
    """Cached custom shape. `paint(surf, k)` draws with logical coords times k,
    relative to (x, y)."""
    pw, ph = math.ceil(w * S), math.ceil(h * S)
    sprite = _sprite(("vector", key, pw, ph), pw, ph, lambda s, ss: paint(s, S * ss))
    _blit(surface, sprite, (int(round(x * S)), int(round(y * S))))


def shade(surface, area, rgba):
    r = rect_px(area)
    overlay = pygame.Surface(r.size, pygame.SRCALPHA)
    overlay.fill(rgba)
    surface.blit(overlay, r.topleft)
