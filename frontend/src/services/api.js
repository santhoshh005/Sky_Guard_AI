/**
 * API Client & WebSocket Service for SkyGuard AI
 */

const hostname = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const API_BASE = import.meta.env.VITE_API_URL || `http://${hostname}:8000/api/v1`;
const WS_BASE = import.meta.env.VITE_WS_URL || `ws://${hostname}:8000/api/v1/ws/live`;

async function fetchJson(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API ${endpoint} failed (${response.status}): ${errorText}`);
  }

  return response.json();
}

export const api = {
  // Dashboard
  getDashboardSummary: () => fetchJson('/dashboard/summary'),

  // Stations
  getStations: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJson(`/stations${query ? `?${query}` : ''}`);
  },
  getStationDetail: (id) => fetchJson(`/stations/${id}`),
  createStation: (data) => fetchJson('/stations', { method: 'POST', body: JSON.stringify(data) }),

  // Anomalies
  getAnomalies: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJson(`/anomalies${query ? `?${query}` : ''}`);
  },
  getAnomalyDetail: (id) => fetchJson(`/anomalies/${id}`),

  // Alerts
  getAlerts: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJson(`/alerts${query ? `?${query}` : ''}`);
  },
  resolveAlert: (id) => fetchJson(`/alerts/${id}/resolve`, { method: 'PATCH' }),

  // Health
  getHealth: (stationId) => fetchJson(`/health/${stationId}`),
  getHealthHistory: (stationId, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return fetchJson(`/health/${stationId}/history${query ? `?${query}` : ''}`);
  },

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

  function connect() {
    try {
      ws = new WebSocket(WS_BASE);

      ws.onopen = () => {
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

      ws.onerror = (error) => {
        if (onStatusChange) onStatusChange('error');
      };

      ws.onclose = () => {
        if (onStatusChange) onStatusChange('disconnected');
        if (!isClosedManually) {
          reconnectTimer = setTimeout(connect, 3000);
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
