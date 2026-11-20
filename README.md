# THE Checker GAME — AI Checkers (Python + Pygame)

A complete checkers game with three modes (Human vs Human, Human vs AI, AI vs AI)
and two AI agents: **Minimax with Alpha-Beta Pruning** and **Monte Carlo Tree Search**.
The board reproduces the wooden board used in the project slides: maple and walnut
squares in a wooden frame, flat red and black discs with a dark rim and inner ring,
crowned kings, white rings for moves and white curved arrows for the last move.

## Running

```
pip install -r requirements.txt
python main.py                      # the game
python -m unittest discover -s tests -v   # rule and AI tests
python benchmark.py --games 20      # AI vs AI experiments (all difficulties)
python benchmark.py --summary       # summary of every recorded AI vs AI game
```

## Controls

* Click a piece to select it; white rings show where it can go. Coral rings and
  an ✕ mark a capture. Click a ring to move.
* In a multiple capture, click each landing square in turn; the turn only ends
  when the sequence is complete.
* Capturing is optional: when a capture is available you may take it or make
  any other legal move. (With `MANDATORY_CAPTURE = True` in `config.py`, the
  pieces that must capture are outlined in gold and other moves are refused.)
* AI vs AI: **Start**, **Pause/Resume** (also the Space key) and **Reset**.
* **Restart** and **Menu** are always available; Esc returns to the menu.

## Rules implemented

* 8×8 board, 12 pieces each, pieces only on the dark squares. Black (bottom) moves first.
* Ordinary pieces move one square diagonally forward and capture by jumping
  diagonally forward over an enemy piece into the empty square behind it.
* Capturing is **optional** (setting `MANDATORY_CAPTURE` in `config.py`; set it to
  `True` for the standard forced-capture rule). Once a capture is started, the
  capturing piece must keep jumping while it can (multiple captures in one turn).
  A piece cannot be jumped twice in one move.
* A piece reaching the opponent's back row becomes a King; crowning ends the move.
* Kings move and capture diagonally forwards and backwards.
* A player loses when all of their pieces are captured or when they have no legal move.
* **Threefold repetition**: the game is drawn when the same board position occurs
  for the third time with the same player to move (board + side to move fully
  determines the legal moves, so it is also the same legal-move situation).
* **40-move rule** (standard checkers rule, can be turned off in `config.py`):
  a draw after 40 moves per side with no capture and no ordinary-piece move. It
  only affects long king endgames and guarantees AI vs AI games always finish.

Humans and both AIs use the same legal-move generator (`move_generator.py`), and
`GameState.make_move` rejects any move that generator does not produce.

## Game modes and difficulty

| Human vs AI | Algorithm | Configuration |
|---|---|---|
| Easy | Minimax + Alpha-Beta | depth 2 |
| Medium | Minimax + Alpha-Beta | depth 4 |
| Hard | Minimax + Alpha-Beta | depth 8 |

| AI vs AI | Agent 1 (Minimax + α-β) | Agent 2 (MCTS) |
|---|---|---|
| Easy | depth 2 | 100 simulations |
| Medium | depth 4 | 500 simulations |
| Hard | depth 6 | 2,000 simulations |

In Human vs AI you choose your colour; in AI vs AI you choose which colour Minimax plays.
AI agents run on a background thread, so the window keeps redrawing while they think.

## AI algorithms

**Minimax + Alpha-Beta (`minimax.py`)**: explicit MAX/MIN search with alpha-beta
cut-offs, iterative deepening up to the configured depth, move ordering
(previous best move from a transposition table, then longest captures, then
promotions) and a capture extension so positions are never evaluated in the
middle of an exchange (with optional captures, declining is also considered). Positions that already occurred in the game are
scored as draws, so a side that is ahead keeps making progress.

**Heuristic (`evaluation.py`)**: piece count (man 100, king 160), positional
terms (advancement, back-row guard, centre control, safe edges, central kings)
and endgame terms (trade down when ahead, kings approach the remaining enemy pieces).

**MCTS (`mcts.py`)**: UCT selection (c = 1.414), expansion of one untried move,
random legal-move rollouts (scored with the heuristic after 40 plies if the game
has not ended), and backpropagation. The most-visited root move is played.
A child position that would be the third repetition is treated as a draw.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Entry point |
| `ui.py` | Menus, buttons, sidebar, game screen and main loop |
| `game.py` | `GameState` (turns, captures, win/draw detection) and the background `AIWorker` |
| `board.py` | `Board` data and `BoardRenderer` (the slide-style wooden board) |
| `piece.py` | Piece codes, King promotion and movement directions |
| `move_generator.py` | Legal moves, captures, multiple jumps, applying moves |
| `evaluation.py` | Heuristic evaluation |
| `minimax.py` | Minimax with Alpha-Beta Pruning |
| `mcts.py` | Monte Carlo Tree Search |
| `config.py` | Layout, colours, rules options and difficulty tables |
| `stats.py` | Recording and summarising AI vs AI results |
| `benchmark.py` | Headless AI vs AI experiments |
| `tests/test_rules.py` | Rule and AI tests |

## AI vs AI results

Every finished AI vs AI game (GUI or `benchmark.py`) is appended to
`results/ai_vs_ai_games.csv`, and all statistics are calculated from those rows.
Colours alternate between games in the benchmark. Run `python benchmark.py --summary`
for the current numbers.

### Measured results (optional captures — the current rules)

60 games run with `benchmark.py` on 2026-11-07, colours alternating every game:

| Difficulty | Games | Minimax win | MCTS win | Draw | Minimax avg decision | MCTS avg decision | Avg game length |
|---|---|---|---|---|---|---|---|
| Easy (depth 2 vs 100 sims) | 30 | 100% | 0% | 0% | 0.001 s | 0.073 s | 45.2 plies |
| Medium (depth 4 vs 500 sims) | 20 | 100% | 0% | 0% | 0.031 s | 0.834 s | 50.2 plies |
| Hard (depth 6 vs 2,000 sims) | 10 | 100% | 0% | 0% | 0.137 s | 2.602 s | 55.5 plies |

Games ended by capturing all pieces or leaving the opponent with no legal move;
none reached a draw. Decision times depend on the machine and on other programs
running at the same time (another CPU-heavy program was running during the
Medium and Hard runs), so compare them relative to each other.

### Earlier results with mandatory captures

Before capturing was made optional, 60 games were played with the forced-capture
rule (`results/old_mandatory_capture/`):

| Difficulty | Games | Minimax win | MCTS win | Draw | Minimax avg decision | MCTS avg decision |
|---|---|---|---|---|---|---|
| Easy | 30 | 60.0% | 33.3% | 6.7% | 0.002 s | 0.070 s |
| Medium | 20 | 35.0% | 30.0% | 35.0% | 0.016 s | 0.375 s |
| Hard | 10 | 60.0% | 10.0% | 30.0% | 0.045 s | 0.683 s |

A likely explanation for the difference: with forced captures, MCTS's random
rollouts must still play every capture, so they resemble real games. With
optional captures, random rollouts constantly ignore free pieces and give
pieces away, which makes MCTS's estimates much noisier, while Minimax's
search is unaffected.
