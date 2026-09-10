"""Run the historical nuclear-fusion research benchmark without a web service."""

from __future__ import annotations

import argparse
import json

from app.science.historical_nuclear_fusion import (
    benchmark_historical_fusion,
    comparative_algorithm_laboratory,
    parameter_regime_campaign,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--uncertainty-samples", type=int, default=100)
    parser.add_argument("--laboratory", action="store_true", help="compare Euler, RK4, fused, and matrix-exponential methods")
    parser.add_argument("--campaign", action="store_true", help="sweep chain length, stiffness, duration, steps, uncertainty, and precision")
    parser.add_argument("--cases-per-regime", type=int, default=4)
    args = parser.parse_args()
    if args.campaign:
        report = parameter_regime_campaign(cases_per_regime=args.cases_per_regime, seed=args.seed)
    elif args.laboratory:
        report = comparative_algorithm_laboratory(
            samples=args.samples, seed=args.seed, uncertainty_samples=args.uncertainty_samples
        )
    else:
        report = benchmark_historical_fusion(samples=args.samples, seed=args.seed)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
