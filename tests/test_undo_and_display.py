"""Undo, movable-piece highlights support, and drawing at different window sizes."""

import os
import sys
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

import config as C  # noqa: E402
import gfx  # noqa: E402
import ui  # noqa: E402
from board import square_center  # noqa: E402
from game import GameState  # noqa: E402
from piece import BLACK, RED  # noqa: E402


def sq(name):
    return (8 - int(name[1])) * 8 + "abcdefgh".index(name[0])


class GameUndoTests(unittest.TestCase):
    def test_undo_restores_everything(self):
        g = GameState()
        states = []
        for _ in range(30):
            if g.over:
                break
            states.append((list(g.squares), g.turn, dict(g.captured), g.quiet_plies, dict(g.position_counts)))
            g.make_move(g.legal_moves()[0])
        while states:
            g.undo()
            self.assertEqual((list(g.squares), g.turn, dict(g.captured), g.quiet_plies,
                              dict(g.position_counts)), states.pop())
        self.assertEqual(g.history, [])
        with self.assertRaises(ValueError):
            g.undo()


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ui.App()

    def tearDown(self):
        self.app._cancel_worker()

    def start(self, mode, human=BLACK):
        app = self.app
        app.mode, app.human_color, app.difficulty = mode, human, "Easy"
        app.new_game()

    def click(self, name):
        self.app.on_board_click(square_center(sq(name)))

    def test_human_vs_human_undo_one_move(self):
        self.start(ui.HVH)
        self.assertFalse(self.app.can_undo())
        self.click("c3")
        self.click("d4")
        self.assertEqual(self.app.game.turn, RED)
        self.app.undo()
        self.assertEqual((self.app.game.turn, len(self.app.game.history)), (BLACK, 0))

    def test_human_vs_ai_undo_takes_back_both_moves(self):
        self.start(ui.HVAI)
        self.click("c3")
        self.click("d4")
        reply = self.app.game.legal_moves()[0]
        self.app.play_move(reply, animate=True)
        self.app.undo()
        self.assertEqual((self.app.game.turn, len(self.app.game.history)), (BLACK, 0))
        self.assertIsNone(self.app.anim)

    def test_undo_while_ai_thinks_keeps_turn_with_human(self):
        self.start(ui.HVAI)
        self.click("c3")
        self.click("d4")
        self.app.ai_ready_at = 0
        self.app.update_game()
        self.assertIsNotNone(self.app.worker)
        self.app.undo()
        self.assertIsNone(self.app.worker)
        self.assertEqual(self.app.game.turn, BLACK)

    def test_ai_opening_move_cannot_be_undone(self):
        self.start(ui.HVAI, human=RED)
        self.app.play_move(self.app.game.legal_moves()[0], animate=False)
        self.assertFalse(self.app.can_undo())

    def test_ai_vs_ai_has_no_undo(self):
        self.start(ui.AIVAI)
        self.app.play_move(self.app.game.legal_moves()[0], animate=False)
        self.assertFalse(self.app.can_undo())

    def test_clicks_map_correctly_when_maximised(self):
        app = self.app
        pygame.display.set_mode((1920, 1017), pygame.RESIZABLE)
        try:
            app._sync_display()
            self.assertEqual(gfx.px(C.WINDOW_HEIGHT), 1017)
            self.start(ui.HVH)
            x, y = square_center(sq("c3"))
            real = (app.offset[0] + gfx.px(x), app.offset[1] + gfx.px(y))
            app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=real))
            self.assertEqual(app.selected_path, [sq("c3")])
            app.draw_game((0, 0))
        finally:
            pygame.display.set_mode((C.WINDOW_WIDTH, C.WINDOW_HEIGHT), pygame.RESIZABLE)
            app._sync_display()


if __name__ == "__main__":
    unittest.main()
