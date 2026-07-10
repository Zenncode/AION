import { ReactKeycloakProvider } from '@react-keycloak/web';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ApolloProvider } from '@apollo/client';
import keycloak from '@/auth/keycloak';
import { apolloClient } from '@/graphql/client';
import MainLayout from '@/components/layout/MainLayout';
import Dashboard from '@/components/dashboard/Dashboard';
import Copilot from '@/components/copilot/Copilot';
import DataTable from '@/components/grid/DataTable';

// Local dev: skip Keycloak if not configured
const isKeycloakConfigured = !!import.meta.env.VITE_KEYCLOAK_URL;

function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/copilot" element={<Copilot />} />
          <Route path="/data" element={<DataTable />} />
          <Route path="/data/:table" element={<DataTable />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default function App() {
  if (!isKeycloakConfigured) {
    // No Keycloak — run without auth (local dev)
    return (
      <ApolloProvider client={apolloClient}>
        <AppRoutes />
      </ApolloProvider>
    );
  }

  return (
    <ReactKeycloakProvider
      authClient={keycloak}
      initOptions={{
        onLoad: 'login-required',
        checkLoginIframe: false,
        pkceMethod: 'S256',
      }}
      onTokens={(tokens) => {
        if (tokens.token) {
          sessionStorage.setItem('aion_token', tokens.token);
        }
      }}
    >
      <ApolloProvider client={apolloClient}>
        <AppRoutes />
      </ApolloProvider>
    </ReactKeycloakProvider>
  );
}
