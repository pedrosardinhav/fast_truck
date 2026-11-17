"""Servidor da apresentação, com pasta resolvida pelo próprio arquivo."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main():
    directory = Path(__file__).resolve().parent
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 8001), handler)
    except OSError as exc:
        raise SystemExit(
            "Não foi possível iniciar na porta 8001. Pare o servidor anterior "
            "com Ctrl+C e execute este comando novamente."
        ) from exc
    print("Apresentação FasTruck: http://127.0.0.1:8001", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor da apresentação encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
