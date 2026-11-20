"""AI Checkers Game - application entry point.

    python main.py
"""

import os
import sys
import warnings

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
warnings.filterwarnings("ignore", category=UserWarning, module="pygame")

from ui import App  # noqa: E402


def main():
    # Let the GUI thread run more often while an AI searches in the background.
    sys.setswitchinterval(0.002)
    App().run()


if __name__ == "__main__":
    main()
