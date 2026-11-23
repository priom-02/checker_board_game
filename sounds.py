"""Sound effects.

All effects are synthesised here with the Python standard library, so the
project needs no downloaded or licensed audio. They are saved as WAV files in
assets/sounds/ the first time the game runs. If the computer has no audio
device, the game simply runs silently.

    python sounds.py      # (re)create every WAV file
"""

import array
import math
import os
import random
import wave

import pygame

import config as C

SAMPLE_RATE = 22050
SOUND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sounds")

# Note frequencies (Hz)
C4, E4, G4, A4, C5, E5, G5, C6 = 261.63, 329.63, 392.00, 440.00, 523.25, 659.25, 783.99, 1046.50


def _silence(seconds):
    return [0.0] * int(seconds * SAMPLE_RATE)


def _add(buffer, part, at=0.0):
    """Mix `part` into `buffer`, starting `at` seconds in."""
    start = int(at * SAMPLE_RATE)
    if len(buffer) < start + len(part):
        buffer.extend([0.0] * (start + len(part) - len(buffer)))
    for i, value in enumerate(part):
        buffer[start + i] += value


def _tone(freq, seconds, volume=0.5, decay=6.0, end_freq=None, harmonics=(1.0, 0.25)):
    """A decaying tone, optionally sliding to `end_freq`."""
    n = int(seconds * SAMPLE_RATE)
    end_freq = end_freq or freq
    out = []
    phase = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        progress = i / max(1, n - 1)
        phase += math.tau * (freq + (end_freq - freq) * progress) / SAMPLE_RATE
        wave_value = sum(a * math.sin(phase * (h + 1)) for h, a in enumerate(harmonics))
        attack = min(1.0, i / (0.003 * SAMPLE_RATE))
        release = min(1.0, (n - i) / (0.006 * SAMPLE_RATE))
        out.append(volume * wave_value * attack * release * math.exp(-decay * t))
    return out


def _knock(seconds=0.09, volume=0.5, pitch=190.0, seed=1):
    """A wooden 'clack': a low body tone plus a very short noise tick."""
    rng = random.Random(seed)
    body = _tone(pitch, seconds, volume, decay=45.0, end_freq=pitch * 0.72, harmonics=(1.0, 0.45, 0.15))
    tick_len = int(0.012 * SAMPLE_RATE)
    for i in range(min(tick_len, len(body))):
        body[i] += volume * 0.6 * rng.uniform(-1, 1) * (1 - i / tick_len)
    return body


def _melody(notes, step, length, volume=0.32, decay=5.0):
    buffer = []
    for i, freq in enumerate(notes):
        _add(buffer, _tone(freq, length, volume, decay), i * step)
    return buffer


def _build_all():
    capture = _knock(0.11, 0.55, 150, seed=2)
    _add(capture, _knock(0.10, 0.42, 245, seed=3), 0.055)
    _add(capture, _tone(520, 0.11, 0.10, decay=22, end_freq=300), 0.03)

    invalid = _tone(165, 0.10, 0.30, decay=10, harmonics=(1.0, 0.5, 0.3))
    _add(invalid, _tone(130, 0.14, 0.30, decay=10, harmonics=(1.0, 0.5, 0.3)), 0.12)

    win = _melody([C5, E5, G5], 0.11, 0.26)
    _add(win, _tone(C6, 0.65, 0.34, decay=3.5), 0.33)
    _add(win, _tone(G5, 0.65, 0.18, decay=3.5), 0.33)
    _add(win, _tone(E5, 0.65, 0.16, decay=3.5), 0.33)

    lose = _melody([G4, E4, C4], 0.20, 0.42, volume=0.34, decay=4.0)
    _add(lose, _tone(C4 / 2, 0.70, 0.30, decay=3.5), 0.60)

    draw = _tone(A4, 0.34, 0.30, decay=5)
    _add(draw, _tone(A4, 0.60, 0.28, decay=4), 0.24)
    _add(draw, _tone(E4, 0.60, 0.20, decay=4), 0.24)

    return {
        "click": _tone(1150, 0.04, 0.42, decay=70, harmonics=(1.0,)),
        "select": _tone(760, 0.07, 0.42, decay=42, end_freq=960, harmonics=(1.0, 0.1)),
        "move": _knock(),
        "capture": capture,
        "king": _melody([C5, E5, G5, C6], 0.075, 0.26, volume=0.30, decay=8.0),
        "invalid": invalid,
        "start": _melody([G4, C5], 0.10, 0.24),
        "win": win,
        "lose": lose,
        "draw": draw,
    }


def _write_wav(path, samples):
    peak = max(1.0, max(abs(v) for v in samples) / 0.9)   # keep clear of clipping
    pcm = array.array("h", (int(v / peak * 32767) for v in samples))
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(pcm.tobytes())


def generate_sounds(folder=SOUND_DIR):
    os.makedirs(folder, exist_ok=True)
    built = _build_all()
    for name, samples in built.items():
        _write_wav(os.path.join(folder, f"{name}.wav"), samples)
    return sorted(built)


SOUND_NAMES = ("click", "select", "move", "capture", "king", "invalid", "start", "win", "lose", "draw")


class SoundManager:
    """Loads and plays the effects. Audio problems never interrupt the game."""

    def __init__(self):
        self.enabled = C.SOUND_ENABLED
        self.sounds = {}
        try:
            if any(not os.path.exists(os.path.join(SOUND_DIR, f"{n}.wav")) for n in SOUND_NAMES):
                generate_sounds()
            if not pygame.mixer.get_init():
                pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
            pygame.mixer.set_num_channels(16)
            for name in SOUND_NAMES:
                sound = pygame.mixer.Sound(os.path.join(SOUND_DIR, f"{name}.wav"))
                sound.set_volume(C.SOUND_VOLUME)
                self.sounds[name] = sound
        except (pygame.error, OSError):
            self.sounds = {}          # no audio device: run silently

    def play(self, name):
        if self.enabled and name in self.sounds:
            self.sounds[name].play()

    def toggle(self):
        self.enabled = not self.enabled
        if not self.enabled and pygame.mixer.get_init():
            pygame.mixer.stop()
        return self.enabled


if __name__ == "__main__":
    print("Created:", ", ".join(generate_sounds()), "in", SOUND_DIR)
