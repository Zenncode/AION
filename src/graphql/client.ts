import { ApolloClient, InMemoryCache, createHttpLink, split } from '@apollo/client';
import { setContext } from '@apollo/client/link/context';
import { GraphQLWsLink } from '@apollo/client/link/subscriptions';
import { createClient } from 'graphql-ws';
import { getMainDefinition } from '@apollo/client/utilities';


const httpLink = createHttpLink({
  uri: import.meta.env.VITE_GRAPHQL_URL || '/graphql',
});

const authLink = setContext((_, { headers }) => {
  // Keycloak token is injected at runtime via the provider
  const token = sessionStorage.getItem('aion_token');
  return {
    headers: {
      ...headers,
      authorization: token ? `Bearer ${token}` : '',
    },
  };
});

const wsLink = new GraphQLWsLink(
  createClient({
    url: import.meta.env.VITE_GRAPHQL_WS_URL || 'ws://gateway.aion.svc.cluster.local:4000/graphql',
    connectionParams: () => ({
      authorization: `Bearer ${sessionStorage.getItem('aion_token') || ''}`,
    }),
    shouldRetry: () => true,
    retryAttempts: 5,
  })
);

const splitLink = split(
  ({ query }) => {
    const definition = getMainDefinition(query);
    return (
      definition.kind === 'OperationDefinition' &&
      definition.operation === 'subscription'
    );
  },
  wsLink,
  authLink.concat(httpLink)
);

import { mockLink } from './mockLink';

const useMockData =
  import.meta.env.VITE_USE_MOCK_DATA === 'true' ||
  !import.meta.env.VITE_GRAPHQL_URL ||
  import.meta.env.VITE_GRAPHQL_URL.includes('your-staging-server.com');

export const apolloClient = new ApolloClient({
  link: useMockData ? mockLink : splitLink,
  cache: new InMemoryCache({
    typePolicies: {
      Query: {
        fields: {
          revenueMetrics: {
            merge(_, incoming) {
              return incoming;
            },
          },
          activeUsers: {
            merge(_, incoming) {
              return incoming;
            },
          },
        },
      },
    },
  }),
  defaultOptions: {
    watchQuery: {
      fetchPolicy: 'cache-and-network',
      nextFetchPolicy: 'cache-first',
    },
  },
});
