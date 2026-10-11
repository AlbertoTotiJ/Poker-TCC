"""Script de inicialização da interface gráfica web da mesa de Texas Hold'em."""

import argparse
from pathlib import Path
import socket
import sys
import webbrowser

# Garante resolução dos módulos a partir da raiz do repositório
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.visualization.web_server import start_poker_web_server  # noqa: E402


def get_local_ip() -> str:
    """Detecta o endereço IP local da máquina na rede local (Wi-Fi ou Ethernet)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inicializa a mesa virtual gráfica de Texas Hold'em no navegador."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Endereço de rede para vincular o servidor (padrão: 0.0.0.0).",
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
        host=args.host,
        port=args.port,
        num_players=args.players,
        starting_stack=args.stack,
    )

    local_url = f"http://localhost:{port}"
    lan_ip = get_local_ip()
    network_url = (
        f"http://{lan_ip}:{port}"
        if lan_ip not in ("127.0.0.1", "localhost")
        else None
    )

    print("=" * 72)
    print(" MESA GRÁFICA VIRTUAL DE TEXAS HOLD'EM INICIADA! ".center(72, "="))
    print("=" * 72)
    print(f" > Acesso Local (este computador): {local_url}")
    if network_url:
        print(f" > Acesso na Rede (outros dispositivos/celular): {network_url}")
    print(f" > Endereço Vinculado (Host): {args.host} | Porta: {port}")
    print(f" > Jogadores configurados: {args.players}")
    print(f" > Stack inicial: {args.stack} fichas")
    print(" Pressione Ctrl+C no terminal a qualquer momento para encerrar.")
    print("=" * 72 + "\n")

    if not args.no_browser:
        webbrowser.open(local_url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor da mesa encerrado com sucesso.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
