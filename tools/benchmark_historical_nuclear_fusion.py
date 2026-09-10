"""Run the historical nuclear-fusion research benchmark without a web service."""

from __future__ import annotations

import argparse
import json

from app.science.historical_nuclear_fusion import benchmark_historical_fusion


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(benchmark_historical_fusion(samples=args.samples, seed=args.seed), indent=2))


if __name__ == "__main__":
    main()
