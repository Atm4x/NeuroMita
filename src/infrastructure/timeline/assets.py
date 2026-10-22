from __future__ import annotations

from contextlib import closing

from domain.timeline import TimelineConflict, TimelineNotFound
from domain.timeline.assets import TimelineAsset


ASSET_SCHEMA = """CREATE TABLE IF NOT EXISTS timeline_assets (
    asset_id TEXT PRIMARY KEY, media_type TEXT NOT NULL,
    byte_size INTEGER NOT NULL, content BLOB NOT NULL)"""


class SQLiteTimelineAssets:
    """Immutable content-addressed objects shared by all timeline consumers."""

    def __init__(self, connection_factory):
        self._factory = connection_factory
        with closing(self._factory()) as conn:
            conn.execute(ASSET_SCHEMA)
            conn.commit()

    @staticmethod
    def insert(conn, asset: TimelineAsset) -> None:
        asset.validate()
        conn.execute("INSERT OR IGNORE INTO timeline_assets VALUES (?, ?, ?, ?)",
                     (asset.asset_id, asset.media_type, len(asset.data), asset.data))
        existing = conn.execute("SELECT media_type, byte_size, content FROM timeline_assets WHERE asset_id=?",
                                (asset.asset_id,)).fetchone()
        if tuple(existing) != (asset.media_type, len(asset.data), asset.data):
            raise TimelineConflict("Attachment identity collides with different stored content")

    def put(self, asset: TimelineAsset) -> None:
        with closing(self._factory()) as conn:
            self.insert(conn, asset)
            conn.commit()

    def get(self, asset_id: str) -> TimelineAsset:
        with closing(self._factory()) as conn:
            row = conn.execute("SELECT media_type, content FROM timeline_assets WHERE asset_id=?", (asset_id,)).fetchone()
        if row is None:
            raise TimelineNotFound(f"Unknown timeline attachment: {asset_id}")
        asset = TimelineAsset(asset_id, row[0], bytes(row[1]))
        asset.validate()
        return asset
