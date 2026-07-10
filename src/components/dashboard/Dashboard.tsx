import { useState, useMemo } from 'react';
import { useQuery, useSubscription } from '@apollo/client';
import { Responsive, WidthProvider } from 'react-grid-layout';
import { GET_REVENUE_METRICS, GET_ACTIVE_USERS, GET_INVENTORY_METRICS, SUBSCRIBE_KPI_UPDATES } from '@/graphql/queries';
import { RevenueMetrics, ActiveUsersMetrics, InventoryMetrics, KPIData } from '@/types';
import KPICard from './KPICard';
import RevenueChart from './RevenueChart';
import UsersChart from './UsersChart';
import InventoryChart from './InventoryChart';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const ResponsiveGridLayout = WidthProvider(Responsive);

const defaultLayouts = {
  lg: [
    { i: 'kpi-revenue', x: 0, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
    { i: 'kpi-users', x: 3, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
    { i: 'kpi-inventory', x: 6, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
    { i: 'kpi-churn', x: 9, y: 0, w: 3, h: 2, minW: 2, minH: 2 },
    { i: 'revenue-chart', x: 0, y: 2, w: 8, h: 5, minW: 4, minH: 3 },
    { i: 'users-chart', x: 8, y: 2, w: 4, h: 5, minW: 3, minH: 3 },
    { i: 'inventory-chart', x: 0, y: 7, w: 6, h: 5, minW: 4, minH: 3 },
    { i: 'revenue-breakdown', x: 6, y: 7, w: 6, h: 5, minW: 4, minH: 3 },
  ],
  md: [
    { i: 'kpi-revenue', x: 0, y: 0, w: 5, h: 2 },
    { i: 'kpi-users', x: 5, y: 0, w: 5, h: 2 },
    { i: 'kpi-inventory', x: 0, y: 2, w: 5, h: 2 },
    { i: 'kpi-churn', x: 5, y: 2, w: 5, h: 2 },
    { i: 'revenue-chart', x: 0, y: 4, w: 10, h: 5 },
    { i: 'users-chart', x: 0, y: 9, w: 10, h: 4 },
    { i: 'inventory-chart', x: 0, y: 13, w: 10, h: 4 },
    { i: 'revenue-breakdown', x: 0, y: 17, w: 10, h: 4 },
  ],
  sm: [
    { i: 'kpi-revenue', x: 0, y: 0, w: 6, h: 2 },
    { i: 'kpi-users', x: 0, y: 2, w: 6, h: 2 },
    { i: 'kpi-inventory', x: 0, y: 4, w: 6, h: 2 },
    { i: 'kpi-churn', x: 0, y: 6, w: 6, h: 2 },
    { i: 'revenue-chart', x: 0, y: 8, w: 6, h: 5 },
    { i: 'users-chart', x: 0, y: 13, w: 6, h: 4 },
    { i: 'inventory-chart', x: 0, y: 17, w: 6, h: 4 },
    { i: 'revenue-breakdown', x: 0, y: 21, w: 6, h: 4 },
  ],
};

export default function Dashboard() {
  const [layouts, setLayouts] = useState(defaultLayouts);

  const { data: revenueData, loading: revenueLoading } = useQuery<{ revenueMetrics: RevenueMetrics }>(
    GET_REVENUE_METRICS,
    {
      variables: {
        dateRange: {
          start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          end: new Date().toISOString().split('T')[0],
        },
      },
      pollInterval: 60000,
    }
  );

  const { data: usersData, loading: usersLoading } = useQuery<{ activeUsers: ActiveUsersMetrics }>(
    GET_ACTIVE_USERS,
    {
      variables: {
        dateRange: {
          start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          end: new Date().toISOString().split('T')[0],
        },
      },
      pollInterval: 60000,
    }
  );

  const { data: inventoryData, loading: inventoryLoading } = useQuery<{ inventoryMetrics: InventoryMetrics }>(
    GET_INVENTORY_METRICS,
    {
      variables: {
        dateRange: {
          start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          end: new Date().toISOString().split('T')[0],
        },
      },
      pollInterval: 60000,
    }
  );

  // Real-time KPI subscription
  const { data: kpiSubData } = useSubscription<{ kpiUpdated: KPIData }>(SUBSCRIBE_KPI_UPDATES);

  const revenue = revenueData?.revenueMetrics;
  const users = usersData?.activeUsers;
  const inventory = inventoryData?.inventoryMetrics;

  const kpiCards = useMemo(() => [
    {
      id: 'kpi-revenue',
      name: 'Total Revenue',
      value: revenue?.totalRevenue ?? 0,
      previousValue: revenue ? revenue.totalRevenue / (1 + revenue.revenueGrowth) : 0,
      format: 'currency' as const,
      trend: (revenue?.revenueGrowth ?? 0) >= 0 ? 'up' as const : 'down' as const,
      change: revenue?.revenueGrowth ?? 0,
      sparkline: revenue?.dailyRevenue.map(d => d.value) ?? [],
    },
    {
      id: 'kpi-users',
      name: 'Active Users',
      value: users?.dailyActiveUsers ?? 0,
      previousValue: users ? users.dailyActiveUsers / (1 + users.userGrowthRate) : 0,
      format: 'number' as const,
      trend: (users?.userGrowthRate ?? 0) >= 0 ? 'up' as const : 'down' as const,
      change: users?.userGrowthRate ?? 0,
      sparkline: users?.dailyActiveUsersTrend.map(d => d.value) ?? [],
    },
    {
      id: 'kpi-inventory',
      name: 'Inventory Turns',
      value: inventory?.inventoryTurns ?? 0,
      previousValue: 0,
      format: 'decimal' as const,
      trend: 'up' as const,
      change: 0,
      sparkline: inventory?.turnoverByCategory.map(c => c.value) ?? [],
    },
    {
      id: 'kpi-churn',
      name: 'Stockout Risk',
      value: inventory?.stockoutRiskCount ?? 0,
      previousValue: 0,
      format: 'number' as const,
      trend: (inventory?.stockoutRiskCount ?? 0) > 10 ? 'down' as const : 'up' as const,
      change: 0,
      sparkline: inventory?.stockoutTrend.map(d => d.value) ?? [],
    },
  ], [revenue, users, inventory]);

  const loading = revenueLoading || usersLoading || inventoryLoading;

  return (
    <div className="p-6 h-full">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Executive Dashboard</h1>
          <p className="text-gray-400 text-sm mt-1">
            Real-time business intelligence · Last updated: {new Date().toLocaleTimeString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
          </span>
          <span className="text-sm text-gray-400">Live</span>
        </div>
      </div>

      {/* Grid Layout */}
      <ResponsiveGridLayout
        className="layout"
        layouts={layouts}
        breakpoints={{ lg: 1200, md: 996, sm: 768 }}
        cols={{ lg: 12, md: 10, sm: 6 }}
        rowHeight={40}
        onLayoutChange={(_currentLayout, allLayouts) => setLayouts(allLayouts)}
        draggableHandle=".drag-handle"
        isResizable={true}
      >
        {/* KPI Cards */}
        {kpiCards.map((kpi) => (
          <div key={kpi.id}>
            <KPICard
              name={kpi.name}
              value={kpi.value}
              format={kpi.format}
              trend={kpi.trend}
              change={kpi.change}
              sparkline={kpi.sparkline}
              loading={loading}
            />
          </div>
        ))}

        {/* Revenue Chart */}
        <div key="revenue-chart">
          <RevenueChart data={revenue} loading={revenueLoading} />
        </div>

        {/* Users Chart */}
        <div key="users-chart">
          <UsersChart data={users} loading={usersLoading} />
        </div>

        {/* Inventory Chart */}
        <div key="inventory-chart">
          <InventoryChart data={inventory} loading={inventoryLoading} />
        </div>

        {/* Revenue Breakdown */}
        <div key="revenue-breakdown">
          <RevenueChart data={revenue} loading={revenueLoading} variant="breakdown" />
        </div>
      </ResponsiveGridLayout>
    </div>
  );
}
