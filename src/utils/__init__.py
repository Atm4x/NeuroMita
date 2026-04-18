# src/utils/__init__.py
import importlib

def __getattr__(name):
    if name == 'UvSync':
        from .uv_sync import UvSync
        return UvSync

    try:
        module = importlib.import_module('.common', __package__)
        
        if hasattr(module, name):
            return getattr(module, name)
    except Exception:
        if name in ('getTranslationVariant', '_'):
            return lambda ru, en="": ru
            
    raise AttributeError(f"module {__name__} has no attribute {name}")

def __dir__():
    try:
        module = importlib.import_module('.common', __package__)
        return list(module.__dict__.keys()) + ['UvSync']
    except Exception:
        return ['UvSync', 'getTranslationVariant', '_']