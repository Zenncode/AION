import { ReactKeycloakProvider } from '@react-keycloak/web';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ApolloProvider } from '@apollo/client';
import keycloak from '@/auth/keycloak';
import { apolloClient } from '@/graphql/client';
import ProtectedRoute from '@/auth/ProtectedRoute';
import MainLayout from '@/components/layout/MainLayout';
import Dashboard from '@/components/dashboard/Dashboard';
import Copilot from '@/components/copilot/Copilot';
import DataTable from '@/components/grid/DataTable';

export default function App() {
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
        <BrowserRouter>
          <Routes>
            <Route element={<ProtectedRoute />}>
              <Route element={<MainLayout />}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/copilot" element={<Copilot />} />
                <Route path="/data" element={<DataTable />} />
                <Route path="/data/:table" element={<DataTable />} />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </ApolloProvider>
    </ReactKeycloakProvider>
  );
}
