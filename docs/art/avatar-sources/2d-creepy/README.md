# 2D and Creepy Mita avatar sources

Development artwork archive; the application reads only the final 512 x 512 PNGs
in `assets/avatars/twod.png` and `assets/avatars/creepy.png`.

- `twod-source.png`, `creepy-source.png`: full-resolution approved generation,
  with mouths removed and Creepy's skin changed to a cool off-white.
- `twod-v1.png`, `creepy-v1.png`: previous versions for comparison.
- `reference-*`: downloaded character appearance references; source URLs and
  generation prompts are in `generation-notes.md`.
- `comparison.png`: existing and new avatars, including circular small previews.
- `prepare_icons.py`: reproduce the final crops and comparison from this folder;
  requires Pillow. Run from the repository root:
  `python docs/art/avatar-sources/2d-creepy/prepare_icons.py`.

These sources are intentionally outside the runtime `assets` directory and `src`.
The standard `build.env` and release workflow copy `extra/Prompts`, `assets`,
and `libs`; the only documentation folder explicitly copied by `build.py` is
`docs/wiki`. This folder is therefore excluded from the standard build package.
