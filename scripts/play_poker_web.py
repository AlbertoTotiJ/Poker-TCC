"""Script de inicialização da interface gráfica web da mesa de Texas Hold'em."""

import argparse
from pathlib import Path
import sys
import webbrowser

# Garante resolução dos módulos a partir da raiz do repositório
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.visualization.web_server import start_poker_web_server  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inicializa a mesa virtual gráfica de Texas Hold'em no navegador."
    )
    parser.add_argument(
        "--players",
        "-p",
        type=int,
        default=4,
        help="Quantidade de jogadores inicial na mesa (2 a 9). Padrão: 4.",
    )
    parser.add_argument(
        "--stack",
        "-s",
        type=int,
        default=1000,
        help="Stack inicial de fichas por jogador. Padrão: 1000.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Porta TCP desejada para o servidor (seleciona porta livre se omitido).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Não abre automaticamente a janela do navegador.",
    )
    args = parser.parse_args()

    httpd, port = start_poker_web_server(
        port=args.port,
        num_players=args.players,
        starting_stack=args.stack,
    )

    url = f"http://127.0.0.1:{port}"
    print("=" * 70)
    print(" MESA GRÁFICA VIRTUAL DE TEXAS HOLD'EM INICIADA! ".center(70, "="))
    print("=" * 70)
    print(f" Endereço da Mesa no Navegador: {url}")
    print(f" Jogadores configurados: {args.players}")
    print(f" Stack inicial: {args.stack} fichas")
    print(" Pressione Ctrl+C no terminal a qualquer momento para encerrar.")
    print("=" * 70 + "\n")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor da mesa encerrado com sucesso.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
