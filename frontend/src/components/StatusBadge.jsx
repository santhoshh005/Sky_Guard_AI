import React from 'react';

export default function StatusBadge({ status = 'normal', size = 'md' }) {
  const norm = String(status || 'normal').toLowerCase();

  const styles = {
    // Health status
    healthy: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    degraded: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    maintenance_recommended: 'bg-red-500/15 text-red-400 border-red-500/30',
    sensor_critical: 'bg-rose-600/25 text-rose-300 border-rose-500/40 animate-pulse',

    // Severity
    normal: 'bg-slate-500/15 text-slate-300 border-slate-600/30',
    info: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
    warning: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    critical: 'bg-red-500/20 text-red-300 border-red-500/40 font-bold animate-pulse',

    // Root causes
    spike: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
    frozen: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
    drift: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
    communication: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
    multivariate: 'bg-fuchsia-500/20 text-fuchsia-300 border-fuchsia-500/40',
  };

  const style = styles[norm] || styles.normal;
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : size === 'lg' ? 'px-3 py-1 text-sm' : 'px-2.5 py-1 text-xs';

  const label = norm.replace(/_/g, ' ').toUpperCase();

  return (
    <span className={`inline-flex items-center font-semibold rounded-md border tracking-wider ${sizeClasses} ${style}`}>
      <span className="h-1.5 w-1.5 rounded-full mr-1.5 bg-current opacity-75" />
      {label}
    </span>
  );
}
