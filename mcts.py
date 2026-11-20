"""Monte Carlo Tree Search (UCT).

Each simulation runs the four classic stages:

  1. Selection       - from the root, repeatedly pick the child with the best
                       UCT value  w/n + c * sqrt(ln N / n)  while the node is
                       fully expanded;
  2. Expansion       - add one untried legal move as a new child node;
  3. Simulation      - play random legal moves (a "rollout") from the new node
                       until the game ends or MCTS_ROLLOUT_DEPTH plies pass;
                       an unfinished rollout is scored with the heuristic
                       evaluation squashed into [0, 1];
  4. Backpropagation - add the result to every node on the path back to the root.

After the simulation budget is spent the most-visited root move is played.
A child position that would occur for the third time in the game is treated
as a terminal draw (threefold repetition), exactly as the game rules do.
All moves come from the same legal-move generator used by the game.
"""

import math
import random
import time

from config import MCTS_EXPLORATION, MCTS_ROLLOUT_DEPTH, REPETITION_LIMIT
from evaluation import evaluate
from minimax import SearchAborted
from move_generator import apply_move, get_legal_moves
from piece import BLACK


class MCTSNode:
    __slots__ = ("squares", "to_move", "parent", "move", "children", "untried", "visits", "wins",
                 "draw")

    def __init__(self, squares, to_move, parent=None, move=None, rng=None, draw=False):
        self.squares = squares
        self.to_move = to_move          # player to move in this position
        self.parent = parent
        self.move = move                # move that led here from the parent
        self.children = []
        self.draw = draw                # terminal by threefold repetition
        self.untried = [] if draw else get_legal_moves(squares, to_move)
        if rng is not None:
            rng.shuffle(self.untried)
        self.visits = 0
        self.wins = 0.0                 # from the view of the player who made `move`

    def is_terminal(self):
        return not self.untried and not self.children

    def best_uct_child(self, c):
        log_n = math.log(self.visits)
        best, best_value = None, -1.0
        for child in self.children:
            value = child.wins / child.visits + c * math.sqrt(log_n / child.visits)
            if value > best_value:
                best, best_value = child, value
        return best


class MCTSAgent:
    algorithm = "Monte Carlo Tree Search"

    def __init__(self, simulations, exploration=MCTS_EXPLORATION,
                 rollout_depth=MCTS_ROLLOUT_DEPTH, seed=None):
        self.simulations = simulations
        self.c = exploration
        self.rollout_depth = rollout_depth
        self.rng = random.Random(seed)
        self.last_stats = {}

    @property
    def label(self):
        return f"MCTS ({self.simulations:,} simulations)"

    @property
    def short_label(self):
        return "MCTS"

    def choose_move(self, squares, player, stop_event=None, history=None):
        """`history`: optional (board tuple, side to move) -> occurrences so far."""
        history = history or {}
        t0 = time.perf_counter()
        moves = get_legal_moves(squares, player)
        self.last_stats = {"simulations": 0, "time": 0.0}
        if not moves:
            return None
        if len(moves) == 1:
            self.last_stats.update(time=time.perf_counter() - t0, forced=True)
            return moves[0]

        root = MCTSNode(list(squares), player, rng=self.rng)
        for i in range(self.simulations):
            if stop_event is not None and i % 16 == 0 and stop_event.is_set():
                raise SearchAborted()

            # 1. Selection
            node = root
            while not node.untried and node.children:
                node = node.best_uct_child(self.c)

            # 2. Expansion
            if node.untried:
                move = node.untried.pop()
                child_squares = apply_move(node.squares, move)
                repeats = history.get((tuple(child_squares), -node.to_move), 0)
                child = MCTSNode(child_squares, -node.to_move, parent=node, move=move,
                                 rng=self.rng, draw=repeats >= REPETITION_LIMIT - 1)
                node.children.append(child)
                node = child

            # 3. Simulation
            black_result = self._rollout(node)

            # 4. Backpropagation
            while node is not None:
                node.visits += 1
                mover = -node.to_move
                node.wins += black_result if mover == BLACK else 1.0 - black_result
                node = node.parent

        best = max(root.children, key=lambda ch: ch.visits)
        self.last_stats = {
            "simulations": self.simulations,
            "visits": best.visits,
            "win_rate": best.wins / best.visits,
            "time": time.perf_counter() - t0,
        }
        return best.move

    def _rollout(self, node):
        """Random playout. Returns the result from Black's view: 1 win, 0 loss."""
        squares, to_move = node.squares, node.to_move
        if node.draw:
            return 0.5
        if node.is_terminal():
            return 0.0 if to_move == BLACK else 1.0
        choice = self.rng.choice
        for _ in range(self.rollout_depth):
            moves = get_legal_moves(squares, to_move)
            if not moves:
                return 0.0 if to_move == BLACK else 1.0   # side to move loses
            squares = apply_move(squares, choice(moves))
            to_move = -to_move
        # Rollout cut short: convert the heuristic score into a win probability.
        score = evaluate(squares, BLACK)
        return 1.0 / (1.0 + math.exp(-score / 200.0))
