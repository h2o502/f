"""AI 服务 - 云端 API 调用"""
import json
import re
import httpx
from backend.config import config


# 文件名非法字符（Windows + macOS + Linux 并集）
_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\n\r\t]')


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    name = _ILLEGAL_FILENAME_CHARS.sub('_', name).strip()
    # 限制长度
    if len(name) > 200:
        name = name[:200]
    return name


class AIService:
    def __init__(self):
        self.refresh_config()

    def refresh_config(self):
        """从 config 重新读取配置（用户修改设置后调用）"""
        self.api_url = config.get("api_url")
        self.api_key = config.get("api_key")
        self.model = config.get("model", "qwen3.6-flash")
        self.deep_model = config.get("deep_model", "qwen3.6-plus")

    async def chat(self, messages: list, model: str = None, max_tokens: int = 2000) -> str:
        """调用云端 LLM"""
        model = model or self.model
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def generate_tags(self, filename: str, content: str) -> list:
        """为文件生成标签"""
        # 截取内容前2000字
        snippet = content[:2000] if content else "[无文本内容]"
        messages = [
            {"role": "system", "content": "你是一个文件标签生成器。根据文件名和内容，生成5-10个简洁的中文标签。只输出标签，用逗号分隔，不要其他内容。"},
            {"role": "user", "content": f"文件名: {filename}\n\n内容摘要:\n{snippet}"}
        ]
        result = await self.chat(messages, max_tokens=200)
        tags = [t.strip() for t in result.split(",") if t.strip()]
        return tags[:10]

    async def generate_summary(self, filename: str, content: str) -> str:
        """为文件生成摘要"""
        snippet = content[:3000] if content else "[无文本内容]"
        messages = [
            {"role": "system", "content": "你是一个文件摘要生成器。用1-3句话概括文件的核心内容。只输出摘要，不要其他内容。"},
            {"role": "user", "content": f"文件名: {filename}\n\n内容:\n{snippet}"}
        ]
        return await self.chat(messages, max_tokens=300)

    async def suggest_name(self, filename: str, content: str) -> str:
        """为文件建议新名称"""
        snippet = content[:2000] if content else "[无文本内容]"
        messages = [
            {"role": "system", "content": "你是一个文件命名专家。根据文件内容，建议一个简洁、有意义的文件名。保留原始扩展名。只输出新文件名，不要其他内容，不要换行。"},
            {"role": "user", "content": f"原文件名: {filename}\n\n内容摘要:\n{snippet}"}
        ]
        name = await self.chat(messages, max_tokens=100)
        return sanitize_filename(name)

    async def deep_search(self, query: str, candidates: list) -> list:
        """深度搜索：用 LLM 从候选文件中筛选最相关的"""
        if not candidates:
            return []

        candidate_text = ""
        for i, c in enumerate(candidates[:20]):  # 最多20个候选
            candidate_text += f"\n[{i}] {c['filename']} - {c.get('summary', '无摘要')} (标签: {', '.join(c.get('tags', []))})"

        messages = [
            {"role": "system", "content": "你是一个文件搜索助手。用户给出搜索意图，你从候选文件中选出最相关的，返回文件编号列表。格式：只输出编号，用逗号分隔，按相关度排序。例如：0,3,5"},
            {"role": "user", "content": f"搜索: {query}\n\n候选文件:{candidate_text}"}
        ]
        result = await self.chat(messages, model=self.deep_model, max_tokens=100)

        # 解析结果
        indices = []
        for part in result.split(","):
            part = part.strip()
            try:
                idx = int(part)
                if 0 <= idx < len(candidates):
                    indices.append(idx)
            except ValueError:
                continue

        return [candidates[i] for i in indices]

    async def compare_files(self, file1: dict, file2: dict) -> dict:
        """比对两个文件"""
        content1 = file1.get("content", "")[:3000]
        content2 = file2.get("content", "")[:3000]

        messages = [
            {"role": "system", "content": "你是一个文件比对专家。比对两个文件的内容差异，输出JSON格式：{\"summary\": \"一句话概括差异\", \"differences\": [\"差异1\", \"差异2\", ...], \"merge_suggestion\": \"合并建议（如有）\"}"},
            {"role": "user", "content": f"文件1: {file1['filename']}\n{content1}\n\n---\n\n文件2: {file2['filename']}\n{content2}"}
        ]
        result = await self.chat(messages, model=self.deep_model, max_tokens=1000)

        try:
            # 尝试解析 JSON
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]
            return json.loads(result.strip())
        except (json.JSONDecodeError, IndexError):
            return {
                "summary": result[:200],
                "differences": [],
                "merge_suggestion": ""
            }

    async def batch_rename(self, files: list, instruction: str) -> list:
        """批量重命名"""
        file_list = "\n".join(f"[{i}] {f['filename']}" for i, f in enumerate(files))
        messages = [
            {"role": "system", "content": "你是一个文件命名专家。根据用户指令，为每个文件生成新名称。输出JSON数组，格式：[{\"index\": 0, \"new_name\": \"新文件名\"}, ...]。保留原始扩展名。"},
            {"role": "user", "content": f"文件列表:\n{file_list}\n\n重命名要求: {instruction}"}
        ]
        result = await self.chat(messages, model=self.deep_model, max_tokens=1000)

        try:
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]
            rename_list = json.loads(result.strip())
            # 清理每个文件名
            for item in rename_list:
                if "new_name" in item:
                    item["new_name"] = sanitize_filename(item["new_name"])
            return rename_list
        except (json.JSONDecodeError, IndexError):
            return []

    async def suggest_structure(self, files: list) -> dict:
        """建议文件夹结构"""
        file_list = "\n".join(f"- {f['filename']} (标签: {', '.join(f.get('tags', []))})" for f in files[:100])
        messages = [
            {"role": "system", "content": "你是一个文件管理专家。根据文件列表，建议一个合理的文件夹分类结构。输出JSON格式：{\"folders\": [{\"name\": \"文件夹名\", \"files\": [\"文件名1\", \"文件名2\"]}, ...]}"},
            {"role": "user", "content": f"文件列表:\n{file_list}"}
        ]
        result = await self.chat(messages, model=self.deep_model, max_tokens=2000)

        try:
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]
            return json.loads(result.strip())
        except (json.JSONDecodeError, IndexError):
            return {"folders": []}


ai_service = AIService()
