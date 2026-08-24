import React from 'react';

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  color = 'cyan',
  trend = null,
  alert = false,
}) {
  const colorConfigs = {
    cyan: {
      lightBar: 'from-transparent via-cyan-400 to-transparent',
      iconBg: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20 shadow-cyan-500/10',
      valueColor: 'text-cyan-300',
    },
    emerald: {
      lightBar: 'from-transparent via-emerald-400 to-transparent',
      iconBg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20 shadow-emerald-500/10',
      valueColor: 'text-emerald-300',
    },
    amber: {
      lightBar: 'from-transparent via-amber-400 to-transparent',
      iconBg: 'bg-amber-500/10 text-amber-400 border-amber-500/20 shadow-amber-500/10',
      valueColor: 'text-amber-300',
    },
    crimson: {
      lightBar: 'from-transparent via-rose-500 to-transparent',
      iconBg: 'bg-rose-500/15 text-rose-400 border-rose-500/30 shadow-rose-500/15',
      valueColor: 'text-rose-300',
    },
    purple: {
      lightBar: 'from-transparent via-purple-400 to-transparent',
      iconBg: 'bg-purple-500/10 text-purple-400 border-purple-500/20 shadow-purple-500/10',
      valueColor: 'text-purple-300',
    },
  };

  const current = colorConfigs[color] || colorConfigs.cyan;

  return (
    <div
      className={`relative overflow-hidden rounded-xl border bg-[#08122c]/75 backdrop-blur-md p-4 sm:p-5 shadow-xl transition-all duration-300 hover:border-cyan-500/40 hover:shadow-2xl hover:shadow-cyan-500/10 hover:-translate-y-0.5 ${
        alert ? 'border-rose-500/50 ring-1 ring-rose-500/30' : 'border-cyan-500/15'
      }`}
    >
      {/* Top glowing lightbar */}
      <div className={`absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r ${current.lightBar}`} />

      <div className="flex items-center justify-between">
        <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-slate-400">
          {title}
        </span>
        {Icon && (
          <div className={`rounded-lg p-2 border shadow-inner ${current.iconBg}`}>
            <Icon className="h-4 w-4" />
          </div>
        )}
      </div>

      <div className="mt-3 flex items-baseline justify-between">
        <span className={`text-2xl sm:text-3xl font-black tracking-tight font-mono ${current.valueColor}`}>
          {value}
        </span>
        {trend && (
          <span className="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
            {trend}
          </span>
        )}
      </div>

      {subtitle && (
        <p className="mt-1.5 text-[11px] text-slate-400 font-medium truncate">
          {subtitle}
        </p>
      )}
    </div>
  );
}
