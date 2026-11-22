from pathlib import Path
import ast
import re
from PIL import Image, ImageChops, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
for name in ('twod', 'creepy'):
    source = Image.open(OUT / f'{name}-source.png').convert('RGB')
    difference = ImageChops.difference(source, Image.new('RGB', source.size, 'white'))
    mask = difference.convert('L').point(lambda value: 255 if value > 45 else 0)
    box = mask.getbbox()
    assert box is not None
    # Square crop with a narrow safety margin; retain every hair tip and bow.
    left, top, right, bottom = box
    side = max(right - left, bottom - top) + 24
    center_x, center_y = (left + right) // 2, (top + bottom) // 2
    canvas = Image.new('RGB', (side, side), 'white')
    canvas.paste(source, (side // 2 - center_x, side // 2 - center_y))
    final = canvas.resize((512, 512), Image.Resampling.LANCZOS).convert('RGBA')
    final.save(ROOT / 'assets' / 'avatars' / f'{name}.png', optimize=True)
    print(name, 'source', source.size, 'content', box, 'square', side, 'final', final.size)

names = ['crazy', 'mila', 'ghost', 'twod', 'creepy']
preview = Image.new('RGB', (1000, 330), '#f0edf4')
draw = ImageDraw.Draw(preview)
for column, name in enumerate(names):
    avatar = Image.open(ROOT / 'assets' / 'avatars' / f'{name}.png').convert('RGB')
    tile = ImageOps.contain(avatar, (184, 184), Image.Resampling.LANCZOS)
    x = column * 200 + 8
    preview.paste(tile, (x + (184 - tile.width) // 2, 20))
    draw.text((x + 55, 213), name, fill='#34263d')
    for offset, size in [(25, 36), (90, 64)]:
        square = ImageOps.fit(avatar, (size, size), Image.Resampling.LANCZOS)
        alpha = Image.new('L', (size * 4, size * 4))
        ImageDraw.Draw(alpha).ellipse((0, 0, size * 4, size * 4), fill=255)
        alpha = alpha.resize((size, size), Image.Resampling.LANCZOS)
        preview.paste(square, (x + offset, 245), alpha)
preview.save(OUT / 'comparison.png')

source_text = (ROOT / 'src/ui/chat/message_widget.py').read_text(encoding='utf-8')
tree = ast.parse(source_text)
selected = []
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {'AVATAR_MAP', '_AVATAR_ALIASES'} for t in node.targets):
        selected.append(node)
    elif isinstance(node, ast.FunctionDef) and node.name in {'_normalise_avatar_identity', '_resolve_avatar_filename'}:
        selected.append(node)
    elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == '_AVATAR_ALIASES':
        selected.append(node)
scope = {'re': re}
exec(compile(ast.Module(body=selected, type_ignores=[]), '<avatar resolver>', 'exec'), scope)
for identity in ['TwoD', 'TwoDMita', '2D Mita', 'two_d', '2D Mita → Cappie', 'Creepy', 'Creepy Mita', 'creepy_mita']:
    filename = scope['_resolve_avatar_filename'](identity)
    assert filename in {'twod.png', 'creepy.png'}, (identity, filename)
    with Image.open(ROOT / 'assets/avatars' / filename) as asset:
        assert asset.size == (512, 512) and asset.mode == 'RGBA'
    print(ascii(identity), '->', filename)
