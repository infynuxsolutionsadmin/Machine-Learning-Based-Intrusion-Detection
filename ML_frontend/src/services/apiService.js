const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

async function fetchJson(endpoint, options = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      cache: 'no-store',
      ...options,
    });
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error(`Error fetching ${endpoint}:`, error);
    throw error;
  }
}

// System Health
export const fetchHealth = () => fetchJson('/api/health');
export const fetchMetricsComparison = () => fetchJson('/api/metrics/comparison');

// Simulation
export const fetchNetworkNodes = () => fetchJson('/api/network/nodes');
export const fetchSimulationStatus = () => fetchJson('/api/simulation/status');
export const runSimulation = (nnodes, simulation_time, malicious_nodes) => {
  const maliciousNodesArray = malicious_nodes ? malicious_nodes.split(',').map(n => parseInt(n.trim())).filter(n => !isNaN(n)) : [];
  return fetchJson('/api/simulation/run', {
    method: 'POST',
    body: JSON.stringify({ 
      nNodes: parseInt(nnodes), 
      attackEnabled: maliciousNodesArray.length > 0,
      maliciousNodes: maliciousNodesArray 
    }),
  });
};

// Machine Learning
export const fetchMLFeatures = () => fetchJson('/api/ml/features');
export const fetchMLModels = () => fetchJson('/api/ml/models');
export const fetchMLMetrics = () => fetchJson('/api/ml/metrics');
export const predictML = (features, model_name = 'RandomForest') => 
  fetchJson('/api/ml/predict', {
    method: 'POST',
    body: JSON.stringify({ features, model_name }),
  });
export const fetchDynamicTrust = () => fetchJson('/api/trust/dynamic');

// Routing
export const fetchRoutingPath = () => fetchJson('/api/routing/path');

// Prevention
export const fetchPreventionSummary = () => fetchJson('/api/prevention/summary');
