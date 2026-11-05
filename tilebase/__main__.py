import os

os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")

from tilebase.demo import main

main()
