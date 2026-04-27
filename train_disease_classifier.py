from __future__ import annotations

import argparse
from pathlib import Path

from biogears_sim.disease_classifier import train_classifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train disease classifier from BioGears patient XML files")
    parser.add_argument("--patients-dir", type=str, default="patients")
    parser.add_argument("--model-out", type=str, default="models/disease_classifier.pkl")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output = train_classifier(Path(args.patients_dir), Path(args.model_out))
    print(f"Disease model trained: {output}")


if __name__ == "__main__":
    main()

