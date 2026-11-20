const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const buildQuery = (params = {}) => {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.append(key, value);
    }
  }
  const qs = searchParams.toString();
  return qs ? `?${qs}` : '';
};

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
export const fetchMetricsComparison = (run_id) =>
  fetchJson(`/api/metrics/comparison${buildQuery({ run_id })}`);

// Simulation
export const fetchNetworkNodes = (run_id) =>
  fetchJson(`/api/network/nodes${buildQuery({ run_id })}`);
export const fetchSimulationStatus = () => fetchJson('/api/simulation/status');
export const fetchSimulationRuns = ({ limit, offset, status } = {}) =>
  fetchJson(`/api/simulation/runs${buildQuery({ limit, offset, status })}`);
export const fetchSimulationSummary = (run_id) =>
  fetchJson(`/api/simulation/summary${buildQuery({ run_id })}`);
export const fetchSimulationMetrics = (run_id) =>
  fetchJson(`/api/simulation/metrics${buildQuery({ run_id })}`);

export const runSimulation = (nnodes, simulation_time, malicious_nodes) => {
  const maliciousNodesArray = malicious_nodes
    ? (typeof malicious_nodes === 'string'
        ? malicious_nodes.split(',').map(n => parseInt(n.trim())).filter(n => !isNaN(n))
        : (Array.isArray(malicious_nodes) ? malicious_nodes : []))
    : [];

  const payload = {
    nNodes: parseInt(nnodes),
    attackEnabled: maliciousNodesArray.length > 0,
    maliciousNodes: maliciousNodesArray,
  };

  if (simulation_time !== undefined && simulation_time !== null && !isNaN(parseFloat(simulation_time))) {
    payload.simulationTime = parseFloat(simulation_time);
  }

  return fetchJson('/api/simulation/run', {
    method: 'POST',
    body: JSON.stringify(payload),
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
export const fetchDynamicTrust = (run_id) =>
  fetchJson(`/api/trust/dynamic${buildQuery({ run_id })}`);

// Routing
export const fetchRoutingPath = (run_id) =>
  fetchJson(`/api/routing/path${buildQuery({ run_id })}`);

// Prevention
export const fetchPreventionSummary = (run_id) =>
  fetchJson(`/api/prevention/summary${buildQuery({ run_id })}`);
export const fetchPreventionEvents = (paramsOrRunId = {}, options = {}) => {
  let queryParams = {};
  if (typeof paramsOrRunId === 'string') {
    queryParams = { run_id: paramsOrRunId, ...options };
  } else if (paramsOrRunId && typeof paramsOrRunId === 'object') {
    queryParams = paramsOrRunId;
  }
  return fetchJson(`/api/prevention/events${buildQuery(queryParams)}`);
};

// Federated Learning
export const fetchFLStatus = (run_id) =>
  fetchJson(`/api/fl/status${buildQuery({ run_id })}`);
export const fetchFLRounds = (run_id) =>
  fetchJson(`/api/fl/rounds${buildQuery({ run_id })}`);
export const fetchFLClients = (run_id) =>
  fetchJson(`/api/fl/clients${buildQuery({ run_id })}`);

