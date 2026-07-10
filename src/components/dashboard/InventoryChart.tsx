import { useMemo } from 'react';
import { Bar, Line } from 'react-chartjs-2';
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
} from 'chart.js';
import { InventoryMetrics } from '@/types';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend);

interface InventoryChartProps {
  data: InventoryMetrics | undefined;
  loading: boolean;
}

export default function InventoryChart({ data, loading }: InventoryChartProps) {
  const turnoverData = useMemo(() => {
    if (!data) return null;
    return {
      labels: data.turnoverByCategory.map((c) => c.category),
      datasets: [
        {
          label: 'Inventory Turns',
          data: data.turnoverByCategory.map((c) => c.value),
          backgroundColor: 'rgba(245, 158, 11, 0.8)',
          borderColor: 'rgb(245, 158, 11)',
          borderWidth: 1,
          borderRadius: 6,
        },
      ],
    };
  }, [data]);

  const stockoutData = useMemo(() => {
    if (!data) return null;
    return {
      labels: data.stockoutTrend.map((d) =>
        new Date(d.date).toLocaleDateString('en-EU', { month: 'short', day: 'numeric' })
      ),
      datasets: [
        {
          label: 'Stockout Risk Items',
          data: data.stockoutTrend.map((d) => d.value),
          borderColor: 'rgb(239, 68, 68)',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    };
  }, [data]);

  const barOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y' as const,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#f8fafc',
          bodyColor: '#94a3b8',
          borderColor: '#334155',
          borderWidth: 1,
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(51, 65, 85, 0.5)' },
          ticks: { color: '#94a3b8' },
        },
        y: {
          grid: { display: false },
          ticks: { color: '#94a3b8' },
        },
      },
    }),
    []
  );

  const lineOptions = useMemo(
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
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(51, 65, 85, 0.5)' },
          ticks: { color: '#94a3b8', maxTicksLimit: 8 },
        },
        y: {
          grid: { color: 'rgba(51, 65, 85, 0.5)' },
          ticks: { color: '#94a3b8' },
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
        <h3 className="text-sm font-medium text-gray-400">Inventory Health</h3>
        {data && (
          <div className="flex gap-3 text-xs">
            <span className="text-yellow-400">● {data.stockoutRiskCount} at risk</span>
            <span className="text-red-400">● {data.overstockCount} overstock</span>
          </div>
        )}
      </div>
      <div className="flex-1 min-h-0 grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-gray-500 mb-2">Turns by Category</p>
          <div className="h-full">
            {turnoverData && <Bar data={turnoverData} options={barOptions} />}
          </div>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-2">Stockout Trend</p>
          <div className="h-full">
            {stockoutData && <Line data={stockoutData} options={lineOptions} />}
          </div>
        </div>
      </div>
    </div>
  );
}
