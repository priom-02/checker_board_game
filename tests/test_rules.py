"""Rule and AI tests.  Run from the project folder:  python -m unittest -v"""

import os
import random
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as C  # noqa: E402
from game import GameState  # noqa: E402
from mcts import MCTSAgent  # noqa: E402
from minimax import MinimaxAgent  # noqa: E402
from move_generator import (  # noqa: E402
    Move, apply_move, apply_partial, get_legal_moves, initial_squares,
)
from piece import (  # noqa: E402
    BLACK, BLACK_KING, BLACK_MAN, EMPTY, RED, RED_KING, RED_MAN,
)


def sq(name):
    """'c3' -> board index (a-h columns, rank 8 at the top)."""
    return (8 - int(name[1])) * 8 + "abcdefgh".index(name[0])


def board_with(**pieces):
    """board_with(c3=BLACK_MAN, d4=RED_MAN) -> 64-square list."""
    b = [EMPTY] * 64
    for name, piece in pieces.items():
        i = sq(name)
        assert (i // 8 + i % 8) % 2 == 1, f"{name} is not a dark square"
        b[i] = piece
    return b


def paths(moves):
    return sorted(tuple(m.path) for m in moves)


def caps(moves):
    return [m for m in moves if m.is_capture]


class SetupTests(unittest.TestCase):
    def test_initial_position(self):
        b = initial_squares()
        self.assertEqual(sum(1 for p in b if p == BLACK_MAN), 12)
        self.assertEqual(sum(1 for p in b if p == RED_MAN), 12)
        for i, p in enumerate(b):
            if p != EMPTY:
                self.assertEqual((i // 8 + i % 8) % 2, 1, "pieces only on dark squares")

    def test_opening_moves(self):
        b = initial_squares()
        self.assertEqual(len(get_legal_moves(b, BLACK)), 7)
        self.assertEqual(len(get_legal_moves(b, RED)), 7)
        for m in get_legal_moves(b, BLACK):
            self.assertLess(m.end // 8, m.start // 8, "black men move up the board")


class MovementTests(unittest.TestCase):
    def test_man_moves_forward_only(self):
        b = board_with(d4=BLACK_MAN)
        self.assertEqual(paths(get_legal_moves(b, BLACK)), sorted([(sq("d4"), sq("c5")), (sq("d4"), sq("e5"))]))
        b = board_with(e5=RED_MAN)
        self.assertEqual(paths(get_legal_moves(b, RED)), sorted([(sq("e5"), sq("d4")), (sq("e5"), sq("f4"))]))

    def test_king_moves_both_directions(self):
        b = board_with(d4=BLACK_KING)
        ends = sorted(m.end for m in get_legal_moves(b, BLACK))
        self.assertEqual(ends, sorted(sq(n) for n in ("c5", "e5", "c3", "e3")))

    def test_blocked_by_edge_and_pieces(self):
        b = board_with(a3=BLACK_MAN, b4=BLACK_MAN)
        ends = sorted(m.end for m in get_legal_moves(b, BLACK))
        self.assertEqual(ends, sorted(sq(n) for n in ("a5", "c5")))


class CaptureTests(unittest.TestCase):
    def test_single_capture(self):
        b = board_with(c3=BLACK_MAN, d4=RED_MAN)
        moves = caps(get_legal_moves(b, BLACK))
        self.assertEqual(len(moves), 1)
        m = moves[0]
        self.assertEqual(m.path, (sq("c3"), sq("e5")))
        self.assertEqual(m.captures, (sq("d4"),))
        after = apply_move(b, m)
        self.assertEqual(after[sq("d4")], EMPTY)
        self.assertEqual(after[sq("e5")], BLACK_MAN)

    def test_capture_is_mandatory_when_enabled(self):
        b = board_with(c3=BLACK_MAN, d4=RED_MAN, g3=BLACK_MAN)
        moves = get_legal_moves(b, BLACK, mandatory_capture=True)
        self.assertTrue(all(m.is_capture for m in moves))
        self.assertEqual(len(moves), 1)

    def test_capture_is_optional_by_default(self):
        self.assertFalse(C.MANDATORY_CAPTURE)
        b = board_with(c3=BLACK_MAN, d4=RED_MAN, g3=BLACK_MAN)
        moves = get_legal_moves(b, BLACK)
        self.assertEqual(len(caps(moves)), 1)
        # c3-b4, g3-f4, g3-h4 are also allowed when capturing is optional
        simple = sorted(m.path for m in moves if not m.is_capture)
        self.assertEqual(simple, sorted([(sq("c3"), sq("b4")), (sq("g3"), sq("f4")), (sq("g3"), sq("h4"))]))
        self.assertTrue(moves[0].is_capture, "captures are listed first")

    def test_man_cannot_capture_backwards(self):
        b = board_with(e5=BLACK_MAN, d6=EMPTY, d4=RED_MAN)
        self.assertFalse(any(m.is_capture for m in get_legal_moves(b, BLACK)))

    def test_multiple_jump_must_continue(self):
        b = board_with(a1=BLACK_MAN, b2=RED_MAN, d4=RED_MAN, f6=RED_MAN)
        moves = caps(get_legal_moves(b, BLACK))
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0].path, (sq("a1"), sq("c3"), sq("e5"), sq("g7")))
        self.assertEqual(len(moves[0].captures), 3)

    def test_branching_multi_jump(self):
        b = board_with(c1=BLACK_MAN, d2=RED_MAN, d4=RED_MAN, f4=RED_MAN)
        got = paths(get_legal_moves(b, BLACK))
        self.assertIn((sq("c1"), sq("e3"), sq("c5")), got)
        self.assertIn((sq("c1"), sq("e3"), sq("g5")), got)

    def test_cannot_jump_same_piece_twice(self):
        # king loop around a 2x2 block: each enemy piece may be jumped only once
        b = board_with(c3=BLACK_KING, d4=RED_MAN, d6=RED_MAN, b6=RED_MAN, b4=RED_MAN)
        for m in get_legal_moves(b, BLACK):
            self.assertEqual(len(m.captures), len(set(m.captures)))
        best = max(get_legal_moves(b, BLACK), key=lambda m: len(m.captures))
        self.assertEqual(len(best.captures), 4)
        self.assertEqual(best.end, sq("c3"), "king may finish on its starting square")

    def test_king_captures_backwards(self):
        b = board_with(e5=BLACK_KING, d4=RED_MAN)
        moves = caps(get_legal_moves(b, BLACK))
        self.assertEqual(paths(moves), [(sq("e5"), sq("c3"))])

    def test_partial_jump_display(self):
        b = board_with(a1=BLACK_MAN, b2=RED_MAN, d4=RED_MAN)
        partial = apply_partial(b, [sq("a1"), sq("c3")])
        self.assertEqual(partial[sq("b2")], EMPTY)
        self.assertEqual(partial[sq("d4")], RED_MAN)
        self.assertEqual(partial[sq("c3")], BLACK_MAN)


class PromotionTests(unittest.TestCase):
    def test_promotion_on_simple_move(self):
        b = board_with(c7=BLACK_MAN)
        m = [m for m in get_legal_moves(b, BLACK) if m.end == sq("b8")][0]
        self.assertTrue(m.promotes)
        self.assertEqual(apply_move(b, m)[sq("b8")], BLACK_KING)

    def test_red_promotion(self):
        b = board_with(d2=RED_MAN)
        for m in get_legal_moves(b, RED):
            self.assertEqual(apply_move(b, m)[m.end], RED_KING)

    def test_promotion_ends_the_jump(self):
        # after crowning on d8 the new king could jump e7 backwards, but may not
        b = board_with(b6=BLACK_MAN, c7=RED_MAN, e7=RED_MAN)
        moves = caps(get_legal_moves(b, BLACK))
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0].path, (sq("b6"), sq("d8")))
        self.assertTrue(moves[0].promotes)


class TerminalTests(unittest.TestCase):
    def _game(self, squares, turn):
        g = GameState(first_player=turn)
        g.board.squares = list(squares)
        g.position_counts.clear()
        g.position_counts[g.position_key()] += 1
        g._legal = None
        g.winner, g.is_draw = None, False
        g._check_game_over()
        return g

    def test_win_by_capturing_all(self):
        g = self._game(board_with(c3=BLACK_MAN, d4=RED_MAN), BLACK)
        g.make_move(g.legal_moves()[0])
        self.assertTrue(g.over)
        self.assertEqual(g.winner, BLACK)
        self.assertIn("no pieces", g.result_reason)

    def test_loss_by_no_legal_moves(self):
        # the red man on b8 is boxed in by black men
        b = board_with(b8=RED_MAN, a7=BLACK_MAN, c7=BLACK_MAN, d6=BLACK_MAN)
        g = self._game(b, RED)
        self.assertTrue(g.over)
        self.assertEqual(g.winner, BLACK)
        self.assertIn("no legal moves", g.result_reason)

    def test_threefold_repetition(self):
        b = board_with(b8=RED_KING, f6=RED_KING, b2=BLACK_KING, h2=BLACK_KING)
        g = self._game(b, BLACK)
        shuffle = [("b2", "a3"), ("b8", "a7"), ("a3", "b2"), ("a7", "b8")]
        for _ in range(2):
            for a, z in shuffle:
                self.assertFalse(g.over)
                g.make_move(Move((sq(a), sq(z))))
        self.assertTrue(g.is_draw)
        self.assertEqual(g.result_reason, "Threefold repetition")
        self.assertEqual(g.position_counts[g.position_key()], 3)

    def test_declining_a_capture(self):
        b = board_with(c3=BLACK_MAN, d4=RED_MAN, g3=BLACK_MAN, h8=RED_MAN)
        g = self._game(b, BLACK)
        g.make_move(Move((sq("g3"), sq("h4"))))          # optional: allowed
        self.assertEqual(g.turn, RED)
        with mock.patch.object(C, "MANDATORY_CAPTURE", True):
            g = self._game(b, BLACK)
            with self.assertRaises(ValueError):
                g.make_move(Move((sq("g3"), sq("h4"))))  # mandatory: rejected

    def test_illegal_move_rejected(self):
        g = GameState()
        with self.assertRaises(ValueError):
            g.make_move(Move((sq("c3"), sq("c4"))))


class AITests(unittest.TestCase):
    def _random_positions(self, n, seed=1):
        rng = random.Random(seed)
        out = []
        while len(out) < n:
            g = GameState()
            for _ in range(rng.randint(0, 50)):
                if g.over:
                    break
                g.make_move(rng.choice(g.legal_moves()))
            if not g.over:
                out.append((list(g.squares), g.turn))
        return out

    def test_agents_return_legal_moves(self):
        agents = [MinimaxAgent(2, seed=0), MinimaxAgent(4, seed=0), MCTSAgent(100, seed=0)]
        for squares, turn in self._random_positions(25):
            legal = get_legal_moves(squares, turn)
            for agent in agents:
                move = agent.choose_move(list(squares), turn)
                self.assertIn(move, legal, f"{agent.label} returned an illegal move")

    def test_minimax_takes_free_piece(self):
        b = board_with(c3=BLACK_MAN, d4=RED_MAN, h8=RED_MAN, a1=BLACK_MAN)
        move = MinimaxAgent(4, seed=0).choose_move(b, BLACK)
        self.assertTrue(move.is_capture)

    def test_minimax_finds_double_jump_win(self):
        b = board_with(a1=BLACK_KING, b2=RED_MAN, d4=RED_MAN, h8=BLACK_MAN)
        move = MinimaxAgent(2, seed=0).choose_move(b, BLACK)
        self.assertEqual(len(move.captures), 2)

    def test_mcts_prefers_winning_capture(self):
        # Red's only piece can be captured: MCTS must find it.
        b = board_with(e3=BLACK_MAN, f4=RED_MAN, a1=BLACK_MAN)
        move = MCTSAgent(200, seed=0).choose_move(b, BLACK)
        self.assertTrue(move.is_capture)

    def test_agents_legal_with_mandatory_capture(self):
        with mock.patch.object(C, "MANDATORY_CAPTURE", True):
            for squares, turn in self._random_positions(10, seed=7):
                legal = get_legal_moves(squares, turn)
                for agent in (MinimaxAgent(4, seed=0), MCTSAgent(100, seed=0)):
                    self.assertIn(agent.choose_move(list(squares), turn), legal)

    def test_full_ai_game_is_legal(self):
        g = GameState()
        agents = {BLACK: MinimaxAgent(2, seed=1), RED: MCTSAgent(100, seed=1)}
        while not g.over:
            move = agents[g.turn].choose_move(list(g.squares), g.turn)
            self.assertIn(move, g.legal_moves())
            g.make_move(move)
        self.assertTrue(g.winner is not None or g.is_draw)


if __name__ == "__main__":
    unittest.main()
