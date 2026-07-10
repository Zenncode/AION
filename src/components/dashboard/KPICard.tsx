import { useMemo } from 'react';
import { HiArrowTrendingUp, HiArrowTrendingDown, HiArrowsRightLeft } from 'react-icons/hi2';

interface KPICardProps {
  name: string;
  value: number;
  format: 'currency' | 'number' | 'percent' | 'decimal';
  trend: 'up' | 'down' | 'flat';
  change: number;
  sparkline: number[];
  loading: boolean;
}

export default function KPICard({ name, value, format, trend, change, sparkline, loading }: KPICardProps) {
  const formattedValue = useMemo(() => {
    switch (format) {
      case 'currency':
        return new Intl.NumberFormat('en-EU', {
          style: 'currency',
          currency: 'EUR',
          notation: 'compact',
          maximumFractionDigits: 1,
        }).format(value);
      case 'percent':
        return `${(value * 100).toFixed(1)}%`;
      case 'decimal':
        return value.toFixed(2);
      default:
        return new Intl.NumberFormat('en-US', {
          notation: 'compact',
          maximumFractionDigits: 1,
        }).format(value);
    }
  }, [value, format]);

  const sparklinePath = useMemo(() => {
    if (sparkline.length < 2) return '';
    const max = Math.max(...sparkline);
    const min = Math.min(...sparkline);
    const range = max - min || 1;
    const width = 120;
    const height = 32;
    const step = width / (sparkline.length - 1);

    return sparkline
      .map((v, i) => {
        const x = i * step;
        const y = height - ((v - min) / range) * height;
        return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
      })
      .join(' ');
  }, [sparkline]);

  const TrendIcon = trend === 'up' ? HiArrowTrendingUp : trend === 'down' ? HiArrowTrendingDown : HiArrowsRightLeft;
  const trendColor = trend === 'up' ? 'text-green-400' : trend === 'down' ? 'text-red-400' : 'text-gray-400';

  if (loading) {
    return (
      <div className="bg-[#1e293b] rounded-xl border border-[#334155] p-5 h-full animate-pulse">
        <div className="h-4 bg-[#334155] rounded w-24 mb-3" />
        <div className="h-8 bg-[#334155] rounded w-32 mb-2" />
        <div className="h-3 bg-[#334155] rounded w-16" />
      </div>
    );
  }

  return (
    <div className="bg-[#1e293b] rounded-xl border border-[#334155] p-5 h-full flex flex-col justify-between hover:border-blue-500/30 transition-colors group">
      <div className="drag-handle cursor-grab active:cursor-grabbing">
        <p className="text-gray-400 text-sm font-medium">{name}</p>
      </div>

      <div className="flex items-end justify-between mt-2">
        <div>
          <p className="text-2xl font-bold tracking-tight">{formattedValue}</p>
          <div className={`flex items-center gap-1 mt-1 text-sm ${trendColor}`}>
            <TrendIcon className="w-4 h-4" />
            <span className="font-medium">
              {change >= 0 ? '+' : ''}{(change * 100).toFixed(1)}%
            </span>
            <span className="text-gray-500">vs prev</span>
          </div>
        </div>

        {/* Sparkline */}
        {sparkline.length > 1 && (
          <svg width="120" height="32" className="opacity-50 group-hover:opacity-100 transition-opacity">
            <path
              d={sparklinePath}
              fill="none"
              stroke={trend === 'up' ? '#22c55e' : trend === 'down' ? '#ef4444' : '#94a3b8'}
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </div>
    </div>
  );
}
