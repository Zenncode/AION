import { useMemo } from 'react';
import { Line, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { RevenueMetrics } from '@/types';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend, Filler);

interface RevenueChartProps {
  data: RevenueMetrics | undefined;
  loading: boolean;
  variant?: 'trend' | 'breakdown';
}

export default function RevenueChart({ data, loading, variant = 'trend' }: RevenueChartProps) {
  const chartData = useMemo(() => {
    if (!data) return null;

    if (variant === 'breakdown') {
      return {
        labels: data.revenueByRegion.map((r) => r.region),
        datasets: [
          {
            label: 'Revenue by Region',
            data: data.revenueByRegion.map((r) => r.value),
            backgroundColor: [
              'rgba(37, 99, 235, 0.8)',
              'rgba(34, 197, 94, 0.8)',
              'rgba(245, 158, 11, 0.8)',
              'rgba(239, 68, 68, 0.8)',
              'rgba(168, 85, 247, 0.8)',
            ],
            borderColor: [
              'rgb(37, 99, 235)',
              'rgb(34, 197, 94)',
              'rgb(245, 158, 11)',
              'rgb(239, 68, 68)',
              'rgb(168, 85, 247)',
            ],
            borderWidth: 1,
            borderRadius: 6,
          },
        ],
      };
    }

    return {
      labels: data.dailyRevenue.map((d) =>
        new Date(d.date).toLocaleDateString('en-EU', { month: 'short', day: 'numeric' })
      ),
      datasets: [
        {
          label: 'Daily Revenue (EUR)',
          data: data.dailyRevenue.map((d) => d.value),
          borderColor: 'rgb(37, 99, 235)',
          backgroundColor: 'rgba(37, 99, 235, 0.1)',
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4,
          borderWidth: 2,
        },
      ],
    };
  }, [data, variant]);

  const options = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#f8fafc',
          bodyColor: '#94a3b8',
          borderColor: '#334155',
          borderWidth: 1,
          padding: 12,
          displayColors: false,
          callbacks: {
            label: (ctx: any) =>
              `${ctx.dataset.label}: €${ctx.parsed.y.toLocaleString()}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(51, 65, 85, 0.5)' },
          ticks: { color: '#94a3b8', maxTicksLimit: 10 },
        },
        y: {
          grid: { color: 'rgba(51, 65, 85, 0.5)' },
          ticks: {
            color: '#94a3b8',
            callback: (v: number | string) => `€${Number(v).toLocaleString()}`,
          },
        },
      },
    }),
    []
  );

  if (loading) {
    return (
      <div className="bg-[#1e293b] rounded-xl border border-[#334155] p-5 h-full animate-pulse">
        <div className="h-4 bg-[#334155] rounded w-32 mb-4" />
        <div className="h-full bg-[#334155] rounded" />
      </div>
    );
  }

  return (
    <div className="bg-[#1e293b] rounded-xl border border-[#334155] p-5 h-full flex flex-col">
      <div className="drag-handle cursor-grab active:cursor-grabbing mb-3 flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-400">
          {variant === 'breakdown' ? 'Revenue by Region' : 'Revenue Trend'}
        </h3>
        {data && (
          <span className="text-xs text-gray-500">
            MTD: €{data.mtdRevenue.toLocaleString()}
          </span>
        )}
      </div>
      <div className="flex-1 min-h-0 relative">
        {chartData && (
          variant === 'breakdown' ? (
            <Bar data={chartData} options={options} />
          ) : (
            <Line data={chartData} options={options} />
          )
        )}
      </div>
    </div>
  );
}
