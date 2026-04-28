(() => {
  let selectedSceneId = null;
  let uploadedFile = null;
  let ws = null;

  const sceneGrid      = document.getElementById('scene-grid');
  const uploadArea     = document.getElementById('upload-area');
  const fileInput      = document.getElementById('file-input');
  const placeholder    = document.getElementById('upload-placeholder');
  const previewImg     = document.getElementById('preview-img');
  const btnReupload    = document.getElementById('btn-reupload');
  const btnGenerate    = document.getElementById('btn-generate');
  const progressWrap   = document.getElementById('progress-wrap');
  const progressFill   = document.getElementById('progress-fill');
  const progressLabel  = document.getElementById('progress-label');
  const sectionResult  = document.getElementById('section-result');
  const resultImg      = document.getElementById('result-img');
  const btnDownload    = document.getElementById('btn-download');
  const btnRetry       = document.getElementById('btn-retry');
  const btnChangeScene = document.getElementById('btn-change-scene');
  const toast          = document.getElementById('toast');

  const SCENE_ICONS = { 1: '🏰', 2: '🚀', 3: '🌆' };

  // ── Load scenes ──
  async function loadScenes() {
    try {
      const { scenes } = await fetch('/api/scenes').then(r => r.json());
      renderScenes(scenes);
    } catch {
      showToast('无法加载场景列表，请刷新页面');
    }
  }

  function renderScenes(scenes) {
    sceneGrid.innerHTML = '';
    scenes.forEach(scene => {
      const card = document.createElement('div');
      card.className = 'scene-card';
      card.dataset.id = scene.id;
      card.innerHTML = `
        <img class="scene-thumb" src="${scene.thumbnail}" alt="${scene.name}"
          onerror="this.outerHTML='<div class=\\'scene-thumb-placeholder\\'><span class=\\'scene-icon\\'>${SCENE_ICONS[scene.id] || '🎬'}</span><span>${scene.name}</span></div>'" />
        <div class="scene-info">
          <div class="scene-name">${scene.name}</div>
          <div class="scene-desc">${scene.description}</div>
        </div>`;
      card.addEventListener('click', () => selectScene(scene.id, card));
      sceneGrid.appendChild(card);
    });
  }

  function selectScene(id, cardEl) {
    selectedSceneId = id;
    document.querySelectorAll('.scene-card').forEach(c => c.classList.remove('selected'));
    cardEl.classList.add('selected');
    updateGenerateBtn();
  }

  // ── Upload ──
  uploadArea.addEventListener('click', (e) => { if (e.target !== btnReupload) fileInput.click(); });
  uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); uploadArea.classList.add('drag-over'); });
  uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('drag-over'));
  uploadArea.addEventListener('drop', (e) => {
    e.preventDefault(); uploadArea.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', () => { if (fileInput.files[0]) handleFile(fileInput.files[0]); });
  btnReupload.addEventListener('click', (e) => { e.stopPropagation(); resetUpload(); });

  function handleFile(file) {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      showToast('仅支持 JPG / PNG / WebP 格式'); return;
    }
    if (file.size > 10 * 1024 * 1024) { showToast('图片大小不能超过 10MB'); return; }
    uploadedFile = file;
    const reader = new FileReader();
    reader.onload = e => {
      previewImg.src = e.target.result;
      previewImg.classList.remove('hidden');
      placeholder.classList.add('hidden');
      btnReupload.style.display = 'block';
    };
    reader.readAsDataURL(file);
    updateGenerateBtn();
  }

  function resetUpload() {
    uploadedFile = null; fileInput.value = '';
    previewImg.classList.add('hidden'); previewImg.src = '';
    placeholder.classList.remove('hidden'); btnReupload.style.display = 'none';
    updateGenerateBtn();
  }

  function updateGenerateBtn() {
    btnGenerate.disabled = !(selectedSceneId && uploadedFile);
  }

  // ── Generate ──
  btnGenerate.addEventListener('click', startGenerate);
  btnRetry.addEventListener('click', startGenerate);
  btnChangeScene.addEventListener('click', () => {
    sectionResult.classList.add('hidden');
    progressWrap.classList.add('hidden');
    progressFill.style.width = '0%';
    updateGenerateBtn();
  });

  async function startGenerate() {
    if (!selectedSceneId || !uploadedFile) return;
    sectionResult.classList.add('hidden');
    btnGenerate.disabled = true;
    progressWrap.classList.remove('hidden');
    setProgress(0, '准备中…');

    const formData = new FormData();
    formData.append('scene_id', selectedSceneId);
    formData.append('photo', uploadedFile);

    let taskId;
    try {
      const res = await fetch('/api/generate', { method: 'POST', body: formData });
      if (!res.ok) throw new Error((await res.json()).detail || '请求失败');
      taskId = (await res.json()).task_id;
    } catch (e) {
      showToast(e.message); resetGenerateUI(); return;
    }
    openWebSocket(taskId);
  }

  function openWebSocket(taskId) {
    if (ws) { ws.close(); ws = null; }
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws/progress/${taskId}`);
    ws.onmessage = e => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'progress') {
        setProgress(msg.percent, msg.step);
      } else if (msg.type === 'done') {
        setProgress(100, '完成！');
        setTimeout(() => showResult(msg.task_id), 400);
      } else if (msg.type === 'error') {
        showToast(msg.message || '生成失败，请重试'); resetGenerateUI();
      }
    };
    ws.onerror = () => { showToast('连接错误，请刷新页面'); resetGenerateUI(); };
    ws.onclose = () => { ws = null; };
  }

  function setProgress(pct, label) {
    progressFill.style.width = pct + '%';
    progressLabel.textContent = label;
  }

  function showResult(taskId) {
    const imgUrl = `/api/result/${taskId}?t=${Date.now()}`;
    resultImg.src = imgUrl;
    btnDownload.href = imgUrl;
    btnDownload.download = `souvenir_scene${selectedSceneId}.jpg`;
    sectionResult.classList.remove('hidden');
    sectionResult.scrollIntoView({ behavior: 'smooth', block: 'start' });
    resetGenerateUI();
  }

  function resetGenerateUI() {
    btnGenerate.disabled = !(selectedSceneId && uploadedFile);
  }

  // ── Toast ──
  let toastTimer = null;
  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.remove('hidden');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.add('hidden'), 4000);
  }

  loadScenes();
})();
