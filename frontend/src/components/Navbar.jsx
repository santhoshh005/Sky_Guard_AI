import React, { useState } from 'react';
import { NavLink, Link } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Flame,
  Globe2,
  HeartPulse,
  Menu,
  Radio,
  ShieldCheck,
  Sliders,
  X,
  Zap,
} from 'lucide-react';

export default function Navbar({ wsStatus = 'connected' }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    { to: '/', label: 'Live Operations', icon: Activity, exact: true },
    { to: '/stations', label: 'AWS Fleet', icon: Globe2 },
    { to: '/anomalies', label: 'Neural Diagnostics', icon: AlertTriangle },
    { to: '/alerts', label: 'Alert Feeds', icon: Radio },
    { to: '/health', label: 'Sensor Matrix', icon: HeartPulse },
    { to: '/demo', label: 'Demo Center', icon: Sliders, highlight: true },
  ];

  // Dummy continuous ticker data
  const tickerItems = [
    '🛰️ AWS_MUM_001 [MUMBAI]: 31.8°C | RH 76% | 1008 hPa • NOMINAL',
    '⚡ AWS_DEL_001 [DELHI]: 34.2°C | RH 58% | 1004 hPa • NOMINAL',
    '🌊 AWS_CHN_001 [CHENNAI]: 32.0°C | RH 81% | 1009 hPa • NOMINAL',
    '🍃 AWS_BLR_001 [BENGALURU]: 26.5°C | RH 64% | 915 hPa • SENSOR HEALTH 98%',
    '☀️ AWS_KOL_001 [KOLKATA]: 33.1°C | RH 74% | 1007 hPa • NOMINAL',
    '🤖 3-CHANNEL ML FUSION ENGINE: 94.94% BENCHMARK F1 ACTIVE',
  ];

  return (
    <header className="sticky top-0 z-50 flex flex-col border-b border-cyan-500/20 bg-[#060b1e]/90 backdrop-blur-xl">
      {/* 1. Top Telemetry Ticker Marquee */}
      <div className="hidden sm:flex h-6 items-center overflow-hidden border-b border-cyan-500/10 bg-[#030712]/80 px-4 text-[11px] font-mono text-cyan-400/90">
        <span className="shrink-0 font-bold uppercase tracking-wider text-emerald-400 mr-3 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-ping" />
          LIVE TELEMETRY STREAM:
        </span>
        <div className="flex-1 overflow-hidden relative">
          <div className="animate-ticker space-x-8">
            {[...tickerItems, ...tickerItems].map((item, idx) => (
              <span key={idx} className="inline-block hover:text-white transition-colors cursor-default">
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* 2. Main HUD Navigation */}
      <div className="max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Branding */}
          <Link to="/" className="flex items-center space-x-3 group">
            <div className="relative flex items-center justify-center h-10 w-10 rounded-lg bg-gradient-to-br from-cyan-500 via-blue-600 to-indigo-700 p-0.5 shadow-lg shadow-cyan-500/20 group-hover:shadow-cyan-500/40 transition-all">
              <div className="h-full w-full bg-[#070e24] rounded-[6px] flex items-center justify-center">
                <ShieldCheck className="h-5 w-5 text-cyan-400 group-hover:scale-110 transition-transform" />
              </div>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-lg font-black tracking-tight text-white font-sans">
                  SkyGuard<span className="text-cyan-400">.AI</span>
                </span>
                <span className="px-1.5 py-0.2 text-[9px] font-extrabold uppercase tracking-widest bg-cyan-500/15 text-cyan-300 rounded border border-cyan-500/30">
                  SIH26073
                </span>
              </div>
              <p className="text-[10px] text-slate-400 font-mono tracking-wide">MoES / IMD AWS Neural Ops</p>
            </div>
          </Link>

          {/* Desktop Nav Items */}
          <nav className="hidden lg:flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.exact}
                  className={({ isActive }) =>
                    `flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs font-semibold tracking-wide transition-all ${
                      item.highlight
                        ? 'bg-gradient-to-r from-cyan-500/20 to-blue-600/30 text-cyan-300 border border-cyan-400/40 shadow-md shadow-cyan-500/10 hover:border-cyan-400'
                        : isActive
                        ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 shadow-inner'
                        : 'text-slate-300 hover:text-white hover:bg-slate-800/50 border border-transparent'
                    }`
                  }
                >
                  <Icon className="h-4 w-4 text-cyan-400" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>

          {/* Right Status Beacon & Mobile Toggle */}
          <div className="flex items-center space-x-3">
            {/* Live Socket Beacon */}
            <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-full bg-[#08122c] border border-cyan-500/20 text-xs shadow-inner">
              <span
                className={`h-2 w-2 rounded-full ${
                  wsStatus === 'connected'
                    ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]'
                    : wsStatus === 'connecting'
                    ? 'bg-amber-400 animate-ping'
                    : 'bg-rose-500'
                }`}
              />
              <span className="text-slate-300 font-mono text-[11px] uppercase tracking-wider font-semibold">
                {wsStatus === 'connected' ? 'Neural Link Live' : wsStatus}
              </span>
            </div>

            {/* Quick Demo Button */}
            <Link
              to="/demo"
              className="hidden sm:inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-500 hover:from-blue-500 hover:to-cyan-400 text-white text-xs font-bold shadow-lg shadow-cyan-500/20 transition-all hover:scale-105"
            >
              <Zap className="h-3.5 w-3.5 fill-current" />
              <span>Simulate Fault</span>
            </Link>

            {/* Mobile Hamburger Menu Toggle */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white"
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Slide-down Navigation Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden bg-[#070e24] border-b border-cyan-500/20 px-4 pt-2 pb-4 space-y-1.5 animate-fadeIn">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.exact}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                    isActive
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                      : 'text-slate-300 hover:bg-slate-800/60'
                  }`
                }
              >
                <Icon className="h-4 w-4 text-cyan-400" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </div>
      )}
    </header>
  );
}
