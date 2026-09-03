// YT Automation Studio - Mobile Client Logic
document.addEventListener('DOMContentLoaded', () => {
  // 1. PWA Service Worker Registration
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js')
      .then((reg) => console.log('[PWA] Service Worker registered:', reg.scope))
      .catch((err) => console.log('[PWA] Service Worker registration failed:', err));
  }

  // App State
  let channelsData = [];
  let summaryData = {};
  let nextSlotUtcTime = null;

  // DOM Elements
  const channelsContainer = document.getElementById('channelsContainer');
  const feedList = document.getElementById('feedList');
  const valTotalChannels = document.getElementById('valTotalChannels');
  const valTotalShorts = document.getElementById('valTotalShorts');
  const valUploadedToday = document.getElementById('valUploadedToday');
  const clockNextSlot = document.getElementById('clockNextSlot');
  const lblNextSlotName = document.getElementById('lblNextSlotName');
  const lblNextSlotLocal = document.getElementById('lblNextSlotLocal');
  const inputSearch = document.getElementById('inputSearch');
  const btnRefresh = document.getElementById('btnRefresh');

  // Modal Elements
  const addChannelModal = document.getElementById('addChannelModal');
  const btnOpenAddModal = document.getElementById('btnOpenAddModal');
  const btnCloseAddModal = document.getElementById('btnCloseAddModal');
  const btnGenerateConfig = document.getElementById('btnGenerateConfig');
  const wizardOutputBox = document.getElementById('wizardOutputBox');

  // Bottom Tabs
  const tabDashboard = document.getElementById('tabDashboard');
  const tabAddChannel = document.getElementById('tabAddChannel');
  const tabSync = document.getElementById('tabSync');

  // Toast Function
  function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="${type === 'success' ? '#10b981' : '#06b6d4'}" stroke-width="2">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
        <polyline points="22 4 12 14.01 9 11.01"></polyline>
      </svg>
      <span>${message}</span>
    `;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }

  // Copy to clipboard helper
  window.copyToClipboard = function(text, label = 'Copied') {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        showToast(`📋 ${label}: ${text}`, 'success');
      });
    } else {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      showToast(`📋 ${label}: ${text}`, 'success');
    }
  };

  // Fetch Channels & Sync Data
  async function loadData() {
    try {
      const [resSummary, resChannels] = await Promise.all([
        fetch('/api/summary').then(r => r.ok ? r.json() : null).catch(() => null),
        fetch('/api/channels').then(r => r.ok ? r.json() : null).catch(() => null)
      ]);

      if (resChannels && resChannels.channels) {
        channelsData = resChannels.channels;
      } else {
        // Fallback default structure if served statically without Python server
        channelsData = [{
          id: 'channel_1',
          tiktok_username: 'blindonthemove',
          youtube_channel_name: 'Mike Mulligan',
          youtube_handle: '@AasAsad-l5s',
          owner_email: 'thechannel@gmail.com',
          enabled: true,
          videos_per_day: 2,
          upload_mode: 'popular_split',
          slot_publish_times_utc: { 1: "22:00", 2: "00:00" },
          today_status: { slot_1: 'success', slot_2: 'pending', uploaded_today: 1 },
          data: {
            stats: { total_uploaded: 1, total_runs: 1 },
            posted_videos: [{
              tiktok_id: "7680681988440837407",
              title: "A white cane 🦯 is an important tool to help someone who is blind or v... #shorts",
              youtube_id: "mEF2dR2GjrI",
              duration: 61.3,
              view_count: 1839,
              upload_date: "20260901",
              status: "uploaded",
              slot: 1
            }],
            runs: [{ slot: 1, status: "success", video_id: "mEF2dR2GjrI", date: "2026-09-02" }]
          }
        }];
      }

      renderGlobalMetrics();
      renderChannels(channelsData);
      renderRecentFeed(channelsData);
      updateScheduleCountdown();
    } catch (err) {
      console.error('Error loading portal data:', err);
    }
  }

  // Render Global Metrics
  function renderGlobalMetrics() {
    valTotalChannels.textContent = channelsData.length;
    let totalUploaded = 0;
    let uploadedToday = 0;

    channelsData.forEach(ch => {
      if (ch.data && ch.data.stats) {
        totalUploaded += ch.data.stats.total_uploaded || 0;
      }
      if (ch.today_status) {
        uploadedToday += ch.today_status.uploaded_today || 0;
      }
    });

    valTotalShorts.textContent = totalUploaded;
    valUploadedToday.textContent = `+${uploadedToday} today`;
  }

  // Render Channel Cards
  function renderChannels(channels) {
    channelsContainer.innerHTML = '';

    if (!channels || channels.length === 0) {
      channelsContainer.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">
          No matching channels found.
        </div>
      `;
      return;
    }

    channels.forEach(ch => {
      const card = document.createElement('div');
      card.className = 'channel-card';

      const initial = (ch.youtube_channel_name || ch.id).charAt(0).toUpperCase();
      const tiktokUser = ch.tiktok_username || 'creator';
      const ytName = ch.youtube_channel_name || 'YouTube Channel';
      const isSlot1Done = ch.today_status && ch.today_status.slot_1 === 'success';
      const isSlot2Done = ch.today_status && ch.today_status.slot_2 === 'success';
      const totalPosted = ch.data && ch.data.stats ? ch.data.stats.total_uploaded : 0;
      const ownerEmail = ch.owner_email || 'Owner Account';

      card.innerHTML = `
        <div class="channel-card-header">
          <div class="channel-info">
            <div class="channel-avatar">${initial}</div>
            <div class="channel-meta">
              <h3>${ytName}</h3>
              <a href="https://www.youtube.com/@AasAsad-l5s" target="_blank" class="channel-handle">@AasAsad-l5s</a>
              <span class="tiktok-badge">Source: @${tiktokUser}</span>
            </div>
          </div>
          <span class="status-badge status-active">
            <span class="pulse-dot"></span> Active
          </span>
        </div>

        <div class="channel-metrics">
          <div class="metric-item">
            <div class="m-val">${totalPosted}</div>
            <div class="m-lbl">Uploaded</div>
          </div>
          <div class="metric-item">
            <div class="m-val">2/day</div>
            <div class="m-lbl">Frequency</div>
          </div>
          <div class="metric-item">
            <div class="m-val">1080p HD</div>
            <div class="m-lbl">Format</div>
          </div>
        </div>

        <div class="slots-progress-box">
          <div class="slots-header">
            <span>Today's Upload Slots (UTC)</span>
            <span>${(isSlot1Done ? 1 : 0) + (isSlot2Done ? 1 : 0)} / 2 Done</span>
          </div>
          <div class="slot-badges">
            <div class="slot-pill ${isSlot1Done ? 'completed' : 'waiting'}">
              <span>Slot 1 (22:00)</span>
              <span>${isSlot1Done ? '✓ Uploaded' : '⏳ Pending'}</span>
            </div>
            <div class="slot-pill ${isSlot2Done ? 'completed' : 'waiting'}">
              <span>Slot 2 (00:00)</span>
              <span>${isSlot2Done ? '✓ Uploaded' : '⏳ Pending'}</span>
            </div>
          </div>
        </div>

        <div class="channel-actions">
          <a href="https://www.youtube.com/@AasAsad-l5s" target="_blank" class="btn-action btn-yt">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z"/></svg>
            YouTube
          </a>
          <a href="https://www.tiktok.com/@${tiktokUser}" target="_blank" class="btn-action btn-tt">
            TikTok Source
          </a>
          <button class="btn-action btn-copy-email" onclick="copyToClipboard('${ownerEmail}', 'Owner Gmail')">
            Copy Email
          </button>
        </div>
      `;
      channelsContainer.appendChild(card);
    });
  }

  // Render Recent Activity Feed
  function renderRecentFeed(channels) {
    feedList.innerHTML = '';
    const allVideos = [];

    channels.forEach(ch => {
      if (ch.data && ch.data.posted_videos) {
        ch.data.posted_videos.forEach(v => {
          allVideos.push({ ...v, channel_name: ch.youtube_channel_name || ch.id });
        });
      }
    });

    if (allVideos.length === 0) {
      feedList.innerHTML = `
        <div style="text-align: center; color: var(--text-muted); padding: 16px;">
          No upload logs recorded yet.
        </div>
      `;
      return;
    }

    allVideos.slice(0, 10).forEach(v => {
      const item = document.createElement('div');
      item.className = 'feed-item';
      const ytLink = v.youtube_id ? `https://www.youtube.com/watch?v=${v.youtube_id}` : '#';

      item.innerHTML = `
        <div class="feed-left">
          <span class="feed-slot-badge">Slot ${v.slot || 1}</span>
          <div>
            <div class="feed-title" title="${v.title}">${v.title || 'YouTube Short Upload'}</div>
            <div class="feed-time">${v.posted_at ? new Date(v.posted_at).toLocaleString() : 'Recently posted'} • ${Math.round(v.duration || 60)}s</div>
          </div>
        </div>
        <div>
          ${v.youtube_id ? `
            <a href="${ytLink}" target="_blank" class="btn btn-glass btn-sm" style="text-decoration: none;">
              Watch ↗
            </a>
          ` : '<span style="font-size:0.75rem; color:var(--text-muted);">Processed</span>'}
        </div>
      `;
      feedList.appendChild(item);
    });
  }

  // Next Slot Schedule Countdown (US schedule 22:00 & 00:00 UTC)
  function updateScheduleCountdown() {
    const now = new Date();
    const nowUtc = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), now.getUTCHours(), now.getUTCMinutes(), now.getUTCSeconds());

    // Slot 1: 22:00 UTC, Slot 2: 00:00 UTC (next day)
    const slot1Today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), 22, 0, 0);
    const slot2Today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 0, 0, 0);

    let targetTime = null;
    let slotName = 'Slot 1';
    let slotTimeUtc = '22:00 UTC';

    if (nowUtc < slot1Today) {
      targetTime = slot1Today;
      slotName = 'Slot 1';
      slotTimeUtc = '22:00 UTC';
    } else if (nowUtc < slot2Today) {
      targetTime = slot2Today;
      slotName = 'Slot 2';
      slotTimeUtc = '00:00 UTC';
    } else {
      // Slot 1 tomorrow
      targetTime = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 22, 0, 0);
      slotName = 'Slot 1';
      slotTimeUtc = '22:00 UTC';
    }

    lblNextSlotName.textContent = slotName;

    // Convert target UTC to local time string
    const targetLocalDate = new Date(targetTime);
    lblNextSlotLocal.textContent = `Scheduled at ${slotTimeUtc} (${targetLocalDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} Local)`;

    const diffMs = targetTime - nowUtc;
    if (diffMs <= 0) {
      clockNextSlot.textContent = '00:00:00';
      return;
    }

    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diffMs % (1000 * 60)) / 1000);

    const pad = (n) => String(n).padStart(2, '0');
    clockNextSlot.textContent = `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
  }

  // Ticking countdown loop
  setInterval(updateScheduleCountdown, 1000);

  // Search Filter Handler
  inputSearch.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    if (!q) {
      renderChannels(channelsData);
      return;
    }
    const filtered = channelsData.filter(ch => {
      const name = (ch.youtube_channel_name || '').toLowerCase();
      const tt = (ch.tiktok_username || '').toLowerCase();
      const id = (ch.id || '').toLowerCase();
      return name.includes(q) || tt.includes(q) || id.includes(q);
    });
    renderChannels(filtered);
  });

  // Modal Event Handlers
  function openModal() {
    addChannelModal.classList.add('open');
  }

  function closeModal() {
    addChannelModal.classList.remove('open');
  }

  btnOpenAddModal.addEventListener('click', openModal);
  btnCloseAddModal.addEventListener('click', closeModal);
  addChannelModal.addEventListener('click', (e) => {
    if (e.target === addChannelModal) closeModal();
  });

  // Bottom Nav Actions
  tabAddChannel.addEventListener('click', openModal);
  tabSync.addEventListener('click', () => {
    loadData();
    showToast('🔄 Synchronized with local pipelines', 'success');
  });
  btnRefresh.addEventListener('click', () => {
    loadData();
    showToast('🔄 Synchronized with local pipelines', 'success');
  });

  // Interactive "Add New Channel" Config Generator
  btnGenerateConfig.addEventListener('click', () => {
    const chId = document.getElementById('newChannelId').value.trim() || 'channel_2';
    const tiktokUser = document.getElementById('newTiktokUser').value.replace('@', '').trim();
    const ytName = document.getElementById('newYoutubeName').value.trim();
    const ownerEmail = document.getElementById('newOwnerEmail').value.trim();
    const tzGroup = document.getElementById('newTimezoneGroup').value;
    const mode = document.getElementById('newUploadMode').value;

    if (!tiktokUser || !ytName || !ownerEmail) {
      showToast('⚠️ Please fill in TikTok handle, YouTube name, and Owner email.', 'error');
      return;
    }

    let slot1 = "22:00";
    let slot2 = "00:00";
    if (tzGroup === "EU") { slot1 = "17:00"; slot2 = "19:00"; }
    if (tzGroup === "JP") { slot1 = "09:00"; slot2 = "11:00"; }

    const yamlSnippet = `  - id: ${chId}
    tiktok_username: "${tiktokUser}"
    youtube_channel_name: "${ytName}"
    owner_email: "${ownerEmail}"
    google_credentials_file: "credentials/${chId}_client_secret.json"
    oauth_token_file: "tokens/${chId}_token.json"
    videos_per_day: 2
    description_footer: "#${tiktokUser} #shorts #viral"
    default_tags: ["${tiktokUser}", "shorts", "viral"]
    youtube_category_id: "22"
    enabled: true
    max_retry_days: 7
    shorts_max_seconds: 180
    upload_mode: ${mode}
    max_download_candidates: 20
    slot_publish_times_utc:
      1: "${slot1}"
      2: "${slot2}"`;

    const tokenCommand = `python reauth_nobrowser.py ${chId}`;
    const secretsHelp = `# Add these in GitHub Repo -> Settings -> Secrets -> Actions:
${chId.toUpperCase()}_CLIENT_SECRET: [Base64 of credentials/${chId}_client_secret.json]
${chId.toUpperCase()}_TOKEN: [Base64 of tokens/${chId}_token.json]`;

    document.getElementById('codeChannelsYaml').textContent = yamlSnippet;
    document.getElementById('codeTokenCmd').textContent = tokenCommand;
    document.getElementById('codeSecretsHelp').textContent = secretsHelp;

    wizardOutputBox.style.display = 'block';
    showToast('✨ Channel setup configuration generated!', 'success');
  });

  // Initial Load
  loadData();
});
