import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { fetchSimulationRuns } from '../services/apiService';

const RunContext = createContext(null);

export const RunProvider = ({ children }) => {
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [availableRuns, setAvailableRuns] = useState([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [runsError, setRunsError] = useState(null);

  const refreshRuns = useCallback(async () => {
    setLoadingRuns(true);
    setRunsError(null);
    try {
      const data = await fetchSimulationRuns({ limit: 50 });
      const runs = Array.isArray(data?.runs) ? data.runs : [];
      setAvailableRuns(runs);
    } catch (err) {
      console.error('Failed to load simulation runs:', err);
      setRunsError(err.message || 'Failed to fetch historical runs');
    } finally {
      setLoadingRuns(false);
    }
  }, []);

  useEffect(() => {
    refreshRuns();

    const handleSimulationCompleted = () => {
      refreshRuns();
    };

    window.addEventListener('simulation-completed', handleSimulationCompleted);
    return () => {
      window.removeEventListener('simulation-completed', handleSimulationCompleted);
    };
  }, [refreshRuns]);

  const value = {
    selectedRunId,
    setSelectedRunId,
    availableRuns,
    loadingRuns,
    runsError,
    refreshRuns,
  };

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
};

export const useRun = () => {
  const context = useContext(RunContext);
  if (!context) {
    throw new Error('useRun must be used within a RunProvider');
  }
  return context;
};

export default RunContext;
