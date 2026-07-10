import Keycloak from 'keycloak-js';

const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL || 'https://auth.aion.internal',
  realm: import.meta.env.VITE_KEYCLOAK_REALM || 'aion',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'aion-frontend',
});

export default keycloak;
