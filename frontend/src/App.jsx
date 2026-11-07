import React, { Component, Suspense, lazy, useEffect, useState } from 'react';
import { BrowserRouter as Router, Link, Route, Routes } from 'react-router-dom';
import Navbar from './components/Navbar';
import { createLiveWebSocket } from './services/api';

// Route-level code splitting: Leaflet and Recharts load only with the pages that use them
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Stations = lazy(() => import('./pages/Stations'));
const StationDetail = lazy(() => import('./pages/StationDetail'));
const Anomalies = lazy(() => import('./pages/Anomalies'));
const AnomalyDetail = lazy(() => import('./pages/AnomalyDetail'));
const Alerts = lazy(() => import('./pages/Alerts'));
const Health = lazy(() => import('./pages/Health'));
const DemoControls = lazy(() => import('./pages/DemoControls'));

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div role="alert" className="p-10 text-center space-y-3">
          <p className="text-rose-300 font-semibold">Something went wrong while rendering this page.</p>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="px-4 py-2 rounded-lg border border-cyan-500/30 text-cyan-300 text-sm hover:bg-cyan-500/10"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function PageLoader() {
  return (
    <div className="p-12 text-center text-slate-400 font-mono text-sm" role="status" aria-live="polite">
      Loading…
    </div>
  );
}

function NotFound() {
  return (
    <div className="p-12 text-center space-y-3">
      <p className="text-lg font-bold text-white">Page not found</p>
      <Link to="/" className="text-cyan-400 hover:text-cyan-300 text-sm font-semibold">
        Back to the dashboard
      </Link>
    </div>
  );
}

export default function App() {
  const [wsStatus, setWsStatus] = useState('connecting');
  const [liveAlerts, setLiveAlerts] = useState([]);
  const [liveAnomalies, setLiveAnomalies] = useState([]);

  useEffect(() => {
    const ws = createLiveWebSocket(
      (message) => {
        if (message.type === 'alert') {
          setLiveAlerts((prev) => [message.data, ...prev.slice(0, 19)]);
        } else if (message.type === 'anomaly' && message.data?.is_anomaly) {
          setLiveAnomalies((prev) => [message.data, ...prev.slice(0, 19)]);
        }
      },
      setWsStatus
    );
    return () => ws.close();
  }, []);

  return (
    <Router>
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[2000] focus:px-3 focus:py-2 focus:rounded-lg focus:bg-cyan-600 focus:text-white"
        >
          Skip to content
        </a>
        <Navbar wsStatus={wsStatus} />
        <main id="main" className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-6">
          <ErrorBoundary>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/" element={<Dashboard liveAlerts={liveAlerts} liveAnomalies={liveAnomalies} />} />
                <Route path="/stations" element={<Stations />} />
                <Route path="/stations/:id" element={<StationDetail />} />
                <Route path="/anomalies" element={<Anomalies />} />
                <Route path="/anomalies/:id" element={<AnomalyDetail />} />
                <Route path="/alerts" element={<Alerts />} />
                <Route path="/health" element={<Health />} />
                <Route path="/demo" element={<DemoControls />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
    </Router>
  );
}
