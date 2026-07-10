// =============================================================================
// AION Frontend — TypeScript Type Definitions
// =============================================================================

// --- KPI Dashboard ---

export interface KPIData {
  id: string;
  name: string;
  value: number;
  previousValue: number;
  unit: string;
  format: 'currency' | 'number' | 'percent' | 'decimal';
  trend: 'up' | 'down' | 'flat';
  sparkline: number[];
  updatedAt: string;
}

export interface RevenueMetrics {
  totalRevenue: number;
  mtdRevenue: number;
  revenueGrowth: number;
  avgOrderValue: number;
  dailyRevenue: TimeSeriesPoint[];
  revenueByRegion: RegionalBreakdown[];
  revenueBySegment: SegmentBreakdown[];
}

export interface ActiveUsersMetrics {
  totalActiveUsers: number;
  dailyActiveUsers: number;
  weeklyActiveUsers: number;
  monthlyActiveUsers: number;
  userGrowthRate: number;
  dailyActiveUsersTrend: TimeSeriesPoint[];
  usersByRegion: RegionalBreakdown[];
}

export interface InventoryMetrics {
  totalInventoryValue: number;
  inventoryTurns: number;
  stockoutRiskCount: number;
  overstockCount: number;
  avgDaysOfSupply: number;
  turnoverByCategory: CategoryBreakdown[];
  stockoutTrend: TimeSeriesPoint[];
}

export interface TimeSeriesPoint {
  date: string;
  value: number;
  label?: string;
}

export interface RegionalBreakdown {
  region: string;
  value: number;
  percentage: number;
}

export interface SegmentBreakdown {
  segment: string;
  value: number;
  percentage: number;
}

export interface CategoryBreakdown {
  category: string;
  value: number;
  quantity: number;
}

// --- Copilot ---

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sqlQuery?: string;
  chartData?: ChartData;
  sqlResults?: Record<string, unknown>[];
  timestamp: string;
  modelUsed?: string;
  latencyMs?: number;
  guardrailFlags?: GuardrailFlag[];
}

export interface ChartData {
  type: 'line' | 'bar' | 'pie' | 'scatter' | 'doughnut';
  labels: string[];
  datasets: ChartDataset[];
  title?: string;
}

export interface ChartDataset {
  label: string;
  data: number[];
  backgroundColor?: string | string[];
  borderColor?: string;
  borderWidth?: number;
  fill?: boolean;
  tension?: number;
}

export interface GuardrailFlag {
  type: string;
  severity: string;
  message: string;
}

export interface ChatRequest {
  question: string;
  userId?: string;
  conversationId?: string;
  maxResults?: number;
  modelPreference?: 'claude' | 'openai';
}

export interface ChatResponse {
  answer: string;
  sqlQuery: string | null;
  sqlResults: Record<string, unknown>[] | null;
  retrievedContext: string[] | null;
  guardrailFlags: GuardrailFlag[];
  modelUsed: string | null;
  tokensUsed: number;
  latencyMs: number;
}

// --- Data Grid ---

export interface DataGridColumn {
  headerName: string;
  field: string;
  type?: 'text' | 'number' | 'date' | 'boolean';
  sortable?: boolean;
  filter?: boolean;
  width?: number;
}

export interface DataGridRequest {
  startRow: number;
  endRow: number;
  sortModel: SortModel[];
  filterModel: FilterModel;
}

export interface DataGridResponse {
  rows: Record<string, unknown>[];
  totalCount: number;
}

export interface SortModel {
  colId: string;
  sort: 'asc' | 'desc';
}

export interface FilterModel {
  [key: string]: {
    type: string;
    filter: unknown;
  };
}

// --- Auth ---

export interface User {
  id: string;
  email: string;
  name: string;
  roles: string[];
}
