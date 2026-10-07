"""Handler Serverless para execução na Vercel."""

from pathlib import Path
import sys

# Adiciona a raiz do projeto ao path para carregar os módulos em src
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.visualization.web_server import PokerApiHandler  # noqa: E402


class handler(PokerApiHandler):
    """Ponto de entrada serverless para a Vercel."""

    pass
