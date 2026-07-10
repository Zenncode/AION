import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/graphql': {
        target: 'http://gateway.aion.svc.cluster.local:4000',
        changeOrigin: true,
      },
      '/copilot': {
        target: 'http://aion-copilot.aion-copilot.svc.cluster.local:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/copilot/, ''),
      },
    },
  },
  build: {
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          charts: ['chart.js', 'react-chartjs-2'],
          grid: ['ag-grid-community', 'ag-grid-react'],
          graphql: ['@apollo/client', 'graphql'],
        },
      },
    },
  },
});
