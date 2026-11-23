"""Menus, buttons, sidebar and the main application loop."""

import time

import pygame

import config as C
import stats
from board import BoardRenderer, draw_piece, square_at, square_center
from game import AIWorker, GameState
from mcts import MCTSAgent
from minimax import MinimaxAgent
from move_generator import apply_partial, initial_squares
from piece import BLACK, PLAYER_NAMES, RED, opponent
from sounds import SAMPLE_RATE, SoundManager

HVH, HVAI, AIVAI = "Human vs Human", "Human vs AI", "AI vs AI"
FONT_NAMES = "arialroundedmtbold,segoeuisemibold,segoeui,arial"

_font_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont(FONT_NAMES, size, bold=bold)
    return _font_cache[key]


def draw_text(surface, text, size, color, pos, bold=False, anchor="topleft"):
    img = font(size, bold).render(text, True, color)
    rect = img.get_rect(**{anchor: pos})
    surface.blit(img, rect)
    return rect


def wrap_text(text, size, width, bold=False):
    words, lines, line = text.split(), [], ""
    f = font(size, bold)
    for w in words:
        trial = f"{line} {w}".strip()
        if f.size(trial)[0] <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


class Button:
    def __init__(self, rect, text, action, style="primary", size=20):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.action = action
        self.style = style          # primary | secondary | toggle
        self.size = size
        self.enabled = True
        self.selected = False

    def draw(self, surface, mouse):
        hover = self.enabled and self.rect.collidepoint(mouse)
        if not self.enabled:
            bg, fg, border = C.BUTTON_DISABLED, C.BUTTON_TEXT, C.BUTTON_DISABLED
        elif self.style == "primary":
            bg, fg, border = (C.BUTTON_HOVER if hover else C.BUTTON_BG), C.BUTTON_TEXT, C.BUTTON_BG
        elif self.style == "toggle" and self.selected:
            bg, fg, border = C.TOGGLE_ON, C.BUTTON_TEXT, C.TOGGLE_ON
        else:
            bg = (243, 240, 252) if hover else C.BUTTON_ALT_BG
            fg, border = C.TITLE_BLUE, C.TITLE_BLUE
        pygame.draw.rect(surface, bg, self.rect, border_radius=10)
        pygame.draw.rect(surface, border, self.rect, 2, border_radius=10)
        draw_text(surface, self.text, self.size, fg, self.rect.center, bold=True, anchor="center")

    def hit(self, pos):
        return self.enabled and self.rect.collidepoint(pos)


def draw_decor(surface):
    """Brown rounded corner shapes used on every slide of the presentation."""
    w, h = surface.get_size()
    pygame.draw.rect(surface, C.DECOR_BROWN, pygame.Rect(-60, -60, 130, 290), border_radius=65)
    pygame.draw.rect(surface, C.DECOR_BROWN, pygame.Rect(w - 70, h - 230, 130, 290), border_radius=65)


class App:
    def __init__(self):
        pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption(f"{C.GAME_TITLE} - AI Checkers")
        icon = pygame.Surface((32, 32), pygame.SRCALPHA)
        pygame.draw.circle(icon, C.RED_RIM, (16, 16), 15)
        pygame.draw.circle(icon, C.RED_PIECE, (16, 16), 12)
        pygame.display.set_icon(icon)
        flags = pygame.SCALED | pygame.RESIZABLE
        if getattr(C, "FULLSCREEN", True):
            flags |= pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((C.WINDOW_WIDTH, C.WINDOW_HEIGHT), flags)
        self.clock = pygame.time.Clock()
        self.renderer = BoardRenderer()
        self.running = True
        self.sounds = SoundManager()
        self.sound_rect = pygame.Rect(C.WINDOW_WIDTH - C.MARGIN - 38, 16, 38, 34)

        self.screen_name = "menu"
        self.mode = None
        self.difficulty = "Medium"
        self.human_color = BLACK
        self.minimax_color = BLACK
        self.game = None
        self.worker = None
        self.session_stats = {}       # difficulty -> list of records (this session)

        self.menu_preview = self._make_preview()
        self._build_menu()

    # ------------------------------------------------------------------
    # Screens and buttons
    # ------------------------------------------------------------------
    def _make_preview(self):
        surf = pygame.Surface((C.WINDOW_WIDTH, C.WINDOW_HEIGHT))
        self.renderer.draw(surf, initial_squares())
        crop = surf.subsurface(pygame.Rect(C.FRAME_X, C.FRAME_Y, C.FRAME_SIZE, C.FRAME_SIZE)).copy()
        return pygame.transform.smoothscale(crop, (430, 430))

    @property
    def is_fullscreen(self):
        surf = pygame.display.get_surface()
        return bool(surf and (surf.get_flags() & pygame.FULLSCREEN))

    def toggle_fullscreen(self):
        try:
            pygame.display.toggle_fullscreen()
        except pygame.error:
            pass
        if hasattr(self, "fs_button"):
            self.fs_button.text = "Windowed" if self.is_fullscreen else "Fullscreen"

    def _build_menu(self):
        x, y = 70, 330
        fs_label = "Windowed" if self.is_fullscreen else "Fullscreen"
        self.fs_button = Button((x, y + 192, 154, 50), fs_label, ("toggle_fullscreen",),
                                style="secondary", size=17)
        self.buttons = [
            Button((x, y, 320, 50), HVH, ("mode", HVH)),
            Button((x, y + 64, 320, 50), HVAI, ("mode", HVAI)),
            Button((x, y + 128, 320, 50), AIVAI, ("mode", AIVAI)),
            self.fs_button,
            Button((x + 166, y + 192, 154, 50), "Quit", ("quit",), style="secondary"),
        ]

    def _build_setup(self):
        self.buttons = []
        x0 = 120
        for i, d in enumerate(C.DIFFICULTIES):
            b = Button((x0 + i * 200, 230, 180, 52), d, ("difficulty", d), style="toggle")
            b.selected = d == self.difficulty
            self.buttons.append(b)
        current = self.human_color if self.mode == HVAI else self.minimax_color
        for i, (label, color) in enumerate((("Black (moves first)", BLACK), ("Red", RED))):
            b = Button((x0 + i * 300, 470, 280, 50), label, ("color", color), style="toggle", size=18)
            b.selected = color == current
            self.buttons.append(b)
        self.buttons.append(Button((x0, 580, 260, 54), "Start Game", ("start",)))
        self.buttons.append(Button((x0 + 300, 580, 180, 54), "Back", ("menu",), style="secondary"))

    def _build_game_buttons(self):
        x, w = C.SIDEBAR_X, C.SIDEBAR_W
        bottom = C.WINDOW_HEIGHT - C.MARGIN - 46
        self.buttons = [
            Button((x, bottom, w // 2 - 6, 46), "Restart", ("restart",), style="secondary"),
            Button((x + w // 2 + 6, bottom, w // 2 - 6, 46), "Menu", ("menu",), style="secondary"),
        ]
        if self.mode == AIVAI:
            self.ctrl_button = Button((x, 352, w // 2 - 6, 44), "Start", ("toggle_run",), size=19)
            self.buttons.append(self.ctrl_button)
            self.buttons.append(Button((x + w // 2 + 6, 352, w // 2 - 6, 44), "Reset", ("reset",),
                                       style="secondary", size=19))
        # overlay buttons (only active when the game is over)
        cx, cy = C.BOARD_X + C.BOARD_PIXELS // 2, C.BOARD_Y + C.BOARD_PIXELS // 2
        self.overlay_buttons = [
            Button((cx - 170, cy + 40, 160, 48), "Play Again", ("restart",)),
            Button((cx + 10, cy + 40, 160, 48), "Main Menu", ("menu",), style="secondary"),
        ]

    # ------------------------------------------------------------------
    # Game session management
    # ------------------------------------------------------------------
    def new_game(self, autostart=True):
        self._cancel_worker()
        self.game = GameState()
        self.players = {BLACK: None, RED: None}
        if self.mode == HVAI:
            depth = C.HUMAN_VS_AI[self.difficulty]["depth"]
            self.players[opponent(self.human_color)] = MinimaxAgent(depth)
        elif self.mode == AIVAI:
            cfg = C.AI_VS_AI[self.difficulty]
            self.players[self.minimax_color] = MinimaxAgent(cfg["minimax_depth"])
            self.players[opponent(self.minimax_color)] = MCTSAgent(cfg["mcts_simulations"])
        self.selected_path = []
        self.anim = None
        self.flash = None             # (text, until) short-lived hint after a bad click
        self.decision_times = {BLACK: [], RED: []}
        self.last_decision = {BLACK: None, RED: None}
        self.result_recorded = False
        self.started = autostart if self.mode == AIVAI else True
        self.paused = False
        self.ai_ready_at = time.perf_counter() + C.AI_MOVE_DELAY
        self.error = None
        self.screen_name = "game"
        self._build_game_buttons()

    def _cancel_worker(self):
        if self.worker is not None:
            self.worker.cancel()
            self.worker = None

    def is_human_turn(self):
        return self.game is not None and not self.game.over and self.players[self.game.turn] is None

    def play_move(self, move, animate):
        pre = list(self.game.squares)
        piece = pre[move.start]
        move = self.game.make_move(move)
        self.selected_path = []
        now = time.perf_counter()
        duration = 0.0
        if animate:
            duration = C.ANIM_SEGMENT_TIME * (len(move.path) - 1)
            self.anim = {"pre": pre, "move": move, "piece": piece, "t0": now, "duration": duration,
                         "hops_played": 0}
        else:
            self._play_move_sound(move, final=True)
        self.ai_ready_at = now + duration + C.AI_MOVE_DELAY

    def update_game(self):
        now = time.perf_counter()
        if self.anim:
            self._play_anim_sounds(now)
        if self.anim and now - self.anim["t0"] >= self.anim["duration"]:
            self.anim = None
        if self.game.over:
            if not self.anim and not self.result_recorded:
                self._record_result()
            return
        if self.anim or self.error:
            return
        agent = self.players[self.game.turn]
        if agent is None:
            return
        if self.mode == AIVAI and not self.started:
            return
        if self.worker is None:
            if not self.paused and now >= self.ai_ready_at:
                self.worker = AIWorker(agent, self.game.squares, self.game.turn,
                                       self.game.position_counts)
        elif self.worker.done and not self.paused:
            worker, self.worker = self.worker, None
            if worker.error is not None:
                self.error = f"AI error: {worker.error}"
                return
            if worker.move is None:
                return
            self.decision_times[worker.player].append(worker.elapsed)
            self.last_decision[worker.player] = worker.elapsed
            self.play_move(worker.move, animate=True)

    def _play_move_sound(self, move, final):
        self.sounds.play("capture" if move.captures else "move")
        if final and move.promotes:
            self.sounds.play("king")

    def _play_anim_sounds(self, now):
        """Play one sound as the animated piece lands on each square."""
        a = self.anim
        hops = len(a["move"].path) - 1
        landed = min(hops, int((now - a["t0"]) / C.ANIM_SEGMENT_TIME))
        while a["hops_played"] < landed:
            a["hops_played"] += 1
            self._play_move_sound(a["move"], final=a["hops_played"] == hops)

    def _play_result_sound(self):
        game = self.game
        if game.is_draw:
            self.sounds.play("draw")
        elif self.mode == HVAI and self.players[game.winner] is not None:
            self.sounds.play("lose")
        else:
            self.sounds.play("win")

    def _record_result(self):
        self.result_recorded = True
        self._play_result_sound()
        if self.mode != AIVAI:
            return
        mm = self.players[self.minimax_color]
        mc = self.players[opponent(self.minimax_color)]
        record = stats.make_record(
            "gui", self.difficulty, mm, mc, self.minimax_color, self.game,
            self.decision_times[self.minimax_color], self.decision_times[opponent(self.minimax_color)])
        self.session_stats.setdefault(self.difficulty, []).append(record)
        try:
            stats.append_record(record)
        except OSError:
            pass  # results file not writable: the in-window statistics still work

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def handle_action(self, action):
        kind = action[0]
        if kind == "quit":
            self.running = False
        elif kind == "mode":
            self.mode = action[1]
            if self.mode == HVH:
                self.new_game()
            else:
                self.screen_name = "setup"
                self._build_setup()
        elif kind == "difficulty":
            self.difficulty = action[1]
            self._build_setup()
        elif kind == "color":
            if self.mode == HVAI:
                self.human_color = action[1]
            else:
                self.minimax_color = action[1]
            self._build_setup()
        elif kind == "start":
            self.new_game(autostart=False)
        elif kind == "menu":
            self._cancel_worker()
            self.game = None
            self.screen_name = "menu"
            self._build_menu()
        elif kind == "restart":
            self.new_game(autostart=True)
        elif kind == "reset":
            self.new_game(autostart=False)
        elif kind == "toggle_run":
            if not self.started:
                self.started = True
                self.ai_ready_at = time.perf_counter() + 0.1
            else:
                self.paused = not self.paused
                if not self.paused:
                    self.ai_ready_at = time.perf_counter() + 0.1
        elif kind == "toggle_fullscreen":
            self.toggle_fullscreen()

    def on_board_click(self, pos):
        if not self.is_human_turn() or self.anim:
            return
        idx = square_at(pos)
        if idx is None:
            return
        game = self.game
        legal = game.legal_moves()
        sp = self.selected_path

        if sp:
            k = len(sp)
            candidates = [m for m in legal if m.path[:k] == tuple(sp)]
            if idx in {m.path[k] for m in candidates}:
                sp.append(idx)
                full = [m for m in candidates if m.path == tuple(sp)]
                if full:
                    self.play_move(full[0], animate=False)
                else:
                    self.sounds.play("capture")     # one hop of a multiple capture
                return
            if k > 1:
                self._flash("You must keep capturing with this piece.")
                return
            if idx == sp[0]:
                self.selected_path = []
                self.sounds.play("click")
                return

        # (re)select a piece
        if game.squares[idx] * game.turn > 0:
            if any(m.start == idx for m in legal):
                self.selected_path = [idx]
                self.sounds.play("select")
            elif C.MANDATORY_CAPTURE and any(m.is_capture for m in legal):
                self.selected_path = []
                self._flash("Capture is mandatory - choose a piece that can jump.")
            else:
                self.selected_path = []
                self._flash("That piece has no legal moves.")
        else:
            self.selected_path = []

    def _flash(self, text):
        self.flash = (text, time.perf_counter() + 2.5)
        self.sounds.play("invalid")

    def _press(self, action):
        """Run a button action with its sound."""
        starts_game = action[0] in ("start", "restart", "reset") or action == ("mode", HVH)
        self.sounds.play("start" if starts_game else "click")
        self.handle_action(action)

    def _draw_sound_button(self, mouse):
        """Speaker icon in the top-right corner."""
        s, r = self.screen, self.sound_rect
        color = C.TITLE_BLUE if self.sounds.enabled else C.TEXT_MUTED
        if r.collidepoint(mouse):
            pygame.draw.rect(s, (243, 240, 252), r, border_radius=8)
        pygame.draw.rect(s, color, r, 2, border_radius=8)
        x, y = r.x + 8, r.centery
        pygame.draw.polygon(s, color, [(x, y - 4), (x + 5, y - 4), (x + 11, y - 9),
                                       (x + 11, y + 9), (x + 5, y + 4), (x, y + 4)])
        if self.sounds.enabled:
            pygame.draw.arc(s, color, (x + 7, y - 6, 10, 12), -1.1, 1.1, 2)
            pygame.draw.arc(s, color, (x + 7, y - 10, 15, 20), -1.1, 1.1, 2)
        else:
            pygame.draw.line(s, C.ACCENT_CORAL, (x + 14, y - 5), (x + 22, y + 5), 2)
            pygame.draw.line(s, C.ACCENT_CORAL, (x + 22, y - 5), (x + 14, y + 5), 2)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_m:
                self.sounds.toggle()
            elif event.key == pygame.K_ESCAPE:
                if self.screen_name == "menu":
                    self.running = False
                else:
                    self.handle_action(("menu",))
            elif event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and (event.mod & pygame.KMOD_ALT)):
                self.toggle_fullscreen()
            elif self.screen_name == "game" and event.key == pygame.K_SPACE and self.mode == AIVAI:
                self.handle_action(("toggle_run",))
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.sound_rect.collidepoint(event.pos):
                if self.sounds.toggle():
                    self.sounds.play("click")
                return
            if self.screen_name == "game" and self.game.over and not self.anim:
                for b in self.overlay_buttons:
                    if b.hit(event.pos):
                        self._press(b.action)
                        return
            for b in list(self.buttons):
                if b.hit(event.pos):
                    self._press(b.action)
                    return
            if self.screen_name == "game":
                self.on_board_click(event.pos)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw_menu(self, mouse):
        s = self.screen
        s.fill(C.BG_COLOR)
        draw_decor(s)
        draw_text(s, "THE", 64, C.TEXT_DARK, (230, 60), bold=True, anchor="midtop")
        draw_text(s, "Checker", 76, C.TEXT_DARK, (230, 130), bold=True, anchor="midtop")
        draw_text(s, "GAME", 64, C.TEXT_DARK, (230, 214), bold=True, anchor="midtop")
        s.blit(self.menu_preview, (C.WINDOW_WIDTH - 430 - 90, 70))
        draw_text(s, "AI Checkers  ·  Minimax α-β  ·  MCTS", 18, C.ACCENT_CORAL,
                  (C.WINDOW_WIDTH - 90 - 215, 520), bold=True, anchor="midtop")
        draw_text(s, "By", 22, C.TITLE_BLUE, (C.WINDOW_WIDTH - 90 - 430, 560), bold=True)
        for i, name in enumerate(C.CREDITS):
            draw_text(s, name, 18, C.TITLE_BLUE, (C.WINDOW_WIDTH - 90 - 430, 592 + i * 28), bold=True)
        for b in self.buttons:
            b.draw(s, mouse)
        self._draw_sound_button(mouse)

    def draw_setup(self, mouse):
        s = self.screen
        s.fill(C.BG_COLOR)
        draw_decor(s)
        x0 = 120
        draw_text(s, self.mode, 44, C.TITLE_BLUE, (x0, 50), bold=True)
        draw_text(s, "Game Modes & Difficulty Levels", 20, C.ACCENT_CORAL, (x0, 110), bold=True)
        draw_text(s, "Difficulty", 24, C.TEXT_DARK, (x0, 190), bold=True)

        if self.mode == HVAI:
            depth = C.HUMAN_VS_AI[self.difficulty]["depth"]
            lines = [f"Opponent: Minimax + Alpha-Beta Pruning, search depth {depth}"]
            draw_text(s, "Play as", 24, C.TEXT_DARK, (x0, 430), bold=True)
        else:
            cfg = C.AI_VS_AI[self.difficulty]
            lines = [f"AI Agent 1: Minimax + Alpha-Beta Pruning (depth {cfg['minimax_depth']})",
                     f"AI Agent 2: Monte Carlo Tree Search ({cfg['mcts_simulations']:,} simulations)"]
            draw_text(s, "Minimax plays", 24, C.TEXT_DARK, (x0, 430), bold=True)
        panel = pygame.Rect(x0, 305, 770, 100)
        pygame.draw.rect(s, C.PANEL_BG, panel, border_radius=12)
        pygame.draw.rect(s, C.PANEL_BORDER, panel, 2, border_radius=12)
        for i, line in enumerate(lines):
            draw_text(s, line, 20, C.TEXT_DARK, (x0 + 22, 322 + i * 34), bold=i == 0 or self.mode == AIVAI)
        for b in self.buttons:
            b.draw(s, mouse)
        self._draw_sound_button(mouse)

    def _display_state(self):
        """Squares to draw, plus squares to hide and the animated piece."""
        if self.anim:
            a = self.anim
            path, caps = a["move"].path, a["move"].captures
            elapsed = time.perf_counter() - a["t0"]
            seg = min(int(elapsed / C.ANIM_SEGMENT_TIME), len(path) - 2)
            frac = min(1.0, (elapsed - seg * C.ANIM_SEGMENT_TIME) / C.ANIM_SEGMENT_TIME)
            squares = list(a["pre"])
            for c in caps[:seg]:
                squares[c] = 0
            (x1, y1), (x2, y2) = square_center(path[seg]), square_center(path[seg + 1])
            pos = (x1 + (x2 - x1) * frac, y1 + (y2 - y1) * frac)
            return squares, {path[0]}, (pos, a["piece"])
        if self.selected_path:
            return apply_partial(self.game.squares, self.selected_path), set(), None
        return self.game.squares, set(), None

    def draw_game(self, mouse):
        s = self.screen
        s.fill(C.BG_COLOR)
        game = self.game
        squares, hidden, moving = self._display_state()

        selected, dests, cap_dests, cap_targets, must = None, [], set(), [], set()
        if self.is_human_turn() and not self.anim:
            legal = game.legal_moves()
            sp = self.selected_path
            if sp:
                k = len(sp)
                cands = [m for m in legal if m.path[:k] == tuple(sp)]
                selected = sp[-1]
                for m in cands:
                    nxt = m.path[k]
                    if nxt not in dests:
                        dests.append(nxt)
                    if m.is_capture:
                        cap_dests.add(nxt)
                        cap_targets.append((sp[-1] + nxt) // 2)
            elif C.MANDATORY_CAPTURE and any(m.is_capture for m in legal):
                must = {m.start for m in legal}

        last = game.last_move if (not self.anim and not self.selected_path) else None
        self.renderer.draw(s, squares, hidden=hidden, selected=selected, destinations=dests,
                           capture_targets=cap_targets, capture_destinations=cap_dests,
                           must_capture=must, last_move=last)
        if moving:
            draw_piece(s, moving[0], moving[1])

        self.draw_sidebar(mouse)
        if game.over and not self.anim:
            self.draw_game_over(mouse)
        self._draw_sound_button(mouse)

    def _player_role(self, color):
        agent = self.players[color]
        if agent is not None:
            return agent.label
        if self.mode == HVAI:
            return "You"
        return "Player 1" if color == BLACK else "Player 2"

    def _status_text(self):
        game = self.game
        if self.error:
            return self.error, C.ACCENT_CORAL
        if game.over:
            if game.is_draw:
                return f"Draw - {game.result_reason}.", C.TITLE_BLUE
            return f"{PLAYER_NAMES[game.winner]} wins - {game.result_reason}.", C.TITLE_BLUE
        if self.flash and time.perf_counter() < self.flash[1]:
            return self.flash[0], C.ACCENT_CORAL
        name = PLAYER_NAMES[game.turn]
        agent = self.players[game.turn]
        if self.mode == AIVAI and not self.started:
            return "Press Start to begin the match.", C.TEXT_DARK
        if self.mode == AIVAI and self.paused:
            return "Match paused. Press Resume to continue.", C.TEXT_DARK
        if agent is not None:
            if self.worker is not None:
                dots = "." * (int(time.perf_counter() * 3) % 4)
                return f"{agent.short_label} ({name}) is thinking{dots}", C.TEXT_DARK
            return f"{name} ({agent.short_label}) to move.", C.TEXT_DARK
        if len(self.selected_path) > 1:
            return "Continue capturing with the same piece.", C.ACCENT_CORAL
        legal = game.legal_moves()
        who = "Your" if self.mode == HVAI else f"{name}'s"
        if any(m.is_capture for m in legal):
            if C.MANDATORY_CAPTURE:
                return f"{name} to move - a capture is mandatory!", C.ACCENT_CORAL
            return f"{who} turn. A capture is available (optional).", C.TEXT_DARK
        return f"{who} turn. Select a piece to move.", C.TEXT_DARK

    def draw_sidebar(self, mouse):
        s = self.screen
        x, w = C.SIDEBAR_X, C.SIDEBAR_W
        game = self.game
        draw_text(s, self.mode, 28, C.TITLE_BLUE, (x, 18), bold=True)
        sub = "Local two-player game" if self.mode == HVH else f"Difficulty: {self.difficulty}"
        draw_text(s, sub, 18, C.ACCENT_CORAL, (x, 54), bold=True)

        # Player cards: Red on top (its side of the board), Black below.
        for i, color in enumerate((RED, BLACK)):
            rect = pygame.Rect(x, 86 + i * 84, w, 74)
            active = not game.over and game.turn == color
            pygame.draw.rect(s, C.PANEL_BG, rect, border_radius=12)
            pygame.draw.rect(s, C.ACCENT_CORAL if active else C.PANEL_BORDER, rect,
                             3 if active else 2, border_radius=12)
            draw_piece(s, (rect.x + 34, rect.centery), color, radius=20)
            draw_text(s, PLAYER_NAMES[color], 20, C.TEXT_DARK, (rect.x + 64, rect.y + 10), bold=True)
            role = self._player_role(color)
            role_size = next(sz for sz in (16, 15, 14, 13, 12)
                             if font(sz, True).size(role)[0] <= rect.w - 64 - 74 or sz == 12)
            draw_text(s, role, role_size, C.TEXT_MUTED, (rect.x + 64, rect.y + 38), bold=True)
            draw_text(s, str(game.captured[color]), 26, C.TITLE_BLUE, (rect.right - 16, rect.y + 6),
                      bold=True, anchor="topright")
            draw_text(s, "captured", 13, C.TEXT_MUTED, (rect.right - 14, rect.y + 40), anchor="topright")
            if active:
                agent = self.players[color]
                tag = "THINKING" if (agent is not None and self.worker is not None) else "TO MOVE"
                tag_img = font(12, True).render(tag, True, C.BUTTON_TEXT)
                tag_rect = tag_img.get_rect(topright=(rect.right - 70, rect.y + 10)).inflate(12, 6)
                pygame.draw.rect(s, C.ACCENT_CORAL, tag_rect, border_radius=8)
                s.blit(tag_img, tag_img.get_rect(center=tag_rect.center))

        # Status message
        status_rect = pygame.Rect(x, 262, w, 78)
        pygame.draw.rect(s, (255, 255, 255), status_rect, border_radius=12)
        pygame.draw.rect(s, C.PANEL_BORDER, status_rect, 2, border_radius=12)
        text, color = self._status_text()
        for i, line in enumerate(wrap_text(text, 17, w - 28, bold=True)[:3]):
            draw_text(s, line, 17, color, (x + 14, status_rect.y + 12 + i * 22), bold=True)

        if self.mode == AIVAI:
            if not self.started:
                self.ctrl_button.text = "Start"
            else:
                self.ctrl_button.text = "Resume" if self.paused else "Pause"
            self.ctrl_button.enabled = not game.over
            self.draw_ai_panel(pygame.Rect(x, 408, w, 200))
        else:
            self.draw_info_panel(pygame.Rect(x, 352, w, 150))

        for b in self.buttons:
            b.draw(s, mouse)

    def draw_info_panel(self, rect):
        s = self.screen
        game = self.game
        pygame.draw.rect(s, C.PANEL_BG, rect, border_radius=12)
        pygame.draw.rect(s, C.PANEL_BORDER, rect, 2, border_radius=12)
        b = game.board
        rows = [
            ("Moves played", str(len(game.history))),
            ("Pieces  (Red / Black)", f"{b.count(RED)} / {b.count(BLACK)}"),
            ("Kings  (Red / Black)", f"{b.king_count(RED)} / {b.king_count(BLACK)}"),
            ("Repetitions of position", f"{game.position_counts[game.position_key()]} / {C.REPETITION_LIMIT}"),
        ]
        if self.mode == HVAI and self.last_decision[opponent(self.human_color)] is not None:
            rows.append(("AI last decision", f"{self.last_decision[opponent(self.human_color)]:.2f} s"))
        for i, (k, v) in enumerate(rows):
            y = rect.y + 14 + i * 26
            draw_text(s, k, 15, C.TEXT_MUTED, (rect.x + 14, y), bold=True)
            draw_text(s, v, 15, C.TEXT_DARK, (rect.right - 14, y), bold=True, anchor="topright")

    def draw_ai_panel(self, rect):
        s = self.screen
        pygame.draw.rect(s, C.PANEL_BG, rect, border_radius=12)
        pygame.draw.rect(s, C.PANEL_BORDER, rect, 2, border_radius=12)
        mm_c, mc_c = self.minimax_color, opponent(self.minimax_color)
        y = rect.y + 10
        draw_text(s, "Decision time (this game)", 15, C.TITLE_BLUE, (rect.x + 14, y), bold=True)
        for color in (mm_c, mc_c):
            y += 22
            times = self.decision_times[color]
            last = self.last_decision[color]
            avg = sum(times) / len(times) if times else 0.0
            txt = f"last {last:.2f}s · avg {avg:.2f}s" if last is not None else "-"
            draw_text(s, f"{self.players[color].short_label}", 15, C.TEXT_MUTED, (rect.x + 14, y), bold=True)
            draw_text(s, txt, 15, C.TEXT_DARK, (rect.right - 14, y), bold=True, anchor="topright")

        y += 30
        records = self.session_stats.get(self.difficulty, [])
        summary = stats.summarize(records).get(self.difficulty)
        draw_text(s, f"Session results ({self.difficulty})", 15, C.TITLE_BLUE, (rect.x + 14, y), bold=True)
        if not summary:
            draw_text(s, "No completed games yet.", 15, C.TEXT_MUTED, (rect.x + 14, y + 24), bold=True)
            return
        rows = [
            ("Games played", f"{summary['games']}"),
            ("Minimax wins", f"{summary['minimax_wins']}  ({summary['minimax_win_rate']:.0%})"),
            ("MCTS wins", f"{summary['mcts_wins']}  ({summary['mcts_win_rate']:.0%})"),
            ("Draws", f"{summary['draws']}  ({summary['draw_rate']:.0%})"),
        ]
        for k, v in rows:
            y += 22
            draw_text(s, k, 15, C.TEXT_MUTED, (rect.x + 14, y), bold=True)
            draw_text(s, v, 15, C.TEXT_DARK, (rect.right - 14, y), bold=True, anchor="topright")

    def draw_game_over(self, mouse):
        s = self.screen
        game = self.game
        shade = pygame.Surface((C.BOARD_PIXELS, C.BOARD_PIXELS), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 120))
        s.blit(shade, (C.BOARD_X, C.BOARD_Y))
        cx, cy = C.BOARD_X + C.BOARD_PIXELS // 2, C.BOARD_Y + C.BOARD_PIXELS // 2
        panel = pygame.Rect(0, 0, 420, 240)
        panel.center = (cx, cy)
        pygame.draw.rect(s, C.BG_COLOR, panel, border_radius=16)
        pygame.draw.rect(s, C.DECOR_BROWN, panel, 4, border_radius=16)

        if game.is_draw:
            title, sub = "Draw!", game.result_reason
        else:
            wname = PLAYER_NAMES[game.winner]
            agent = self.players[game.winner]
            if self.mode == HVAI:
                title = "You Win!" if agent is None else "You Lose!"
            elif self.mode == AIVAI:
                title = f"{agent.short_label} ({wname}) Wins!"
            else:
                title = f"{wname} Wins!"
            sub = game.result_reason
        draw_text(s, title, 36, C.TITLE_BLUE, (cx, panel.y + 30), bold=True, anchor="midtop")
        for i, line in enumerate(wrap_text(sub, 18, 380, bold=True)[:2]):
            draw_text(s, line, 18, C.ACCENT_CORAL, (cx, panel.y + 84 + i * 24), bold=True, anchor="midtop")
        for b in self.overlay_buttons:
            b.draw(s, mouse)

    # ------------------------------------------------------------------
    def run(self):
        while self.running:
            for event in pygame.event.get():
                self.handle_event(event)
            if self.screen_name == "game":
                self.update_game()
            mouse = pygame.mouse.get_pos()
            if self.screen_name == "menu":
                self.draw_menu(mouse)
            elif self.screen_name == "setup":
                self.draw_setup(mouse)
            else:
                self.draw_game(mouse)
            pygame.display.flip()
            self.clock.tick(C.FPS)
        self._cancel_worker()
        pygame.quit()

