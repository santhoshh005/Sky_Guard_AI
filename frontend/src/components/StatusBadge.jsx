import React from 'react';

export default function StatusBadge({ status = 'normal', size = 'md' }) {
  const norm = String(status || 'normal').toLowerCase();

  const styles = {
    // Health status
    healthy: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shadow-[0_0_10px_rgba(52,211,153,0.15)]',
    degraded: 'bg-amber-500/10 text-amber-400 border-amber-500/30 shadow-[0_0_10px_rgba(251,191,36,0.15)]',
    maintenance_recommended: 'bg-rose-500/15 text-rose-400 border-rose-500/40 shadow-[0_0_12px_rgba(244,63,94,0.2)]',
    sensor_critical: 'bg-rose-600/25 text-rose-300 border-rose-500/50 animate-pulse shadow-[0_0_15px_rgba(244,63,94,0.3)]',

    // Severity
    normal: 'bg-slate-500/10 text-slate-300 border-slate-600/30',
    info: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
    warning: 'bg-amber-500/15 text-amber-300 border-amber-500/40 font-bold',
    critical: 'bg-rose-500/20 text-rose-300 border-rose-500/50 font-bold animate-pulse',

    // Root causes
    spike: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
    frozen: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    drift: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
    communication: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    multivariate: 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30',
  };

  const style = styles[norm] || styles.normal;
  const sizeClasses =
    size === 'sm'
      ? 'px-2 py-0.5 text-[10px]'
      : size === 'lg'
      ? 'px-3.5 py-1.5 text-xs'
      : 'px-2.5 py-1 text-[11px]';

  const label = norm.replace(/_/g, ' ').toUpperCase();

  return (
    <span
      className={`inline-flex items-center font-mono font-bold rounded-md border tracking-wider transition-all ${sizeClasses} ${style}`}
    >
      <span className="h-1.5 w-1.5 rounded-full mr-1.5 bg-current opacity-80 animate-ping" style={{ animationDuration: '3s' }} />
      {label}
    </span>
  );
}
