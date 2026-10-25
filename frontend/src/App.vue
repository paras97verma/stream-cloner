<script setup>
import { ref, computed, onMounted } from 'vue';
import {
  Download,
  Folder,
  FolderOpen,
  History,
  Trash2,
  Video,
  Music,
  Layers,
  ListMusic,
  CheckSquare,
  Square,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Linkedin,
  Sparkles,
  Clock,
  HardDrive,
  Search,
  X,
  XCircle
} from 'lucide-vue-next';
import { api } from './api';

// --- State Variables ---
const urlInput = ref('');
const isDiscovering = ref(false);
const isDownloading = ref(false);
const metadata = ref(null);
const selectedMode = ref('video'); // 'video' | 'audio'
const selectedQualityKey = ref('');
const selectedAudioBitrate = ref('320');
const maxParallel = ref(2);
const downloadDir = ref('');
const fileManagerName = ref('Finder');
const isMac = ref(true);
const hasFfmpeg = ref(true);
const hasJs = ref(true);

// Playlist / Multi-URL Queue
const queueItems = ref([]);
const selectAllChecked = computed(() => {
  return queueItems.value.length > 0 && queueItems.value.every(item => item.selected);
});
const selectedQueueCount = computed(() => {
  return queueItems.value.filter(item => item.selected).length;
});

// Progress Tracking
const overallProgress = ref({
  percentage: 0,
  statusMessage: '',
  speedBytes: 0,
  etaSeconds: null,
  downloadedBytes: 0,
  totalBytes: 0,
  currentItem: 1,
  totalItems: 1,
});

// Active Simultaneous Slots
const activeSlots = ref([]);

// History
const isHistoryOpen = ref(false);
const historyItems = ref([]);
const historySearch = ref('');

// Notifications / Toast
const toast = ref({ show: false, message: '', type: 'info' });
let toastTimeout = null;

function showToast(message, type = 'info') {
  if (toastTimeout) clearTimeout(toastTimeout);
  toast.value = { show: true, message, type };
  toastTimeout = setTimeout(() => {
    toast.value.show = false;
  }, 4000);
}

// Multi-URL Detection from comma
const detectedUrls = computed(() => {
  if (!urlInput.value) return [];
  return urlInput.value
    .split(',')
    .map(u => u.trim())
    .filter(u => u.length > 0 && (u.startsWith('http://') || u.startsWith('https://') || u.includes('youtu')));
});

// Format conversion helpers
function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '--:--';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const h = Math.floor(m / 60);
  if (h > 0) {
    return `${h}:${(m % 60).toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatSpeed(bytesPerSec) {
  if (!bytesPerSec || bytesPerSec <= 0) return '0 MB/s';
  return `${(bytesPerSec / (1024 * 1024)).toFixed(1)} MB/s`;
}

function formatEta(seconds) {
  if (seconds === null || seconds === undefined || seconds <= 0) return '--';
  if (seconds > 3600) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  }
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
}

// --- Simultaneous Downloads Setting ---
async function selectMaxParallel(val) {
  maxParallel.value = val;
  try {
    await api.setMaxParallel(val);
    showToast(`Simultaneous downloads set to ${val}`, 'success');
  } catch (err) {
    console.error('Failed to set max parallel:', err);
  }
}

// --- Directory Picker & Revealing ---
async function chooseDirectory() {
  try {
    const res = await api.chooseDirectory();
    if (res && res.download_dir) {
      downloadDir.value = res.download_dir;
      showToast('Download directory updated', 'success');
    }
  } catch (err) {
    console.error('Directory choice error:', err);
  }
}

async function openFolder(path = null) {
  try {
    await api.openFolder(path || downloadDir.value);
  } catch (err) {
    showToast(`Unable to reveal in ${fileManagerName.value}`, 'error');
  }
}

function openExternalLink(url) {
  if (url) {
    api.openUrl(url).catch(() => {
      window.open(url, '_blank');
    });
  }
}

// --- Clipboard Paste Helper ---
async function pasteFromClipboard() {
  try {
    const text = await navigator.clipboard.readText();
    if (text) {
      urlInput.value = text.trim();
      onUrlChanged();
    }
  } catch (err) {
    showToast('Clipboard access not permitted or empty', 'error');
  }
}

function onUrlChanged() {
  if (detectedUrls.value.length > 1) {
    queueItems.value = detectedUrls.value.map((url, idx) => ({
      index: idx + 1,
      video_id: `multi_${idx + 1}`,
      title: `Track ${idx + 1} (Click "Fetch Info" to resolve metadata)`,
      url: url,
      duration: 0,
      thumbnail_url: '',
      selected: true,
    }));
  } else {
    queueItems.value = [];
  }
}

// --- Discovery ---
async function discoverMedia() {
  if (!urlInput.value || !urlInput.value.trim()) {
    showToast('Please enter a YouTube link or multiple comma-separated URLs', 'error');
    return;
  }

  isDiscovering.value = true;
  metadata.value = null;

  try {
    const rawUrl = urlInput.value.trim();
    const res = await api.discoverMedia(rawUrl, true);
    if (!res || !res.success) {
      showToast(res?.error || 'Failed to analyze stream link', 'error');
      return;
    }

    metadata.value = res;

    if (res.playlist_entries && res.playlist_entries.length > 0) {
      queueItems.value = res.playlist_entries.map(e => ({
        ...e,
        selected: true,
      }));
    } else {
      queueItems.value = [];
    }

    if (res.video_formats && res.video_formats.length > 0) {
      const defaultFmt = res.video_formats.find(f => f.is_default) || res.video_formats[0];
      selectedQualityKey.value = JSON.stringify(defaultFmt.selection_key);
    }

    showToast('Stream analyzed successfully', 'success');
  } catch (err) {
    console.error('Discovery error:', err);
    showToast(err.message || 'Stream inspection failed', 'error');
  } finally {
    isDiscovering.value = false;
  }
}

// --- Queue Selection Helpers ---
function toggleAllQueueItems() {
  const target = !selectAllChecked.value;
  queueItems.value.forEach(item => {
    item.selected = target;
  });
}

function toggleQueueItem(index) {
  const item = queueItems.value.find(i => i.index === index);
  if (item) item.selected = !item.selected;
}

// --- Download Execution ---
async function startDownload() {
  if (isDownloading.value) return;

  const url = urlInput.value.trim();
  if (!url) {
    showToast('Please provide a URL to download', 'error');
    return;
  }

  const selectedItems = queueItems.value.filter(i => i.selected);
  if (queueItems.value.length > 0 && selectedItems.length === 0) {
    showToast('Please select at least one video to download', 'error');
    return;
  }

  let targetHeight = 0;
  let targetFps = null;
  if (selectedMode.value === 'video' && selectedQualityKey.value) {
    try {
      const parsed = JSON.parse(selectedQualityKey.value);
      if (Array.isArray(parsed) && parsed.length >= 2) {
        targetHeight = parsed[0];
        targetFps = parsed[1];
      }
    } catch (e) {
      console.warn('Failed to parse quality key', e);
    }
  }

  const effectiveSlots = Math.min(
    maxParallel.value,
    selectedItems.length > 0 ? selectedItems.length : 1
  );
  activeSlots.value = Array.from({ length: effectiveSlots }, (_, idx) => ({
    slot_index: idx,
    item_title: `Slot ${idx + 1} (Waiting...)`,
    percentage: 0,
    status_message: 'Initializing...',
  }));

  overallProgress.value = {
    percentage: 0,
    statusMessage: 'Starting download process...',
    speedBytes: 0,
    etaSeconds: null,
    downloadedBytes: 0,
    totalBytes: 0,
    currentItem: 1,
    totalItems: selectedItems.length > 0 ? selectedItems.length : 1,
  };

  isDownloading.value = true;

  try {
    const payload = {
      url: url,
      mode: selectedMode.value,
      target_height: targetHeight,
      target_fps: targetFps,
      audio_bitrate: selectedAudioBitrate.value,
      playlist_items: selectedItems,
      playlist_title: metadata.value?.title || (selectedItems.length > 1 ? 'Batch_Download' : null),
      max_parallel: maxParallel.value,
    };

    const res = await api.startDownload(payload);
    if (!res || !res.success) {
      isDownloading.value = false;
      showToast(res?.error || 'Failed to initiate download', 'error');
    }
  } catch (err) {
    isDownloading.value = false;
    showToast(err.message || 'Download request failed', 'error');
  }
}

async function cancelDownload() {
  try {
    await api.cancelDownload();
    showToast('Cancelling download...', 'info');
  } catch (err) {
    console.error('Cancel error:', err);
  }
}

// --- Bridge Events ---
function setupGlobalBridgeEvents() {
  window.onDownloadProgress = (data) => {
    if (!data) return;
    overallProgress.value.percentage = Math.round(data.overall_percentage || data.percentage || 0);
    overallProgress.value.statusMessage = data.status_message || '';
    overallProgress.value.downloadedBytes = data.downloaded_bytes || 0;
    overallProgress.value.totalBytes = data.total_bytes || 0;
    overallProgress.value.speedBytes = data.speed_bytes || 0;
    overallProgress.value.etaSeconds = data.eta_seconds;
    overallProgress.value.currentItem = data.current_item || 1;
    overallProgress.value.totalItems = data.total_items || 1;
  };

  window.onSlotProgress = (data) => {
    if (!data || data.slot_index === undefined) return;
    const existing = activeSlots.value.find(s => s.slot_index === data.slot_index);
    if (existing) {
      existing.item_title = data.item_title || existing.item_title;
      existing.percentage = Math.round(data.percentage || 0);
      existing.status_message = data.status_message || existing.status_message;
    } else {
      activeSlots.value.push({
        slot_index: data.slot_index,
        item_title: data.item_title || `Slot ${data.slot_index + 1}`,
        percentage: Math.round(data.percentage || 0),
        status_message: data.status_message || '',
      });
    }
  };

  window.onDownloadFinished = (data) => {
    isDownloading.value = false;
    overallProgress.value.percentage = 100;
    overallProgress.value.statusMessage = 'Download complete!';
    showToast(`Successfully downloaded ${data.count || 1} item(s)`, 'success');
    loadHistory();
  };

  window.onDownloadFailed = (data) => {
    isDownloading.value = false;
    if (data.cancelled) {
      showToast('Download was cancelled', 'info');
    } else {
      showToast(data.error || 'Download failed', 'error');
    }
  };
}

// --- History Drawer ---
async function loadHistory() {
  try {
    const items = await api.getHistory();
    historyItems.value = items || [];
  } catch (err) {
    console.error('History load error:', err);
  }
}

async function deleteHistoryItem(id) {
  try {
    const updated = await api.deleteHistoryItem(id);
    historyItems.value = updated || [];
    showToast('Record removed from history', 'info');
  } catch (err) {
    showToast('Failed to delete history item', 'error');
  }
}

async function clearAllHistory() {
  try {
    await api.clearHistory();
    historyItems.value = [];
    showToast('History cleared', 'info');
  } catch (err) {
    showToast('Failed to clear history', 'error');
  }
}

const filteredHistory = computed(() => {
  if (!historySearch.value) return historyItems.value;
  const q = historySearch.value.toLowerCase();
  return historyItems.value.filter(
    item => (item.title && item.title.toLowerCase().includes(q)) ||
            (item.file_path && item.file_path.toLowerCase().includes(q))
  );
});

// --- Lifecycle Init ---
onMounted(async () => {
  setupGlobalBridgeEvents();

  try {
    const state = await api.getInitialState();
    if (state) {
      downloadDir.value = state.download_dir || '';
      maxParallel.value = state.max_parallel || 2;
      fileManagerName.value = state.file_manager_name || 'Finder';
      isMac.value = state.is_macos !== undefined ? state.is_macos : true;
      hasFfmpeg.value = state.has_ffmpeg !== undefined ? state.has_ffmpeg : true;
      hasJs.value = state.has_js !== undefined ? state.has_js : true;
    }
  } catch (err) {
    console.error('Initial state fetch error:', err);
  }

  loadHistory();
});
</script>

<template>
  <div class="glass-canvas min-h-screen text-slate-100 p-4 sm:p-6 md:p-8">
    <!-- Ambient Background Glows -->
    <div class="fixed inset-0 overflow-hidden pointer-events-none -z-10">
      <div class="absolute -top-32 -left-32 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl"></div>
      <div class="absolute top-1/3 -right-32 w-96 h-96 bg-indigo-500/20 rounded-full blur-3xl"></div>
      <div class="absolute -bottom-32 left-1/3 w-96 h-96 bg-purple-500/15 rounded-full blur-3xl"></div>
    </div>

    <!-- Toast Notification -->
    <transition
      enter-active-class="transition duration-300 ease-out transform"
      enter-from-class="-translate-y-4 opacity-0 scale-95"
      enter-to-class="translate-y-0 opacity-100 scale-100"
      leave-active-class="transition duration-200 ease-in transform"
      leave-from-class="translate-y-0 opacity-100 scale-100"
      leave-to-class="-translate-y-4 opacity-0 scale-95"
    >
      <div
        v-if="toast.show"
        class="fixed top-5 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 px-4 py-2.5 rounded-full shadow-2xl backdrop-blur-xl border text-sm font-semibold"
        :class="{
          'bg-slate-900/95 text-slate-100 border-white/10 shadow-slate-900/40': toast.type === 'info',
          'bg-emerald-600 text-white border-emerald-500 shadow-emerald-600/30': toast.type === 'success',
          'bg-rose-600 text-white border-rose-500 shadow-rose-600/30': toast.type === 'error',
        }"
      >
        <CheckCircle2 v-if="toast.type === 'success'" class="w-4 h-4 flex-shrink-0" />
        <AlertCircle v-else-if="toast.type === 'error'" class="w-4 h-4 flex-shrink-0" />
        <Sparkles v-else class="w-4 h-4 text-blue-500 flex-shrink-0" />
        <span>{{ toast.message }}</span>
      </div>
    </transition>

    <!-- Main Container -->
    <div class="max-w-5xl mx-auto space-y-5">
      <!-- HEADER NAVBAR -->
      <header class="glass-card rounded-2xl p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4 card-3d">
        <!-- Logo and App Title -->
        <div class="flex items-center gap-3.5">
          <div class="relative w-11 h-11 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/25 ring-1 ring-white/40 p-2 overflow-hidden">
            <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="w-full h-full drop-shadow">
              <!-- Source Stream Card (Top Left) -->
              <rect x="7" y="8" width="31" height="23" rx="5" fill="#ffffff" fill-opacity="0.25" stroke="#ffffff" stroke-width="2.2" stroke-opacity="0.85" />
              <!-- Media Play Glyph -->
              <polygon points="18,14 18,25 27,19.5" fill="#ffffff" />

              <!-- Cloned Stream Card (Bottom Right) -->
              <rect x="23" y="22" width="33" height="33" rx="7" fill="#0b0f19" fill-opacity="0.9" stroke="#60a5fa" stroke-width="2.4" />
              <!-- Download Arrow -->
              <path d="M39.5 28V43M33.5 37.5L39.5 43.5L45.5 37.5" stroke="#38bdf8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
              <!-- Bottom Tray Base Line -->
              <path d="M30 47.5H49" stroke="#a78bfa" stroke-width="2.6" stroke-linecap="round" />
            </svg>
          </div>
          <div>
            <div class="flex items-center gap-2.5">
              <h1 class="text-xl sm:text-2xl font-black tracking-tight text-white">
                Stream Cloner
              </h1>
              <span class="text-[11px] font-black tracking-wider uppercase px-2 py-0.5 rounded-md bg-blue-950/60 text-blue-300 border border-blue-700/60">
                PRO v2.0
              </span>
            </div>
          </div>
        </div>

        <!-- Right Side: Status Badges & History -->
        <div class="flex items-center flex-wrap gap-2 sm:gap-3">
          <!-- FFmpeg Status Badge -->
          <div
            class="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border"
            :class="hasFfmpeg
              ? 'bg-emerald-950/60 text-emerald-300 border-emerald-700/60'
              : 'bg-rose-950/60 text-rose-300 border-rose-700/60'"
            :title="hasFfmpeg ? 'FFmpeg installed & active' : 'FFmpeg not detected'"
          >
            <div class="w-2 h-2 rounded-full" :class="hasFfmpeg ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'"></div>
            <span>FFmpeg</span>
          </div>

          <!-- History Drawer Button -->
          <button
            @click="isHistoryOpen = true"
            class="btn-secondary-3d flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-bold text-slate-200 transition-all cursor-pointer shadow-xs"
          >
            <History class="w-4 h-4 text-blue-400" />
            <span class="hidden sm:inline">History</span>
            <span v-if="historyItems.length > 0" class="px-1.5 py-0.2 rounded-full bg-blue-600 text-white text-[10px] font-bold">
              {{ historyItems.length }}
            </span>
          </button>
        </div>
      </header>

      <!-- CARD 1: INPUT, MULTI-URL DISCOVERY & MEDIA DETAILS -->
      <section class="glass-card rounded-2xl p-5 sm:p-6 card-3d space-y-4">
        <div class="flex items-center justify-between">
          <label class="text-sm font-extrabold text-slate-100 flex items-center gap-2">
            <span>Video URL or Multiple Links</span>
            <span class="text-xs text-slate-400 font-medium hidden sm:inline">(Separate multiple links with commas)</span>
          </label>
          <div v-if="detectedUrls.length > 1" class="flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-950/60 text-blue-300 border border-blue-700 text-xs font-bold">
            <Layers class="w-3.5 h-3.5" />
            <span>{{ detectedUrls.length }} URLs Detected</span>
          </div>
        </div>

        <!-- Input Bar with Paste & Fetch Buttons -->
        <div class="flex flex-col sm:flex-row gap-2.5">
          <div class="relative flex-1">
            <input
              v-model="urlInput"
              @input="onUrlChanged"
              @keyup.enter="discoverMedia"
              type="text"
              placeholder="https://www.youtube.com/watch?v=..., https://youtu.be/..."
              class="w-full h-12 pl-4 pr-16 rounded-xl bg-slate-900/90 border border-slate-700 text-slate-100 text-sm font-mono placeholder:font-sans placeholder:text-slate-400 focus:outline-none focus:border-blue-600 focus:ring-4 focus:ring-blue-500/20 shadow-xs transition-all"
            />
            <button
              @click="pasteFromClipboard"
              class="absolute right-2.5 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-600 text-xs font-bold text-slate-200 transition-all cursor-pointer shadow-2xs"
              title="Paste from clipboard"
            >
              Paste
            </button>
          </div>

          <button
            @click="discoverMedia"
            :disabled="isDiscovering || !urlInput.trim()"
            class="btn-3d h-12 px-6 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 text-white text-sm font-bold flex items-center justify-center gap-2 cursor-pointer shadow-lg shadow-blue-500/25 border border-blue-600"
          >
            <RefreshCw v-if="isDiscovering" class="w-4 h-4 animate-spin" />
            <Sparkles v-else class="w-4 h-4" />
            <span>{{ isDiscovering ? 'Analyzing...' : 'Fetch Info' }}</span>
          </button>
        </div>

        <!-- Single Media Preview Card (High Contrast) -->
        <div
          v-if="metadata && !metadata.is_playlist && queueItems.length <= 1"
          class="glass-inner rounded-xl p-4 flex flex-col sm:flex-row gap-4 items-center sm:items-start shadow-xs"
        >
          <img
            v-if="metadata.thumbnail_url"
            :src="metadata.thumbnail_url"
            alt="Thumbnail"
            class="w-full sm:w-44 h-28 object-cover rounded-lg shadow-md border border-slate-700"
          />
          <div class="flex-1 space-y-1.5 text-center sm:text-left w-full">
            <h3 class="text-base font-bold text-white line-clamp-2 leading-snug">{{ metadata.title }}</h3>
            <p class="text-xs text-slate-400 font-semibold flex items-center justify-center sm:justify-start gap-3">
              <span>{{ metadata.uploader || 'YouTube Channel' }}</span>
              <span>•</span>
              <span class="flex items-center gap-1 font-mono">
                <Clock class="w-3.5 h-3.5" />
                {{ formatDuration(metadata.duration) }}
              </span>
            </p>
            <div class="flex flex-wrap gap-2 pt-1 justify-center sm:justify-start">
              <span class="px-2.5 py-0.5 rounded-md bg-blue-950/60 text-blue-300 border border-blue-800 text-xs font-bold">
                Available: {{ metadata.video_formats?.length || 0 }} resolutions
              </span>
              <span class="px-2.5 py-0.5 rounded-md bg-purple-950/60 text-purple-300 border border-purple-800 text-xs font-bold">
                Audio bitrates up to 320 kbps
              </span>
            </div>
          </div>
        </div>

        <!-- Playlist / Multiple URLs Video Selector Queue -->
        <div v-if="queueItems.length > 0" class="glass-inner rounded-xl p-4 space-y-3 shadow-xs">
          <div class="flex items-center justify-between flex-wrap gap-2">
            <div class="flex items-center gap-2">
              <ListMusic class="w-4 h-4 text-blue-400" />
              <h3 class="text-sm font-extrabold text-slate-100">
                Batch Video Selection
                <span class="text-xs font-semibold text-slate-400 ml-1">({{ selectedQueueCount }} of {{ queueItems.length }} selected)</span>
              </h3>
            </div>
            <div class="flex items-center gap-2">
              <button
                @click="toggleAllQueueItems"
                class="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-bold text-slate-200 border border-slate-700 transition-all cursor-pointer flex items-center gap-1.5 shadow-2xs"
              >
                <CheckSquare v-if="selectAllChecked" class="w-3.5 h-3.5 text-blue-400" />
                <Square v-else class="w-3.5 h-3.5 text-slate-400" />
                <span>{{ selectAllChecked ? 'Deselect All' : 'Select All' }}</span>
              </button>
            </div>
          </div>

          <!-- Queue Items List -->
          <div class="max-h-60 overflow-y-auto space-y-2 pr-1">
            <div
              v-for="item in queueItems"
              :key="item.index"
              @click="toggleQueueItem(item.index)"
              class="flex items-center gap-3 p-2.5 rounded-xl border transition-all cursor-pointer"
              :class="item.selected
                ? 'bg-blue-950/40 border-blue-600/50 text-blue-100 font-semibold shadow-2xs'
                : 'bg-slate-800/40 hover:bg-slate-800 border-slate-800 text-slate-400'"
            >
              <input
                type="checkbox"
                :checked="item.selected"
                @click.stop="toggleQueueItem(item.index)"
                class="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 cursor-pointer"
              />
              <span class="text-xs font-bold text-slate-400 w-6 flex-shrink-0">#{{ item.index }}</span>
              <span class="text-xs font-semibold flex-1 truncate">{{ item.title }}</span>
              <span v-if="item.duration" class="text-[11px] font-mono text-slate-400 flex-shrink-0">
                {{ formatDuration(item.duration) }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- CARD 2: DOWNLOAD SETTINGS, SIMULTANEOUS DOWNLOADS & PATH -->
      <section class="glass-card rounded-2xl p-5 sm:p-6 card-3d space-y-5">
        <h2 class="text-xs font-extrabold tracking-wider uppercase text-slate-400 flex items-center gap-2">
          <span>Preferences & Output Settings</span>
        </h2>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
          <!-- Left Column: Output Mode & Quality Selection -->
          <div class="space-y-4">
            <!-- Mode Selector (Video vs Audio) -->
            <div>
              <label class="text-xs font-bold text-slate-300 mb-1.5 block">Format Type</label>
              <div class="grid grid-cols-2 p-1 rounded-xl bg-slate-900/90 border border-slate-800">
                <button
                  @click="selectedMode = 'video'"
                  :class="selectedMode === 'video'
                    ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/40'
                    : 'text-slate-400 hover:text-white font-semibold'"
                  class="h-10 rounded-lg flex items-center justify-center gap-2 text-xs transition-all cursor-pointer"
                >
                  <Video class="w-4 h-4" />
                  <span>Video (MP4 / MKV)</span>
                </button>
                <button
                  @click="selectedMode = 'audio'"
                  :class="selectedMode === 'audio'
                    ? 'bg-purple-600 text-white font-bold shadow-md shadow-purple-600/40'
                    : 'text-slate-400 hover:text-white font-semibold'"
                  class="h-10 rounded-lg flex items-center justify-center gap-2 text-xs transition-all cursor-pointer"
                >
                  <Music class="w-4 h-4" />
                  <span>Audio (MP3)</span>
                </button>
              </div>
            </div>

            <!-- Quality Option Dropdown / Selector -->
            <div>
              <label class="text-xs font-bold text-slate-300 mb-1.5 block">
                {{ selectedMode === 'video' ? 'Video Resolution' : 'Audio Quality (MP3 Bitrate)' }}
              </label>

              <!-- Video Resolutions -->
              <div v-if="selectedMode === 'video'">
                <select
                  v-if="metadata && metadata.video_formats && metadata.video_formats.length > 0"
                  v-model="selectedQualityKey"
                  class="w-full h-11 px-3 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 text-xs font-semibold focus:outline-none focus:border-blue-600 focus:ring-4 focus:ring-blue-500/20 shadow-xs cursor-pointer"
                >
                  <option
                    v-for="fmt in metadata.video_formats"
                    :key="JSON.stringify(fmt.selection_key)"
                    :value="JSON.stringify(fmt.selection_key)"
                  >
                    {{ fmt.display_label }} {{ fmt.approx_size ? `(~${fmt.approx_size})` : '' }} {{ fmt.is_hdr ? '[HDR]' : '' }}
                  </option>
                </select>
                <div v-else class="text-xs text-slate-300 p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center gap-2.5 font-medium shadow-2xs">
                  <Sparkles class="w-4 h-4 text-blue-400 flex-shrink-0" />
                  <span>Click "Fetch Info" for available options, or best quality will be selected automatically (Up to 4K/1080p).</span>
                </div>
              </div>

              <!-- Audio Bitrate Selector -->
              <div v-else>
                <div v-if="metadata && metadata.audio_formats && metadata.audio_formats.length > 0" class="grid grid-cols-4 gap-2">
                  <button
                    v-for="rate in ['320', '256', '192', '128']"
                    :key="rate"
                    @click="selectedAudioBitrate = rate"
                    :class="selectedAudioBitrate === rate
                      ? 'bg-purple-600 text-white font-bold shadow-md shadow-purple-600/30 border border-purple-600'
                      : 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold shadow-2xs'"
                    class="h-10 rounded-xl text-xs flex flex-col items-center justify-center transition-all cursor-pointer"
                  >
                    <span>{{ rate }} kbps</span>
                    <span class="text-[9px] opacity-80">{{ rate === '320' ? 'Extreme' : rate === '256' ? 'High' : 'Normal' }}</span>
                  </button>
                </div>
                <div v-else class="text-xs text-slate-300 p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center gap-2.5 font-medium shadow-2xs">
                  <Sparkles class="w-4 h-4 text-purple-400 flex-shrink-0" />
                  <span>Click "Fetch Info" for available options, or best audio quality will be selected automatically (Up to 320 kbps MP3).</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Right Column: Simultaneous Downloads & Output Folder -->
          <div class="space-y-4">
            <!-- Simultaneous Downloads Segmented Selector -->
            <div>
              <div class="flex items-center justify-between mb-2">
                <label class="text-xs font-bold text-slate-300">
                  Simultaneous Downloads
                </label>
                <span class="text-[11px] font-mono font-bold text-blue-400 bg-blue-950/60 border border-blue-800/60 px-2 py-0.5 rounded-md">
                  {{ maxParallel }} concurrent
                </span>
              </div>
              <div class="grid grid-cols-5 p-1 rounded-xl bg-slate-900/90 border border-slate-700/80 shadow-inner gap-1.5 max-w-xs">
                <button
                  v-for="num in [1, 2, 3, 4, 5]"
                  :key="num"
                  @click="selectMaxParallel(num)"
                  :class="maxParallel === num
                    ? 'bg-blue-600 text-white shadow-md shadow-blue-600/40 font-black ring-1 ring-blue-400/50'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/80 bg-slate-800/30 font-semibold'"
                  class="h-9 rounded-lg flex items-center justify-center text-xs transition-all cursor-pointer"
                >
                  <span>{{ num }}</span>
                </button>
              </div>
            </div>

            <!-- Download Destination & Reveal Folder -->
            <div>
              <label class="text-xs font-bold text-slate-300 mb-1.5 block">
                Destination Folder
              </label>
              <div class="flex gap-2">
                <div class="relative flex-1">
                  <input
                    type="text"
                    readonly
                    :value="downloadDir"
                    class="w-full h-11 pl-3 pr-8 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 text-xs font-mono font-medium truncate shadow-2xs"
                  />
                  <Folder class="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
                </div>
                <button
                  @click="chooseDirectory"
                  class="btn-secondary-3d h-11 px-3.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-bold text-slate-200 transition-all cursor-pointer flex items-center gap-1.5 shadow-2xs"
                  title="Browse folder"
                >
                  <FolderOpen class="w-4 h-4 text-blue-400" />
                  <span class="hidden sm:inline">Browse</span>
                </button>
                <button
                  @click="openFolder(downloadDir)"
                  class="btn-secondary-3d h-11 px-3.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-bold text-slate-200 transition-all cursor-pointer flex items-center gap-1.5 shadow-2xs"
                  :title="`Reveal in ${fileManagerName}`"
                >
                  <ExternalLink class="w-4 h-4 text-purple-400" />
                  <span class="hidden sm:inline">{{ isMac ? 'Finder' : 'Explorer' }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- CARD 3: DOWNLOAD ACTION, OVERALL PROGRESS & SIMULTANEOUS SLOTS -->
      <section class="glass-card rounded-2xl p-5 sm:p-6 card-3d space-y-5">
        <!-- Action Row: Start or Cancel -->
        <div class="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div class="text-center sm:text-left">
            <h3 class="text-base font-black text-white">
              {{ isDownloading ? 'Active Download in Progress' : 'Ready to Download' }}
            </h3>
            <p class="text-xs text-slate-400 font-semibold">
              {{ isDownloading
                ? `Downloading item ${overallProgress.currentItem} of ${overallProgress.totalItems}`
                : queueItems.length > 0
                  ? `${selectedQueueCount} video(s) ready to download`
                  : 'High-speed multi-threaded media cloning' }}
            </p>
          </div>

          <div class="flex items-center gap-3 w-full sm:w-auto">
            <button
              v-if="isDownloading"
              @click="cancelDownload"
              class="flex-1 sm:flex-none h-12 px-6 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-sm font-bold transition-all cursor-pointer shadow-lg shadow-rose-600/30 flex items-center justify-center gap-2 border border-rose-600"
            >
              <XCircle class="w-4 h-4" />
              <span>Cancel</span>
            </button>
            <button
              v-else
              @click="startDownload"
              :disabled="!urlInput.trim()"
              class="btn-3d flex-1 sm:flex-none h-12 px-8 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 text-white text-sm font-black flex items-center justify-center gap-2.5 cursor-pointer shadow-xl shadow-blue-600/30 tracking-wide border border-blue-600"
            >
              <Download class="w-5 h-5" />
              <span>START DOWNLOAD</span>
            </button>
          </div>
        </div>

        <!-- Master Overall Progress Bar -->
        <div v-if="isDownloading || overallProgress.percentage > 0" class="space-y-2 pt-2">
          <div class="flex justify-between items-center text-xs font-bold">
            <span class="text-slate-200 truncate max-w-[65%]">
              {{ overallProgress.statusMessage || 'Downloading...' }}
            </span>
            <span class="font-mono text-blue-400 font-black text-sm">
              {{ overallProgress.percentage }}%
            </span>
          </div>

          <!-- Progress track -->
          <div class="relative w-full h-4 rounded-full bg-slate-800 border border-slate-700 overflow-hidden shadow-inner">
            <div
              class="h-full rounded-full transition-all duration-300 relative overflow-hidden"
              :class="[
                overallProgress.percentage >= 100 && !isDownloading
                  ? 'bg-emerald-500 shadow-md shadow-emerald-500/30'
                  : 'bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600',
                isDownloading ? 'animate-progress-glow' : ''
              ]"
              :style="{ width: `${Math.max(overallProgress.percentage, isDownloading ? 5 : 0)}%` }"
            >
              <!-- Animated diagonal candy-stripes (ONLY while actively downloading) -->
              <div v-if="isDownloading" class="absolute inset-0 animate-stripes"></div>
              <!-- Shimmer overlay (ONLY while actively downloading) -->
              <div v-if="isDownloading" class="absolute inset-0 bg-white/20 animate-shimmer pointer-events-none"></div>
            </div>
          </div>

          <!-- Telemetry Stats (Speed, ETA, Downloaded Bytes) -->
          <div class="flex flex-wrap justify-between items-center gap-2 text-xs font-mono font-bold text-slate-300">
            <div class="flex items-center gap-3">
              <span>Speed: <strong class="text-white">{{ formatSpeed(overallProgress.speedBytes) }}</strong></span>
              <span>•</span>
              <span>ETA: <strong class="text-white">{{ formatEta(overallProgress.etaSeconds) }}</strong></span>
            </div>
            <div>
              <span>{{ formatBytes(overallProgress.downloadedBytes) }} / {{ formatBytes(overallProgress.totalBytes) }}</span>
            </div>
          </div>
        </div>

        <!-- ACTIVE SIMULTANEOUS SLOTS (Configurable live slots) -->
        <div v-if="isDownloading && activeSlots.length > 0" class="pt-3 space-y-2.5">
          <h4 class="text-xs font-extrabold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Layers class="w-3.5 h-3.5 text-blue-400" />
            <span>Active Download Slots ({{ activeSlots.length }} Threads)</span>
          </h4>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div
              v-for="slot in activeSlots"
              :key="slot.slot_index"
              class="glass-inner rounded-xl p-3.5 space-y-2 border border-slate-800 shadow-xs"
            >
              <div class="flex items-center justify-between text-xs">
                <span class="font-extrabold text-blue-400">Slot {{ slot.slot_index + 1 }}</span>
                <span class="font-mono text-xs font-black text-white">{{ slot.percentage }}%</span>
              </div>
              <p class="text-xs font-bold truncate text-slate-100">{{ slot.item_title }}</p>
              <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden relative shadow-inner">
                <div
                  class="h-full rounded-full transition-all duration-200"
                  :class="[
                    slot.percentage >= 100
                      ? 'bg-emerald-500'
                      : 'bg-blue-600',
                    isDownloading && slot.percentage < 100 ? 'animate-stripes' : ''
                  ]"
                  :style="{ width: `${Math.max(slot.percentage, isDownloading ? 5 : 0)}%` }"
                ></div>
              </div>
              <p class="text-[11px] font-medium text-slate-400 truncate">{{ slot.status_message }}</p>
            </div>
          </div>
        </div>
      </section>

      <!-- FOOTER (Attribution) -->
      <footer class="text-center py-4 text-xs font-medium text-slate-400">
        <p class="flex items-center justify-center gap-1.5">
          <span>Made with ❤️ by</span>
          <a
            href="https://linkedin.com/in/paras0397"
            target="_blank"
            rel="noopener noreferrer"
            @click.prevent="openExternalLink('https://linkedin.com/in/paras0397')"
            class="font-bold text-blue-400 hover:text-blue-300 hover:underline cursor-pointer inline-flex items-center gap-1 transition-colors"
            title="Open LinkedIn Profile (paras0397)"
          >
            <Linkedin class="w-3.5 h-3.5" />
            <span>~peivee</span>
            <ExternalLink class="w-2.5 h-2.5 opacity-70" />
          </a>
        </p>
      </footer>
    </div>

    <!-- HISTORY SLIDE-OVER DRAWER -->
    <transition
      enter-active-class="transition duration-300 ease-out"
      enter-from-class="opacity-0 translate-x-full"
      enter-to-class="opacity-100 translate-x-0"
      leave-active-class="transition duration-200 ease-in"
      leave-from-class="opacity-100 translate-x-0"
      leave-to-class="opacity-0 translate-x-full"
    >
      <div
        v-if="isHistoryOpen"
        class="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-sm"
        @click.self="isHistoryOpen = false"
      >
        <div class="w-full max-w-md h-full bg-[#111827] border-l border-slate-800 shadow-2xl p-5 flex flex-col space-y-4">
          <!-- Drawer Header -->
          <div class="flex items-center justify-between border-b border-slate-800 pb-4">
            <div class="flex items-center gap-2">
              <History class="w-5 h-5 text-blue-400" />
              <h2 class="text-lg font-black text-white">Download History</h2>
            </div>
            <button
              @click="isHistoryOpen = false"
              class="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-all cursor-pointer"
            >
              <X class="w-5 h-5" />
            </button>
          </div>

          <!-- History Search & Clear All -->
          <div class="flex items-center gap-2">
            <div class="relative flex-1">
              <input
                v-model="historySearch"
                type="text"
                placeholder="Search history..."
                class="w-full h-9 pl-8 pr-3 rounded-lg bg-slate-900 border border-slate-700 text-slate-100 text-xs font-medium focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-500/20"
              />
              <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
            </div>
            <button
              v-if="historyItems.length > 0"
              @click="clearAllHistory"
              class="px-2.5 py-2 rounded-lg bg-rose-950/60 hover:bg-rose-900/60 text-rose-300 text-xs font-bold border border-rose-800 transition-all cursor-pointer flex items-center gap-1 shadow-2xs"
              title="Clear all records"
            >
              <Trash2 class="w-3.5 h-3.5" />
              <span>Clear</span>
            </button>
          </div>

          <!-- History Items List -->
          <div class="flex-1 overflow-y-auto space-y-3 pr-1">
            <div
              v-if="filteredHistory.length === 0"
              class="h-64 flex flex-col items-center justify-center text-center text-slate-400 space-y-2"
            >
              <HardDrive class="w-10 h-10 opacity-30" />
              <p class="text-xs font-semibold">No download history records found</p>
            </div>

            <div
              v-for="item in filteredHistory"
              :key="item.id"
              class="glass-inner rounded-xl p-3.5 space-y-2 border border-slate-800 transition-all hover:border-blue-500/40 shadow-xs"
            >
              <div class="flex items-start justify-between gap-2">
                <h4 class="text-xs font-bold leading-snug line-clamp-2 text-slate-100">{{ item.title }}</h4>
                <button
                  @click="deleteHistoryItem(item.id)"
                  class="text-slate-400 hover:text-rose-400 p-1 rounded-md transition-all cursor-pointer flex-shrink-0"
                  title="Delete record"
                >
                  <Trash2 class="w-3.5 h-3.5" />
                </button>
              </div>

              <div class="flex items-center justify-between text-[11px] font-mono text-slate-400 font-semibold">
                <span class="px-2 py-0.5 rounded bg-blue-950/60 text-blue-300 border border-blue-800 text-[10px] font-bold uppercase">
                  {{ item.mode }} • {{ item.quality_label || 'Auto' }}
                </span>
                <span>{{ formatBytes(item.file_size) }}</span>
              </div>

              <div class="pt-1 flex items-center justify-between border-t border-slate-800 text-[10px]">
                <span class="text-slate-400 font-mono">{{ item.timestamp ? new Date(item.timestamp).toLocaleString() : '' }}</span>
                <button
                  @click="openFolder(item.file_path)"
                  class="text-blue-400 hover:underline flex items-center gap-1 font-bold cursor-pointer"
                >
                  <ExternalLink class="w-3 h-3" />
                  <span>Show in {{ isMac ? 'Finder' : 'Explorer' }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>
