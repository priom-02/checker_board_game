"""Record real AI vs AI games as 1080p MP4 videos with the game's sound effects.

    pip install imageio-ffmpeg
    python tools/record_ai_vs_ai.py                     # Medium and Hard
    python tools/record_ai_vs_ai.py --difficulty Hard --seed 3

Moves come from the real agents and rules. Video time is controlled by this
script: each AI "thinks" for a fixed short time on screen so long searches do
not leave the video frozen. The decision times in the sidebar are the real ones.
Videos are saved in screenshots/10_videos/. Results are not added to the CSV.
"""

import argparse
import array
import os
import random
import subprocess
import sys
import tempfile
import wave

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import imageio_ffmpeg  # noqa: E402
import pygame  # noqa: E402

import config as C  # noqa: E402
import sounds  # noqa: E402
import stats  # noqa: E402
import ui  # noqa: E402
from piece import PLAYER_NAMES  # noqa: E402

OUT = os.path.join(ROOT, "screenshots", "10_videos")
WIDTH, HEIGHT, FPS = 1920, 1080, 30
INTRO_SECONDS, THINK_SECONDS, END_SECONDS = 2.0, 0.35, 5.0


class VideoClock:
    """Replaces the UI's clock, so animations follow video time."""

    def __init__(self):
        self.now = 1000.0

    def perf_counter(self):
        return self.now


def mix_audio(events, seconds, path):
    total = int(seconds * sounds.SAMPLE_RATE)
    mix = [0.0] * total
    clips = {}
    for at, name in events:
        if name not in clips:
            with wave.open(os.path.join(sounds.SOUND_DIR, f"{name}.wav")) as f:
                clips[name] = array.array("h", f.readframes(f.getnframes()))
        start = int(at * sounds.SAMPLE_RATE)
        for i, value in enumerate(clips[name][:max(0, total - start)]):
            mix[start + i] += value * C.SOUND_VOLUME
    pcm = array.array("h", (max(-32767, min(32767, int(v))) for v in mix))
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sounds.SAMPLE_RATE)
        f.writeframes(pcm.tobytes())


def record(app, clock, difficulty, seed):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    os.makedirs(OUT, exist_ok=True)
    output = os.path.join(OUT, f"ai_vs_ai_{difficulty.lower()}.mp4")

    app.handle_action(("menu",))
    app.handle_action(("mode", ui.AIVAI))
    app.handle_action(("difficulty", difficulty))
    app.handle_action(("color", ui.BLACK))
    app.handle_action(("start",))
    for offset, agent in enumerate(app.players.values()):
        agent.rng = random.Random(seed + offset)

    start_time = clock.now
    events = []
    app.sounds.play = lambda name: events.append((clock.now - start_time, name))
    display = pygame.display.get_surface()

    with tempfile.TemporaryDirectory() as tmp:
        video_path, audio_path = os.path.join(tmp, "video.mp4"), os.path.join(tmp, "audio.wav")
        encoder = subprocess.Popen(
            [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
             "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", video_path],
            stdin=subprocess.PIPE)
        frames = [0]

        def frame(count=1):
            for _ in range(count):
                app.draw_game((-1, -1))
                display.fill(C.BG_COLOR)
                display.blit(app.screen, app.offset)
                encoder.stdin.write(pygame.image.tobytes(display, "RGB"))
                frames[0] += 1
                clock.now += 1 / FPS

        frame(int(INTRO_SECONDS * FPS))
        app.sounds.play("start")
        app.handle_action(("toggle_run",))
        while not (app.game.over and not app.anim and app.result_recorded):
            app.update_game()
            if app.worker is not None and not app.worker.done:
                frame(int(THINK_SECONDS * FPS))
                app.worker.thread.join()
            frame()
        frame(int(END_SECONDS * FPS))
        encoder.stdin.close()
        if encoder.wait() != 0:
            raise RuntimeError("Video encoding failed")

        seconds = frames[0] / FPS
        mix_audio(events, seconds, audio_path)
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", video_path, "-i", audio_path,
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                        "-shortest", output], check=True)

    game = app.game
    if game.is_draw:
        result = f"Draw ({game.result_reason})"
    else:
        result = f"{app.players[game.winner].short_label} ({PLAYER_NAMES[game.winner]}) wins - {game.result_reason}"
    print(f"{os.path.basename(output)}: {result}; {len(game.history)} moves; {seconds:.0f}s; "
          f"{os.path.getsize(output) / 1e6:.1f} MB")
    return os.path.basename(output), result, len(game.history), seconds


def update_index(rows):
    path = os.path.join(ROOT, "screenshots", "README.md")
    with open(path, encoding="utf-8") as f:
        text = f.read().split("\n## 10_videos")[0].rstrip("\n")
    lines = ["", "", "## 10_videos - AI vs AI match videos (1080p with sound)", "",
             "| File | Match | Result | Moves | Length |", "|---|---|---|---|---|"]
    for name, result, moves, seconds in rows:
        cfg = C.AI_VS_AI[name.split("_")[-1].split(".")[0].capitalize()]
        lines.append(f"| [{name}](10_videos/{name}) | Minimax depth {cfg['minimax_depth']} vs "
                     f"MCTS {cfg['mcts_simulations']:,} simulations | {result} | {moves} | {seconds:.0f} s |")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--difficulty", default="all", choices=["all", "Medium", "Hard"])
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    stats.append_record = lambda *a, **k: None      # demo games must not change the results file
    clock = VideoClock()
    ui.time = clock
    app = ui.App()
    pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    app._sync_display()

    levels = ["Medium", "Hard"] if args.difficulty == "all" else [args.difficulty]
    update_index([record(app, clock, level, args.seed) for level in levels])
    pygame.quit()


if __name__ == "__main__":
    main()
