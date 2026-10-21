import React, { useState, useEffect } from 'react';
import { Route, ArrowRight, CheckCircle, XCircle, AlertCircle, Info } from 'lucide-react';
import { fetchPreventionSummary, fetchRoutingPath, fetchSimulationStatus } from '../services/apiService';

const RouteRecovery = () => {
  const [summary, setSummary] = useState(null);
  const [routingPath, setRoutingPath] = useState(null);
  const [simStatus, setSimStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = () => {
    Promise.allSettled([
      fetchPreventionSummary(),
      fetchRoutingPath(),
      fetchSimulationStatus()
    ]).then(([sumRes, pathRes, simRes]) => {
      let anyError = false;
      if (sumRes.status === 'fulfilled') setSummary(sumRes.value); else anyError = true;
      if (pathRes.status === 'fulfilled') setRoutingPath(pathRes.value);
      if (simRes.status === 'fulfilled') setSimStatus(simRes.value); else anyError = true;
      
      if (anyError && !sumRes.value && !pathRes.value) {
        setError("Unable to load data from backend.");
      }
      setLoading(false);
    });
  };

  useEffect(() => {
    loadData();
    window.addEventListener('simulation-completed', loadData);
    return () => window.removeEventListener('simulation-completed', loadData);
  }, []);

  if (loading) return (
    <div className="p-8 max-w-7xl mx-auto flex items-center justify-center min-h-[50vh]">
      <div className="text-slate-500 font-medium text-lg flex items-center gap-3">
        <span className="w-5 h-5 rounded-full border-2 border-slate-300 border-t-blue-600 animate-spin"></span>
        Loading route data...
      </div>
    </div>
  );
  
  if (error) return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 max-w-xl mx-auto mt-10">
      <h3 className="text-lg font-bold text-red-800 mb-2 flex items-center gap-2">Unable to load data</h3>
      <p className="text-slate-500">{error}</p>
    </div>
  );

  if (!summary && !routingPath) return <div className="p-8 text-slate-500 font-medium">No data available from the backend.</div>;

  const afterNodes = routingPath?.route_nodes || [];
  const isRecoverySuccessful = summary?.recovery_success;
  const sourceNode = simStatus?.source ?? routingPath?.source ?? summary?.source ?? 'N/A';
  const destNode = simStatus?.destination ?? routingPath?.destination ?? summary?.destination ?? 'N/A';
  const routingMethod = summary?.routing_method || 'N/A';
  const maliciousNodesSet = new Set(simStatus?.maliciousNodes || []);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      
      {/* Page Header */}
      <div className="mb-8 border-b border-slate-200 pb-5">
        <h1 className="text-3xl font-black text-slate-800 flex items-center gap-3">
          <Route className="w-8 h-8 text-blue-600" />
          ROUTE RECOVERY
        </h1>
        <p className="text-slate-500 font-medium text-lg mt-1">Trust-based secure routing outcome</p>
      </div>

      {isRecoverySuccessful === true && afterNodes.length > 0 ? (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center gap-3 shadow-sm">
          <CheckCircle className="w-6 h-6 text-emerald-600 shrink-0" />
          <h3 className="font-bold text-emerald-800">Recovery Successful</h3>
        </div>
      ) : isRecoverySuccessful !== undefined && afterNodes.length === 0 ? (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex items-center gap-3 shadow-sm">
          <Info className="w-6 h-6 text-slate-500 shrink-0" />
          <h3 className="font-bold text-slate-800">Recovery Status Available (Route Data Unavailable)</h3>
        </div>
      ) : isRecoverySuccessful === false ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3 shadow-sm">
          <XCircle className="w-6 h-6 text-red-600 shrink-0" />
          <h3 className="font-bold text-red-800">Recovery Failed or Not Required</h3>
        </div>
      ) : (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 flex items-center gap-3 shadow-sm">
          <AlertCircle className="w-6 h-6 text-slate-400 shrink-0" />
          <h3 className="font-bold text-slate-600">Route Status Unknown</h3>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Route Information Card */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex flex-col">
          <h3 className="font-bold text-slate-800 mb-6 border-b border-slate-50 pb-4 flex items-center gap-2">
             Route Information
          </h3>
          
          <div className="flex flex-col gap-0 flex-grow">
            <div className="flex items-center py-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600 w-36 flex-shrink-0">Source Node</span>
              <span className="font-bold text-slate-800">{sourceNode}</span>
            </div>
            
            <div className="flex items-center py-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600 w-36 flex-shrink-0">Destination Node</span>
              <span className="font-bold text-slate-800">{destNode}</span>
            </div>
            
            <div className="flex items-center py-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600 w-36 flex-shrink-0">Safe Route</span>
              <div className="flex items-center gap-2 flex-wrap">
                {afterNodes.length > 0 ? (
                  afterNodes.map((node, idx) => (
                    <React.Fragment key={idx}>
                      <span className="font-bold text-sm bg-emerald-100 text-emerald-800 px-2.5 py-1 rounded shadow-sm border border-emerald-200">{node}</span>
                      {idx < afterNodes.length - 1 && <ArrowRight className="w-4 h-4 text-slate-400" />}
                    </React.Fragment>
                  ))
                ) : (
                  <span className="font-bold text-slate-500 bg-slate-100 px-3 py-1 rounded">Route unavailable</span>
                )}
              </div>
            </div>
            
            <div className="flex items-center py-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600 w-36 flex-shrink-0">Routing Method</span>
              <span className="font-bold text-slate-700 text-sm leading-relaxed">{routingMethod}</span>
            </div>
            
            <div className="flex items-center py-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600 w-36 flex-shrink-0">Recovery Status</span>
              {isRecoverySuccessful ? (
                <span className="font-bold text-sm text-emerald-700">Successful</span>
              ) : (
                <span className="font-bold text-sm text-slate-700">Pending</span>
              )}
            </div>
          </div>
        </div>

        {/* Route Visualization Card */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 flex flex-col">
          <h3 className="font-bold text-slate-800 mb-6 border-b border-slate-50 pb-4 flex justify-between items-center flex-wrap gap-2">
            Route Visualization
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-emerald-500 shadow-sm"></div><span className="text-[10px] font-bold text-slate-500 uppercase">Safe Node</span></div>
              <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-red-500 shadow-sm"></div><span className="text-[10px] font-bold text-slate-500 uppercase">Malicious</span></div>
            </div>
          </h3>
          
          <div className="flex-grow min-h-[250px] flex flex-col items-center justify-center bg-slate-50/50 rounded-xl border border-slate-100 p-6 relative">
             {afterNodes.length > 0 ? (
                <div className="w-full">
                  <div className="text-xs font-bold text-slate-400 uppercase tracking-wider text-center mb-8">Logical Route Sequence</div>
                  <div className="flex flex-wrap gap-x-2 gap-y-6 items-center justify-center">
                    {afterNodes.map((n, i) => {
                      const isMalicious = maliciousNodesSet.has(n);
                      return (
                        <React.Fragment key={i}>
                          <div className={`w-12 h-12 rounded-full border-2 flex items-center justify-center text-sm font-black shadow-sm z-10 ${
                            isMalicious ? 'bg-red-50 border-red-300 text-red-700' : 'bg-white border-emerald-400 text-emerald-800'
                          }`}>
                            {n}
                          </div>
                          {i < afterNodes.length - 1 && (
                            <div className="flex items-center">
                              <div className="h-1 w-6 sm:w-12 bg-emerald-200"></div>
                              <ArrowRight className="w-5 h-5 text-emerald-400 -ml-2" />
                            </div>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </div>
                </div>
             ) : (
                <div className="text-slate-400 text-sm font-bold flex flex-col items-center gap-3">
                  <Route className="w-10 h-10 opacity-50" />
                  No route data available
                </div>
             )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default RouteRecovery;
