# Blackhole - AI 黑洞文件夹

> 把文件扔进来，AI 帮你搞定剩下的。

## 这是什么

Blackhole 是一个本地运行的 AI 文件管理工具。你只需要把文件丢进指定文件夹，AI 会自动完成索引、标签、摘要、智能命名，然后你可以用自然语言瞬间搜到任何文件。

灵感来自 Listary 的"呼出即搜"交互 + Total Commander 的文件管理能力，用 AI 把两者融合升级。

## 核心理念

**一个文件夹，AI 管一切。**

- **存**：拖入文件，AI 后台静默处理（生成标签、摘要、智能命名）
- **找**：输入"李四的定价表"，毫秒级返回结果
- **比**：选中两个文件，AI 一句话说清差异
- **管**：自然语言描述规则，批量重命名或重整文件夹结构

## 功能

### 语义搜索

- **快速搜索**：基于索引中的标签、摘要、文件名，毫秒级响应
- **深度检索**：穿透到文件内容，用 AI 精排，找到"那段话在哪个文件里"

### AI 智能命名

- 每个文件自动生成语义化的新名称（如 `报告_v2.docx` → `李四科技_产品定价方案_2024Q2.docx`）
- 可选择自动应用或手动确认
- 保留原始文件名记录，随时可回溯

### 文件比对

- 选中两个文件，AI 生成差异摘要
- 一句话说清"改了什么"
- 提供合并建议

### 批量管理

- 自然语言描述重命名规则（如"按日期_项目名_版本号格式重命名"）
- AI 分析文件内容，建议最优的文件夹分类结构

### 自动索引

- 文件放入监听文件夹后自动触发索引
- 支持增量更新，内容没变则跳过
- 全量索引带进度显示

## 支持的文件格式

| 类型 | 格式 |
|------|------|
| 文档 | PDF, Word (.docx/.doc), Excel (.xlsx/.xls), PPT (.pptx/.ppt) |
| 文本 | TXT, Markdown, CSV, JSON, XML, HTML |
| 代码 | Python, JavaScript, TypeScript, Java, C/C++, Go, Rust, Ruby, PHP, Shell |
| 图片 | PNG, JPG, GIF, BMP, WebP（提取元数据，暂无 OCR） |
| 压缩 | ZIP, RAR, 7z（仅记录，不解压） |

## 技术架构

```
前端：单页应用（HTML + CSS + JS），暗色主题
后端：Python + FastAPI
索引：SQLite + FTS5 全文检索
AI：  云端 API（兼容 OpenAI 格式）
监听：watchdog 文件系统监听
```

```
blackhole/
├── main.py              # 启动入口（自动安装依赖）
├── requirements.txt     # Python 依赖
├── build.spec           # PyInstaller 打包配置
├── backend/
│   ├── config.py        # 配置管理
│   ├── extractor.py     # 文件内容提取（PDF/Word/Excel/PPT/代码/文本/图片）
│   ├── ai_service.py    # AI 云端服务（标签/摘要/重命名/比对/深度搜索）
│   ├── indexer.py       # SQLite + FTS5 索引引擎
│   ├── watcher.py       # 文件监听 + 自动索引
│   └── app.py           # FastAPI 应用 + API 路由
└── frontend/
    ├── index.html        # 单页应用
    ├── style.css         # 暗色主题 UI
    └── app.js            # 前端交互逻辑
```

## 快速开始

### 运行

```bash
python main.py
```

首次运行会自动安装依赖，然后浏览器打开 `http://localhost:8765`。

指定端口：
```bash
python main.py 9000
```

### 配置

1. 打开设置页
2. 输入监听文件夹路径（你的"黑洞文件夹"）
3. API 地址和 Key 已内置，可直接使用
4. 可选择快速模型和深度模型
5. 可开关"自动应用 AI 建议的文件名"

### 打包成免安装程序

```bash
pip install pyinstaller
pyinstaller build.spec
```

产物在 `dist/Blackhole`（macOS/Linux）或 `dist/Blackhole.exe`（Windows）。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/config | 获取配置 |
| POST | /api/config | 更新配置 |
| POST | /api/folder | 设置监听文件夹 |
| POST | /api/index/start | 开始全量索引 |
| GET | /api/index/status | 获取索引状态 |
| GET | /api/stats | 获取统计信息 |
| GET | /api/files | 获取文件列表 |
| GET | /api/files/{id} | 获取文件详情 |
| POST | /api/search | 搜索文件（quick/deep） |
| POST | /api/compare | 比对两个文件 |
| POST | /api/rename | 重命名单个文件 |
| POST | /api/rename/apply-ai | 应用 AI 建议的名称 |
| POST | /api/batch-rename | 批量重命名 |
| POST | /api/reorganize | AI 建议文件夹结构 |
| GET | /api/models | 列出可用模型 |

## 数据存储

所有数据存储在 `~/.blackhole/` 目录下：

- `config.json`：用户配置
- `blackhole_index.db`：SQLite 索引数据库（文件元数据 + FTS5 全文索引）

索引数据库只存储文件元数据、标签、摘要和内容文本，不复制文件本身。

## 隐私

- 所有文件内容仅在本地处理和存储
- AI 标签/摘要/命名功能通过云端 API 实现，只发送文件名和内容摘要
- API Key 存储在本地配置文件中，不会泄露到前端
- 检索功能完全在本地执行，不依赖网络

## 依赖

- Python 3.9+
- fastapi — Web 框架
- uvicorn — ASGI 服务器
- httpx — HTTP 客户端（调用 AI API）
- watchdog — 文件系统监听
- pypdf — PDF 文本提取
- python-docx — Word 文档提取
- openpyxl — Excel 文件提取
- python-pptx — PPT 文件提取
- Pillow — 图片元数据提取
