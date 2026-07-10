import { useMemo } from 'react';
import { Line, Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { ActiveUsersMetrics } from '@/types';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, ArcElement, Title, Tooltip, Legend, Filler);

interface UsersChartProps {
  data: ActiveUsersMetrics | undefined;
  loading: boolean;
}

export default function UsersChart({ data, loading }: UsersChartProps) {
  const lineData = useMemo(() => {
    if (!data) return null;
    return {
      labels: data.dailyActiveUsersTrend.map((d) =>
        new Date(d.date).toLocaleDateString('en-EU', { month: 'short', day: 'numeric' })
      ),
      datasets: [
        {
          label: 'Daily Active Users',
          data: data.dailyActiveUsersTrend.map((d) => d.value),
          borderColor: 'rgb(34, 197, 94)',
          backgroundColor: 'rgba(34, 197, 94, 0.1)',
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4,
          borderWidth: 2,
        },
      ],
    };
  }, [data]);

  const doughnutData = useMemo(() => {
    if (!data) return null;
    return {
      labels: data.usersByRegion.map((r) => r.region),
      datasets: [
        {
          data: data.usersByRegion.map((r) => r.value),
          backgroundColor: [
            'rgba(37, 99, 235, 0.8)',
            'rgba(34, 197, 94, 0.8)',
            'rgba(245, 158, 11, 0.8)',
            'rgba(239, 68, 68, 0.8)',
          ],
          borderColor: 'transparent',
          borderWidth: 0,
        },
      ],
    };
  }, [data]);

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
          padding: 12,
          displayColors: false,
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(51, 65, 85, 0.5)' },
          ticks: { color: '#94a3b8', maxTicksLimit: 6 },
        },
        y: {
          grid: { color: 'rgba(51, 65, 85, 0.5)' },
          ticks: { color: '#94a3b8' },
        },
      },
    }),
    []
  );

  const doughnutOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: {
        legend: {
          position: 'bottom' as const,
          labels: { color: '#94a3b8', padding: 12, usePointStyle: true, pointStyleWidth: 8 },
        },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#f8fafc',
          bodyColor: '#94a3b8',
          borderColor: '#334155',
          borderWidth: 1,
        },
      },
    }),
    []
  );

  if (loading) {
    return (
      <div className="bg-[#1e293b] rounded-xl border border-[#334155] p-5 h-full animate-pulse">
        <div className="h-4 bg-[#334155] rounded w-28 mb-4" />
        <div className="h-full bg-[#334155] rounded" />
      </div>
    );
  }

  return (
    <div className="bg-[#1e293b] rounded-xl border border-[#334155] p-5 h-full flex flex-col">
      <div className="drag-handle cursor-grab active:cursor-grabbing mb-3">
        <h3 className="text-sm font-medium text-gray-400">Active Users</h3>
        {data && (
          <div className="flex gap-4 mt-2">
            <div>
              <p className="text-lg font-bold">{data.dailyActiveUsers.toLocaleString()}</p>
              <p className="text-xs text-gray-500">Today</p>
            </div>
            <div>
              <p className="text-lg font-bold">{data.weeklyActiveUsers.toLocaleString()}</p>
              <p className="text-xs text-gray-500">This Week</p>
            </div>
            <div>
              <p className="text-lg font-bold">{data.monthlyActiveUsers.toLocaleString()}</p>
              <p className="text-xs text-gray-500">This Month</p>
            </div>
          </div>
        )}
      </div>
      <div className="flex-1 min-h-0 flex flex-col gap-4">
        <div className="flex-1 min-h-0">
          {lineData && <Line data={lineData} options={lineOptions} />}
        </div>
        <div className="h-32">
          {doughnutData && <Doughnut data={doughnutData} options={doughnutOptions} />}
        </div>
      </div>
    </div>
  );
}
