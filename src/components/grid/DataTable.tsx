import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { AgGridReact } from 'ag-grid-react';
import { ColDef, GridReadyEvent } from 'ag-grid-community';
import { apolloClient } from '@/graphql/client';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

import {
  GET_FINANCIAL_TRANSACTIONS,
  GET_CUSTOMER_360,
  GET_INVENTORY_SNAPSHOT,
} from '@/graphql/queries';

// =============================================================================
// Table Configurations
// =============================================================================

const TABLE_CONFIGS: Record<string, { query: any; queryKey: string; columns: ColDef[] }> = {
  transactions: {
    query: GET_FINANCIAL_TRANSACTIONS,
    queryKey: 'financialTransactions',
    columns: [
      { headerName: 'Transaction ID', field: 'transactionId', sortable: true, filter: true, width: 160 },
      { headerName: 'Customer', field: 'customerId', sortable: true, filter: true, width: 110 },
      { headerName: 'Order', field: 'orderId', sortable: true, width: 100 },
      { headerName: 'Type', field: 'transactionType', sortable: true, filter: true, width: 120 },
      { headerName: 'Status', field: 'transactionStatus', sortable: true, filter: true, width: 120 },
      {
        headerName: 'Amount',
        field: 'amount',
        sortable: true,
        width: 120,
        valueFormatter: (p) => `€${Number(p.value).toLocaleString()}`,
      },
      { headerName: 'Currency', field: 'currency', width: 80 },
      {
        headerName: 'Net Amount',
        field: 'netAmount',
        sortable: true,
        width: 130,
        valueFormatter: (p) => `€${Number(p.value).toLocaleString()}`,
      },
      { headerName: 'Payment', field: 'paymentMethod', sortable: true, filter: true, width: 110 },
      { headerName: 'Category', field: 'revenueCategory', sortable: true, filter: true, width: 140 },
      { headerName: 'Region', field: 'region', sortable: true, filter: true, width: 110 },
      {
        headerName: 'Date',
        field: 'transactionTimestamp',
        sortable: true,
        width: 170,
        valueFormatter: (p) => p.value ? new Date(p.value).toLocaleString() : '',
      },
      { headerName: 'Event Date', field: 'eventDate', sortable: true, width: 120 },
    ],
  },
  customers: {
    query: GET_CUSTOMER_360,
    queryKey: 'customer360',
    columns: [
      { headerName: 'Customer ID', field: 'customerId', sortable: true, width: 120 },
      { headerName: 'Name', field: 'customerName', sortable: true, filter: true, width: 160 },
      { headerName: 'Segment', field: 'segment', sortable: true, filter: true, width: 110 },
      { headerName: 'Tier', field: 'tier', sortable: true, filter: true, width: 90 },
      { headerName: 'Country', field: 'country', sortable: true, filter: true, width: 110 },
      { headerName: 'Region', field: 'region', sortable: true, filter: true, width: 110 },
      { headerName: 'Orders (12m)', field: 'totalOrders12m', sortable: true, width: 120 },
      {
        headerName: 'Revenue (12m)',
        field: 'totalRevenue12m',
        sortable: true,
        width: 140,
        valueFormatter: (p) => `€${Number(p.value).toLocaleString()}`,
      },
      {
        headerName: 'Avg Order',
        field: 'avgOrderValue12m',
        sortable: true,
        width: 120,
        valueFormatter: (p) => `€${Number(p.value).toLocaleString()}`,
      },
      {
        headerName: 'RFM Score',
        field: 'rfmCompositeScore',
        sortable: true,
        width: 100,
        cellStyle: (p) => ({
          color: Number(p.value) >= 4 ? '#22c55e' : Number(p.value) >= 2.5 ? '#f59e0b' : '#ef4444',
        }),
      },
      {
        headerName: 'Churn Risk',
        field: 'churnRiskScore',
        sortable: true,
        width: 110,
        valueFormatter: (p) => `${(Number(p.value) * 100).toFixed(1)}%`,
        cellStyle: (p) => ({
          color: Number(p.value) > 0.7 ? '#ef4444' : Number(p.value) > 0.4 ? '#f59e0b' : '#22c55e',
        }),
      },
      {
        headerName: 'LTV',
        field: 'predictedLtv',
        sortable: true,
        width: 120,
        valueFormatter: (p) => `€${Number(p.value).toLocaleString()}`,
      },
      { headerName: 'Date', field: 'eventDate', sortable: true, width: 120 },
    ],
  },
  inventory: {
    query: GET_INVENTORY_SNAPSHOT,
    queryKey: 'inventorySnapshot',
    columns: [
      { headerName: 'Snapshot ID', field: 'snapshotId', sortable: true, width: 120 },
      { headerName: 'Product ID', field: 'productId', sortable: true, width: 110 },
      { headerName: 'Product', field: 'productName', sortable: true, filter: true, width: 180 },
      { headerName: 'Category', field: 'productCategory', sortable: true, filter: true, width: 140 },
      { headerName: 'Warehouse', field: 'warehouseName', sortable: true, filter: true, width: 140 },
      { headerName: 'On Hand', field: 'quantityOnHand', sortable: true, width: 90 },
      { headerName: 'Reserved', field: 'quantityReserved', sortable: true, width: 100 },
      { headerName: 'Available', field: 'quantityAvailable', sortable: true, width: 100 },
      {
        headerName: 'Unit Cost',
        field: 'unitCost',
        sortable: true,
        width: 110,
        valueFormatter: (p) => `€${Number(p.value).toFixed(2)}`,
      },
      {
        headerName: 'Total Value',
        field: 'totalCostValue',
        sortable: true,
        width: 130,
        valueFormatter: (p) => `€${Number(p.value).toLocaleString()}`,
      },
      {
        headerName: 'Days Supply',
        field: 'daysOfSupply',
        sortable: true,
        width: 110,
        cellStyle: (p) => ({
          color: Number(p.value) < 7 ? '#ef4444' : Number(p.value) < 14 ? '#f59e0b' : '#22c55e',
        }),
      },
      {
        headerName: 'Stockout Risk',
        field: 'stockoutRiskFlag',
        sortable: true,
        width: 110,
        cellRenderer: (p: any) =>
          p.value ? (
            <span className="text-red-400 font-medium">● At Risk</span>
          ) : (
            <span className="text-green-400 font-medium">● OK</span>
          ),
      },
      { headerName: 'Date', field: 'eventDate', sortable: true, width: 120 },
    ],
  },
};

// =============================================================================
// DataTable Component
// =============================================================================

export default function DataTable() {
  const { table = 'transactions' } = useParams<{ table: string }>();
  const config = TABLE_CONFIGS[table] || TABLE_CONFIGS.transactions;

  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [gridReady, setGridReady] = useState(false);
  const gridApiRef = useRef<any>(null);

  const onGridReady = useCallback((params: GridReadyEvent) => {
    gridApiRef.current = params.api;
    params.api.sizeColumnsToFit();
    setGridReady(true);
  }, []);

  // Update datasource when configuration changes or grid becomes ready
  useEffect(() => {
    if (gridApiRef.current && gridReady) {
      const datasource = {
        getRows: async (getRowsParams: any) => {
          setLoading(true);
          try {
            // Map AG Grid sortModel to SortInput format expected by GraphQL
            const sortModel = getRowsParams.sortModel.map((s: any) => ({
              colId: s.colId,
              sort: s.sort,
            }));

            const { data } = await apolloClient.query({
              query: config.query,
              variables: {
                startRow: getRowsParams.startRow,
                endRow: getRowsParams.endRow,
                sortModel,
                filterModel: getRowsParams.filterModel,
              },
              fetchPolicy: 'network-only',
            });

            const result = data?.[config.queryKey] || { rows: [], totalCount: 0 };
            setTotalCount(result.totalCount);
            getRowsParams.successCallback(result.rows, result.totalCount);
          } catch (error) {
            console.error('Failed to fetch grid rows:', error);
            getRowsParams.failCallback();
          } finally {
            setLoading(false);
          }
        },
      };

      gridApiRef.current.setGridOption('datasource', datasource);
    }
  }, [config, gridReady]);

  // Handle loading overlay visibility
  useEffect(() => {
    if (gridApiRef.current) {
      if (loading) {
        gridApiRef.current.showLoadingOverlay();
      } else {
        gridApiRef.current.hideOverlay();
      }
    }
  }, [loading]);

  const defaultColDef = useMemo(
    () => ({
      resizable: true,
      sortable: true,
      filter: false,
      suppressMenuHide: true,
      minWidth: 80,
      flex: 0,
    }),
    []
  );

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#334155] flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold capitalize">{table.replace(/-/g, ' ')}</h1>
          <p className="text-gray-400 text-sm mt-1">
            {totalCount.toLocaleString()} rows · Server-side pagination
          </p>
        </div>
        <button
          onClick={() => gridApiRef.current?.purgeInfiniteCache()}
          className="px-4 py-2 bg-[#1e293b] border border-[#334155] rounded-lg text-sm hover:bg-[#334155] transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* AG Grid */}
      <div className="flex-1 ag-theme-alpine-dark">
        <AgGridReact
          columnDefs={config.columns}
          defaultColDef={defaultColDef}
          rowModelType="infinite"
          cacheBlockSize={50}
          maxBlocksInCache={10}
          animateRows={true}
          onGridReady={onGridReady}
          pagination={true}
          paginationPageSize={50}
          suppressRowClickSelection={true}
          enableCellTextSelection={true}
          overlayNoRowsTemplate='<span style="padding: 10px;">No data available</span>'
          getRowId={(params) => {
            const idFields = ['transactionId', 'customerId', 'snapshotId'];
            for (const f of idFields) {
              if (params.data[f]) return String(params.data[f]);
            }
            return String(Math.random());
          }}
        />
      </div>
    </div>
  );
}
