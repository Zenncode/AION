import { useMemo } from 'react';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, Tooltip, Legend } from 'chart.js';
import { Bar, Line, Doughnut, Scatter } from 'react-chartjs-2';
import { ChartData } from '@/types';
import { HiArrowDownTray } from 'react-icons/hi2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, Tooltip, Legend);

interface ChartRendererProps {
  data: ChartData;
}

const COLORS = [
  'rgba(37, 99, 235, 0.8)',
  'rgba(34, 197, 94, 0.8)',
  'rgba(245, 158, 11, 0.8)',
  'rgba(239, 68, 68, 0.8)',
  'rgba(168, 85, 247, 0.8)',
  'rgba(236, 72, 153, 0.8)',
  'rgba(20, 184, 166, 0.8)',
  'rgba(249, 115, 22, 0.8)',
];

export default function ChartRenderer({ data }: ChartRendererProps) {
  const chartData = useMemo(() => {
    const datasets = data.datasets.map((ds, i) => ({
      ...ds,
      backgroundColor: ds.backgroundColor || COLORS[i % COLORS.length],
      borderColor: ds.borderColor || COLORS[i % COLORS.length].replace('0.8', '1'),
      borderWidth: ds.borderWidth ?? 1,
      fill: data.type === 'line' ? (ds.fill ?? true) : false,
      tension: ds.tension ?? 0.4,
    }));

    return { labels: data.labels, datasets };
  }, [data]);

  const options = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: data.datasets.length > 1,
          position: 'top' as const,
          labels: { color: '#94a3b8', usePointStyle: true, pointStyleWidth: 8, padding: 16 },
        },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#f8fafc',
          bodyColor: '#94a3b8',
          borderColor: '#334155',
          borderWidth: 1,
          padding: 12,
        },
      },
      scales:
        data.type === 'doughnut'
          ? undefined
          : {
              x: {
                grid: { color: 'rgba(51, 65, 85, 0.5)' },
                ticks: { color: '#94a3b8', maxTicksLimit: 12 },
              },
              y: {
                grid: { color: 'rgba(51, 65, 85, 0.5)' },
                ticks: { color: '#94a3b8' },
              },
            },
    }),
    [data]
  );

  const ChartComponent = useMemo(() => {
    switch (data.type) {
      case 'line':
        return Line;
      case 'doughnut':
        return Doughnut;
      case 'scatter':
        return Scatter;
      default:
        return Bar;
    }
  }, [data.type]);

  return (
    <div className="bg-[#1e293b] rounded-xl border border-[#334155] p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-medium text-gray-300">{data.title || 'Chart'}</h4>
        <button
          onClick={() => {
            const canvas = document.querySelector('canvas');
            if (canvas) {
              const link = document.createElement('a');
              link.download = `${data.title || 'chart'}.png`;
              link.href = canvas.toDataURL('image/png');
              link.click();
            }
          }}
          className="p-1 rounded text-gray-500 hover:text-gray-300 transition-colors"
          title="Download chart"
        >
          <HiArrowDownTray className="w-4 h-4" />
        </button>
      </div>
      <div style={{ height: '280px' }}>
        <ChartComponent data={chartData} options={options} />
      </div>
    </div>
  );
}
