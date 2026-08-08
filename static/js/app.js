/**
 * XCRDownloader — Web UI JavaScript
 */
document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const urlInput = document.getElementById('url-input');
    const btnDetect = document.getElementById('btn-detect');
    const btnDownload = document.getElementById('btn-download');
    const btnBatchDownload = document.getElementById('btn-batch-download');
    const batchUrls = document.getElementById('batch-urls');
    const qualitySelect = document.getElementById('quality');
    const formatSelect = document.getElementById('format');
    const platformDetect = document.getElementById('platform-detect');
    const progressSection = document.getElementById('progress-section');
    const progressBar = document.getElementById('progress-bar');
    const progressStatus = document.getElementById('progress-status');
    const resultsSection = document.getElementById('results-section');
    const resultsList = document.getElementById('results-list');
    const historyList = document.getElementById('history-list');
    const btnRefresh = document.getElementById('btn-refresh-history');

    const PLATFORM_ICONS = {
        instagram: '📸', tiktok: '🎵', twitter: '🐦',
        pinterest: '📌', generic: '🌐'
    };

    // Tab switching
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
        });
    });

    // Platform detection
    let detectTimer;
    urlInput.addEventListener('input', () => {
        clearTimeout(detectTimer);
        const url = urlInput.value.trim();
        if (!url) { platformDetect.innerHTML = ''; return; }
        detectTimer = setTimeout(() => detectPlatform(url), 300);
    });

    btnDetect.addEventListener('click', () => {
        const url = urlInput.value.trim();
        if (url) detectPlatform(url);
    });

    async function detectPlatform(url) {
        try {
            const resp = await fetch('/api/detect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            const data = await resp.json();
            const platform = data.platform || 'generic';
            const icon = PLATFORM_ICONS[platform] || '🌐';
            platformDetect.innerHTML = `
                <span class="platform-badge ${platform}">${icon} ${platform.toUpperCase()}</span>
                <span style="margin-left:8px;color:var(--text-muted)">→ ${data.handler}</span>
            `;
        } catch (e) {
            platformDetect.innerHTML = '<span style="color:var(--error)">Could not detect platform</span>';
        }
    }

    // Single download
    btnDownload.addEventListener('click', startDownload);
    urlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') startDownload();
    });

    async function startDownload() {
        const url = urlInput.value.trim();
        if (!url) { shakeInput(urlInput); return; }

        btnDownload.classList.add('loading');
        btnDownload.innerHTML = '<span class="btn-icon">⏳</span> Downloading...';
        showProgress('Starting download...');
        hideResults();

        try {
            const resp = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url,
                    quality: qualitySelect.value,
                    audio_only: formatSelect.value === 'audio'
                })
            });
            const data = await resp.json();
            if (data.job_id) {
                pollJob(data.job_id);
            } else {
                showError(data.error || 'Failed to start download');
            }
        } catch (e) {
            showError('Network error: ' + e.message);
        }
    }

    // Batch download
    btnBatchDownload.addEventListener('click', startBatchDownload);

    async function startBatchDownload() {
        const text = batchUrls.value.trim();
        if (!text) { shakeInput(batchUrls); return; }

        const urls = text.split('\n').map(u => u.trim()).filter(u => u && u.startsWith('http'));
        if (urls.length === 0) { showError('No valid URLs found'); return; }

        btnBatchDownload.classList.add('loading');
        btnBatchDownload.innerHTML = '<span class="btn-icon">⏳</span> Downloading...';
        showProgress(`Starting batch download of ${urls.length} URLs...`);
        hideResults();

        try {
            const resp = await fetch('/api/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    urls,
                    quality: document.getElementById('batch-quality').value
                })
            });
            const data = await resp.json();
            if (data.job_id) {
                pollJob(data.job_id, true);
            } else {
                showError(data.error || 'Failed to start batch');
            }
        } catch (e) {
            showError('Network error: ' + e.message);
        }
    }

    // Poll job status
    async function pollJob(jobId, isBatch = false) {
        progressBar.classList.add('indeterminate');
        progressStatus.textContent = 'Downloading...';

        const interval = setInterval(async () => {
            try {
                const resp = await fetch(`/api/job/${jobId}`);
                const job = await resp.json();

                if (job.status === 'completed') {
                    clearInterval(interval);
                    progressBar.classList.remove('indeterminate');
                    progressBar.style.width = '100%';
                    progressStatus.textContent = 'Download complete!';
                    if (isBatch) {
                        showBatchResults(job.results || []);
                    } else {
                        showResult(job.result);
                    }
                    resetButtons();
                    loadHistory();
                } else if (job.status === 'failed') {
                    clearInterval(interval);
                    progressBar.classList.remove('indeterminate');
                    progressBar.style.width = '100%';
                    progressBar.style.background = 'var(--error)';
                    progressStatus.textContent = 'Download failed';
                    if (isBatch) {
                        showBatchResults(job.results || []);
                    } else {
                        showError(job.result?.error || 'Download failed');
                    }
                    resetButtons();
                    loadHistory();
                }
            } catch (e) {
                // Keep polling
            }
        }, 1000);

        // Timeout after 5 minutes
        setTimeout(() => { clearInterval(interval); resetButtons(); }, 300000);
    }

    function showResult(result) {
        resultsSection.style.display = 'block';
        resultsList.innerHTML = '';

        if (!result || !result.success) {
            resultsList.innerHTML = `
                <div class="result-item fade-in">
                    <span class="result-icon">❌</span>
                    <div class="result-info">
                        <div class="filename">Download Failed</div>
                        <div class="meta">${result?.error || 'Unknown error'}</div>
                    </div>
                </div>`;
            return;
        }

        const info = result.info || {};
        for (const file of (result.files || [])) {
            const ext = file.ext || '';
            const icon = ext === '.mp4' ? '🎬' : ext === '.mp3' ? '🎵' : '🖼️';
            resultsList.innerHTML += `
                <div class="result-item fade-in">
                    <span class="result-icon">${icon}</span>
                    <div class="result-info">
                        <div class="filename">${file.path?.split('/').pop()?.split('\\').pop() || 'File'}</div>
                        <div class="meta">${file.size_human || ''} ${info.title ? '· ' + info.title.substring(0, 60) : ''}</div>
                    </div>
                    <span class="result-status">✅</span>
                </div>`;
        }
    }

    function showBatchResults(results) {
        resultsSection.style.display = 'block';
        resultsList.innerHTML = '';

        const success = results.filter(r => r.success).length;
        resultsList.innerHTML += `
            <div class="result-item fade-in" style="background:var(--accent);color:white;border:none;">
                <span class="result-icon">📊</span>
                <div class="result-info">
                    <div class="filename">${success}/${results.length} downloads successful</div>
                </div>
            </div>`;

        for (const result of results) {
            const platform = result.platform || 'generic';
            const icon = PLATFORM_ICONS[platform] || '🌐';
            if (result.success) {
                for (const file of (result.files || [])) {
                    resultsList.innerHTML += `
                        <div class="result-item fade-in">
                            <span class="result-icon">${icon}</span>
                            <div class="result-info">
                                <div class="filename">${file.path?.split('/').pop()?.split('\\').pop() || 'File'}</div>
                                <div class="meta">${file.size_human || ''}</div>
                            </div>
                            <span class="result-status">✅</span>
                        </div>`;
                }
            } else {
                resultsList.innerHTML += `
                    <div class="result-item fade-in">
                        <span class="result-icon">${icon}</span>
                        <div class="result-info">
                            <div class="filename">${result.url || 'URL'}</div>
                            <div class="meta" style="color:var(--error)">${result.error || 'Failed'}</div>
                        </div>
                        <span class="result-status">❌</span>
                    </div>`;
            }
        }
    }

    function showError(msg) {
        resultsSection.style.display = 'block';
        resultsList.innerHTML = `
            <div class="result-item fade-in">
                <span class="result-icon">❌</span>
                <div class="result-info">
                    <div class="filename">Error</div>
                    <div class="meta" style="color:var(--error)">${msg}</div>
                </div>
            </div>`;
        resetButtons();
    }

    function showProgress(msg) {
        progressSection.style.display = 'block';
        progressBar.style.width = '0%';
        progressBar.style.background = '';
        progressStatus.textContent = msg;
    }

    function hideResults() {
        resultsSection.style.display = 'none';
        resultsList.innerHTML = '';
    }

    function resetButtons() {
        btnDownload.classList.remove('loading');
        btnDownload.innerHTML = '<span class="btn-icon">⬇️</span> Download';
        btnBatchDownload.classList.remove('loading');
        btnBatchDownload.innerHTML = '<span class="btn-icon">⬇️</span> Download All';
    }

    function shakeInput(el) {
        el.style.animation = 'none';
        el.offsetHeight;
        el.style.animation = 'shake 0.3s ease';
        el.style.borderColor = 'var(--error)';
        setTimeout(() => { el.style.borderColor = ''; }, 1000);
    }

    // History
    btnRefresh.addEventListener('click', loadHistory);
    loadHistory();

    async function loadHistory() {
        try {
            const resp = await fetch('/api/history');
            const data = await resp.json();
            const jobs = (data.jobs || []).reverse();

            if (jobs.length === 0) {
                historyList.innerHTML = '<p class="empty-state">No downloads yet. Paste a URL above to get started!</p>';
                return;
            }

            historyList.innerHTML = '';
            for (const job of jobs.slice(0, 20)) {
                const platform = job.platform || 'generic';
                const icon = PLATFORM_ICONS[platform] || '🌐';
                const statusClass = job.status === 'completed' ? 'completed' :
                                    job.status === 'failed' ? 'failed' : 'downloading';
                const url = job.url || (job.urls ? `${job.urls.length} URLs` : '');
                historyList.innerHTML += `
                    <div class="history-item">
                        <span class="history-platform">${icon}</span>
                        <div class="history-info">
                            <div class="url" title="${url}">${url}</div>
                            <div class="time">${job.created_at || ''}</div>
                        </div>
                        <span class="history-status ${statusClass}">${job.status}</span>
                    </div>`;
            }
        } catch (e) {
            // silent
        }
    }
});

// Shake animation
const style = document.createElement('style');
style.textContent = `@keyframes shake { 0%,100%{transform:translateX(0)} 25%{transform:translateX(-5px)} 75%{transform:translateX(5px)} }`;
document.head.appendChild(style);
