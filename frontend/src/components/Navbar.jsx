import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Flame,
  Globe2,
  HeartPulse,
  Radio,
  ShieldCheck,
  Sliders,
} from 'lucide-react';

export default function Navbar({ wsStatus = 'connected' }) {
  const navItems = [
    { to: '/', label: 'Live Dashboard', icon: Activity, exact: true },
    { to: '/stations', label: 'AWS Stations', icon: Globe2 },
    { to: '/anomalies', label: 'Anomalies', icon: AlertTriangle },
    { to: '/alerts', label: 'Alerts Feed', icon: Radio },
    { to: '/health', label: 'Sensor Health', icon: HeartPulse },
    { to: '/demo', label: 'Demo Center', icon: Sliders, badge: 'SIH Live' },
  ];

  return (
    <header className="sticky top-0 z-50 bg-slate-900/90 backdrop-blur-md border-b border-slate-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo & IMD Header */}
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-blue-600 to-cyan-400 p-0.5 shadow-lg shadow-blue-500/20">
              <div className="h-full w-full bg-slate-900 rounded-[10px] flex items-center justify-center">
                <ShieldCheck className="h-6 w-6 text-cyan-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-lg font-bold tracking-tight text-white">SkyGuard<span className="text-cyan-400">.AI</span></span>
                <span className="px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider bg-blue-500/20 text-blue-300 rounded border border-blue-500/30">
                  SIH26073
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-medium">MoES / IMD Weather Station Monitor</p>
            </div>
          </div>

          {/* Nav Links */}
          <nav className="hidden md:flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.exact}
                  className={({ isActive }) =>
                    `flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-blue-600/20 text-cyan-300 border border-blue-500/30 shadow-inner'
                        : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
                    }`
                  }
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="ml-1 px-1.5 py-0.2 text-[9px] font-bold uppercase bg-amber-500/20 text-amber-300 border border-amber-500/40 rounded-full animate-pulse">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </nav>

          {/* Live Status Indicator */}
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700 text-xs">
              <span className={`h-2 w-2 rounded-full ${
                wsStatus === 'connected' ? 'bg-emerald-400 animate-ping' : wsStatus === 'connecting' ? 'bg-amber-400' : 'bg-red-500'
              }`} />
              <span className="text-slate-300 font-mono text-[11px] uppercase tracking-wide">
                {wsStatus === 'connected' ? 'Live Stream' : wsStatus}
              </span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
