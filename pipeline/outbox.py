import sqlite3
import time
import pathlib
from dataclasses import dataclass
from typing import Optional

DB_PATH = str(pathlib.Path(__file__).parent.parent / "provenance.db")


@dataclass
class ImageRow:
    watermark_id: str
    short_id: str
    image_bytes: bytes
    sha256: str
    phash: int
    prompt: Optional[str]
    model: Optional[str]
    created_at: int


@dataclass
class JobRow:
    job_id: str
    watermark_id: str
    status: str
    attempts: int
    tx_hash: Optional[str]
    arweave_id: Optional[str]
    error: Optional[str]
    updated_at: int


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    with _connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS images (
                watermark_id  TEXT PRIMARY KEY,
                short_id      TEXT NOT NULL,
                image_bytes   BLOB NOT NULL,
                sha256        TEXT NOT NULL,
                phash         INTEGER NOT NULL,
                prompt        TEXT,
                model         TEXT,
                created_at    INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS outbox_jobs (
                job_id        TEXT PRIMARY KEY,
                watermark_id  TEXT NOT NULL REFERENCES images(watermark_id),
                status        TEXT NOT NULL DEFAULT 'pending',
                attempts      INTEGER NOT NULL DEFAULT 0,
                tx_hash       TEXT,
                arweave_id    TEXT,
                error         TEXT,
                updated_at    INTEGER NOT NULL
            );
        """)


def insert_image(
    db_path: str,
    watermark_id: str,
    short_id: str,
    image_bytes: bytes,
    sha256: str,
    phash: int,
    prompt: Optional[str],
    model: Optional[str],
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO images
               (watermark_id, short_id, image_bytes, sha256, phash, prompt, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (watermark_id, short_id, image_bytes, sha256, phash, prompt, model, int(time.time())),
        )


def insert_job(db_path: str, job_id: str, watermark_id: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO outbox_jobs
               (job_id, watermark_id, status, attempts, updated_at)
               VALUES (?, ?, 'pending', 0, ?)""",
            (job_id, watermark_id, int(time.time())),
        )


def get_image(db_path: str, watermark_id: str) -> Optional[ImageRow]:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM images WHERE watermark_id = ?", (watermark_id,)
        ).fetchone()
    if row is None:
        return None
    return ImageRow(**dict(row))


def get_job(db_path: str, watermark_id: str) -> Optional[JobRow]:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM outbox_jobs WHERE watermark_id = ?", (watermark_id,)
        ).fetchone()
    if row is None:
        return None
    return JobRow(**dict(row))


def get_image_by_short_id(db_path: str, short_id: str) -> Optional[ImageRow]:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM images WHERE short_id = ?", (short_id,)
        ).fetchone()
    if row is None:
        return None
    return ImageRow(**dict(row))


def get_job_by_short_id(db_path: str, short_id: str) -> Optional[JobRow]:
    with _connect(db_path) as conn:
        row = conn.execute(
            """SELECT j.* FROM outbox_jobs j
               JOIN images i ON i.watermark_id = j.watermark_id
               WHERE i.short_id = ?""",
            (short_id,),
        ).fetchone()
    if row is None:
        return None
    return JobRow(**dict(row))


def insert_image_and_job(
    db_path: str,
    watermark_id: str,
    short_id: str,
    image_bytes: bytes,
    sha256: str,
    phash: int,
    prompt: Optional[str],
    model: Optional[str],
    job_id: str,
) -> None:
    now = int(time.time())
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO images
               (watermark_id, short_id, image_bytes, sha256, phash, prompt, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (watermark_id, short_id, image_bytes, sha256, phash, prompt, model, now),
        )
        conn.execute(
            """INSERT INTO outbox_jobs
               (job_id, watermark_id, status, attempts, updated_at)
               VALUES (?, ?, 'pending', 0, ?)""",
            (job_id, watermark_id, now),
        )


def get_images_by_phash_proximity(
    db_path: str,
    phash: int,
    threshold: int = 15,
) -> list[ImageRow]:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM images").fetchall()
    results = []
    for row in rows:
        stored = row["phash"]
        distance = bin(phash ^ stored).count("1")
        if distance <= threshold:
            results.append((distance, ImageRow(**dict(row))))
    results.sort(key=lambda x: x[0])
    return [img for _, img in results]


def update_job(
    db_path: str,
    watermark_id: str,
    status: str,
    tx_hash: Optional[str] = None,
    arweave_id: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """UPDATE outbox_jobs
               SET status = ?, tx_hash = COALESCE(?, tx_hash),
                   arweave_id = COALESCE(?, arweave_id),
                   error = COALESCE(?, error),
                   attempts = attempts + 1,
                   updated_at = ?
               WHERE watermark_id = ?""",
            (status, tx_hash, arweave_id, error, int(time.time()), watermark_id),
        )
