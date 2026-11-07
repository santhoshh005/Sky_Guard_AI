/**
 * API Client & WebSocket Service for SkyGuard AI
 */

const loc = typeof window !== 'undefined' ? window.location : { hostname: '127.0.0.1', protocol: 'http:' };
const API_BASE = import.meta.env.VITE_API_URL || `${loc.protocol}//${loc.hostname}:8000/api/v1`;
const WS_BASE =
  import.meta.env.VITE_WS_URL ||
  `${loc.protocol === 'https:' ? 'wss' : 'ws'}://${loc.hostname}:8000/api/v1/ws/live`;
// Optional: only for protected demo deployments. Anything bundled here is visible to users.
const API_KEY = import.meta.env.VITE_API_KEY || '';
const REQUEST_TIMEOUT_MS = 15000;

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function toQuery(params = {}) {
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  );
  const q = new URLSearchParams(clean).toString();
  return q ? `?${q}` : '';
}

async function fetchJson(endpoint, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
        ...options.headers,
      },
    });

    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = await response.json();
        detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(detail || `Request failed (${response.status})`, response.status);
    }
    return response.status === 204 ? null : response.json();
  } catch (err) {
    if (err.name === 'AbortError') throw new ApiError('The server took too long to respond.', 0);
    if (err instanceof ApiError) throw err;
    throw new ApiError('Cannot reach the SkyGuard API. Is the backend running?', 0);
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  // Dashboard
  getDashboardSummary: () => fetchJson('/dashboard/summary'),

  // Stations
  getStations: (params = {}) => fetchJson(`/stations${toQuery(params)}`),
  getStationDetail: (id) => fetchJson(`/stations/${encodeURIComponent(id)}`),
  getStationObservations: (id, params = {}) =>
    fetchJson(`/stations/${encodeURIComponent(id)}/observations${toQuery(params)}`),
  createStation: (data) => fetchJson('/stations', { method: 'POST', body: JSON.stringify(data) }),

  // Anomalies
  getAnomalies: (params = {}) => fetchJson(`/anomalies${toQuery(params)}`),
  getAnomalyDetail: (id) => fetchJson(`/anomalies/${id}`),

  // Alerts
  getAlerts: (params = {}) => fetchJson(`/alerts${toQuery(params)}`),
  resolveAlert: (id) => fetchJson(`/alerts/${id}/resolve`, { method: 'PATCH' }),

  // Health
  getHealth: (stationId) => fetchJson(`/health/${stationId}`),
  getHealthHistory: (stationId, params = {}) => fetchJson(`/health/${stationId}/history${toQuery(params)}`),

  // Ingestion
  ingestObservation: (data) => fetchJson('/observations', { method: 'POST', body: JSON.stringify(data) }),
  ingestBatch: (data) => fetchJson('/observations/batch', { method: 'POST', body: JSON.stringify(data) }),

  // Demo Controls
  injectAnomaly: (data) => fetchJson('/demo/inject-anomaly', { method: 'POST', body: JSON.stringify(data) }),
  generateData: (data) => fetchJson('/demo/generate-data', { method: 'POST', body: JSON.stringify(data) }),
};

/**
 * Creates a live WebSocket connection with reconnection logic and event dispatching.
 */
export function createLiveWebSocket(onMessage, onStatusChange) {
  let ws = null;
  let isClosedManually = false;
  let reconnectTimer = null;
  let attempts = 0;

  function connect() {
    try {
      ws = new WebSocket(WS_BASE);

      ws.onopen = () => {
        attempts = 0;
        if (onStatusChange) onStatusChange('connected');
        // Subscribe to all stations by default
        ws.send(JSON.stringify({ action: 'subscribe', station_ids: null }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (onMessage) onMessage(data);
        } catch (err) {
          console.warn('Invalid WS message payload:', err);
        }
      };

      ws.onerror = () => {
        if (onStatusChange) onStatusChange('error');
      };

      ws.onclose = () => {
        if (onStatusChange) onStatusChange('disconnected');
        if (!isClosedManually) {
          // exponential backoff, capped at 30 s
          reconnectTimer = setTimeout(connect, Math.min(30000, 1000 * 2 ** attempts++));
        }
      };
    } catch (err) {
      if (onStatusChange) onStatusChange('error');
      reconnectTimer = setTimeout(connect, 3000);
    }
  }

  connect();

  return {
    close: () => {
      isClosedManually = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) ws.close();
    },
    send: (msg) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(typeof msg === 'string' ? msg : JSON.stringify(msg));
      }
    },
  };
}
