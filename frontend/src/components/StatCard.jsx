import React from 'react';

export default function StatCard({ title, value, subtitle, icon: Icon, color = 'blue', alert = false }) {
  const colorStyles = {
    blue: 'border-blue-500/20 from-blue-950/40 to-slate-900/60 text-cyan-400',
    emerald: 'border-emerald-500/20 from-emerald-950/40 to-slate-900/60 text-emerald-400',
    amber: 'border-amber-500/20 from-amber-950/40 to-slate-900/60 text-amber-400',
    red: 'border-red-500/20 from-red-950/40 to-slate-900/60 text-red-400',
    purple: 'border-purple-500/20 from-purple-950/40 to-slate-900/60 text-purple-400',
  };

  const currentStyle = colorStyles[color] || colorStyles.blue;

  return (
    <div className={`relative overflow-hidden rounded-xl border bg-gradient-to-b p-5 shadow-lg backdrop-blur-sm transition-all hover:scale-[1.01] ${currentStyle} ${alert ? 'ring-1 ring-red-500/50' : ''}`}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</p>
        {Icon && (
          <div className="rounded-lg bg-slate-800/80 p-2.5 border border-slate-700/60">
            <Icon className="h-5 w-5" />
          </div>
        )}
      </div>
      <div className="mt-3 flex items-baseline justify-between">
        <p className="text-3xl font-extrabold tracking-tight text-white font-mono">{value}</p>
      </div>
      {subtitle && <p className="mt-2 text-xs text-slate-400 font-medium">{subtitle}</p>}
    </div>
  );
}
