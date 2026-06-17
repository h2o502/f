"""FastAPI 主应用"""
import asyncio
import os
import webbrowser
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from backend.config import config
from backend.indexer import indexer
from backend.ai_service import ai_service
from backend.watcher import watcher
from backend.extractor import extract_text, get_file_info

app = FastAPI(title="Blackhole", description="AI 黑洞文件夹")

# ============ 请求模型 ============

class SearchRequest(BaseModel):
    query: str
    mode: str = "quick"  # quick / deep

class CompareRequest(BaseModel):
    file_id_1: int
    file_id_2: int

class BatchRenameRequest(BaseModel):
    file_ids: list[int]
    instruction: str

class RenameRequest(BaseModel):
    file_id: int
    new_name: str = ""  # 空则用 AI 建议

class ConfigRequest(BaseModel):
    watch_folder: str = ""
    api_key: str = ""
    api_url: str = ""
    model: str = ""
    deep_model: str = ""
    auto_rename: bool = False

class SetFolderRequest(BaseModel):
    folder: str

# ============ API 路由 ============

@app.get("/api/config")
async def get_config():
    """获取配置（API Key 不返回完整值，避免泄露）"""
    c = config.all
    key = c.get("api_key", "")
    # 不返回完整 api_key，用脱敏值和标志位代替
    c["api_key"] = ""  # 清空，前端用 placeholder 显示脱敏值
    c["api_key_masked"] = key[:6] + "****" + key[-4:] if len(key) > 10 else "****"
    c["has_api_key"] = bool(key)
    return c

@app.post("/api/config")
async def update_config(req: ConfigRequest):
    """更新配置"""
    updates = {}
    if req.watch_folder:
        updates["watch_folder"] = req.watch_folder
    # 只有当用户输入了非占位符的 key 时才更新
    if req.api_key and "****" not in req.api_key:
        updates["api_key"] = req.api_key
    if req.api_url:
        updates["api_url"] = req.api_url
    if req.model:
        updates["model"] = req.model
    if req.deep_model:
        updates["deep_model"] = req.deep_model
    updates["auto_rename"] = req.auto_rename
    config.update(updates)
    # 刷新 AI 服务配置
    ai_service.refresh_config()
    return {"status": "ok"}

@app.post("/api/folder")
async def set_watch_folder(req: SetFolderRequest):
    """设置监听文件夹"""
    folder = req.folder
    if not os.path.isdir(folder):
        raise HTTPException(400, "文件夹不存在")
    config.watch_folder = folder

    # 重启监听
    try:
        watcher.stop()
    except Exception:
        pass
    watcher.set_loop(asyncio.get_running_loop())
    watcher.start(folder)

    return {"status": "ok", "folder": folder}

@app.post("/api/index/start")
async def start_indexing():
    """开始全量索引"""
    folder = config.watch_folder
    if not folder or not os.path.isdir(folder):
        raise HTTPException(400, "请先设置监听文件夹")

    # 异步执行索引
    asyncio.create_task(watcher.index_all(folder))
    return {"status": "indexing_started"}

@app.get("/api/index/status")
async def get_index_status():
    """获取索引状态"""
    return watcher.status

@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    return indexer.get_stats()

@app.get("/api/files")
async def list_files(limit: int = 50, offset: int = 0):
    """获取文件列表"""
    return indexer.get_all_files(limit, offset)

@app.get("/api/files/{file_id}")
async def get_file(file_id: int):
    """获取文件详情"""
    f = indexer.get_file(file_id)
    if not f:
        raise HTTPException(404, "文件未找到")
    return f

@app.post("/api/search")
async def search(req: SearchRequest):
    """搜索文件"""
    if not req.query.strip():
        return {"results": []}

    if req.mode == "deep":
        # 深度搜索：先粗筛，再让 AI 精排
        candidates = indexer.get_candidates_for_deep_search(req.query, limit=20)
        results = await ai_service.deep_search(req.query, candidates)
        return {"results": results, "mode": "deep"}
    else:
        # 快速搜索
        results = indexer.quick_search(req.query, limit=20)
        return {"results": results, "mode": "quick"}

@app.post("/api/compare")
async def compare_files(req: CompareRequest):
    """比对两个文件"""
    f1 = indexer.get_file(req.file_id_1)
    f2 = indexer.get_file(req.file_id_2)
    if not f1 or not f2:
        raise HTTPException(404, "文件未找到")

    result = await ai_service.compare_files(
        {"filename": f1["filename"], "content": f1.get("content_text", "")},
        {"filename": f2["filename"], "content": f2.get("content_text", "")},
    )
    return {"file_1": f1["filename"], "file_2": f2["filename"], "comparison": result}

@app.post("/api/rename")
async def rename_file(req: RenameRequest):
    """重命名单个文件"""
    f = indexer.get_file(req.file_id)
    if not f:
        raise HTTPException(404, "文件未找到")

    new_name = req.new_name
    if not new_name:
        # AI 建议名称
        new_name = await ai_service.suggest_name(f["filename"], f.get("content_text", ""))

    old_path = Path(f["path"])
    new_path = old_path.parent / new_name

    if new_path.exists() and new_path != old_path:
        raise HTTPException(400, "目标文件名已存在")

    try:
        old_path.rename(new_path)
        indexer.update_rename(req.file_id, new_name, f["filename"])
        return {"status": "ok", "old_name": f["filename"], "new_name": new_name}
    except Exception as e:
        raise HTTPException(500, f"重命名失败: {str(e)}")

@app.post("/api/batch-rename")
async def batch_rename(req: BatchRenameRequest):
    """批量重命名"""
    files = []
    for fid in req.file_ids:
        f = indexer.get_file(fid)
        if f:
            files.append({"filename": f["filename"], "id": fid})

    if not files:
        raise HTTPException(400, "没有有效文件")

    rename_list = await ai_service.batch_rename(files, req.instruction)

    results = []
    for item in rename_list:
        idx = item.get("index")
        new_name = item.get("new_name")
        if idx is not None and new_name and idx < len(files):
            f = indexer.get_file(files[idx]["id"])
            if f:
                old_path = Path(f["path"])
                new_path = old_path.parent / new_name
                try:
                    if not new_path.exists():
                        old_path.rename(new_path)
                        indexer.update_rename(f["id"], new_name, f["filename"])
                        results.append({"id": f["id"], "old_name": f["filename"], "new_name": new_name, "status": "ok"})
                    else:
                        results.append({"id": f["id"], "old_name": f["filename"], "new_name": new_name, "status": "skipped_exists"})
                except Exception as e:
                    results.append({"id": f["id"], "old_name": f["filename"], "new_name": new_name, "status": f"error: {str(e)}"})

    return {"results": results}

@app.post("/api/reorganize")
async def reorganize():
    """AI 建议文件夹结构"""
    files = indexer.get_all_files(limit=200)
    if not files:
        raise HTTPException(400, "没有已索引的文件")

    result = await ai_service.suggest_structure(files)
    return {"suggestion": result}

@app.post("/api/rename/apply-ai")
async def apply_ai_name(file_id: int):
    """应用 AI 建议的名称"""
    f = indexer.get_file(file_id)
    if not f:
        raise HTTPException(404, "文件未找到")

    ai_name = f.get("ai_name", "")
    if not ai_name:
        raise HTTPException(400, "没有 AI 建议的名称")

    old_path = Path(f["path"])
    new_path = old_path.parent / ai_name

    if new_path.exists() and new_path != old_path:
        raise HTTPException(400, "目标文件名已存在")

    try:
        old_path.rename(new_path)
        indexer.update_rename(file_id, ai_name, f["filename"])
        return {"status": "ok", "old_name": f["filename"], "new_name": ai_name}
    except Exception as e:
        raise HTTPException(500, f"重命名失败: {str(e)}")

@app.get("/api/models")
async def list_models():
    """列出可用模型"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{config.get('api_url')}/models",
                headers={"Authorization": f"Bearer {config.get('api_key')}"}
            )
            data = resp.json()
            return {"models": [m["id"] for m in data.get("data", [])]}
    except Exception as e:
        return {"models": [], "error": str(e)}

# ============ 前端静态文件 ============

frontend_dir = Path(__file__).parent.parent / "frontend"

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return FileResponse(frontend_dir / "index.html")


def mount_static():
    """挂载静态文件"""
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


def start_app(open_browser: bool = True, port: int = 8765):
    """启动应用"""
    import uvicorn

    mount_static()

    if open_browser:
        def _open():
            import time
            time.sleep(1.5)
            webbrowser.open(f"http://localhost:{port}")
        import threading
        threading.Thread(target=_open, daemon=True).start()

    # 启动时自动设置 watcher 的事件循环为当前循环
    @app.on_event("startup")
    async def _startup():
        loop = asyncio.get_event_loop()
        watcher.set_loop(loop)
        # 如果有配置的监听文件夹，自动启动监听
        folder = config.watch_folder
        if folder and os.path.isdir(folder):
            try:
                watcher.start(folder)
            except Exception as e:
                print(f"启动文件监听失败: {e}")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
