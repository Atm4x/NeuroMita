# On-demand skills

A skill is authored instruction text that a character needs only in some scenes:
music selection, wardrobe changes, TV interaction. Keeping every skill in the
prompt costs tokens on every turn, so skills are described by a small catalog and
loaded by the model through the ordinary load_skill tool call.

## Layout

Skills live next to the character prompt set:

```
extra/Prompts/<Character>/<Variant>/Skills/
    catalog.json
    music.md
    wardrobe.md
```

catalog.json:

```json
{
  "version": 1,
  "skills": [
    {
      "id": "music",
      "title": "Music",
      "description": "Pick a track that fits the scene",
      "file": "music.md",
      "capabilities": ["music"]
    }
  ]
}
```

id matches [a-z0-9][a-z0-9_-]{0,39}; file is a relative .md or .txt path inside
Skills/. Absolute paths and parent-directory escapes are rejected, as are
duplicate ids and empty files. A broken entry is skipped and recorded in
SkillCatalog.issues; the rest of the catalog keeps working.

## Prompt shape

When load_skill is enabled, the prompt carries a compact [SKILLS] block with one
line per skill. The bodies are not included. The model calls load_skill with one
or two ids when the current scene needs them; the tool returns the bodies in
the immediate tool continuation (under [LOADED SKILLS]). Two ids in one call
cost a single tool request, which is why the argument is a list.

The complete tool result is also saved alongside its originating assistant turn
in conversation history. In native mode, the tool-role reply keeps the original
tool-call ID; in schema mode, history projects a [LOADED SKILLS] system message
after the assistant turn. In both cases the instruction ages out when that turn
leaves the bounded history/context window. The model can call load_skill again
if a skill is needed later.

There is no session-level re-injection of the last two on-demand skills. The
catalog block is derived from the character prompt set and stays compact.

## Modes

The connected game runtime can send the catalog itself. Its payload
calls it skills_catalog; the same manifest shape is used with body instead
of file, and it wins over the local folder. The folder stays as a fallback
for characters the game does not describe. The catalog is cached per
character so load_skill and the prompt agree on what exists.

In the Unity build the manifest lives in
Assets/StreamingAssets/Data/Skills/: catalog.json lists id, title, description,
file and optional capabilities or characters, and the .md files next to it hold
the bodies. Unity validates that catalog and sends it with every context
snapshot, so the game stays the source of truth for what a scene supports and
this repository keeps no copy of those files.

The snapshot also carries skills_catalog_revision, a hash of the manifest and
every body, and skills_scope, which names the world, the active scene and that
revision. Bodies travel with each snapshot rather than on first use: the game
has no per-connection acknowledgement, so a memo of what a client already has
could leave it without any text at all. The payload is small JSON, and the
revision lets the two sides tell a real change from a repetition.

When skills_scope changes, the catalog is replaced. Older tool results still
belong to historical turns and leave context naturally as history is trimmed;
their instructions must never override current scene state. The model should
reload a scene-specific skill when the location or available mechanics change.

SKILL_LOADING_MODE picks one of two policies over the same catalog and renderer:

on_demand (default) keeps only the compact [SKILLS] list in the static prompt.
Bodies arrive through load_skill, remain in conversation history while their
originating turn is in the context window, and can be reloaded when needed.

eager places every skill body in the stable prompt prefix and never calls the
tool: one request per turn, but the context always carries all authored text.
load_skill is dropped from the tool list in this mode, since a model that
already has the bodies has nothing left to load.

## Enabling

TOOLS_ON and TOOL_ENABLED_load_skill must both be on (Settings - Tools -
On-demand skills). Characters without a Skills/ folder get no catalog block and
the tool reports that there is nothing to load.

The catalog reaches the prompt through the Unity snapshot:
game_connections/handlers/actions/create_task.py projects the request onto a
whitelist of prompt fields, so a new field has to be listed there or the prompt
never sees it.

## Versioned contracts

A runtime may keep mechanic instructions out of the prompt contract and name the
mechanics instead. It then sends prompt_contract_version (2 or later) together
with scene_mechanics entries shaped as {mechanic, skill, state}, where state is
available, unavailable or missing.

Python answers that with a [Unity Scene Mechanics] block. On demand it names the
mechanics and their skills and asks for load_skill before an intent is built; in
eager mode it points at the bodies already in the prompt; without tools it
inlines the bodies itself, because a client that cannot load skills must not be
left without the text. A mechanic whose body never arrived is named as unusable
instead of being advertised. A payload without the marker renders exactly as it
did before, so an older Unity build keeps its self-contained contract.
