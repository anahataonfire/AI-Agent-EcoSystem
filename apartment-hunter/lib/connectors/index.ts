// Connector registry and exports

import { connectorRegistry } from './types';
import { craigslistConnector } from './craigslist';
import { manualConnector } from './manual';
import { genericConnector } from './generic';

// Register all connectors
connectorRegistry.register(craigslistConnector);
connectorRegistry.register(manualConnector);
connectorRegistry.register(genericConnector);

// Re-export everything
export * from './types';
export { craigslistConnector } from './craigslist';
export { manualConnector } from './manual';
export { genericConnector } from './generic';
