"""Global configuration: layout, colours, difficulty tables and rule options.

Everything that a user might want to tweak lives here so the rest of the code
never contains magic numbers.
"""

# ---------------------------------------------------------------------------
# Presentation / credits (taken from the project slides)
# ---------------------------------------------------------------------------
GAME_TITLE = "THE Checker GAME"
CREDITS = ["Priom Sarker - 2207048", "Md. Toufiq Hasan - 2207049"]

# ---------------------------------------------------------------------------
# Window and board layout (pixels)
# ---------------------------------------------------------------------------
BOARD_SIZE = 8
SQUARE_SIZE = 76
BOARD_PIXELS = SQUARE_SIZE * BOARD_SIZE          # 608
FRAME_WIDTH = 18                                 # wooden frame around the grid
MARGIN = 20

FRAME_X = MARGIN
FRAME_Y = MARGIN
FRAME_SIZE = BOARD_PIXELS + 2 * FRAME_WIDTH
BOARD_X = FRAME_X + FRAME_WIDTH                  # top-left of square (0, 0)
BOARD_Y = FRAME_Y + FRAME_WIDTH

SIDEBAR_X = FRAME_X + FRAME_SIZE + MARGIN
SIDEBAR_W = 300
WINDOW_WIDTH = SIDEBAR_X + SIDEBAR_W + MARGIN
WINDOW_HEIGHT = FRAME_Y + FRAME_SIZE + MARGIN
FPS = 60

PIECE_RADIUS = int(SQUARE_SIZE * 0.39)

# ---------------------------------------------------------------------------
# Colours sampled from the board illustrations in the slides
# ---------------------------------------------------------------------------
# Wooden board
LIGHT_SQUARE = (236, 214, 181)      # pale maple squares
LIGHT_GRAIN = (222, 195, 158)
DARK_SQUARE = (141, 89, 45)         # walnut squares (playable)
DARK_GRAIN = (122, 75, 35)
FRAME_COLOR = (124, 76, 36)         # outer wooden frame
FRAME_GRAIN = (105, 62, 27)
FRAME_EDGE = (82, 48, 20)           # thin dark line between frame and grid

# Pieces
RED_PIECE = (214, 12, 12)
RED_RIM = (140, 0, 0)
RED_RING = (182, 0, 0)
RED_CROWN = (255, 205, 205)
BLACK_PIECE = (52, 52, 52)
BLACK_RIM = (14, 14, 14)
BLACK_RING = (34, 34, 34)
BLACK_CROWN = (205, 205, 205)

# Indicators (white rings as used in the slides, coral for captures)
SELECT_RING = (255, 255, 255)
MOVE_RING = (255, 255, 255)
MOVE_FILL = (90, 55, 25, 90)        # translucent brown inside move rings
CAPTURE_COLOR = (255, 90, 95)       # slide accent coral
MUST_CAPTURE_RING = (255, 196, 64)
LAST_MOVE_COLOR = (255, 255, 255, 150)

# Slide theme (menus and sidebar)
BG_COLOR = (255, 255, 255)
TITLE_BLUE = (32, 8, 168)
ACCENT_CORAL = (255, 90, 95)
DECOR_BROWN = (138, 88, 44)
TEXT_DARK = (20, 20, 20)
TEXT_MUTED = (110, 110, 120)
PANEL_BG = (250, 246, 240)
PANEL_BORDER = (225, 212, 195)
BUTTON_BG = (32, 8, 168)
BUTTON_HOVER = (60, 36, 200)
BUTTON_TEXT = (255, 255, 255)
BUTTON_ALT_BG = (255, 255, 255)
BUTTON_DISABLED = (190, 190, 200)
TOGGLE_ON = (255, 90, 95)

# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
FIRST_PLAYER = "black"              # standard checkers: Black moves first

# False: a player may capture OR make an ordinary move (capturing is optional).
# True : standard tournament rule - if any capture exists, a capture must be made.
# Either way, once a capture sequence is started it must be completed.
MANDATORY_CAPTURE = False
REPETITION_LIMIT = 3                # threefold repetition -> draw

# Standard "40-move rule": the game is drawn if 40 moves per side (80 plies)
# pass without any capture or any man (non-king) moving.  It only matters in
# long king-vs-king endgames and guarantees that AI vs AI games always finish.
ENABLE_MOVE_LIMIT_DRAW = True
MOVE_LIMIT_PLIES = 80

# ---------------------------------------------------------------------------
# AI configuration (from the "Game Modes & Difficulty Levels" slide)
# ---------------------------------------------------------------------------
DIFFICULTIES = ["Easy", "Medium", "Hard"]

# Human vs AI: Minimax + Alpha-Beta Pruning
HUMAN_VS_AI = {
    "Easy": {"depth": 2},
    "Medium": {"depth": 4},
    "Hard": {"depth": 8},           # slide: depth 6-8
}

# AI vs AI: Minimax (agent 1) vs MCTS (agent 2)
AI_VS_AI = {
    "Easy": {"minimax_depth": 2, "mcts_simulations": 100},
    "Medium": {"minimax_depth": 4, "mcts_simulations": 500},
    "Hard": {"minimax_depth": 6, "mcts_simulations": 2000},
}

# Minimax: after the nominal depth is reached, pending forced captures are
# still searched (up to this many extra plies) so the evaluation is never
# taken in the middle of an exchange.
QUIESCENCE_DEPTH = 8

# MCTS
MCTS_EXPLORATION = 1.414            # UCT constant (~sqrt(2))
MCTS_ROLLOUT_DEPTH = 40             # plies before a rollout is scored heuristically

# ---------------------------------------------------------------------------
# Pacing of the GUI
# ---------------------------------------------------------------------------
ANIM_SEGMENT_TIME = 0.18            # seconds per hop when animating AI moves
AI_MOVE_DELAY = 0.30                # pause before an AI starts thinking
RESULTS_DIR = "results"
