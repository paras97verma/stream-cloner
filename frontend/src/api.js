/**
 * Stream Cloner Client API Client.
 * Automatically detects and communicates with Python via pywebview bridge or HTTP API.
 */

function hasPyWebView() {
  return typeof window !== 'undefined' && window.pywebview && window.pywebview.api;
}

// Wait for pywebviewready event if starting up
let pywebviewReadyPromise = null;
function waitForPyWebView() {
  if (hasPyWebView()) {
    return Promise.resolve(window.pywebview.api);
  }
  if (!pywebviewReadyPromise) {
    pywebviewReadyPromise = new Promise((resolve) => {
      window.addEventListener('pywebviewready', () => {
        resolve(window.pywebview.api);
      });
      // Fallback timeout: if pywebview doesn't fire within 800ms, use HTTP
      setTimeout(() => resolve(null), 800);
    });
  }
  return pywebviewReadyPromise;
}

async function request(methodName, httpPath, payload = null, httpMethod = 'POST') {
  await waitForPyWebView();
  if (hasPyWebView() && typeof window.pywebview.api[methodName] === 'function') {
    try {
      if (payload === null || payload === undefined) {
        return await window.pywebview.api[methodName]();
      }
      if (typeof payload === 'object' && !Array.isArray(payload)) {
        return await window.pywebview.api[methodName](payload);
      }
      return await window.pywebview.api[methodName](payload);
    } catch (err) {
      console.warn(`pywebview call ${methodName} failed, falling back to HTTP:`, err);
    }
  }

  // HTTP Fallback
  try {
    const opts = {
      method: httpMethod,
      headers: { 'Content-Type': 'application/json' },
    };
    if (payload && httpMethod === 'POST') {
      opts.body = JSON.stringify(payload);
    }
    const res = await fetch(httpPath, opts);
    return await res.json();
  } catch (err) {
    console.error(`HTTP request to ${httpPath} failed:`, err);
    throw err;
  }
}

export const api = {
  async getInitialState() {
    return await request('get_initial_state', '/api/state', null, 'GET');
  },

  async setMaxParallel(max_parallel) {
    return await request('set_max_parallel', '/api/parallel', { max_parallel });
  },

  async chooseDirectory() {
    return await request('choose_directory', '/api/choose_directory');
  },

  async openFolder(path = null) {
    return await request('open_folder', '/api/open_folder', { path });
  },

  async openUrl(url) {
    return await request('open_url', '/api/open_url', { url });
  },

  async discoverMedia(url, fetch_playlist = false) {
    return await request('discover_media', '/api/discover', { url, fetch_playlist });
  },

  async startDownload(payload) {
    return await request('start_download', '/api/download', payload);
  },

  async cancelDownload() {
    return await request('cancel_download', '/api/cancel');
  },

  async getHistory() {
    const res = await request('get_history', '/api/history', null, 'GET');
    return Array.isArray(res) ? res : (res.items || []);
  },

  async deleteHistoryItem(id) {
    const res = await request('delete_history_item', '/api/history/delete', { id });
    return Array.isArray(res) ? res : (res.items || []);
  },

  async clearHistory() {
    return await request('clear_history', '/api/history/clear');
  },
};
