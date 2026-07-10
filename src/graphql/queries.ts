import { gql } from '@apollo/client';

// =============================================================================
// Dashboard KPI Queries
// =============================================================================

export const GET_REVENUE_METRICS = gql`
  query GetRevenueMetrics($dateRange: DateRangeInput!) {
    revenueMetrics(dateRange: $dateRange) {
      totalRevenue
      mtdRevenue
      revenueGrowth
      avgOrderValue
      dailyRevenue {
        date
        value
      }
      revenueByRegion {
        region
        value
        percentage
      }
      revenueBySegment {
        segment
        value
        percentage
      }
    }
  }
`;

export const GET_ACTIVE_USERS = gql`
  query GetActiveUsers($dateRange: DateRangeInput!) {
    activeUsers(dateRange: $dateRange) {
      totalActiveUsers
      dailyActiveUsers
      weeklyActiveUsers
      monthlyActiveUsers
      userGrowthRate
      dailyActiveUsersTrend {
        date
        value
      }
      usersByRegion {
        region
        value
        percentage
      }
    }
  }
`;

export const GET_INVENTORY_METRICS = gql`
  query GetInventoryMetrics($dateRange: DateRangeInput!) {
    inventoryMetrics(dateRange: $dateRange) {
      totalInventoryValue
      inventoryTurns
      stockoutRiskCount
      overstockCount
      avgDaysOfSupply
      turnoverByCategory {
        category
        value
        quantity
      }
      stockoutTrend {
        date
        value
      }
    }
  }
`;

export const GET_EXECUTIVE_KPIS = gql`
  query GetExecutiveKPIs {
    executiveKPIs {
      customerCount
      totalRevenue
      activeUsers
      inventoryTurns
      churnRate
      npsScore
      avgOrderValue
      revenuePerUser
    }
  }
`;

// =============================================================================
// Real-time Subscriptions
// =============================================================================

export const SUBSCRIBE_KPI_UPDATES = gql`
  subscription OnKpiUpdate {
    kpiUpdated {
      id
      name
      value
      previousValue
      trend
      updatedAt
    }
  }
`;

export const SUBSCRIBE_REVENUE_STREAM = gql`
  subscription OnRevenueStream {
    revenueStream {
      timestamp
      amount
      orderId
      region
      currency
    }
  }
`;

// =============================================================================
// Data Grid Queries (with server-side pagination)
// =============================================================================

export const GET_FINANCIAL_TRANSACTIONS = gql`
  query GetFinancialTransactions(
    $startRow: Int!
    $endRow: Int!
    $sortModel: [SortInput!]
    $filterModel: FilterInput
  ) {
    financialTransactions(
      startRow: $startRow
      endRow: $endRow
      sortModel: $sortModel
      filterModel: $filterModel
    ) {
      rows {
        transactionId
        customerId
        orderId
        transactionType
        transactionStatus
        amount
        currency
        netAmount
        paymentMethod
        revenueCategory
        region
        transactionTimestamp
        eventDate
      }
      totalCount
    }
  }
`;

export const GET_CUSTOMER_360 = gql`
  query GetCustomer360(
    $startRow: Int!
    $endRow: Int!
    $sortModel: [SortInput!]
    $filterModel: FilterInput
  ) {
    customer360(
      startRow: $startRow
      endRow: $endRow
      sortModel: $sortModel
      filterModel: $filterModel
    ) {
      rows {
        customerId
        customerName
        segment
        tier
        country
        region
        totalOrders12m
        totalRevenue12m
        avgOrderValue12m
        rfmCompositeScore
        churnRiskScore
        predictedLtv
        eventDate
      }
      totalCount
    }
  }
`;

export const GET_INVENTORY_SNAPSHOT = gql`
  query GetInventorySnapshot(
    $startRow: Int!
    $endRow: Int!
    $sortModel: [SortInput!]
    $filterModel: FilterInput
  ) {
    inventorySnapshot(
      startRow: $startRow
      endRow: $endRow
      sortModel: $sortModel
      filterModel: $filterModel
    ) {
      rows {
        snapshotId
        productId
        productName
        productCategory
        warehouseName
        quantityOnHand
        quantityReserved
        quantityAvailable
        unitCost
        totalCostValue
        daysOfSupply
        stockoutRiskFlag
        eventDate
      }
      totalCount
    }
  }
`;

// =============================================================================
// Copilot Queries
// =============================================================================

export const SEND_COPilot_MESSAGE = gql`
  mutation SendCopilotMessage($input: CopilotInput!) {
    copilotChat(input: $input) {
      answer
      sqlQuery
      sqlResults
      retrievedContext
      guardrailFlags {
        type
        severity
        message
      }
      modelUsed
      tokensUsed
      latencyMs
    }
  }
`;

export const GET_COPilot_HISTORY = gql`
  query GetCopilotHistory($conversationId: ID!) {
    copilotHistory(conversationId: $conversationId) {
      id
      role
      content
      sqlQuery
      timestamp
      modelUsed
    }
  }
`;
