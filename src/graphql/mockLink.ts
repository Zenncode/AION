import { ApolloLink, Observable, FetchResult } from '@apollo/client';

// =============================================================================
// Mock Metrics & Time Series
// =============================================================================

const mockRevenueMetrics = {
  totalRevenue: 1420500,
  mtdRevenue: 340200,
  revenueGrowth: 0.124,
  avgOrderValue: 84.5,
  dailyRevenue: [
    { date: '2026-06-11', value: 42000 },
    { date: '2026-06-12', value: 45000 },
    { date: '2026-06-13', value: 39000 },
    { date: '2026-06-14', value: 31000 },
    { date: '2026-06-15', value: 48000 },
    { date: '2026-06-16', value: 52000 },
    { date: '2026-06-17', value: 50000 },
    { date: '2026-06-18', value: 46000 },
    { date: '2026-06-19', value: 43000 },
    { date: '2026-06-20', value: 35000 },
    { date: '2026-06-21', value: 32000 },
    { date: '2026-06-22', value: 49000 },
    { date: '2026-06-23', value: 55000 },
    { date: '2026-06-24', value: 58000 },
    { date: '2026-06-25', value: 61000 },
    { date: '2026-06-26', value: 59000 },
    { date: '2026-06-27', value: 42000 },
    { date: '2026-06-28', value: 38000 },
    { date: '2026-06-29', value: 54000 },
    { date: '2026-06-30', value: 62000 },
    { date: '2026-07-01', value: 65000 },
    { date: '2026-07-02', value: 68000 },
    { date: '2026-07-03', value: 63000 },
    { date: '2026-07-04', value: 45000 },
    { date: '2026-07-05', value: 41000 },
    { date: '2026-07-06', value: 72000 },
    { date: '2026-07-07', value: 75000 },
    { date: '2026-07-08', value: 78000 },
    { date: '2026-07-09', value: 81000 },
    { date: '2026-07-10', value: 84000 }
  ],
  revenueByRegion: [
    { region: 'North America', value: 639225, percentage: 0.45 },
    { region: 'Europe', value: 426150, percentage: 0.30 },
    { region: 'Asia-Pacific', value: 213075, percentage: 0.15 },
    { region: 'Latin America', value: 142050, percentage: 0.10 }
  ],
  revenueBySegment: [
    { segment: 'Enterprise', value: 710250, percentage: 0.50 },
    { segment: 'Mid-Market', value: 426150, percentage: 0.30 },
    { segment: 'SMB', value: 284100, percentage: 0.20 }
  ]
};

const mockActiveUsers = {
  totalActiveUsers: 124500,
  dailyActiveUsers: 18450,
  weeklyActiveUsers: 68200,
  monthlyActiveUsers: 124500,
  userGrowthRate: 0.082,
  dailyActiveUsersTrend: [
    { date: '2026-06-11', value: 14200 },
    { date: '2026-06-12', value: 14500 },
    { date: '2026-06-13', value: 13900 },
    { date: '2026-06-14', value: 12100 },
    { date: '2026-06-15', value: 15100 },
    { date: '2026-06-16', value: 15800 },
    { date: '2026-06-17', value: 15500 },
    { date: '2026-06-18', value: 15200 },
    { date: '2026-06-19', value: 14800 },
    { date: '2026-06-20', value: 12500 },
    { date: '2026-06-21', value: 11900 },
    { date: '2026-06-22', value: 15900 },
    { date: '2026-06-23', value: 16400 },
    { date: '2026-06-24', value: 16800 },
    { date: '2026-06-25', value: 17200 },
    { date: '2026-06-26', value: 17000 },
    { date: '2026-06-27', value: 13500 },
    { date: '2026-06-28', value: 12800 },
    { date: '2026-06-29', value: 17400 },
    { date: '2026-06-30', value: 17900 },
    { date: '2026-07-01', value: 18100 },
    { date: '2026-07-02', value: 18300 },
    { date: '2026-07-03', value: 18000 },
    { date: '2026-07-04', value: 14200 },
    { date: '2026-07-05', value: 13500 },
    { date: '2026-07-06', value: 18500 },
    { date: '2026-07-07', value: 18900 },
    { date: '2026-07-08', value: 19100 },
    { date: '2026-07-09', value: 19400 },
    { date: '2026-07-10', value: 18450 }
  ],
  usersByRegion: [
    { region: 'North America', value: 56025, percentage: 0.45 },
    { region: 'Europe', value: 37350, percentage: 0.30 },
    { region: 'Asia-Pacific', value: 24900, percentage: 0.20 },
    { region: 'Latin America', value: 6225, percentage: 0.05 }
  ]
};

const mockInventoryMetrics = {
  totalInventoryValue: 845000,
  inventoryTurns: 6.8,
  stockoutRiskCount: 14,
  overstockCount: 8,
  avgDaysOfSupply: 18.5,
  turnoverByCategory: [
    { category: 'Electronics', value: 340000, quantity: 1200 },
    { category: 'Apparel', value: 210000, quantity: 3400 },
    { category: 'Home Goods', value: 185000, quantity: 850 },
    { category: 'Office Supplies', value: 110000, quantity: 5600 }
  ],
  stockoutTrend: [
    { date: '2026-06-11', value: 8 },
    { date: '2026-06-12', value: 9 },
    { date: '2026-06-13', value: 9 },
    { date: '2026-06-14', value: 10 },
    { date: '2026-06-15', value: 11 },
    { date: '2026-06-16', value: 12 },
    { date: '2026-06-17', value: 12 },
    { date: '2026-06-18', value: 11 },
    { date: '2026-06-19', value: 10 },
    { date: '2026-06-20', value: 10 },
    { date: '2026-06-21', value: 9 },
    { date: '2026-06-22', value: 11 },
    { date: '2026-06-23', value: 13 },
    { date: '2026-06-24', value: 14 },
    { date: '2026-06-25', value: 15 },
    { date: '2026-06-26', value: 15 },
    { date: '2026-06-27', value: 14 },
    { date: '2026-06-28', value: 13 },
    { date: '2026-06-29', value: 15 },
    { date: '2026-06-30', value: 16 },
    { date: '2026-07-01', value: 17 },
    { date: '2026-07-02', value: 16 },
    { date: '2026-07-03', value: 15 },
    { date: '2026-07-04', value: 13 },
    { date: '2026-07-05', value: 12 },
    { date: '2026-07-06', value: 14 },
    { date: '2026-07-07', value: 14 },
    { date: '2026-07-08', value: 15 },
    { date: '2026-07-09', value: 15 },
    { date: '2026-07-10', value: 14 }
  ]
};

// =============================================================================
// Mock Financial Transactions (Data Grid)
// =============================================================================

const mockTransactions = Array.from({ length: 150 }).map((_, i) => {
  const transactionId = `TX-${10000 + i}`;
  const customerId = `CUST-${20000 + (i % 23)}`;
  const orderId = `ORD-${30000 + i}`;
  const types = ['SALE', 'REFUND', 'CHARGEBACK'];
  const type = types[i % 10 === 0 ? 1 : i % 25 === 0 ? 2 : 0];
  const statuses = ['COMPLETED', 'PENDING', 'FAILED'];
  const status = statuses[i % 15 === 0 ? 1 : i % 40 === 0 ? 2 : 0];
  const amount = parseFloat((50 + (i % 7) * 45 + Math.random() * 20).toFixed(2));
  const netAmount = parseFloat((amount * 0.95).toFixed(2));
  const payments = ['CREDIT_CARD', 'PAYPAL', 'STRIPE', 'BANK_TRANSFER'];
  const payment = payments[i % 4];
  const categories = ['SOFTWARE_LICENSE', 'HARDWARE', 'CONSULTING', 'SUPPORT'];
  const category = categories[i % 4];
  const regions = ['North America', 'Europe', 'Asia-Pacific', 'Latin America'];
  const region = regions[i % 4];
  const date = new Date(Date.now() - (i * 4 * 60 * 60 * 1000)).toISOString();

  return {
    transactionId,
    customerId,
    orderId,
    transactionType: type,
    transactionStatus: status,
    amount,
    currency: 'EUR',
    netAmount,
    paymentMethod: payment,
    revenueCategory: category,
    region,
    transactionTimestamp: date,
    eventDate: date.split('T')[0]
  };
});

// =============================================================================
// Mock Customers (Data Grid)
// =============================================================================

const mockCustomers = Array.from({ length: 100 }).map((_, i) => {
  const customerId = `CUST-${20000 + i}`;
  const firstNames = ['John', 'Jane', 'Michael', 'Emily', 'David', 'Sarah', 'James', 'Jessica', 'Robert', 'Karen'];
  const lastNames = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez'];
  const customerName = `${firstNames[i % 10]} ${lastNames[(i + 3) % 10]}`;
  const segments = ['Enterprise', 'Mid-Market', 'SMB'];
  const segment = segments[i % 3];
  const tiers = ['PLATINUM', 'GOLD', 'SILVER', 'BRONZE'];
  const tier = tiers[i % 4];
  const countries = ['USA', 'Germany', 'Japan', 'Brazil', 'UK', 'France', 'Australia', 'Canada'];
  const country = countries[i % 8];
  const regions = ['North America', 'Europe', 'Asia-Pacific', 'Latin America'];
  const region = regions[i % 4];
  const totalOrders = 5 + (i % 15);
  const totalRevenue = parseFloat((totalOrders * 85 + Math.random() * 100).toFixed(2));
  const avgOrder = parseFloat((totalRevenue / totalOrders).toFixed(2));
  const rfm = parseFloat((1 + Math.random() * 4).toFixed(1));
  const churn = parseFloat(Math.random().toFixed(2));
  const ltv = parseFloat((totalRevenue * 3.5).toFixed(2));

  return {
    customerId,
    customerName,
    segment,
    tier,
    country,
    region,
    totalOrders12m: totalOrders,
    totalRevenue12m: totalRevenue,
    avgOrderValue12m: avgOrder,
    rfmCompositeScore: rfm,
    churnRiskScore: churn,
    predictedLtv: ltv,
    eventDate: new Date().toISOString().split('T')[0]
  };
});

// =============================================================================
// Mock Inventory Snapshots (Data Grid)
// =============================================================================

const mockInventory = Array.from({ length: 80 }).map((_, i) => {
  const snapshotId = `INV-SNAP-${1000 + i}`;
  const productId = `PROD-${5000 + i}`;
  const productNames = [
    'AION Enterprise Suite', 'Cognitive Sync Hub', 'Neural DB Connector',
    'Flow Orchestrator', 'Data Lake Streamer', 'Predictive Analytics Node',
    'Smart Relay Controller', 'Vector Index Engine', 'Edge Inference Guard',
    'Semantic Gateway Pro'
  ];
  const productName = productNames[i % 10] + ` (V${(i % 3) + 1})`;
  const categories = ['Software', 'Hardware Addon', 'API Service', 'Consulting Block'];
  const category = categories[i % 4];
  const warehouses = ['Central EU WH', 'US East WH', 'APAC Regional WH'];
  const warehouse = warehouses[i % 3];
  const onHand = 50 + (i % 25) * 12;
  const reserved = Math.floor(onHand * 0.2);
  const available = onHand - reserved;
  const unitCost = parseFloat((25.50 + (i % 5) * 150).toFixed(2));
  const totalValue = parseFloat((onHand * unitCost).toFixed(2));
  const daysSupply = 5 + (i % 25);
  const stockoutRisk = daysSupply < 10;

  return {
    snapshotId,
    productId,
    productName,
    productCategory: category,
    warehouseName: warehouse,
    quantityOnHand: onHand,
    quantityReserved: reserved,
    quantityAvailable: available,
    unitCost,
    totalCostValue: totalValue,
    daysOfSupply: daysSupply,
    stockoutRiskFlag: stockoutRisk,
    eventDate: new Date().toISOString().split('T')[0]
  };
});

// =============================================================================
// Mock Executive KPIs
// =============================================================================

const mockExecutiveKPIs = {
  customerCount: 1250,
  totalRevenue: 1420500,
  activeUsers: 124500,
  inventoryTurns: 6.8,
  churnRate: 0.024,
  npsScore: 72,
  avgOrderValue: 84.5,
  revenuePerUser: 11.4
};

// =============================================================================
// Mock AI Copilot Response Engine
// =============================================================================

const getMockCopilotResponse = (question: string) => {
  const q = question.toLowerCase();
  let answer = `I've analyzed the business databases. Here's what I found regarding your query: "${question}".`;
  let sqlQuery = `SELECT * FROM financial_transactions LIMIT 5;`;
  let sqlResults: any[] = [
    { region: 'North America', revenue: 639225 },
    { region: 'Europe', revenue: 426150 },
    { region: 'Asia-Pacific', revenue: 213075 },
    { region: 'Latin America', revenue: 142050 }
  ];

  if (q.includes('revenue') || q.includes('sales') || q.includes('sold')) {
    answer = `Based on the latest financial transaction ledger, our total revenue is **€1.42M**, growing at **12.4%** quarter-over-quarter. North America remains our largest segment, contributing 45% of the total revenue.`;
    sqlQuery = `SELECT region, SUM(amount) as revenue \nFROM financial_transactions \nGROUP BY region \nORDER BY revenue DESC;`;
    sqlResults = [
      { region: 'North America', revenue: 639225 },
      { region: 'Europe', revenue: 426150 },
      { region: 'Asia-Pacific', revenue: 213075 },
      { region: 'Latin America', revenue: 142050 }
    ];
  } else if (q.includes('customer') || q.includes('user')) {
    answer = `We have **124.5k** active users. The composite RFM scores segment our Platinum tier customers as contributing the highest customer lifetime value (LTV). Churn risk is relatively low at an average of **2.4%** across high-tier users.`;
    sqlQuery = `SELECT tier, COUNT(customerId) as users, AVG(churnRiskScore) as avg_churn \nFROM customer_360 \nGROUP BY tier;`;
    sqlResults = [
      { tier: 'PLATINUM', users: 25, avg_churn: 0.12 },
      { tier: 'GOLD', users: 35, avg_churn: 0.28 },
      { tier: 'SILVER', users: 20, avg_churn: 0.45 },
      { tier: 'BRONZE', users: 20, avg_churn: 0.62 }
    ];
  } else if (q.includes('inventory') || q.includes('stock') || q.includes('product')) {
    answer = `The current warehouse snapshot shows an inventory turnover of **6.8**. There are **14 products** flagged with a critical stockout risk (less than 7 days of supply remaining), mostly in the Central EU warehouse.`;
    sqlQuery = `SELECT productName, quantityAvailable, daysOfSupply \nFROM inventory_snapshot \nWHERE stockoutRiskFlag = true \nORDER BY daysOfSupply ASC;`;
    sqlResults = [
      { productName: 'AION Enterprise Suite (V1)', quantityAvailable: 12, daysOfSupply: 3 },
      { productName: 'Neural DB Connector (V2)', quantityAvailable: 8, daysOfSupply: 5 },
      { productName: 'Vector Index Engine (V3)', quantityAvailable: 15, daysOfSupply: 6 }
    ];
  }

  return {
    copilotChat: {
      answer,
      sqlQuery,
      sqlResults,
      retrievedContext: [
        "AION Ledger Database - financial_transactions",
        "AION Customer CRM - customer_360",
        "AION Warehouse Log - inventory_snapshot"
      ],
      guardrailFlags: [],
      modelUsed: "Claude 3.5 Sonnet",
      tokensUsed: 1024,
      latencyMs: 342
    }
  };
};

// =============================================================================
// Custom Apollo Mock Link
// =============================================================================

export const mockLink = new ApolloLink((operation, forward) => {
  const operationName = operation.operationName;
  const variables = operation.variables;

  console.log(`[Apollo MockLink] Intercepted query: ${operationName}`, variables);

  return new Observable<FetchResult>((observer) => {
    let responseData: any = null;

    try {
      switch (operationName) {
        case 'GetRevenueMetrics':
          responseData = { revenueMetrics: mockRevenueMetrics };
          break;
        case 'GetActiveUsers':
          responseData = { activeUsers: mockActiveUsers };
          break;
        case 'GetInventoryMetrics':
          responseData = { inventoryMetrics: mockInventoryMetrics };
          break;
        case 'GetExecutiveKPIs':
          responseData = { executiveKPIs: mockExecutiveKPIs };
          break;
        case 'GetFinancialTransactions': {
          const { startRow = 0, endRow = 50 } = variables;
          responseData = {
            financialTransactions: {
              rows: mockTransactions.slice(startRow, endRow),
              totalCount: mockTransactions.length
            }
          };
          break;
        }
        case 'GetCustomer360': {
          const { startRow = 0, endRow = 50 } = variables;
          responseData = {
            customer360: {
              rows: mockCustomers.slice(startRow, endRow),
              totalCount: mockCustomers.length
            }
          };
          break;
        }
        case 'GetInventorySnapshot': {
          const { startRow = 0, endRow = 50 } = variables;
          responseData = {
            inventorySnapshot: {
              rows: mockInventory.slice(startRow, endRow),
              totalCount: mockInventory.length
            }
          };
          break;
        }
        case 'SendCopilotMessage':
          responseData = getMockCopilotResponse(variables.input?.question || '');
          break;
        default:
          if (forward) {
            const next = forward(operation);
            const subscription = next.subscribe({
              next: observer.next.bind(observer),
              error: observer.error.bind(observer),
              complete: observer.complete.bind(observer)
            });
            return () => subscription.unsubscribe();
          }
          break;
      }

      if (responseData) {
        const timer = setTimeout(() => {
          observer.next({ data: responseData });
          observer.complete();
        }, 150);

        return () => clearTimeout(timer);
      }
    } catch (e) {
      observer.error(e);
    }
  });
});
