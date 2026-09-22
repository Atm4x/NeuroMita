# NeuroMita Discord Lite

Discord Lite is a standalone, low-resource runtime that reuses NeuroMita's existing API preset resolver, model settings, retry/key rotation, fallback chain, and provider manager. It does not start the desktop controller, Unity, voice, local models, or Discord gateway.

## Stage 1: CLI LLM smoke test

Install only the Discord runtime dependencies into a fresh virtual environment (do not install `requirements.txt`):

```bash
python3 -m venv .venv-discord
. .venv-discord/bin/activate
python -m pip install -r requirements-discord.txt
```

Configure the NeuroMita API preset files and `settings.json` under `DiscordData/Settings/`. Do not copy desktop settings wholesale; add only the preset(s) and credentials needed on this server. Keep the data directory private (`chmod 700 DiscordData`) and the preset file private (`chmod 600 DiscordData/Settings/api_presets.json`). Never commit these files.

Run one request without connecting to Discord:

```bash
PYTHONPATH=src python -m discord_bot.test_llm "Привет"
```

An alternate data directory can be selected with `--data-dir`; an optional preset id can be passed with `--preset-id`. The CLI prints the model response and exits nonzero if all configured attempts fail.

Only move on to the Discord gateway after this CLI request succeeds on the target VPS.

## Memory budget

The VPS's roughly 500 MB currently available is shared with the OS and VPN. Treat it as the whole remaining headroom, not the bot allocation. Start with one generation worker and short conversations; measure the process RSS and available host memory on the VPS before raising concurrency or adding features. Swap is only an OOM buffer, not usable RAM.
