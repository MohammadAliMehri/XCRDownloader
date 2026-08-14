/**
 * XCRDownloader — Web UI v1.7.0
 * Downloader + Music/Video/Podcast Player + Anime Stream
 */
document.addEventListener('DOMContentLoaded', () => {
    // ===== TOP NAV =====
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('page-' + tab.dataset.page).classList.add('active');
        });
    });

    // ===== DOWNLOADER TABS =====
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
        });
    });

    const PLATFORM_ICONS = {
        instagram: '📸', tiktok: '🎵', twitter: '🐦', pinterest: '📌',
        youtube: '▶️', soundcloud: '🔊', youtube_music: '🎶', generic: '🌐'
    };
    const PROVIDER_LABELS = {
        yomi: 'Yomi', aniwatchtv: 'AniWatchTV', f2mc: 'Film2Media', miruro: 'Miruro'
    };

    // ===== URL PREVIEW =====
    const urlInput = document.getElementById('url-input');
    const platformDetect = document.getElementById('platform-detect');
    const previewCard = document.getElementById('preview-card');
    const previewThumb = document.getElementById('preview-thumb');
    const previewTitle = document.getElementById('preview-title');
    const previewMeta = document.getElementById('preview-meta');
    const previewDesc = document.getElementById('preview-desc');
    const qualitySelect = document.getElementById('quality');
    const formatSelect = document.getElementById('format');

    let detectTimer;
    urlInput.addEventListener('input', () => {
        clearTimeout(detectTimer);
        hidePreview();
        const url = urlInput.value.trim();
        if (!url) { platformDetect.innerHTML = ''; return; }
        if (url.startsWith('http')) detectTimer = setTimeout(() => fetchPreview(url), 500);
    });

    async function fetchPreview(url) {
        platformDetect.innerHTML = '<span style="color:var(--text-2)">⏳ Detecting...</span>';
        hidePreview();
        try {
            const det = await (await fetch('/api/detect', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({url}) })).json();
            const p = det.platform || 'generic';
            const icon = PLATFORM_ICONS[p] || '🌐';
            platformDetect.innerHTML = `<span class="platform-badge ${p}">${icon} ${p.toUpperCase()}</span><span style="margin-left:8px;color:var(--text-3)">→ ${det.handler}</span><span class="pl" style="margin-left:12px;color:var(--text-3)">⏳ Loading...</span>`;
            const data = await (await fetch('/api/preview', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({url}) })).json();
            const pl = platformDetect.querySelector('.pl'); if (pl) pl.remove();
            if (data.success && data.preview) showPreview(data.preview, p);
            else if (data.error) platformDetect.innerHTML += `<span style="margin-left:12px;color:var(--warning);font-size:0.8rem">⚠ ${data.error}</span>`;
        } catch { platformDetect.innerHTML = '<span style="color:var(--error)">Failed</span>'; }
    }

    function showPreview(p, platform) {
        previewCard.style.display = 'flex';
        if (p.thumbnail) { previewThumb.src = p.thumbnail; previewThumb.style.display = 'block'; }
        else previewThumb.style.display = 'none';
        previewTitle.textContent = p.title || 'Unknown';
        const parts = [];
        if (p.uploader) parts.push(p.uploader);
        if (p.duration_str) parts.push(p.duration_str);
        else if (p.duration) parts.push(fmtDur(p.duration));
        if (p.view_count) parts.push(fmtNum(p.view_count) + ' views');
        previewMeta.textContent = parts.join(' · ');
        if (p.description) { previewDesc.textContent = p.description.substring(0, 200); previewDesc.style.display = 'block'; }
        else previewDesc.style.display = 'none';
        if (platform === 'soundcloud' || platform === 'youtube_music') formatSelect.value = 'audio';
    }
    function hidePreview() { previewCard.style.display = 'none'; }

    // ===== DOWNLOAD =====
    const progressSection = document.getElementById('progress-section');
    const progressBar = document.getElementById('progress-bar');
    const progressStatus = document.getElementById('progress-status');
    const resultsSection = document.getElementById('results-section');
    const resultsList = document.getElementById('results-list');
    const historyList = document.getElementById('history-list');

    document.getElementById('btn-download').addEventListener('click', startDownload);
    urlInput.addEventListener('keydown', e => { if (e.key === 'Enter') startDownload(); });

    async function startDownload() {
        const url = urlInput.value.trim();
        if (!url) { shake(urlInput); return; }
        const btn = document.getElementById('btn-download');
        btn.textContent = '⏳ Downloading...';
        showProgress('Starting...');
        try {
            const data = await (await fetch('/api/download', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({url, quality:qualitySelect.value, audio_only:formatSelect.value==='audio'}) })).json();
            if (data.job_id) pollJob(data.job_id); else showError(data.error || 'Failed');
        } catch(e) { showError('Network: ' + e.message); }
    }

    document.getElementById('btn-batch-download').addEventListener('click', async () => {
        const text = document.getElementById('batch-urls').value.trim();
        if (!text) { shake(document.getElementById('batch-urls')); return; }
        const urls = text.split('\n').map(u=>u.trim()).filter(u=>u.startsWith('http'));
        if (!urls.length) { showError('No valid URLs'); return; }
        showProgress(`Batch: ${urls.length} URLs...`);
        try {
            const data = await (await fetch('/api/batch', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({urls, quality:document.getElementById('batch-quality').value}) })).json();
            if (data.job_id) pollJob(data.job_id, true); else showError(data.error || 'Failed');
        } catch(e) { showError('Network: ' + e.message); }
    });

    async function pollJob(jobId, isBatch=false) {
        progressBar.classList.add('indeterminate');
        progressStatus.textContent = 'Downloading...';
        const iv = setInterval(async () => {
            try {
                const job = await (await fetch(`/api/job/${jobId}`)).json();
                if (job.status === 'completed' || job.status === 'failed') {
                    clearInterval(iv);
                    progressBar.classList.remove('indeterminate');
                    progressBar.style.width = '100%';
                    progressStatus.textContent = job.status === 'completed' ? 'Done!' : 'Failed';
                    if (job.status === 'failed') progressBar.style.background = 'var(--error)';
                    if (isBatch) showBatchResults(job.results||[]);
                    else job.status === 'completed' ? showResult(job.result) : showError(job.result?.error||'Failed');
                    resetBtns(); loadHistory();
                }
            } catch {}
        }, 1000);
        setTimeout(() => clearInterval(iv), 300000);
    }

    function showResult(r) {
        resultsSection.style.display = 'block';
        if (!r?.success) { resultsList.innerHTML = `<div class="result-item"><span class="result-icon">❌</span><div class="result-info"><div class="filename">Failed</div><div class="meta" style="color:var(--error)">${r?.error||'Unknown'}</div></div></div>`; return; }
        resultsList.innerHTML = '';
        for (const f of r.files||[]) {
            resultsList.innerHTML += `<div class="result-item fade-in"><span class="result-icon">${f.ext==='.mp4'?'🎬':'🎵'}</span><div class="result-info"><div class="filename">${f.path?.split(/[\\/]/).pop()||'File'}</div><div class="meta">${f.size_human||''}</div></div><span class="result-status">✅</span></div>`;
        }
    }
    function showBatchResults(results) {
        resultsSection.style.display = 'block';
        const ok = results.filter(r=>r.success).length;
        resultsList.innerHTML = `<div class="result-item" style="background:var(--accent);color:white;border:none;"><span class="result-icon">📊</span><div class="result-info"><div class="filename">${ok}/${results.length} successful</div></div></div>`;
        for (const r of results) {
            for (const f of r.files||[]) {
                resultsList.innerHTML += `<div class="result-item"><span class="result-icon">${PLATFORM_ICONS[r.platform]||'🌐'}</span><div class="result-info"><div class="filename">${f.path?.split(/[\\/]/).pop()||'File'}</div><div class="meta">${f.size_human||''}</div></div><span class="result-status">${r.success?'✅':'❌'}</span></div>`;
            }
        }
    }
    function showError(msg) {
        resultsSection.style.display = 'block';
        resultsList.innerHTML = `<div class="result-item"><span class="result-icon">❌</span><div class="result-info"><div class="filename">Error</div><div class="meta" style="color:var(--error)">${msg}</div></div></div>`;
        resetBtns();
    }
    function showProgress(msg) { progressSection.style.display='block'; progressBar.style.width='0%'; progressBar.style.background=''; progressStatus.textContent=msg; }
    function resetBtns() { document.getElementById('btn-download').textContent='Download'; }

    // History
    document.getElementById('btn-refresh-history').addEventListener('click', loadHistory);
    loadHistory();
    async function loadHistory() {
        try {
            const data = await (await fetch('/api/history')).json();
            const jobs = (data.jobs||[]).reverse();
            if (!jobs.length) { historyList.innerHTML = '<p class="empty-state">No downloads yet.</p>'; return; }
            historyList.innerHTML = '';
            for (const j of jobs.slice(0,20)) {
                const p = j.platform||'generic';
                const sc = j.status==='completed'?'completed':j.status==='failed'?'failed':'downloading';
                const url = j.url || (j.urls?`${j.urls.length} URLs`:'');
                historyList.innerHTML += `<div class="history-item"><span class="history-platform">${PLATFORM_ICONS[p]||'🌐'}</span><div class="history-info"><div class="url" title="${url}">${url}</div><div class="time">${j.created_at||''}</div></div><span class="history-status ${sc}">${j.status}</span></div>`;
            }
        } catch {}
    }

    function fmtDur(sec) { if(!sec)return''; const m=Math.floor(sec/60),s=Math.floor(sec%60); return m+':'+String(s).padStart(2,'0'); }
    function fmtNum(n) { if(n>=1e9)return(n/1e9).toFixed(1)+'B'; if(n>=1e6)return(n/1e6).toFixed(1)+'M'; if(n>=1e3)return(n/1e3).toFixed(1)+'K'; return String(n); }
    function shake(el) { el.style.animation='none'; el.offsetHeight; el.style.animation='shake 0.3s ease'; el.style.borderColor='var(--error)'; setTimeout(()=>{el.style.borderColor='';},1000); }

    // =========================================================================
    // PLAYER
    // =========================================================================
    const searchInput = document.getElementById('music-search-input');
    const searchResults = document.getElementById('search-results');
    const searchStatus = document.getElementById('search-status');
    const searchLoadMore = document.getElementById('search-load-more');
    const categoryTabs = document.getElementById('category-tabs');
    const btnLoadMore = document.getElementById('btn-load-more');
    const playerProvider = document.getElementById('player-provider');

    // Player elements
    const npCover = document.getElementById('np-cover');
    const npVideo = document.getElementById('np-video');
    const npEmbed = document.getElementById('np-embed');
    const npAudio = document.getElementById('np-audio');
    const npTitle = document.getElementById('np-title');
    const npArtist = document.getElementById('np-artist');
    const npPlayPause = document.getElementById('np-playpause');
    const npProgressFill = document.getElementById('np-progress-fill');
    const npCurrent = document.getElementById('np-current');
    const npDuration = document.getElementById('np-duration');
    const npPrev = document.getElementById('np-prev');
    const npNext = document.getElementById('np-next');
    const npShuffle = document.getElementById('np-shuffle');
    const npRepeat = document.getElementById('np-repeat');
    const npVolume = document.getElementById('np-volume');
    const npVolIcon = document.getElementById('np-vol-icon');
    const npVideoToggle = document.getElementById('np-video-toggle');
    const npDownload = document.getElementById('np-download');
    const npArtWrap = document.querySelector('.np-art-wrap');
    const npPlaceholder = document.getElementById('np-art-placeholder');
    const queueList = document.getElementById('queue-list');

    const SRC_TAG = { youtube:'tag-youtube', youtube_music:'tag-youtube-music', soundcloud:'tag-soundcloud' };
    const KIND_ICON = { track:'🎵', video:'🎬', podcast:'🎙️', album:'💿', artist:'👤' };

    let currentQuery = '', currentPage = 0, allResults = [], trackQueue = [];
    let currentTrack = null, currentIdx = -1, isPlaying = false;
    let shuffleOn = false, repeatOn = false, videoMode = false;
    let activeCategory = 'all';

    function activeMedia() { return videoMode ? npVideo : npAudio; }

    function stopAllMedia() {
        npAudio.pause(); npAudio.src = '';
        npVideo.pause(); npVideo.src = '';
        npEmbed.src = 'about:blank';
        npEmbed.style.display = 'none';
    }

    // Category filter
    categoryTabs.addEventListener('click', e => {
        const pill = e.target.closest('.pill');
        if (!pill) return;
        categoryTabs.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        activeCategory = pill.dataset.cat;
        filterRender();
    });

    function filterRender() {
        searchResults.innerHTML = '';
        const filtered = activeCategory === 'all' ? allResults : allResults.filter(r => r.kind === activeCategory);
        for (const r of filtered) searchResults.appendChild(rowEl(r));
        trackQueue = filtered.filter(r => r.kind === 'track' || r.kind === 'video' || r.kind === 'podcast');
        renderQueue();
        highlight();
    }

    function highlight() {
        searchResults.querySelectorAll('.sr-row').forEach(el => {
            el.classList.toggle('active', currentTrack && el.dataset.id === currentTrack.id);
        });
        queueList.querySelectorAll('.q-item').forEach(el => {
            el.classList.toggle('active', currentTrack && el.dataset.idx === String(currentIdx));
        });
    }

    // Search
    searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(searchInput.value, 0); });
    playerProvider.addEventListener('change', () => {
        if (searchInput.value.trim()) doSearch(searchInput.value, 0);
    });
    btnLoadMore.addEventListener('click', () => doSearch(currentQuery, currentPage + 1));

    function doSearch(query, page) {
        if (!query.trim()) return;
        currentQuery = query; currentPage = page;
        if (page === 0) {
            allResults = []; searchResults.innerHTML = '';
            document.getElementById('search-empty').style.display = 'none';
            searchStatus.innerHTML = '<span class="loading">⏳ Searching YouTube, YouTube Music & SoundCloud...</span>';
            categoryTabs.style.display = 'none';
        }
        fetch(`/api/search?q=${encodeURIComponent(query)}&page=${page}&provider=${encodeURIComponent(playerProvider.value)}`)
            .then(r => r.json())
            .then(data => {
                searchStatus.innerHTML = '';
                document.getElementById('search-empty').style.display = 'none';
                if (data.error) { searchStatus.innerHTML = `<span class="error">❌ ${data.error}</span>`; return; }
                const results = data.results || [];
                if (!results.length && page === 0) {
                    document.getElementById('search-empty').style.display = 'flex';
                    categoryTabs.style.display = 'none';
                    return;
                }
                allResults = allResults.concat(results);
                categoryTabs.style.display = 'flex';
                filterRender();
                searchLoadMore.style.display = data.has_more ? 'block' : 'none';
            })
            .catch(e => { searchStatus.innerHTML = `<span class="error">❌ ${e.message}</span>`; });
    }

    function rowEl(r) {
        const el = document.createElement('div');
        el.className = 'sr-row fade-in'; el.dataset.id = r.id || '';
        const kind = r.kind || 'track';
        const playable = kind === 'track' || kind === 'video' || kind === 'podcast';
        const srcTag = SRC_TAG[r.source] || '';
        const dur = r.duration ? fmtDur(r.duration) : '';
        const cover = r.cover ? `<img class="sr-art" src="${r.cover}" alt="" loading="lazy">` : `<div class="sr-art ph">${KIND_ICON[kind]||'🎵'}</div>`;

        el.innerHTML = `
            ${playable ? `<button class="sr-play" data-i='${JSON.stringify({id:r.id,source_url:r.source_url,preview_url:r.preview_url,title:r.title,artist:r.artist,cover:r.cover,kind,has_video:r.has_video})}'>▶</button>` : `<div style="width:32px"></div>`}
            ${cover}
            <div class="sr-body">
                <div class="sr-title">${esc(r.title)}</div>
                <div class="sr-sub">
                    <span class="tag ${srcTag}">${r.source||''}</span>
                    <span>${KIND_ICON[kind]||''} ${kind}</span>
                    ${r.artist?`<span>${esc(r.artist)}</span>`:''}
                    ${dur?`<span>${dur}</span>`:''}
                </div>
            </div>
            ${playable?`<button class="sr-dl" data-src="${esc(r.source_url||'')}" data-t="${esc(r.title)}" data-a="${esc(r.artist)}">⬇</button>`:''}
        `;

        if (playable) {
            el.querySelector('.sr-play').addEventListener('click', e => {
                e.stopPropagation();
                const d = JSON.parse(e.currentTarget.dataset.i);
                const idx = trackQueue.findIndex(t => t.id === d.id);
                currentIdx = idx >= 0 ? idx : -1;
                playTrack(d);
            });
            const dl = el.querySelector('.sr-dl');
            if (dl) dl.addEventListener('click', e => { e.stopPropagation(); downloadTrack(dl.dataset.src, dl.dataset.t, dl.dataset.a); });
        }
        // Click row to play
        if (playable) el.addEventListener('click', () => {
            const btn = el.querySelector('.sr-play');
            if (btn) { const d = JSON.parse(btn.dataset.i); const idx = trackQueue.findIndex(t => t.id === d.id); currentIdx = idx >= 0 ? idx : -1; playTrack(d); }
        });

        return el;
    }

    function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

    // Queue
    function renderQueue() {
        if (!trackQueue.length) { queueList.innerHTML = '<p class="empty-state">Queue is empty</p>'; return; }
        queueList.innerHTML = '';
        trackQueue.forEach((t, i) => {
            const el = document.createElement('div');
            el.className = 'q-item'; el.dataset.idx = String(i);
            el.innerHTML = `<span class="q-num">${i+1}</span><span class="q-title">${esc(t.title)}</span><span class="q-dur">${t.duration?fmtDur(t.duration):''}</span>`;
            el.addEventListener('click', () => { currentIdx = i; playTrack(t); });
            queueList.appendChild(el);
        });
        highlight();
    }

    // Play
    function playTrack(track) {
        stopAllMedia();
        currentTrack = track;
        npTitle.textContent = track.title || 'Unknown';
        npArtist.textContent = track.artist || '';

        // Art
        if (track.cover) { npCover.src = track.cover; npArtWrap.classList.add('has-art'); }
        else { npArtWrap.classList.remove('has-art'); }
        npArtWrap.classList.remove('has-video');

        // Video toggle
        const canVideo = track.has_video || track.kind === 'video' || track.kind === 'podcast';
        npVideoToggle.style.display = canVideo ? 'inline-block' : 'none';
        if (track.kind === 'video' && canVideo) videoMode = true;
        else if (track.kind === 'track') videoMode = false;
        updateVideoUI();

        npPlayPause.textContent = '⏳';
        npProgressFill.style.width = '0%';
        npCurrent.textContent = '0:00';
        npDuration.textContent = '0:00';
        highlight();

        fetch('/api/stream', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ source_url: track.source_url, want_video: videoMode && canVideo, title: track.title||'', artist: track.artist||'', source: track.source||'' }),
        })
        .then(r => r.json())
        .then(data => {
            if (data.success && data.embed_url) {
                videoMode = true;
                npEmbed.src = data.embed_url;
                npEmbed.style.display = 'block';
                npArtWrap.classList.add('has-video');
                npVideoToggle.style.display = 'inline-block';
                npVideoToggle.classList.add('active');
                isPlaying = true;
                npPlayPause.textContent = '⏸';
                npArtist.textContent = track.artist + ' (official YouTube player)';
            } else if (data.success && data.stream_url) {
                const m = activeMedia();
                m.src = data.stream_url;
                m.play().then(() => { isPlaying = true; npPlayPause.textContent = '⏸'; })
                    .catch(() => { npPlayPause.textContent = '▶'; });
                // Show note if fallback
                if (data.fallback) npArtist.textContent = track.artist + ' (via YouTube)';
                else if (data.preview_only) npArtist.textContent = track.artist + ' — 30s preview';
                else npArtist.textContent = track.artist || '';
            } else { npPlayPause.textContent = '✕'; npTitle.textContent = track.title; npArtist.textContent = data.error || 'Unavailable'; }
        })
        .catch(() => { npPlayPause.textContent = '✕'; });
    }

    function updateVideoUI() {
        if (videoMode) {
            npVideo.style.display = 'block';
            npArtWrap.classList.add('has-video');
            npVideo.volume = parseFloat(npVolume.value);
            npVideoToggle.classList.add('active');
        } else {
            npVideo.style.display = 'none';
            npEmbed.style.display = 'none';
            npEmbed.src = 'about:blank';
            npArtWrap.classList.remove('has-video');
            npVideoToggle.classList.remove('active');
        }
    }

    // Media events
    function bindMedia(el) {
        el.addEventListener('timeupdate', () => {
            if (el.duration && isFinite(el.duration)) {
                npProgressFill.style.width = (el.currentTime/el.duration*100)+'%';
                npCurrent.textContent = fmtDur(Math.floor(el.currentTime));
                npDuration.textContent = fmtDur(Math.floor(el.duration));
            }
        });
        el.addEventListener('ended', () => { if (repeatOn) { el.currentTime=0; el.play(); return; } playNext(); });
        el.addEventListener('pause', () => { isPlaying=false; npPlayPause.textContent='▶'; });
        el.addEventListener('play', () => { isPlaying=true; npPlayPause.textContent='⏸'; });
    }
    bindMedia(npAudio); bindMedia(npVideo);

    // Controls
    npPlayPause.addEventListener('click', () => { const m=activeMedia(); if(!m.src)return; isPlaying?m.pause():m.play(); });
    document.getElementById('np-progress-bar').addEventListener('click', e => {
        const m=activeMedia(); if(!m.duration||!isFinite(m.duration))return;
        const r=e.currentTarget.getBoundingClientRect();
        m.currentTime=((e.clientX-r.left)/r.width)*m.duration;
    });
    npPrev.addEventListener('click', () => {
        if (!trackQueue.length) return;
        const m=activeMedia(); if(m.currentTime>3){m.currentTime=0;return;}
        if(shuffleOn){playRandom();return;}
        currentIdx=currentIdx<=0?trackQueue.length-1:currentIdx-1;
        playTrack(trackQueue[currentIdx]);
    });
    npNext.addEventListener('click', playNext);
    function playNext() {
        if(!trackQueue.length)return; if(shuffleOn){playRandom();return;}
        currentIdx=(currentIdx+1)%trackQueue.length;
        playTrack(trackQueue[currentIdx]);
    }
    function playRandom() {
        if(trackQueue.length<=1){playNext();return;}
        let i; do{i=Math.floor(Math.random()*trackQueue.length)}while(i===currentIdx);
        currentIdx=i; playTrack(trackQueue[currentIdx]);
    }
    npShuffle.addEventListener('click', () => { shuffleOn=!shuffleOn; npShuffle.classList.toggle('active',shuffleOn); });
    npRepeat.addEventListener('click', () => { repeatOn=!repeatOn; npRepeat.classList.toggle('active',repeatOn); });

    // Video toggle
    npVideoToggle.addEventListener('click', () => {
        if(!currentTrack)return;
        const wasPlaying=isPlaying, wasTime=activeMedia().currentTime||0;
        videoMode=!videoMode;
        stopAllMedia();
        updateVideoUI();
        const canVideo=currentTrack.has_video||currentTrack.kind==='video'||currentTrack.kind==='podcast';
        fetch('/api/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_url:currentTrack.source_url,want_video:videoMode&&canVideo,title:currentTrack.title||'',artist:currentTrack.artist||'',source:currentTrack.source||''})})
        .then(r=>r.json()).then(data=>{
            if(data.success&&data.embed_url){
                videoMode = true;
                npEmbed.src = data.embed_url;
                npEmbed.style.display = 'block';
                npVideo.style.display = 'none';
                npArtWrap.classList.add('has-video');
                npVideoToggle.classList.add('active');
                isPlaying = true;
                npPlayPause.textContent = '⏸';
            } else if(data.success&&data.stream_url){
                const m=activeMedia();m.src=data.stream_url;m.currentTime=wasTime;if(wasPlaying)m.play();
            }
        }).catch(()=>{});
    });

    // Volume
    npVolume.addEventListener('input', () => { const v=parseFloat(npVolume.value); npAudio.volume=v; npVideo.volume=v; updateVolIcon(); });
    npVolIcon.addEventListener('click', () => {
        const m=activeMedia();
        if(m.volume>0){npAudio.dataset.pv=m.volume;npAudio.volume=0;npVideo.volume=0;npVolume.value=0;}
        else{const p=parseFloat(npAudio.dataset.pv||1);npAudio.volume=p;npVideo.volume=p;npVolume.value=p;}
        updateVolIcon();
    });
    function updateVolIcon() { const v=activeMedia().volume; npVolIcon.textContent=v===0?'🔇':v<0.5?'🔉':'🔊'; }

    // Download from player
    npDownload.addEventListener('click', () => { if(currentTrack)downloadTrack(currentTrack.source_url,currentTrack.title,currentTrack.artist); });

    function downloadTrack(src,title,artist) {
        if(!src)return;
        fetch('/api/download-track',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_url:src,title:title||'Unknown',artist:artist||''})})
        .then(r=>r.json()).then(d=>{if(d.job_id){pollJob(d.job_id);document.querySelector('.nav-tab[data-page="downloader"]').click();}}).catch(()=>{});
    }

    // =========================================================================
    // ANIME — search & stream (Yomi/MegaPlay, AniWatchTV, Film2Media, Miruro)
    // =========================================================================
    const animeInput = document.getElementById('anime-search-input');
    const animeProvider = document.getElementById('anime-provider');
    const animeResults = document.getElementById('anime-results');
    const animeStatus = document.getElementById('anime-status');
    const animeDetail = document.getElementById('anime-detail');
    const animeEpisodes = document.getElementById('anime-episodes');
    const animeDub = document.getElementById('anime-dub');
    const animeDubWrap = document.getElementById('anime-dub-wrap');
    const animePlayerCard = document.getElementById('anime-player-card');
    const animeVideo = document.getElementById('anime-video');
    const animeEmbed = document.getElementById('anime-embed');
    const animePlayerTitle = document.getElementById('anime-player-title');
    let currentAnime = null;

    animeInput.addEventListener('keydown', e => { if (e.key === 'Enter') animeSearch(animeInput.value); });
    animeProvider.addEventListener('change', () => { if (animeInput.value.trim()) animeSearch(animeInput.value); });
    document.getElementById('anime-player-close').addEventListener('click', () => {
        animePlayerCard.style.display = 'none';
        stopAnimePlayback();
    });

    function animeSearch(q) {
        if (!q.trim()) return;
        animeResults.innerHTML = '';
        animeDetail.style.display = 'none';
        animePlayerCard.style.display = 'none';
        stopAnimePlayback();
        document.getElementById('anime-results-loading').style.display = 'flex';
        document.getElementById('anime-results-empty').style.display = 'none';
        animeStatus.innerHTML = '';
        fetch(`/api/anime/search?q=${encodeURIComponent(q)}&provider=${encodeURIComponent(animeProvider.value)}`)
            .then(r => r.json())
            .then(data => {
                document.getElementById('anime-results-loading').style.display = 'none';
                if (data.error) { animeStatus.innerHTML = `<span class="error">❌ ${data.error}</span>`; return; }
                const rs = data.results || [];
                if (!rs.length) {
                    animeResults.innerHTML = '';
                    document.getElementById('anime-results-empty').style.display = 'flex';
                    return;
                }
                document.getElementById('anime-results-empty').style.display = 'none';
                rs.forEach(r => animeResults.appendChild(animeCard(r)));
            })
            .catch(e => {
                document.getElementById('anime-results-loading').style.display = 'none';
                animeStatus.innerHTML = `<span class="error">❌ ${e.message}</span>`;
            });
    }

    function animeCard(r) {
        const el = document.createElement('div');
        el.className = 'anime-card fade-in';
        const cover = r.cover
            ? `<div class="anime-card-cover-wrap">
                <img class="anime-card-cover" src="${r.cover}" loading="lazy" alt="">
                <div class="anime-card-cover-overlay"><div class="anime-card-play">▶</div></div>
               </div>`
            : `<div class="anime-card-cover anime-ph">🎬</div>`;
        const metaBits = [];
        if (r.year) metaBits.push(r.year);
        if (r.format) metaBits.push(r.format);
        if (r.score) metaBits.push(`⭐ ${(r.score / 10).toFixed(1)}`);
        const epCount = r.episodes ? `<span class="anime-card-eps">📺 ${r.episodes} ep</span>` : '';
        el.innerHTML = `
            ${cover}
            <div class="anime-card-body">
                <div class="anime-card-title">${esc(r.title)}</div>
                <div class="anime-card-meta">
                    <span class="anime-badge anime-badge-${esc(r.provider)}">${esc(PROVIDER_LABELS[r.provider] || r.provider)}</span>
                    ${metaBits.map(m => `<span>${m}</span>`).join('')}
                </div>
                ${epCount}
            </div>`;
        el.addEventListener('click', () => openAnime(r));
        return el;
    }

    function openAnime(r) {
        currentAnime = r;
        animePlayerCard.style.display = 'none';
        stopAnimePlayback();
        const coverImg = document.getElementById('anime-detail-cover');
        if (r.cover) { coverImg.src = r.cover; coverImg.style.display = 'block'; }
        else { coverImg.removeAttribute('src'); coverImg.style.display = 'none'; }
        document.getElementById('anime-detail-title').textContent = r.title || '';
        const meta = [];
        if (r.alt_title && r.alt_title !== r.title) meta.push(r.alt_title);
        if (r.year) meta.push(r.year);
        if (r.format) meta.push(r.format);
        if (r.episodes) meta.push(`${r.episodes} episodes`);
        if (r.score) meta.push(`⭐ ${(r.score / 10).toFixed(1)}`);
        if (r.genres && r.genres.length) meta.push(r.genres.slice(0, 4).join(', '));
        document.getElementById('anime-detail-meta').textContent = meta.join(' · ');
        document.getElementById('anime-detail-desc').textContent = r.description || '';
        animeDubWrap.style.display = (r.provider === 'yomi') ? 'flex' : 'none';
        animeDetail.style.display = 'block';
        animeEpisodes.innerHTML = '<div class="anime-loading"><div class="anime-loading-inner"><div class="anime-spinner"></div><span>Loading episodes...</span></div></div>';
        const params = new URLSearchParams({ provider: r.provider });
        if (r.provider === 'yomi' && r.anime_id) params.set('anime_id', r.anime_id);
        if (r.url) params.set('page_url', r.url);
        fetch(`/api/anime/episodes?${params}`)
            .then(x => x.json())
            .then(d => {
                if (!d.success) {
                    if (r.provider === 'f2mc') {
                        animeEpisodes.innerHTML = `<div class="anime-note">Film2Media is a download portal — open the post page for download links.
                            <a class="btn btn-primary" style="margin-top:10px;" href="${esc(r.url || '#')}" target="_blank" rel="noopener">↗ Open page</a></div>`;
                    } else {
                        animeEpisodes.innerHTML = `<div class="anime-empty-state"><div class="anime-empty-icon">⚠</div><div class="anime-empty-title">${esc(d.error || 'Failed to load episodes')}</div></div>`;
                    }
                    return;
                }
                const eps = d.episodes || [];
                if (!eps.length) {
                    animeEpisodes.innerHTML = `<div class="anime-empty-state"><div class="anime-empty-icon">📭</div><div class="anime-empty-title">No episodes listed</div></div>`;
                    return;
                }
                const total = eps.length;
                animeEpisodes.innerHTML = `<div class="anime-episodes-header"><span class="anime-episodes-count">${total} episode${total !== 1 ? 's' : ''}</span></div>`;
                const fragment = document.createDocumentFragment();
                eps.forEach(e => fragment.appendChild(epBtn(e)));
                animeEpisodes.appendChild(fragment);
            })
            .catch(() => animeEpisodes.innerHTML = '<span class="error">❌ Network error</span>');
        animeDetail.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function epBtn(e) {
        const b = document.createElement('button');
        b.className = 'anime-ep-btn';
        b.textContent = e.episode;
        b.title = e.title;
        b.addEventListener('click', () => playEpisode(e));
        return b;
    }

    function playEpisode(e) {
        const r = currentAnime;
        if (!r) return;
        animePlayerTitle.textContent = `${r.title} — ${e.title}`;
        animePlayerCard.style.display = 'block';
        stopAnimePlayback();
        fetch('/api/anime/stream', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider: r.provider, anime_id: r.anime_id, episode: e.episode, dub: animeDub.checked, page_url: r.url, episode_url: e.url || '' }),
        })
        .then(x => x.json())
        .then(d => {
            if (!d.success) {
                animePlayerTitle.textContent = `⚠ ${d.error || 'Unavailable'}`;
                return;
            }
            if (d.embed_only || !d.stream_url) {
                animeEmbed.src = d.player_url || d.page_url || 'about:blank';
                animeEmbed.style.display = 'block';
                animeVideo.style.display = 'none';
                return;
            }
            animeEmbed.style.display = 'none';
            animeEmbed.src = 'about:blank';
            animeVideo.style.display = 'block';
            playAnimeHls(d.stream_url, d.subtitles || []);
        })
        .catch(() => animePlayerTitle.textContent = '⚠ Network error');
        animePlayerCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    let animeHls = null;
    function stopAnimePlayback() {
        if (animeHls) { try { animeHls.destroy(); } catch (e) {} animeHls = null; }
        animeVideo.pause();
        animeVideo.removeAttribute('src');
        animeVideo.load();
        animeVideo.querySelectorAll('track').forEach(t => t.remove());
        animeEmbed.src = 'about:blank';
    }

    function playAnimeHls(url, subs) {
        stopAnimePlayback();
        animeVideo.style.display = 'block';
        // native <track> elements for the external VTT subtitle files
        (subs || []).forEach((s, i) => {
            const t = document.createElement('track');
            t.kind = 'subtitles';
            t.label = s.label || ('Subtitle ' + (i + 1));
            t.srclang = 'en';
            t.src = s.file;
            t.default = (i === 0);
            animeVideo.appendChild(t);
        });
        if (window.Hls && Hls.isSupported()) {
            animeHls = new Hls({ enableWorker: true });
            animeHls.loadSource(url);
            animeHls.attachMedia(animeVideo);
            animeHls.on(Hls.Events.MANIFEST_PARSED, () => {
                animeVideo.play().catch(() => {});
                enableAnimeSubs();
            });
        } else if (animeVideo.canPlayType('application/vnd.apple.mpegurl')) {
            animeVideo.src = url;
            animeVideo.addEventListener('loadedmetadata', () => {
                animeVideo.play().catch(() => {});
                enableAnimeSubs();
            }, { once: true });
        } else {
            animePlayerTitle.textContent = '⚠ Your browser cannot play HLS streams';
        }
    }

    // Force the subtitle tracks to show (hls.js attaches its own text track layer)
    function enableAnimeSubs() {
        setTimeout(() => {
            const tracks = animeVideo.textTracks;
            for (let i = 0; i < tracks.length; i++) {
                if (tracks[i].kind === 'subtitles') tracks[i].mode = 'showing';
            }
        }, 600);
    }
});
