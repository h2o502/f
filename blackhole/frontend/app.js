/* Blackhole - AI 黑洞文件夹 前端逻辑 */

const API = '';

// ============ 工具函数 ============

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
}

function formatDate(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    return d.toLocaleDateString('zh-CN') + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function getFileIcon(ext) {
    const map = {
        '.pdf': { cls: 'pdf', icon: 'PDF' },
        '.doc': { cls: 'doc', icon: 'DOC' }, '.docx': { cls: 'doc', icon: 'DOC' },
        '.xls': { cls: 'xls', icon: 'XLS' }, '.xlsx': { cls: 'xls', icon: 'XLS' },
        '.ppt': { cls: 'ppt', icon: 'PPT' }, '.pptx': { cls: 'ppt', icon: 'PPT' },
        '.png': { cls: 'img', icon: 'IMG' }, '.jpg': { cls: 'img', icon: 'IMG' },
        '.jpeg': { cls: 'img', icon: 'IMG' }, '.gif': { cls: 'img', icon: 'IMG' },
        '.py': { cls: 'code', icon: 'PY' }, '.js': { cls: 'code', icon: 'JS' },
        '.ts': { cls: 'code', icon: 'TS' }, '.java': { cls: 'code', icon: 'JV' },
        '.go': { cls: 'code', icon: 'GO' }, '.rs': { cls: 'code', icon: 'RS' },
        '.md': { cls: 'txt', icon: 'MD' }, '.txt': { cls: 'txt', icon: 'TXT' },
        '.csv': { cls: 'xls', icon: 'CSV' },
    };
    return map[ext] || { cls: 'default', icon: ext.replace('.', '').toUpperCase().slice(0, 3) || 'FILE' };
}

async function api(path, method = 'GET', body = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(API + path, opts);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || '请求失败');
    }
    return resp.json();
}

function showLoading(container, text = '加载中...') {
    container.innerHTML = `<div class="loading"><div class="spinner"></div>${text}</div>`;
}

function showEmpty(container, text = '暂无数据', hint = '') {
    container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">●</div><div class="empty-state-text">${text}</div>${hint ? `<div class="empty-state-hint">${hint}</div>` : ''}</div>`;
}

// ============ 标签页切换 ============

document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');

        // 切换到文件页时刷新列表
        if (btn.dataset.tab === 'files') loadFiles();
        if (btn.dataset.tab === 'compare') loadCompareOptions();
        if (btn.dataset.tab === 'manage') loadManageFiles();
    });
});

// ============ 搜索 ============

let searchMode = 'quick';

document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        searchMode = btn.dataset.mode;
    });
});

const searchInput = document.getElementById('search-input');
const searchBtn = document.getElementById('search-btn');
const searchResults = document.getElementById('search-results');

searchInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') doSearch();
});
searchBtn.addEventListener('click', doSearch);

async function doSearch() {
    const query = searchInput.value.trim();
    if (!query) return;

    searchBtn.disabled = true;
    showLoading(searchResults, searchMode === 'deep' ? '深度检索中，AI 正在分析...' : '搜索中...');

    try {
        const data = await api('/api/search', 'POST', { query, mode: searchMode });
        renderSearchResults(data.results, data.mode);
    } catch (e) {
        searchResults.innerHTML = `<div class="empty-state"><div class="empty-state-text">搜索失败: ${e.message}</div></div>`;
    } finally {
        searchBtn.disabled = false;
    }
}

function renderSearchResults(results, mode) {
    if (!results || results.length === 0) {
        showEmpty(searchResults, '没有找到相关文件', '试试换个关键词，或使用深度检索');
        return;
    }

    const modeLabel = mode === 'deep' ? '<span class="tag" style="background:rgba(0,184,148,0.15);color:var(--success)">深度检索</span>' : '<span class="tag">快速搜索</span>';

    searchResults.innerHTML = modeLabel + results.map(f => {
        const icon = getFileIcon(f.extension);
        const tags = (f.tags || []).map(t => `<span class="tag">${t}</span>`).join('');
        return `
            <div class="result-card" onclick="showFileDetail(${f.id})">
                <div class="result-header">
                    <div class="result-icon ${icon.cls}">${icon.icon}</div>
                    <div>
                        <span class="result-name">${f.filename}</span>
                        ${f.ai_name && f.ai_name !== f.filename ? `<span class="result-ai-name">AI: ${f.ai_name}</span>` : ''}
                    </div>
                </div>
                <div class="result-summary">${f.summary || '暂无摘要'}</div>
                <div class="result-tags">${tags}</div>
                <div class="result-meta">
                    <span>${formatSize(f.file_size)}</span>
                    <span>${formatDate(f.modified_at)}</span>
                </div>
            </div>
        `;
    }).join('');
}

// ============ 文件列表 ============

async function loadFiles() {
    const list = document.getElementById('file-list');
    const countEl = document.getElementById('file-count');
    showLoading(list);

    try {
        const [files, stats] = await Promise.all([
            api('/api/files?limit=100'),
            api('/api/stats')
        ]);

        countEl.textContent = `共 ${stats.total_files} 个文件，${formatSize(stats.total_size)}`;

        if (files.length === 0) {
            showEmpty(list, '还没有索引文件', '请先设置监听文件夹并开始索引');
            return;
        }

        list.innerHTML = files.map(f => {
            const icon = getFileIcon(f.extension);
            const tags = (f.tags || []).slice(0, 3).map(t => `<span class="tag">${t}</span>`).join('');
            return `
                <div class="file-item" onclick="showFileDetail(${f.id})">
                    <div class="result-icon ${icon.cls}" style="width:28px;height:28px;font-size:11px">${icon.icon}</div>
                    <span class="file-item-name">${f.filename}</span>
                    <div class="file-item-tags">${tags}</div>
                    <span class="file-item-size">${formatSize(f.file_size)}</span>
                </div>
            `;
        }).join('');
    } catch (e) {
        list.innerHTML = `<div class="empty-state"><div class="empty-state-text">加载失败: ${e.message}</div></div>`;
    }
}

// 开始索引
document.getElementById('btn-start-index').addEventListener('click', async () => {
    try {
        await api('/api/index/start', 'POST');
        pollIndexStatus();
    } catch (e) {
        alert('启动索引失败: ' + e.message);
    }
});

async function pollIndexStatus() {
    const progress = document.getElementById('index-progress');
    const fill = progress.querySelector('.progress-fill');
    const text = progress.querySelector('.progress-text');
    progress.style.display = 'block';

    const poll = async () => {
        try {
            const status = await api('/api/index/status');
            const pct = status.total > 0 ? Math.round((status.progress / status.total) * 100) : 0;
            fill.style.width = pct + '%';
            text.textContent = status.running ? `正在索引: ${status.current} (${status.progress}/${status.total})` : '索引完成';

            const badge = document.getElementById('index-status');
            if (status.running) {
                badge.textContent = '索引中...';
                badge.className = 'status-badge indexing';
                setTimeout(poll, 2000);
            } else {
                badge.textContent = '就绪';
                badge.className = 'status-badge active';
                setTimeout(() => { progress.style.display = 'none'; }, 2000);
                loadFiles();
            }
        } catch (e) {
            setTimeout(poll, 3000);
        }
    };
    poll();
}

// ============ 文件详情弹窗 ============

function showFileDetail(fileId) {
    api('/api/files/' + fileId).then(f => {
        const modal = document.getElementById('file-modal');
        document.getElementById('modal-title').textContent = f.filename;
        const tags = (f.tags || []).map(t => `<span class="tag">${t}</span>`).join('');
        const content = (f.content_text || '').substring(0, 3000);

        document.getElementById('modal-body').innerHTML = `
            <div class="detail-section">
                <div class="detail-label">AI 建议名称</div>
                <div class="detail-value" style="display:flex;align-items:center;gap:8px">
                    ${f.ai_name || '无'}
                    ${f.ai_name && f.ai_name !== f.filename ? `<button class="btn btn-sm btn-primary" onclick="applyAiName(${f.id})">应用此名称</button>` : ''}
                </div>
            </div>
            <div class="detail-section">
                <div class="detail-label">标签</div>
                <div class="detail-value">${tags || '无'}</div>
            </div>
            <div class="detail-section">
                <div class="detail-label">摘要</div>
                <div class="detail-value">${f.summary || '暂无摘要'}</div>
            </div>
            <div class="detail-section">
                <div class="detail-label">文件信息</div>
                <div class="detail-value">
                    大小: ${formatSize(f.file_size)} | 
                    修改时间: ${formatDate(f.modified_at)} |
                    类型: ${f.extension}
                </div>
            </div>
            <div class="detail-section">
                <div class="detail-label">内容预览</div>
                <div class="detail-content">${content || '[无可提取内容]'}</div>
            </div>
        `;
        modal.style.display = 'flex';
    }).catch(e => alert('加载失败: ' + e.message));
}

function closeModal() {
    document.getElementById('file-modal').style.display = 'none';
}

async function applyAiName(fileId) {
    try {
        const result = await api('/api/rename/apply-ai?file_id=' + fileId, 'POST');
        alert(`已重命名: ${result.old_name} → ${result.new_name}`);
        closeModal();
        loadFiles();
    } catch (e) {
        alert('重命名失败: ' + e.message);
    }
}

// ============ 文件比对 ============

async function loadCompareOptions() {
    try {
        const files = await api('/api/files?limit=200');
        const options = files.map(f => `<option value="${f.id}">${f.filename}</option>`).join('');
        document.getElementById('compare-file-1').innerHTML = '<option value="">选择文件...</option>' + options;
        document.getElementById('compare-file-2').innerHTML = '<option value="">选择文件...</option>' + options;
    } catch (e) { /* ignore */ }
}

document.getElementById('btn-compare').addEventListener('click', async () => {
    const id1 = parseInt(document.getElementById('compare-file-1').value);
    const id2 = parseInt(document.getElementById('compare-file-2').value);

    if (!id1 || !id2) { alert('请选择两个文件'); return; }
    if (id1 === id2) { alert('请选择不同的文件'); return; }

    const resultDiv = document.getElementById('compare-result');
    showLoading(resultDiv, 'AI 正在比对两个文件...');

    try {
        const data = await api('/api/compare', 'POST', { file_id_1: id1, file_id_2: id2 });
        const comp = data.comparison || {};

        let html = `<div class="compare-summary">${comp.summary || '比对完成'}</div>`;

        if (comp.differences && comp.differences.length > 0) {
            html += '<ul class="compare-diffs">' +
                comp.differences.map(d => `<li>${d}</li>`).join('') +
                '</ul>';
        }

        if (comp.merge_suggestion) {
            html += `<div class="compare-merge">合并建议: ${comp.merge_suggestion}</div>`;
        }

        resultDiv.innerHTML = html;
    } catch (e) {
        resultDiv.innerHTML = `<div class="empty-state"><div class="empty-state-text">比对失败: ${e.message}</div></div>`;
    }
});

// ============ 文件管理 ============

let manageSelectedFiles = new Set();

async function loadManageFiles() {
    const list = document.getElementById('rename-file-list');
    try {
        const files = await api('/api/files?limit=100');
        if (files.length === 0) {
            showEmpty(list, '暂无文件');
            return;
        }
        list.innerHTML = files.map(f => `
            <div class="manage-file-item">
                <input type="checkbox" value="${f.id}" onchange="toggleManageFile(${f.id}, this.checked)">
                <span>${f.filename}</span>
            </div>
        `).join('');
    } catch (e) { /* ignore */ }
}

function toggleManageFile(id, checked) {
    if (checked) manageSelectedFiles.add(id);
    else manageSelectedFiles.delete(id);
}

// 批量重命名
document.getElementById('btn-batch-rename').addEventListener('click', async () => {
    const instruction = document.getElementById('rename-instruction').value.trim();
    if (!instruction) { alert('请输入重命名规则'); return; }
    if (manageSelectedFiles.size === 0) { alert('请先选择文件'); return; }

    try {
        const data = await api('/api/batch-rename', 'POST', {
            file_ids: Array.from(manageSelectedFiles),
            instruction
        });

        const results = data.results || [];
        let msg = results.map(r => `${r.old_name} → ${r.new_name}: ${r.status}`).join('\n');
        alert('重命名结果:\n' + msg);
        loadManageFiles();
    } catch (e) {
        alert('批量重命名失败: ' + e.message);
    }
});

// 结构重整
document.getElementById('btn-reorganize').addEventListener('click', async () => {
    const resultDiv = document.getElementById('reorganize-result');
    showLoading(resultDiv, 'AI 正在分析文件结构...');

    try {
        const data = await api('/api/reorganize', 'POST');
        const suggestion = data.suggestion || {};
        const folders = suggestion.folders || [];

        if (folders.length === 0) {
            showEmpty(resultDiv, '无法生成建议');
            return;
        }

        resultDiv.innerHTML = folders.map(folder => `
            <div class="reorganize-folder">
                <div class="reorganize-folder-name">📁 ${folder.name}</div>
                ${(folder.files || []).map(f => `<div class="reorganize-file">📄 ${f}</div>`).join('')}
            </div>
        `).join('');
    } catch (e) {
        resultDiv.innerHTML = `<div class="empty-state"><div class="empty-state-text">生成失败: ${e.message}</div></div>`;
    }
});

// ============ 设置 ============

async function loadSettings() {
    try {
        const cfg = await api('/api/config');
        document.getElementById('setting-folder').value = cfg.watch_folder || '';
        document.getElementById('setting-api-url').value = cfg.api_url || '';
        document.getElementById('setting-api-key').value = cfg.api_key || '';
        document.getElementById('setting-auto-rename').checked = cfg.auto_rename || false;

        // 加载模型列表
        const models = await api('/api/models');
        const modelList = models.models || [];
        const modelSelect = document.getElementById('setting-model');
        const deepModelSelect = document.getElementById('setting-deep-model');

        const options = modelList.map(m => `<option value="${m}">${m}</option>`).join('');
        modelSelect.innerHTML = options;
        deepModelSelect.innerHTML = options;

        if (cfg.model) modelSelect.value = cfg.model;
        if (cfg.deep_model) deepModelSelect.value = cfg.deep_model;
    } catch (e) { /* ignore */ }
}

// 选择文件夹（浏览器无法直接选本地文件夹，使用手动输入）
document.getElementById('btn-select-folder').addEventListener('click', () => {
    const folder = prompt('请输入文件夹路径:', document.getElementById('setting-folder').value);
    if (folder) document.getElementById('setting-folder').value = folder;
});

// 保存设置
document.getElementById('btn-save-settings').addEventListener('click', async () => {
    try {
        await api('/api/config', 'POST', {
            watch_folder: document.getElementById('setting-folder').value,
            api_url: document.getElementById('setting-api-url').value,
            api_key: document.getElementById('setting-api-key').value,
            model: document.getElementById('setting-model').value,
            deep_model: document.getElementById('setting-deep-model').value,
            auto_rename: document.getElementById('setting-auto-rename').checked,
        });

        // 如果设置了文件夹，启动监听
        const folder = document.getElementById('setting-folder').value;
        if (folder) {
            await api('/api/folder', 'POST', { folder });
        }

        alert('设置已保存');
    } catch (e) {
        alert('保存失败: ' + e.message);
    }
});

// ============ 初始化 ============

async function init() {
    loadSettings();

    // 检查是否已有监听文件夹
    try {
        const cfg = await api('/api/config');
        if (cfg.watch_folder) {
            const badge = document.getElementById('index-status');
            badge.textContent = '就绪';
            badge.className = 'status-badge active';
        }
    } catch (e) { /* ignore */ }
}

init();
