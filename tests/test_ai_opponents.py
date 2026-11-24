"""Human vs AI opponent choices: MCTS and Minimax + Alpha-Beta."""

import os
import sys
import time
import unittest

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as C  # noqa: E402
import ui  # noqa: E402
from board import square_center  # noqa: E402
from mcts import MCTSAgent  # noqa: E402
from minimax import MinimaxAgent  # noqa: E402
from piece import BLACK, RED  # noqa: E402


def sq(name):
    return (8 - int(name[1])) * 8 + "abcdefgh".index(name[0])


class OpponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ui.App()

    def tearDown(self):
        self.app._cancel_worker()

    def setup_game(self, algorithm, difficulty):
        app = self.app
        app.handle_action(("menu",))
        app.handle_action(("mode", ui.HVAI))
        app.handle_action(("algorithm", algorithm))
        app.handle_action(("difficulty", difficulty))
        app.handle_action(("color", BLACK))
        app.draw_setup((0, 0))
        app.handle_action(("start",))
        app.draw_game((0, 0))

    def test_each_opponent_and_difficulty_uses_the_slide_settings(self):
        expected = {
            C.ALGO_MCTS: (MCTSAgent, "simulations", {"Easy": 100, "Medium": 500, "Hard": 2000}),
            C.ALGO_ALPHA_BETA: (MinimaxAgent, "depth", {"Easy": 2, "Medium": 4, "Hard": 6}),
        }
        for algorithm, (agent_class, field, levels) in expected.items():
            for difficulty, value in levels.items():
                self.setup_game(algorithm, difficulty)
                agent = self.app.players[RED]
                self.assertIs(type(agent), agent_class)
                self.assertEqual(getattr(agent, field), value)

    def test_mcts_opponent_replies_with_a_legal_move(self):
        self.setup_game(C.ALGO_MCTS, "Easy")
        app = self.app
        app.on_board_click(square_center(sq("c3")))
        app.on_board_click(square_center(sq("d4")))
        legal = list(app.game.legal_moves())
        app.ai_ready_at = 0
        deadline = time.time() + 20
        while len(app.game.history) < 2 and time.time() < deadline:
            app.update_game()
            time.sleep(0.005)
        self.assertEqual(len(app.game.history), 2)
        self.assertIn(app.game.history[1][1], legal)


if __name__ == "__main__":
    unittest.main()
