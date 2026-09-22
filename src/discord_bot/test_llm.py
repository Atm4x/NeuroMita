from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send one test message through NeuroMita's configured LLM preset.")
    parser.add_argument("message", help="Text to send to the active preset")
    parser.add_argument("--data-dir", type=Path, help="Isolated Discord data directory")
    parser.add_argument("--preset-id", type=int, help="Optional preset ID; otherwise use the active preset")
    args = parser.parse_args(argv)

    from discord_bot.llm_runtime import DiscordLLMRuntime

    runtime = DiscordLLMRuntime(data_dir=args.data_dir)
    try:
        response = runtime.generate([{"role": "user", "content": args.message}], args.preset_id)
        if response is None or not response.text:
            detail = getattr(response, "error_message", None) or "all configured preset attempts failed"
            print(f"LLM smoke test failed: {detail}", file=sys.stderr)
            return 1
        print(response.text)
        return 0
    finally:
        runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())
