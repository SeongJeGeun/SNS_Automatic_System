// static/dashboard.js

// 1. Toast Notification System
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.style.borderLeftColor = type === 'success' ? 'var(--color-teal)' : 'var(--status-danger)';
  toast.innerHTML = `<span style="display:flex;align-items:center;gap:0.5rem;"><i class="lucide-info"></i> ${message}</span>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'none'; // reset
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Global states
let globalIntegrations = [];
let networkInstance = null;

// 2. Fetch Status and Update UI
async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    updateStatusUI(data);
  } catch (err) {
    console.error('Failed to fetch status:', err);
  }
}

function updateStatusUI(data) {
  const runBtn = document.getElementById('btn-run-now');
  const statusIndicator = document.getElementById('header-status-indicator');
  const statusDot = statusIndicator.querySelector('.status-dot');
  const statusText = statusIndicator.querySelector('span');

  const summaryAgent = document.getElementById('summary-current-agent');
  const summaryProgress = document.getElementById('summary-progress-text');
  const progressBar = document.getElementById('pipeline-progress-bar');
  const summaryNextRun = document.getElementById('summary-next-run');

  // Update running states
  if (data.is_running) {
    runBtn.style.display = 'none';
    statusDot.classList.add('active');
    statusText.textContent = `실행중: ${data.current_agent}`;

    progressBar.style.width = `${data.progress}%`;
    summaryProgress.textContent = `${data.progress}%`;
    summaryAgent.textContent = data.current_agent;
  } else {
    runBtn.style.display = 'flex';
    statusDot.classList.remove('active');

    if (data.paused) {
       statusText.textContent = '상태: 일시 중지됨 (Paused)';
       summaryAgent.textContent = '일시중지';
    } else {
       statusText.textContent = `대기중: 다음 실행 예정 시각 ${data.next_run_at || '대기 중'}`;
       summaryAgent.textContent = '대기 중';
    }

    progressBar.style.width = `${data.progress}%`;
    summaryProgress.textContent = `${data.progress}%`;
  }

  if (summaryNextRun) {
    summaryNextRun.textContent = data.next_run_at || '대기 중';
  }

  // Update pipeline visual nodes (1-7 steps mapping)
  updatePipelineNodes(data.current_step, data.is_running);
}

// Pipeline Steps Definition for layout matching
const pipelineStepMapping = [
  { id: 'audience', agents: ['Audience Agent'] },
  { id: 'trend', agents: ['Trend Agent', 'RAG Agent'] },
  { id: 'strategy', agents: ['Strategy Agent'] },
  { id: 'story_quality', agents: ['Story Agent', 'Quality Agent', 'Story Agent Retry', 'Quality Agent Retry'] },
  { id: 'visual_drive', agents: ['Visual Agent', 'Hosting Agent'] },
  { id: 'publish', agents: ['Publishing Agent'] },
  { id: 'performance_learning', agents: ['Growth Agent', 'Recovery Agent', 'Report Agent', 'Cleanup Agent'] }
];

function updatePipelineNodes(activeStep, isRunning) {
  const nodes = document.querySelectorAll('.pipeline-node');

  let activeIndex = -1;
  pipelineStepMapping.forEach((step, idx) => {
    if (step.id === activeStep || step.agents.includes(document.getElementById('summary-current-agent').textContent)) {
      activeIndex = idx;
    }
  });

  if (activeIndex === -1) {
    if (activeStep === 'publish') activeIndex = 5;
    else if (activeStep === 'story_quality') activeIndex = 3;
    else if (activeStep === 'visual_drive') activeIndex = 4;
  }

  nodes.forEach((node, idx) => {
    node.classList.remove('completed', 'active', 'failed');

    if (idx < activeIndex) {
      node.classList.add('completed');
    } else if (idx === activeIndex) {
      if (isRunning) {
        node.classList.add('active');
      } else {
        node.classList.add('completed');
      }
    }
  });
}

// 3. Trigger Run Now Post
async function toggleExecution() {
  try {
    const res = await fetch('/api/run-now', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const result = await res.json();
    if (result.ok) {
      showToast(result.message, 'success');
      fetchStatus();
    } else {
      showToast(result.message, 'error');
    }
  } catch (err) {
    showToast('파이프라인 실행 요청 전송 실패', 'error');
  }
}

// 4. Fetch and update other API modules
async function fetchDriveLinks() {
  try {
    const res = await fetch('/api/drive/links');
    const data = await res.json();

    const linksGrid = document.querySelector('.links-grid');
    if (!linksGrid) return;

    linksGrid.innerHTML = `
      <div class="link-row">
        <div class="link-info">
          <span class="link-name">오늘 카드뉴스 결과 폴더</span>
          <div class="link-meta">
            <span class="pill info">Google Drive</span>
            <span>주소: ${data.daily_output_folder.substring(0, 45)}${data.daily_output_folder.length > 45 ? '...' : ''}</span>
          </div>
        </div>
        <a href="${data.daily_output_folder}" target="_blank" class="btn btn-outline btn-teal ${data.daily_output_folder === '미설정' ? 'disabled' : ''}" style="padding:0.4rem 0.8rem; font-size:0.75rem; text-decoration:none;" ${data.daily_output_folder === '미설정' ? 'onclick="event.preventDefault(); showToast(\'드라이브 주소가 설정되지 않았습니다.\', \'error\');"' : ''}>
          <i class="lucide-external-link"></i> 열기
        </a>
      </div>
      <div class="link-row">
        <div class="link-info">
          <span class="link-name">합성 이미지 결과 폴더</span>
          <div class="link-meta">
            <span class="pill info">Google Drive</span>
            <span>주소: ${data.image_folder.substring(0, 45)}${data.image_folder.length > 45 ? '...' : ''}</span>
          </div>
        </div>
        <a href="${data.image_folder}" target="_blank" class="btn btn-outline btn-teal ${data.image_folder === '미설정' ? 'disabled' : ''}" style="padding:0.4rem 0.8rem; font-size:0.75rem; text-decoration:none;" ${data.image_folder === '미설정' ? 'onclick="event.preventDefault(); showToast(\'이미지 폴더 주소가 설정되지 않았습니다.\', \'error\');"' : ''}>
          <i class="lucide-external-link"></i> 열기
        </a>
      </div>
      <div class="link-row">
        <div class="link-info">
          <span class="link-name">성과 리포트 Google Sheet</span>
          <div class="link-meta">
            <span class="pill success">Google Sheets</span>
            <span>주소: ${data.report_sheet.substring(0, 45)}${data.report_sheet.length > 45 ? '...' : ''}</span>
          </div>
        </div>
        <a href="${data.report_sheet}" target="_blank" class="btn btn-outline btn-teal ${data.report_sheet === '미설정' ? 'disabled' : ''}" style="padding:0.4rem 0.8rem; font-size:0.75rem; text-decoration:none;" ${data.report_sheet === '미설정' ? 'onclick="event.preventDefault(); showToast(\'성과 구글시트 주소가 설정되지 않았습니다.\', \'error\');"' : ''}>
          <i class="lucide-external-link"></i> 열기
        </a>
      </div>
      <div class="link-row">
        <div class="link-info">
          <span class="link-name">최종 Instagram 게시물 링크</span>
          <div class="link-meta">
            <span class="pill info" style="background-color:rgba(139,92,246,0.1); color:var(--color-purple-light);">Instagram Graph</span>
            <span>주소: ${data.latest_post_url}</span>
          </div>
        </div>
        <a href="${data.latest_post_url}" target="_blank" class="btn btn-outline ${data.latest_post_url === '미설정' ? 'disabled' : ''}" style="padding:0.4rem 0.8rem; font-size:0.75rem; text-decoration:none;" ${data.latest_post_url === '미설정' ? 'onclick="event.preventDefault(); showToast(\'최근 발행 포스트 링크가 존재하지 않습니다.\', \'error\');"' : ''}>
          <i class="lucide-external-link"></i> 열기
        </a>
      </div>
      <div class="link-row">
        <div class="link-info">
          <span class="link-name">최근 Threads 게시물 링크</span>
          <div class="link-meta">
            <span class="pill info" style="background-color:rgba(6,182,212,0.1); color:var(--color-teal-light);">Threads API</span>
            <span>상태: ${data.latest_threads_status} · ID: ${data.latest_threads_post_id}</span>
          </div>
        </div>
        <a href="${data.latest_threads_post_url}" target="_blank" class="btn btn-outline btn-teal ${data.latest_threads_post_url === '미설정' ? 'disabled' : ''}" style="padding:0.4rem 0.8rem; font-size:0.75rem; text-decoration:none;" ${data.latest_threads_post_url === '미설정' ? 'onclick="event.preventDefault(); showToast(\'최근 Threads 게시물 링크가 존재하지 않습니다.\', \'error\');"' : ''}>
          <i class="lucide-external-link"></i> 열기
        </a>
      </div>
    `;
  } catch (err) {
     console.error('Failed to load drive links:', err);
  }
}

async function fetchTrends() {
  try {
    const res = await fetch('/api/trends');
    const data = await res.json();

    const container = document.querySelector('.trends-container');
    if (!container) return;

    container.innerHTML = '';
    data.forEach(t => {
      const card = document.createElement('div');
      card.className = 'trend-card';

      const statusClass = t.status === '상승' ? 'up' : (t.status === '안정' ? 'stable' : 'candidate');
      const statusText = t.status === '상승' ? '상승세 (HOT)' : (t.status === '안정' ? '안정 (Stable)' : '후보 (Candidate)');

      card.innerHTML = `
        <div class="trend-header">
          <span class="trend-title">${t.keyword}</span>
          <span class="status-pill ${statusClass}">${statusText}</span>
        </div>
        <p class="trend-desc">${t.analysis}</p>
        <div class="trend-tags">
          <span>방향: ${t.recommended_content}</span>
        </div>
        <div class="trend-tags" style="margin-top:0.2rem; color:var(--text-muted);">
          <span>예상: ${t.expected_response} | 주의: ${t.risk}</span>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
     console.error('Failed to load trends:', err);
  }
}

async function fetchPerformance() {
  try {
    const res = await fetch('/api/performance');
    const data = await res.json();

    const tbody = document.querySelector('.performance-table tbody');
    if (!tbody) return;

    tbody.innerHTML = '';
    data.forEach(p => {
      const tr = document.createElement('tr');

      let pillClass = 'info';
      if (p.judgement === '성공') pillClass = 'success';
      else if (p.judgement === '치유 발동') pillClass = 'warning';

      tr.innerHTML = `
        <td style="font-weight:600; color:var(--text-primary);">${p.topic}</td>
        <td>${p.goal}</td>
        <td style="color:${p.judgement === '성공' ? 'var(--status-success)' : (p.judgement === '치유 발동' ? 'var(--status-danger)' : 'var(--text-secondary)')}">${p.current}</td>
        <td><span class="pill ${pillClass}">${p.judgement}</span></td>
        <td>${p.next_action}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed to load performance table:', err);
  }
}

async function fetchGoals() {
  try {
    const res = await fetch('/api/goals');
    const data = await res.json();

    const list = document.querySelector('.goals-list');
    if (!list) return;

    list.innerHTML = '';
    data.forEach(g => {
      const item = document.createElement('div');
      item.className = 'goal-item';

      const barColor = g.achievement_rate >= 100 ? 'var(--status-success)' : 'linear-gradient(to right, var(--color-purple), var(--color-teal))';
      const judgeColor = g.ai_judgement.includes('미달') ? 'var(--status-warning)' : 'var(--status-success)';

      item.innerHTML = `
        <div class="goal-info">
          <span class="goal-name"><i class="lucide-star" style="color:var(--color-teal); font-size:0.9rem;"></i> ${g.name}</span>
          <span class="goal-values">현재 ${g.current} / 목표 ${g.target} (${g.achievement_rate}%)</span>
        </div>
        <div class="goal-progress">
          <div class="goal-progress-bar" style="width: ${g.achievement_rate}%; background: ${barColor};"></div>
        </div>
        <div class="goal-meta">
          <span>AI 판단: <strong style="color:${judgeColor};">${g.achievement_rate >= 100 ? '목표 달성' : '미달 (보완 중)'}</strong></span>
          <span>다음 액션: ${g.next_action}</span>
        </div>
      `;
      list.appendChild(item);
    });
  } catch (err) {
     console.error('Failed to load goals:', err);
  }
}

async function fetchAIThoughts() {
  try {
    const res = await fetch('/api/ai-thoughts');
    const data = await res.json();

    const container = document.getElementById('chat-container');
    if (!container) return;

    container.innerHTML = '';
    data.forEach(chat => {
      const bubble = document.createElement('div');

      let avatarClass = 'strategy-agent';
      let avatarInitial = 'SA';
      if (chat.agent === 'Trend Agent') { avatarClass = 'trend-agent'; avatarInitial = 'TA'; }
      else if (chat.agent === 'Learning Agent') { avatarClass = 'learning-agent'; avatarInitial = 'LA'; }

      bubble.className = `chat-bubble ${avatarClass}`;
      bubble.innerHTML = `
        <div class="chat-avatar">${avatarInitial}</div>
        <div class="chat-content">
          <span class="chat-sender">${chat.agent}</span>
          <p class="chat-text">${chat.message}</p>
        </div>
      `;
      container.appendChild(bubble);
    });
    container.scrollTop = container.scrollHeight;
  } catch (err) {
    console.error('Failed to load AI thoughts:', err);
  }
}

async function fetchOperationMemory() {
  try {
    const res = await fetch('/api/operation-memory');
    const data = await res.json();

    const summary = data.summary || {};
    const title = document.getElementById('operation-current-title');
    const desc = document.getElementById('operation-current-desc');
    const threadsStatus = document.getElementById('operation-threads-status');
    const threadsLink = document.getElementById('operation-threads-link');
    const completedList = document.getElementById('operation-completed-list');
    const pendingList = document.getElementById('operation-pending-list');
    const reportSteps = document.getElementById('operation-report-steps');
    const crossRules = document.getElementById('operation-cross-rules');
    const obsidianNote = document.getElementById('operation-obsidian-note');
    const healingNote = document.getElementById('operation-healing-note');

    if (!title) return;

    title.textContent = summary.title || '운영 메모 반영 상태';
    desc.textContent = summary.current_position || '-';
    threadsStatus.textContent = summary.threads_connected ? 'Threads 연결 및 게시 검증 완료' : 'Threads 확인 필요';
    threadsStatus.className = `status-pill ${summary.threads_connected ? 'up' : 'candidate'}`;
    if (threadsLink) {
      threadsLink.href = summary.latest_threads_post || '#';
      threadsLink.classList.toggle('disabled', !summary.latest_threads_post || summary.latest_threads_post === '미기록');
    }

    if (completedList) {
      completedList.innerHTML = (data.completed || []).map(item => `
        <div class="operation-item done"><i class="lucide-check-circle2"></i><span>${item}</span></div>
      `).join('');
    }

    if (pendingList) {
      pendingList.innerHTML = (data.pending || []).map(item => `
        <div class="operation-item waiting"><i class="lucide-circle-dot"></i><span>${item}</span></div>
      `).join('');
    }

    if (reportSteps) {
      reportSteps.innerHTML = (data.report_steps || []).map(step => `
        <div class="report-step">
          <span class="report-step-title">${step.title} · ${step.when}</span>
          <span class="report-step-data">${step.data}</span>
          <span class="report-step-action">${step.action}</span>
        </div>
      `).join('');
    }

    if (crossRules) {
      crossRules.innerHTML = (data.cross_rules || []).map(rule => `
        <div class="operation-item"><i class="lucide-repeat-2"></i><span>${rule}</span></div>
      `).join('');
    }

    if (obsidianNote) {
      const syncItems = data.publish_sync || [];
      const syncedCount = syncItems.length;
      const syncText = syncedCount ? ` · 발행 노트 ${syncedCount}건 동기화됨` : '';
      obsidianNote.textContent = `Obsidian 저장: ${summary.obsidian_storage || '-'}${syncText}`;
    }
    if (healingNote) {
      healingNote.textContent = `자가치유 상태: ${summary.self_healing || '-'}`;
    }
  } catch (err) {
    console.error('Failed to load operation memory:', err);
  }
}

async function fetchIntegrations() {
  try {
    const res = await fetch('/api/integrations');
    const data = await res.json();
    globalIntegrations = data;

    const grid = document.querySelector('.integrations-grid');
    if (!grid) return;

    grid.innerHTML = '';
    data.forEach(item => {
      const card = document.createElement('div');
      card.className = 'integration-card';
      card.setAttribute('onclick', `openIntegrationModal('${item.key}')`);

      let icon = 'lucide-settings';
      if (item.key === 'instagram') icon = 'lucide-instagram';
      else if (item.key === 'threads') icon = 'lucide-message-circle';
      else if (item.key === 'telegram') icon = 'lucide-message-square';
      else if (item.key === 'gdrive') icon = 'lucide-folder';
      else if (item.key === 'gsheet') icon = 'lucide-sheet';
      else if (item.key === 'obsidian') icon = 'lucide-database';
      else if (item.key === 'codex') icon = 'lucide-cpu';

      const statusText = item.status === 'connected' ? '정상' : '확인필요';

      card.innerHTML = `
        <div class="integration-icon"><i class="${icon}"></i></div>
        <span class="integration-name">${item.name}</span>
        <span class="integration-status ${item.status}">${statusText}</span>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
     console.error('Failed to load integrations:', err);
  }
}

// 5. Detailed Pipeline Steps API call
async function selectPipelineNode(nodeId, element) {
  document.querySelectorAll('.pipeline-node').forEach(node => {
    node.classList.remove('active');
  });
  element.classList.add('active');

  try {
    const res = await fetch(`/api/pipeline/${nodeId}`);
    const data = await res.json();

    document.getElementById('panel-title').textContent = data.title;
    document.getElementById('panel-desc').textContent = data.description;
    document.getElementById('panel-input').textContent = data.input.join(', ');
    document.getElementById('panel-task').textContent = data.current_task;
    document.getElementById('panel-success').textContent = data.done_condition;
    document.getElementById('panel-recovery').textContent = data.recovery.join(', ');
    document.getElementById('panel-next').textContent = data.next_step;
    document.getElementById('panel-files').textContent = data.related_files.join(', ');
    document.getElementById('panel-api').textContent = data.api_status;
  } catch (err) {
    console.error('Failed to load step details:', err);
  }
}

// 6. External Integrations Modal Management
let currentSelectedIntegration = '';

function openIntegrationModal(key) {
  const data = globalIntegrations.find(item => item.key === key);
  if (!data) return;

  currentSelectedIntegration = key;

  document.getElementById('modal-name').textContent = data.name;
  document.getElementById('modal-account-val').textContent = data.account_name;
  document.getElementById('modal-id-val').textContent = data.account_id;
  document.getElementById('modal-token-input').value = data.masked_token;
  document.getElementById('modal-permission-val').textContent = data.permissions.join(', ');
  document.getElementById('modal-expiry-val').textContent = data.expires_in_days + '일 남음';
  document.getElementById('modal-check-val').textContent = data.last_checked;
  document.getElementById('modal-error-val').textContent = data.last_error;

  const testBtn = document.getElementById('btn-modal-test');
  const validateBtn = document.getElementById('btn-modal-insta-validate');
  const refreshBtn = document.getElementById('btn-modal-insta-refresh');
  const warningDiv = document.getElementById('modal-insta-warning');

  if (key === 'instagram') {
    if (testBtn) testBtn.style.display = 'none';
    if (validateBtn) validateBtn.style.display = 'inline-block';
    if (refreshBtn) refreshBtn.style.display = 'inline-block';
    if (warningDiv) {
      if (data.status === 'error') {
        warningDiv.style.display = 'block';
      } else {
        warningDiv.style.display = 'none';
      }
    }
  } else {
    if (testBtn) testBtn.style.display = 'inline-block';
    if (validateBtn) validateBtn.style.display = 'none';
    if (refreshBtn) refreshBtn.style.display = 'none';
    if (warningDiv) warningDiv.style.display = 'none';
  }

  document.getElementById('integration-modal').classList.add('open');
}

function closeIntegrationModal() {
  document.getElementById('integration-modal').classList.remove('open');
}

async function testIntegrationConnection() {
  showToast(`${document.getElementById('modal-name').textContent} 연결 테스트 요청 중...`);
  try {
     const res = await fetch('/api/integrations/test', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({ target: currentSelectedIntegration })
     });
     const data = await res.json();
     if (data.ok) {
       showToast(data.message, 'success');
     } else {
       showToast(data.message, 'error');
     }
  } catch (err) {
     showToast('연결 테스트 요청 실패', 'error');
  }
}

async function saveIntegrationToken() {
  const tokenVal = document.getElementById('modal-token-input').value;
  if (!tokenVal) return;

  showToast('신규 토큰 저장 요청 중...');
  try {
     const res = await fetch('/api/integrations/save', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
       body: JSON.stringify({ target: currentSelectedIntegration, token: tokenVal })
     });
     const data = await res.json();
     if (data.ok) {
       showToast(data.message, 'success');
       closeIntegrationModal();
       fetchIntegrations();
     } else {
       showToast(data.message, 'error');
     }
  } catch (err) {
     showToast('토큰 저장 처리 실패', 'error');
  }
}

async function validateInstagramToken() {
  showToast('Instagram 토큰 검증 요청 중...');
  try {
     const res = await fetch('/api/integrations/validate-instagram', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' }
     });
     const data = await res.json();
     if (data.ok) {
       showToast(`토큰 검증 완료: ${data.message}`, 'success');
     } else {
       showToast(`토큰 검증 실패: ${data.message}`, 'error');
     }
     closeIntegrationModal();
     fetchIntegrations();
  } catch (err) {
     showToast('토큰 검증 요청 실패', 'error');
  }
}

async function refreshInstagramToken() {
  showToast('Instagram 토큰 리프레시 요청 중...');
  try {
     const res = await fetch('/api/integrations/refresh-instagram', {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' }
     });
     const data = await res.json();
     if (data.ok) {
       showToast(`토큰 리프레시 완료: ${data.message}`, 'success');
     } else {
       showToast(`토큰 리프레시 실패: ${data.message}`, 'error');
     }
     closeIntegrationModal();
     fetchIntegrations();
  } catch (err) {
     showToast('토큰 리프레시 요청 실패', 'error');
  }
}

// 7. Natural Language command entry
async function sendNLCommand() {
  const input = document.getElementById('nl-command-input');
  const text = input.value.trim();
  if (!text) return;

  showToast(`명령어 송신 중...`);
  input.value = '';

  const chatContainer = document.getElementById('chat-container');
  const userBubble = document.createElement('div');
  userBubble.className = 'chat-bubble';
  userBubble.style.alignSelf = 'flex-end';
  userBubble.style.flexDirection = 'row-reverse';
  userBubble.innerHTML = `
    <div class="chat-avatar" style="border-color:var(--color-purple);color:white;background:var(--color-purple)">FW</div>
    <div class="chat-content" style="border-top-left-radius:12px;border-top-right-radius:0;background:rgba(139,92,246,0.1)">
      <div class="chat-sender" style="text-align:right">포워드 (Operator)</div>
      <div class="chat-text">${text}</div>
    </div>
  `;
  chatContainer.appendChild(userBubble);
  chatContainer.scrollTop = chatContainer.scrollHeight;

  try {
    const res = await fetch('/api/natural-language', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: text })
    });
    const data = await res.json();

    if (data.ok) {
      const responseBubble = document.createElement('div');
      responseBubble.className = 'chat-bubble strategy-agent';
      responseBubble.innerHTML = `
        <div class="chat-avatar" style="border-color:var(--color-purple);color:var(--color-purple-light)">SA</div>
        <div class="chat-content">
          <div class="chat-sender">Strategy Agent</div>
          <div class="chat-text">${data.reply} <br><span style="font-size:0.7rem; color:var(--text-muted);">(작업 ID: ${data.command_id})</span></div>
        </div>
      `;
      chatContainer.appendChild(responseBubble);
      chatContainer.scrollTop = chatContainer.scrollHeight;
      showToast('Codex 작업 등록 완료', 'success');
    } else {
      showToast('AI 명령 접수 오류', 'error');
    }
  } catch (err) {
    showToast('명령 전달 에러 발생', 'error');
  }
}

// 8. Vis.js Obsidian network graph setup
async function initObsidianGraph() {
  const container = document.getElementById('obsidian-network');
  if (!container) return;

  try {
    const res = await fetch('/api/brain/graph');
    const data = await res.json();

    // Update Connection Pill state in UI
    const statusPill = document.getElementById('obsidian-status-pill');
    if (statusPill) {
       statusPill.textContent = `Obsidian Vault: ${data.status}`;
       if (data.status === '연결됨') {
          statusPill.style.backgroundColor = 'rgba(16, 185, 129, 0.1)';
          statusPill.style.color = 'var(--status-success)';
       } else {
          statusPill.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
          statusPill.style.color = 'var(--status-danger)';
       }
    }

    // Bind dynamic nodes and edges
    const visNodes = new vis.DataSet(data.nodes);
    const visEdges = new vis.DataSet(data.edges);
    const visData = { nodes: visNodes, edges: visEdges };

    const options = {
      nodes: {
        shape: 'dot',
        font: {
          color: '#f8fafc',
          size: 11,
          face: 'Outfit'
        },
        borderWidth: 2,
        shadow: true
      },
      edges: {
        color: {
          color: 'rgba(255, 255, 255, 0.15)',
          highlight: 'var(--color-purple)'
        },
        width: 1,
        smooth: {
          type: 'continuous'
        }
      },
      groups: {
        core: {
          color: { background: 'var(--color-purple)', border: 'var(--color-purple-light)' },
        },
        pain: {
          color: { background: '#ef4444', border: '#fca5a5' }
        },
        rule: {
          color: { background: 'var(--color-teal)', border: 'var(--color-teal-light)' }
        },
        insight: {
          color: { background: '#3b82f6', border: '#93c5fd' }
        },
        experiment: {
          color: { background: '#f59e0b', border: '#fde047' }
        },
        tag: {
          color: { background: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.2)' },
          font: { color: 'var(--text-secondary)' }
        }
      },
      physics: {
        barnesHut: {
          gravitationalConstant: -1800,
          centralGravity: 0.3,
          springLength: 90
        }
      },
      interaction: {
        hover: true,
        zoomView: true,
        dragView: true
      }
    };

    if (networkInstance) {
      networkInstance.destroy();
    }
    networkInstance = new vis.Network(container, visData, options);

    networkInstance.on("click", function(params) {
      if (params.nodes.length > 0) {
        const clickedNodeId = params.nodes[0];
        const clickedNode = visNodes.get(clickedNodeId);
        showToast(`Obsidian 지식 노드 선택: "${clickedNode.label}"`);
      }
    });

    // Populate tags dynamically
    const tagsContainer = document.querySelector('.obsidian-tags');
    if (tagsContainer && data.tags) {
       tagsContainer.innerHTML = '';
       data.tags.forEach(tag => {
          const span = document.createElement('span');
          span.className = 'obsidian-tag';
          span.textContent = tag;
          span.onclick = () => {
             showToast(`태그 필터: "${tag}"`);
          };
          tagsContainer.appendChild(span);
       });
    }

  } catch (err) {
    console.error('Failed to init dynamic Obsidian graph:', err);
  }
}

// 9. Initialize EventSource SSE Stream & Load API Modules
function initSSE() {
  const eventSource = new EventSource('/events');

  eventSource.onmessage = function(event) {
    const data = jsonParse(event.data);
    if (!data) return;

    if (data.type === 'status_update') {
      updateStatusUI(data);
      fetchDriveLinks();
      fetchPerformance();
      fetchAIThoughts();
      fetchIntegrations();
      fetchTrends();
      fetchOperationMemory();
    } else if (data.type === 'brain_graph_update') {
      console.log("Obsidian vault change detected. Re-drawing brain graph...");
      initObsidianGraph();
      fetchTrends();
      fetchAIThoughts();
      fetchOperationMemory();
    }
  };

  eventSource.onerror = function() {
    console.warn('SSE EventSource lost connection. Reconnecting...');
  };
}

function jsonParse(str) {
  try {
    return JSON.parse(str);
  } catch (e) {
    return null;
  }
}

// Window load init
window.addEventListener('load', () => {
  fetchStatus();
  fetchDriveLinks();
  fetchTrends();
  fetchPerformance();
  fetchGoals();
  fetchAIThoughts();
  fetchIntegrations();
  fetchOperationMemory();

  initObsidianGraph();
  initSSE();

  const firstNode = document.querySelector('.pipeline-node');
  if (firstNode) {
     selectPipelineNode('audience', firstNode);
  }

  const nlInput = document.getElementById('nl-command-input');
  if (nlInput) {
    nlInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        sendNLCommand();
      }
    });
  }
});
