#!/usr/bin/env python3
import argparse
from pathlib import Path

from photo_dedup.tui import PhotoDedupApp


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Encontra e remove fotos duplicadas/similares, mantendo a de maior qualidade."
    )
    parser.add_argument("directory", type=Path, help="Pasta a escanear")
    parser.add_argument(
        "--threshold",
        type=int,
        default=10,
        help="Distância máxima de pHash para considerar fotos similares (padrão: 10, intervalo: 0–64)",
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="Escanear subpastas recursivamente",
    )
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Erro: '{args.directory}' não é uma pasta.")
        raise SystemExit(1)

    app = PhotoDedupApp(args.directory, args.threshold, args.recursive)
    result = app.run()
    if result:
        print(result)


if __name__ == "__main__":
    main()
