"""Sound tests: the WAV files are valid and each game event plays the right effect."""

import array
import os
import sys
import tempfile
import time
import unittest
import wave

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as C  # noqa: E402
import sounds  # noqa: E402
import ui  # noqa: E402
from board import square_center  # noqa: E402
from move_generator import Move  # noqa: E402
from piece import BLACK, BLACK_MAN, RED, RED_MAN  # noqa: E402


def sq(name):
    return (8 - int(name[1])) * 8 + "abcdefgh".index(name[0])


class WavTests(unittest.TestCase):
    def test_files_are_audible_and_not_clipped(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(sounds.generate_sounds(folder), sorted(sounds.SOUND_NAMES))
            for name in sounds.SOUND_NAMES:
                with wave.open(os.path.join(folder, f"{name}.wav")) as f:
                    self.assertEqual((f.getnchannels(), f.getsampwidth()), (1, 2))
                    seconds = f.getnframes() / f.getframerate()
                    pcm = array.array("h", f.readframes(f.getnframes()))
                peak = max(abs(v) for v in pcm)
                self.assertLess(seconds, 1.5, name)
                self.assertGreater(peak, 8000, f"{name} is too quiet")
                self.assertLess(peak, 32000, f"{name} is clipped")


class EventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ui.App()

    def setUp(self):
        self.played = []
        self.app.sounds.play = self.played.append

    def position(self, mode, pieces, turn):
        app = self.app
        app.mode = mode
        app.human_color = BLACK
        app.new_game()
        g = app.game
        b = [0] * 64
        for name, piece in pieces.items():
            b[sq(name)] = piece
        g.board.squares, g.turn, g._legal = b, turn, None
        g.position_counts.clear()
        g.position_counts[g.position_key()] += 1
        self.played.clear()
        return g

    def click(self, name):
        self.app.on_board_click(square_center(sq(name)))

    def test_select_and_move(self):
        self.position(ui.HVH, {"c3": BLACK_MAN, "h8": RED_MAN}, BLACK)
        self.click("c3")
        self.click("d4")
        self.assertEqual(self.played, ["select", "move"])

    def test_multiple_capture_sounds_once_per_jump(self):
        self.position(ui.HVH, {"a1": BLACK_MAN, "b2": RED_MAN, "d4": RED_MAN, "h8": RED_MAN}, BLACK)
        for name in ("a1", "c3", "e5"):
            self.click(name)
        self.assertEqual(self.played, ["select", "capture", "capture"])

    def test_promotion(self):
        self.position(ui.HVH, {"c7": BLACK_MAN, "h6": RED_MAN}, BLACK)
        self.click("c7")
        self.click("d8")
        self.assertEqual(self.played, ["select", "move", "king"])

    def test_invalid_click(self):
        self.position(ui.HVH, {"a1": BLACK_MAN, "b2": BLACK_MAN, "h8": RED_MAN, "c3": BLACK_MAN,
                               "a3": BLACK_MAN}, BLACK)
        self.click("a1")
        self.assertEqual(self.played, ["invalid"])

    def test_animated_ai_jump_sounds_on_each_landing(self):
        g = self.position(ui.HVH, {"a1": BLACK_MAN, "b2": RED_MAN, "d4": RED_MAN, "h8": RED_MAN}, BLACK)
        self.app.play_move(g.legal_moves()[0], animate=True)
        self.app.anim["t0"] = time.perf_counter() - C.ANIM_SEGMENT_TIME * 3
        self.app.update_game()
        self.assertEqual(self.played, ["capture", "capture"])

    def test_result_sounds(self):
        g = self.position(ui.HVAI, {"c3": BLACK_MAN, "d4": RED_MAN}, BLACK)
        g.make_move(Move((sq("c3"), sq("e5")), (sq("d4"),)))
        self.app.update_game()
        self.app.update_game()
        self.assertEqual(self.played, ["win"], "result plays once")

        g = self.position(ui.HVAI, {"c3": BLACK_MAN, "b4": RED_MAN}, RED)
        g.make_move(Move((sq("b4"), sq("d2")), (sq("c3"),)))
        self.app.update_game()
        self.assertEqual(self.played, ["lose"])


if __name__ == "__main__":
    unittest.main()
