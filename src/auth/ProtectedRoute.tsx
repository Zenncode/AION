import { useKeycloak } from '@react-keycloak/web';
import { Outlet } from 'react-router-dom';


export default function ProtectedRoute() {
  const { keycloak, initialized } = useKeycloak();

  if (!initialized) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!keycloak.authenticated) {
    keycloak.login();
    return null;
  }

  return <Outlet />;
}
