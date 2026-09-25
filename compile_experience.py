"""Manual Phase 3 entry point."""
from __future__ import annotations

import argparse
import json

from dotenv import load_dotenv

from experience_compiler import ExperienceCompiler
from providers.liquid import LiquidError, LiquidNotConfigured
from providers.rawtree import RawTreeEventBackend


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Compile one RawTree run into durable experience")
    parser.add_argument("run_id", help="completed source run, for example RUN-cbc2e587b04f")
    parser.add_argument("--compiler", choices=("liquid", "fallback"), default="liquid")
    args = parser.parse_args()
    try:
        result = ExperienceCompiler(RawTreeEventBackend(), compiler_mode=args.compiler).compile_run(args.run_id)
    except LiquidNotConfigured as error:
        print(json.dumps({"liquid_status": "NOT_CONFIGURED", "detail": str(error)}))
        return 2
    except LiquidError as error:
        print(json.dumps({"liquid_status": "ERROR", "detail": str(error)}))
        return 1
    status = result["provider_status"]
    print(json.dumps({
        "liquid_status": status.state if status else "FALLBACK",
        "liquid_detail": status.detail if status else "Explicit deterministic fallback",
        "compilation_run_id": result["compilation_run_id"],
        "memory": result["memory"].as_dict(),
        "compaction": result["metrics"].as_dict(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
