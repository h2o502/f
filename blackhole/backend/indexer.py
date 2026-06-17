"""索引管理 - SQLite"""
import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from backend.config import config


class Indexer:
    def __init__(self):
        self.db_path = config.db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                original_filename TEXT,
                extension TEXT,
                file_size INTEGER DEFAULT 0,
                content_text TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                ai_name TEXT DEFAULT '',
                content_hash TEXT DEFAULT '',
                created_at TIMESTAMP,
                modified_at TIMESTAMP,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_filename ON files(filename);
            CREATE INDEX IF NOT EXISTS idx_extension ON files(extension);
            CREATE INDEX IF NOT EXISTS idx_content_hash ON files(content_hash);
        """)

        # 创建 FTS5 虚拟表（contentless 模式，手动管理内容）
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(
                    filename, tags, summary, content_text
                )
            """)
        except sqlite3.OperationalError:
            pass  # FTS5 可能已存在

        conn.commit()
        conn.close()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _compute_hash(self, content: str) -> str:
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def add_or_update(self, file_path: str, content: str, summary: str,
                      tags: list, ai_name: str, original_filename: str = None) -> int:
        """添加或更新文件索引"""
        path = Path(file_path)
        stat = path.stat()
        content_hash = self._compute_hash(content)
        tags_json = json.dumps(tags, ensure_ascii=False)

        conn = self._conn()
        try:
            # 检查是否已存在
            existing = conn.execute(
                "SELECT id, content_hash FROM files WHERE path = ?",
                (str(path),)
            ).fetchone()

            if existing and existing["content_hash"] == content_hash:
                # 内容没变，跳过
                return existing["id"]

            if existing:
                # 更新
                conn.execute("""
                    UPDATE files SET
                        filename = ?, extension = ?, file_size = ?,
                        content_text = ?, summary = ?, tags = ?,
                        ai_name = ?, content_hash = ?,
                        modified_at = ?, indexed_at = CURRENT_TIMESTAMP
                    WHERE path = ?
                """, (
                    path.name, path.suffix.lower(), stat.st_size,
                    content, summary, tags_json,
                    ai_name, content_hash,
                    datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    str(path)
                ))
                file_id = existing["id"]
            else:
                # 插入
                conn.execute("""
                    INSERT INTO files (path, filename, original_filename, extension,
                        file_size, content_text, summary, tags, ai_name,
                        content_hash, created_at, modified_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(path), path.name, original_filename or path.name,
                    path.suffix.lower(), stat.st_size,
                    content, summary, tags_json, ai_name,
                    content_hash,
                    datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    datetime.fromtimestamp(stat.st_mtime).isoformat(),
                ))
                file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # 更新 FTS（先删旧的，再插新的，用 rowid 关联）
            try:
                conn.execute("DELETE FROM files_fts WHERE rowid = ?", (file_id,))
                conn.execute("INSERT INTO files_fts (rowid, filename, tags, summary, content_text) VALUES (?, ?, ?, ?, ?)",
                    (file_id, path.name, ", ".join(tags), summary, content[:10000]))
            except sqlite3.OperationalError:
                pass

            conn.commit()
            return file_id
        finally:
            conn.close()

    def remove(self, file_path: str):
        """移除文件索引"""
        conn = self._conn()
        try:
            row = conn.execute("SELECT id FROM files WHERE path = ?", (str(file_path),)).fetchone()
            if row:
                try:
                    conn.execute("DELETE FROM files_fts WHERE rowid = ?", (row["id"],))
                except sqlite3.OperationalError:
                    pass
                conn.execute("DELETE FROM files WHERE path = ?", (str(file_path),))
                conn.commit()
        finally:
            conn.close()

    def quick_search(self, query: str, limit: int = 20) -> list:
        """快速搜索 - 基于 FTS 和关键词匹配"""
        conn = self._conn()
        try:
            results = []

            # FTS 搜索
            try:
                fts_query = " OR ".join(query.split())
                rows = conn.execute("""
                    SELECT f.* FROM files f
                    JOIN files_fts ft ON f.id = ft.rowid
                    WHERE files_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (fts_query, limit)).fetchall()
                results.extend([dict(r) for r in rows])
            except sqlite3.OperationalError:
                pass

            # 关键词 LIKE 搜索（兜底）
            if len(results) < limit:
                like_query = f"%{query}%"
                existing_ids = {r["id"] for r in results}
                rows = conn.execute("""
                    SELECT * FROM files
                    WHERE (filename LIKE ? OR summary LIKE ? OR tags LIKE ?)
                    AND id NOT IN ({})
                    LIMIT ?
                """.format(",".join(str(i) for i in existing_ids) if existing_ids else "0"),
                    (like_query, like_query, like_query, limit - len(results))
                ).fetchall()
                results.extend([dict(r) for r in rows])

            # 解析 tags JSON
            for r in results:
                try:
                    r["tags"] = json.loads(r["tags"]) if isinstance(r["tags"], str) else r["tags"]
                except (json.JSONDecodeError, TypeError):
                    r["tags"] = []

            return results
        finally:
            conn.close()

    def get_all_files(self, limit: int = 100, offset: int = 0) -> list:
        """获取所有文件列表"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM files ORDER BY indexed_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                try:
                    d["tags"] = json.loads(d["tags"]) if isinstance(d["tags"], str) else d["tags"]
                except (json.JSONDecodeError, TypeError):
                    d["tags"] = []
                results.append(d)
            return results
        finally:
            conn.close()

    def get_file(self, file_id: int) -> dict:
        """获取单个文件"""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
            if row:
                d = dict(row)
                try:
                    d["tags"] = json.loads(d["tags"]) if isinstance(d["tags"], str) else d["tags"]
                except (json.JSONDecodeError, TypeError):
                    d["tags"] = []
                return d
            return None
        finally:
            conn.close()

    def get_file_by_path(self, file_path: str) -> dict:
        """按路径获取文件"""
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM files WHERE path = ?", (str(file_path),)).fetchone()
            if row:
                d = dict(row)
                try:
                    d["tags"] = json.loads(d["tags"]) if isinstance(d["tags"], str) else d["tags"]
                except (json.JSONDecodeError, TypeError):
                    d["tags"] = []
                return d
            return None
        finally:
            conn.close()

    def get_candidates_for_deep_search(self, query: str, limit: int = 20) -> list:
        """获取深度搜索的候选文件（先做一轮粗筛）"""
        conn = self._conn()
        try:
            # 先用 FTS + LIKE 粗筛
            results = self.quick_search(query, limit=limit)
            if len(results) >= 5:
                return results

            # 不够的话补充最近索引的文件
            existing_ids = {r["id"] for r in results}
            id_clause = ",".join(str(i) for i in existing_ids) if existing_ids else "0"
            rows = conn.execute(f"""
                SELECT * FROM files
                WHERE id NOT IN ({id_clause})
                ORDER BY indexed_at DESC
                LIMIT ?
            """, (limit - len(results),)).fetchall()

            for r in rows:
                d = dict(r)
                try:
                    d["tags"] = json.loads(d["tags"]) if isinstance(d["tags"], str) else d["tags"]
                except (json.JSONDecodeError, TypeError):
                    d["tags"] = []
                results.append(d)

            return results[:limit]
        finally:
            conn.close()

    def update_rename(self, file_id: int, new_name: str, new_path: str = None, original_filename: str = None):
        """更新文件重命名信息"""
        conn = self._conn()
        try:
            if new_path:
                conn.execute("""
                    UPDATE files SET filename = ?, ai_name = ?, path = ?,
                        original_filename = COALESCE(?, original_filename)
                    WHERE id = ?
                """, (new_name, new_name, new_path, original_filename, file_id))
            else:
                conn.execute("""
                    UPDATE files SET filename = ?, ai_name = ?,
                        original_filename = COALESCE(?, original_filename)
                    WHERE id = ?
                """, (new_name, new_name, original_filename, file_id))
            conn.commit()
        finally:
            conn.close()

    def get_stats(self) -> dict:
        """获取索引统计"""
        conn = self._conn()
        try:
            total = conn.execute("SELECT COUNT(*) as cnt FROM files").fetchone()["cnt"]
            total_size = conn.execute("SELECT COALESCE(SUM(file_size), 0) as sz FROM files").fetchone()["sz"]
            by_type = conn.execute("""
                SELECT extension, COUNT(*) as cnt
                FROM files GROUP BY extension ORDER BY cnt DESC LIMIT 10
            """).fetchall()
            return {
                "total_files": total,
                "total_size": total_size,
                "by_type": [dict(r) for r in by_type],
            }
        finally:
            conn.close()


indexer = Indexer()
