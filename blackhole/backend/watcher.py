"""文件系统监听器"""
import asyncio
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent, FileMovedEvent
from backend.config import config
from backend.extractor import extract_text, get_file_info
from backend.indexer import indexer
from backend.ai_service import ai_service


class BlackholeHandler(FileSystemEventHandler):
    """黑洞文件夹事件处理器"""

    def __init__(self, loop=None):
        super().__init__()
        self.loop = loop
        self._processing = set()
        self._supported = set(config.get("supported_extensions", []))
        self._indexing_status = {"running": False, "current": "", "progress": 0, "total": 0}

    @property
    def status(self) -> dict:
        return self._indexing_status.copy()

    def _should_process(self, path: str) -> bool:
        """判断是否需要处理该文件"""
        p = Path(path)
        if p.suffix.lower() not in self._supported:
            return False
        if p.name.startswith(".") or p.name.startswith("~"):
            return False
        # 忽略索引数据库本身
        if "blackhole_index" in p.name:
            return False
        return True

    def on_created(self, event):
        if not isinstance(event, FileCreatedEvent):
            return
        if self._should_process(event.src_path):
            self._schedule_index(event.src_path)

    def on_modified(self, event):
        if not isinstance(event, FileModifiedEvent):
            return
        if self._should_process(event.src_path):
            self._schedule_index(event.src_path)

    def on_deleted(self, event):
        if not isinstance(event, FileDeletedEvent):
            return
        indexer.remove(event.src_path)

    def on_moved(self, event):
        if not isinstance(event, FileMovedEvent):
            return
        indexer.remove(event.src_path)
        if self._should_process(event.dest_path):
            self._schedule_index(event.dest_path)

    def _schedule_index(self, file_path: str):
        """调度索引任务"""
        if file_path in self._processing:
            return
        self._processing.add(file_path)
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._index_file(file_path), self.loop)
        else:
            # 同步回退
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(self._index_file(file_path), loop)
                else:
                    loop.run_until_complete(self._index_file(file_path))
            except RuntimeError:
                asyncio.run(self._index_file(file_path))

    async def _index_file(self, file_path: str):
        """索引单个文件"""
        try:
            self._indexing_status = {
                "running": True,
                "current": Path(file_path).name,
                "progress": 0,
                "total": 1,
            }

            # 1. 提取文本
            content = extract_text(file_path)
            info = get_file_info(file_path)

            # 2. AI 生成标签
            tags = await ai_service.generate_tags(info["filename"], content)

            # 3. AI 生成摘要
            summary = await ai_service.generate_summary(info["filename"], content)

            # 4. AI 建议名称
            ai_name = await ai_service.suggest_name(info["filename"], content)

            # 5. 写入索引
            file_id = indexer.add_or_update(
                file_path=file_path,
                content=content,
                summary=summary,
                tags=tags,
                ai_name=ai_name,
                original_filename=info["filename"],
            )

            # 6. 如果开启了自动重命名
            if config.get("auto_rename") and ai_name:
                self._rename_file(file_path, ai_name, file_id)

            self._indexing_status = {
                "running": False,
                "current": "",
                "progress": 1,
                "total": 1,
            }
        except Exception as e:
            print(f"索引文件失败 {file_path}: {e}")
            self._indexing_status = {
                "running": False,
                "current": f"错误: {str(e)}",
                "progress": 0,
                "total": 1,
            }
        finally:
            self._processing.discard(file_path)

    def _rename_file(self, old_path: str, new_name: str, file_id: int):
        """重命名文件"""
        try:
            old = Path(old_path)
            new_path = old.parent / new_name
            if new_path.exists() and new_path != old:
                return  # 不覆盖
            old.rename(new_path)
            # 更新索引
            indexer.remove(old_path)
            indexer.update_rename(file_id, new_name)
        except Exception as e:
            print(f"重命名失败 {old_path}: {e}")

    async def index_all(self, folder: str):
        """全量索引文件夹"""
        folder_path = Path(folder)
        files = [f for f in folder_path.rglob("*") if f.is_file() and self._should_process(str(f))]
        total = len(files)
        self._indexing_status = {"running": True, "current": "", "progress": 0, "total": total}

        for i, f in enumerate(files):
            self._indexing_status["progress"] = i
            self._indexing_status["current"] = f.name
            await self._index_file(str(f))

        self._indexing_status = {"running": False, "current": "", "progress": total, "total": total}


class FileWatcher:
    """文件监听器"""

    def __init__(self):
        self.observer = Observer()
        self.handler = BlackholeHandler()
        self._loop = None

    def set_loop(self, loop):
        self._loop = loop
        self.handler.loop = loop

    def start(self, folder: str):
        """开始监听文件夹"""
        self.observer.schedule(self.handler, folder, recursive=True)
        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()

    @property
    def status(self) -> dict:
        return self.handler.status

    async def index_all(self, folder: str):
        """全量索引"""
        await self.handler.index_all(folder)


watcher = FileWatcher()
