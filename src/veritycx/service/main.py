"""Launch the loopback API on the shared Selector loop with approved nonsecret overrides."""

import argparse
import os
from pathlib import Path

import uvicorn

from veritycx.service.app import create_app
from veritycx.service.configuration import ConfigurationError, load_configuration
from veritycx.service.runtime import run_async


def main() -> int:
    """Validate settings and run one server process without reload/multiprocessing."""
    parser = argparse.ArgumentParser(description="Run local support API")
    parser.add_argument("--provider", choices=["deterministic", "openai"])
    parser.add_argument("--corpus-mode", choices=["synthetic", "official"])
    args = parser.parse_args()
    try:
        config = load_configuration(
            Path("config/support.toml"),
            os.environ,
            provider=args.provider,
            corpus_mode=args.corpus_mode,
        )
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(config),
                host=config.settings.bind,
                port=config.settings.port,
                access_log=False,
                log_level="error",
            )
        )
        run_async(server.serve())
    except ConfigurationError as error:
        print(str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
