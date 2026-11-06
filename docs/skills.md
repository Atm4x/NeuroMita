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
line per skill. The bodies are not included. The model calls load_skill(id) when
the current scene needs one; the tool returns the body and the next turn renders
it in a [LOADED SKILLS] block.

Loaded skills are kept per character for the following turns, capped at two
entries and 2000 estimated tokens. The least recently loaded skill is evicted
first; history reset or character removal clears the set.

The catalog block is derived from the character prompt set, so it only changes
when the set does. Loaded bodies change per turn and are placed after the
history, in the volatile part of the prompt.

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

When skills_scope changes, the catalog is replaced and the retained skill text
is dropped, because open skill bodies describe the scene they were loaded in.
Loading a wardrobe skill inside one location and keeping its instructions
after a scene change would describe furniture and clothing that no longer
exist.

SKILL_LOADING_MODE picks one of two policies over the same catalog and renderer:

on_demand (default) keeps only the compact [SKILLS] list in the prompt; bodies
arrive through load_skill and stay loaded for a bounded number of turns.

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
