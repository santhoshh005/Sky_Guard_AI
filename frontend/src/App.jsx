import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Stations from './pages/Stations';
import StationDetail from './pages/StationDetail';
import Anomalies from './pages/Anomalies';
import AnomalyDetail from './pages/AnomalyDetail';
import Alerts from './pages/Alerts';
import Health from './pages/Health';
import DemoControls from './pages/DemoControls';
import { createLiveWebSocket } from './services/api';

export default function App() {
  const [wsStatus, setWsStatus] = useState('connecting');
  const [liveAlerts, setLiveAlerts] = useState([]);
  const [liveAnomalies, setLiveAnomalies] = useState([]);

  useEffect(() => {
    const ws = createLiveWebSocket(
      (message) => {
        if (message.type === 'alert') {
          setLiveAlerts((prev) => [message.data, ...prev.slice(0, 19)]);
        } else if (message.type === 'anomaly') {
          setLiveAnomalies((prev) => [message.data, ...prev.slice(0, 19)]);
        }
      },
      (status) => {
        setWsStatus(status);
      }
    );

    return () => {
      ws.close();
    };
  }, []);

  return (
    <Router>
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
        <Navbar wsStatus={wsStatus} />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 pt-6">
          <Routes>
            <Route path="/" element={<Dashboard liveAlerts={liveAlerts} liveAnomalies={liveAnomalies} />} />
            <Route path="/stations" element={<Stations />} />
            <Route path="/stations/:id" element={<StationDetail />} />
            <Route path="/anomalies" element={<Anomalies />} />
            <Route path="/anomalies/:id" element={<AnomalyDetail />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/health" element={<Health />} />
            <Route path="/demo" element={<DemoControls />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
