import React, { useState, useEffect } from 'react';
import { 
  fetchHealth, fetchSimulationStatus, fetchPreventionSummary, 
  fetchMetricsComparison, fetchDynamicTrust, fetchRoutingPath 
} from '../services/apiService';
import { Activity, ShieldAlert, CheckCircle, Network, Cpu, Route, BarChart3, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react';

const Dashboard = () => {
  const [health, setHealth] = useState(null);
  const [simStatus, setSimStatus] = useState(null);
  const [preventionSummary, setPreventionSummary] = useState(null);
  const [metricsComp, setMetricsComp] = useState(null);
  const [dynamicTrust, setDynamicTrust] = useState(null);
  const [routingPath, setRoutingPath] = useState(null);
  
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const scrollRef = React.useRef(null);
  const [canScroll, setCanScroll] = useState({ left: false, right: true });

  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current;
      setCanScroll({
        left: scrollLeft > 0,
        right: Math.ceil(scrollLeft + clientWidth) < scrollWidth
      });
    }
  };

  const scrollBy = (dir) => {
    if (scrollRef.current) {
      scrollRef.current.scrollBy({ left: dir === 'left' ? -300 : 300, behavior: 'smooth' });
    }
  };

  useEffect(() => {
    handleScroll();
    window.addEventListener('resize', handleScroll);
    return () => window.removeEventListener('resize', handleScroll);
  }, []);

  const loadData = async () => {
    try {
      const [healthRes, simRes, prevRes, metRes, trustRes, routeRes] = await Promise.allSettled([
        fetchHealth(),
        fetchSimulationStatus(),
        fetchPreventionSummary(),
        fetchMetricsComparison(),
        fetchDynamicTrust(),
        fetchRoutingPath()
      ]);
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value);
      if (simRes.status === 'fulfilled') setSimStatus(simRes.value);
      if (prevRes.status === 'fulfilled') setPreventionSummary(prevRes.value);
      if (metRes.status === 'fulfilled') setMetricsComp(metRes.value);
      if (trustRes.status === 'fulfilled') setDynamicTrust(trustRes.value);
      if (routeRes.status === 'fulfilled') setRoutingPath(routeRes.value);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRunning(false);
    }
  };

  useEffect(() => {
    loadData();
    window.addEventListener('simulation-completed', loadData);
    return () => window.removeEventListener('simulation-completed', loadData);
  }, []);

  if (loading) return <div className="p-8 text-slate-500 flex justify-center items-center h-screen">Loading Dashboard Data...</div>;

  const isConnected = health?.status === 'healthy';
  const isCompleted = simStatus?.status === 'completed';
  
  const handleRunSimulation = async () => {
    setRunning(true);
    window.location.href = '/simulation';
  };

  const totalNodes = simStatus?.nNodes ?? 'N/A';
  const maliciousNodes = simStatus?.maliciousNodes || [];
  const safeNodes = typeof totalNodes === 'number' ? totalNodes - maliciousNodes.length : 'N/A';
  const datasetRows = simStatus?.classical_ml?.dataset_rows ?? 'N/A';
  const sourceNode = simStatus?.sourceNode ?? 'N/A';
  const destNode = simStatus?.destinationNode ?? 'N/A';
  
  const detectedMalicious = [...new Set(preventionSummary?.detected_low_trust_nodes || [])];
  const forbiddenNodes = [...new Set(preventionSummary?.blocked_or_restricted_nodes || [])];
  
  const routeNodes = routingPath?.route_nodes || preventionSummary?.recovered_route || [];
  const selectedNextHop = routeNodes.length > 1 ? routeNodes[1] : 'N/A';
  const safeNeighbors = preventionSummary?.trust_scores ? Object.keys(preventionSummary.trust_scores).filter(n => !forbiddenNodes.includes(Number(n)) && Number(n) !== sourceNode) : [];

  const renderStatusBadge = (status) => {
    if (status === 'completed' || status === 'safe_route_found' || status === true) return <span className="px-2 py-1 bg-emerald-100 text-emerald-700 rounded text-xs font-bold uppercase">Completed</span>;
    if (status === 'running') return <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-bold uppercase">Running</span>;
    if (status === 'failed' || status === false) return <span className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-bold uppercase">Failed</span>;
    return <span className="px-2 py-1 bg-slate-100 text-slate-500 rounded text-xs font-bold uppercase">Pending</span>;
  };

  return (
    <div className="space-y-8 pb-12 animate-in fade-in duration-500">
      
      <section className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
        <div className="flex items-center gap-2 mb-6">
          <Network className="w-5 h-5 text-blue-600" />
          <h2 className="text-lg font-bold text-slate-800">1. Network Overview</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
          <div className="p-4 bg-slate-50 rounded-xl">
            <p className="text-xs text-slate-500 uppercase font-semibold">Status</p>
            <p className={`text-xl font-bold ${isConnected ? 'text-emerald-600' : 'text-red-600'}`}>{isConnected ? 'Healthy' : 'Offline'}</p>
          </div>
          <div className="p-4 bg-slate-50 rounded-xl">
            <p className="text-xs text-slate-500 uppercase font-semibold">Total Nodes</p>
            <p className="text-xl font-bold text-slate-800">{totalNodes}</p>
          </div>
          <div className="p-4 bg-slate-50 rounded-xl">
            <p className="text-xs text-slate-500 uppercase font-semibold">Malicious</p>
            <p className="text-xl font-bold text-red-600">[{maliciousNodes.join(', ')}]</p>
          </div>
          <div className="p-4 bg-slate-50 rounded-xl">
            <p className="text-xs text-slate-500 uppercase font-semibold">Safe Nodes</p>
            <p className="text-xl font-bold text-emerald-600">{safeNodes}</p>
          </div>
          <div className="p-4 bg-slate-50 rounded-xl">
            <p className="text-xs text-slate-500 uppercase font-semibold">Dataset Rows</p>
            <p className="text-xl font-bold text-purple-600">{datasetRows}</p>
          </div>
          <div className="p-4 bg-slate-50 rounded-xl">
            <p className="text-xs text-slate-500 uppercase font-semibold">Source</p>
            <p className="text-xl font-bold text-blue-600">{sourceNode}</p>
          </div>
          <div className="p-4 bg-slate-50 rounded-xl">
            <p className="text-xs text-slate-500 uppercase font-semibold">Destination</p>
            <p className="text-xl font-bold text-blue-600">{destNode}</p>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        <section className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Activity className="w-5 h-5 text-indigo-600" />
              <h2 className="text-lg font-bold text-slate-800">2. Simulation Status</h2>
            </div>
            <div className="space-y-3 mb-6">
              <div className="flex justify-between items-center pb-2 border-b border-slate-50">
                <span className="text-sm text-slate-600">Current Status</span>
                {renderStatusBadge(simStatus?.status)}
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-slate-50">
                <span className="text-sm text-slate-600">Run ID</span>
                <span className="text-xs font-mono text-slate-500 max-w-[200px] truncate" title={simStatus?.run_id}>{simStatus?.run_id || 'N/A'}</span>
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-slate-50">
                <span className="text-sm text-slate-600">Pass 1 Status</span>
                {renderStatusBadge(simStatus?.status === 'completed' ? 'completed' : 'pending')}
              </div>
              <div className="flex justify-between items-center pb-2 border-b border-slate-50">
                <span className="text-sm text-slate-600">Pass 2 Status</span>
                {renderStatusBadge(simStatus?.status === 'completed' ? 'completed' : 'pending')}
              </div>
            </div>
          </div>
          <button 
            onClick={handleRunSimulation}
            disabled={running || !isConnected}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-bold rounded-xl transition-colors flex items-center justify-center gap-2"
          >
            {running ? <Activity className="w-5 h-5 animate-spin" /> : <CheckCircle className="w-5 h-5" />} 
            {running ? 'Running...' : 'Run Simulation'}
          </button>
        </section>

        <section className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
          <div className="flex items-center gap-2 mb-4">
            <Cpu className="w-5 h-5 text-purple-600" />
            <h2 className="text-lg font-bold text-slate-800">3. ML & Detection</h2>
          </div>
          <div className="space-y-3">
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">Classical ML</span>
              {renderStatusBadge(simStatus?.classical_ml?.status)}
            </div>
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">LSTM Execution</span>
              {renderStatusBadge(dynamicTrust?.status)}
            </div>
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">Total Predictions</span>
              <span className="text-sm font-bold text-slate-800">{dynamicTrust?.nodes?.length || 'N/A'} nodes evaluated</span>
            </div>
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">Detected Malicious</span>
              <span className="text-sm font-bold text-red-600">[{detectedMalicious.join(', ')}]</span>
            </div>
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">Trust Scores Gen.</span>
              {renderStatusBadge(preventionSummary?.trust_scores ? 'completed' : 'pending')}
            </div>
          </div>
        </section>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
          <div className="flex items-center gap-2 mb-4">
            <ShieldAlert className="w-5 h-5 text-red-500" />
            <h2 className="text-lg font-bold text-slate-800">4. Prevention Status</h2>
          </div>
          <div className="space-y-3">
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">Detected Threats</span>
              <span className="text-sm font-bold text-red-600">[{detectedMalicious.join(', ')}]</span>
            </div>
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">Forbidden Nodes</span>
              <span className="text-sm font-bold text-slate-800">[{forbiddenNodes.join(', ')}]</span>
            </div>
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">Excluded Count</span>
              <span className="text-sm font-bold text-slate-800">{forbiddenNodes.length}</span>
            </div>
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">Prevention Status</span>
              {renderStatusBadge(preventionSummary?.recovery_success)}
            </div>
          </div>
        </section>

        <section className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
          <div className="flex items-center gap-2 mb-4">
            <Route className="w-5 h-5 text-emerald-600" />
            <h2 className="text-lg font-bold text-slate-800">5. Route Recovery</h2>
          </div>
          <div className="space-y-3">
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">Route Request</span>
              <span className="text-sm font-bold text-slate-800">{sourceNode} &rarr; {destNode}</span>
            </div>
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">Eligible Safe Neighbors</span>
              <span className="text-sm font-bold text-slate-800 truncate max-w-[200px]">[{safeNeighbors.join(', ')}]</span>
            </div>
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">Selected Next Hop</span>
              <span className="text-sm font-bold text-blue-600">{selectedNextHop}</span>
            </div>
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">Recovered Safe Route</span>
              <span className="text-sm font-bold text-emerald-600">{routeNodes.join(' → ')}</span>
            </div>
            <div className="flex justify-between items-center pb-2 border-b border-slate-50">
              <span className="text-sm text-slate-600">Route Validation</span>
              {renderStatusBadge(routingPath?.route_available)}
            </div>
          </div>
        </section>
      </div>

      <section className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
        <div className="flex items-center gap-2 mb-6">
          <BarChart3 className="w-5 h-5 text-amber-500" />
          <h2 className="text-lg font-bold text-slate-800">6. Performance Overview</h2>
        </div>
        
        {metricsComp?.baseline ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
              <p className="text-xs text-slate-500 font-bold uppercase mb-1">Baseline PDR</p>
              <p className="text-2xl font-black text-emerald-600">{metricsComp.baseline.pdr_percent?.toFixed(2)}%</p>
            </div>
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
              <p className="text-xs text-slate-500 font-bold uppercase mb-1">Attack PDR</p>
              <p className="text-2xl font-black text-red-600">{metricsComp.attack.pdr_percent?.toFixed(2)}%</p>
            </div>
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
              <p className="text-xs text-slate-500 font-bold uppercase mb-1">Baseline Delay</p>
              <p className="text-2xl font-black text-slate-700">{metricsComp.baseline.mean_delay_ms?.toFixed(2)}ms</p>
            </div>
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
              <p className="text-xs text-slate-500 font-bold uppercase mb-1">Attack Delay</p>
              <p className="text-2xl font-black text-slate-700">{metricsComp.attack.mean_delay_ms?.toFixed(2)}ms</p>
            </div>
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
              <p className="text-xs text-slate-500 font-bold uppercase mb-1">Base T-Put</p>
              <p className="text-2xl font-black text-slate-700">{metricsComp.baseline.throughput_kbps?.toFixed(2)}kbps</p>
            </div>
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
              <p className="text-xs text-slate-500 font-bold uppercase mb-1">Attack T-Put</p>
              <p className="text-2xl font-black text-slate-700">{metricsComp.attack.throughput_kbps?.toFixed(2)}kbps</p>
            </div>
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
              <p className="text-xs text-slate-500 font-bold uppercase mb-1">Packet Loss (Attack)</p>
              <p className="text-2xl font-black text-red-600">{metricsComp.attack.lost_packets}</p>
            </div>
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
              <p className="text-xs text-slate-500 font-bold uppercase mb-1">PDR Drop</p>
              <p className="text-2xl font-black text-orange-500">{metricsComp.pdr_drop_percent?.toFixed(2)}%</p>
            </div>
          </div>
        ) : (
          <div className="p-8 text-center bg-slate-50 rounded-xl text-slate-500 flex flex-col items-center">
             <AlertCircle className="w-8 h-8 mb-2 opacity-50" />
             <p>Performance metrics not available yet. Run a simulation.</p>
          </div>
        )}
      </section>

      <section className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold text-slate-800">7. System Pipeline</h2>
          <div className="flex items-center gap-2">
            <button 
              onClick={() => scrollBy('left')} 
              disabled={!canScroll.left}
              className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <button 
              onClick={() => scrollBy('right')} 
              disabled={!canScroll.right}
              className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
        <div 
          className="flex items-center gap-2 w-full pb-4 overflow-x-auto [&::-webkit-scrollbar]:hidden" 
          style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
          ref={scrollRef}
          onScroll={handleScroll}
        >
          {[
            { name: "Simulation", active: isCompleted },
            { name: "Dataset Gen", active: isCompleted },
            { name: "Classical ML", active: simStatus?.classical_ml?.status === 'completed' },
            { name: "LSTM", active: dynamicTrust?.status === 'completed' },
            { name: "Trust Eval", active: preventionSummary?.trust_scores !== undefined },
            { name: "Prevention", active: preventionSummary?.recovery_success !== undefined },
            { name: "Trust Routing", active: routingPath?.route_available === true },
            { name: "Performance", active: metricsComp?.baseline !== undefined }
          ].map((step, idx, arr) => (
            <React.Fragment key={idx}>
              <div className={`flex flex-col items-center justify-center p-3 rounded-lg border-2 w-32 text-center transition-all shrink-0 ${
                  step.active ? 'border-emerald-500 bg-emerald-50' : 'border-slate-200 bg-slate-50 opacity-60'
                }`}>
                <div className={`w-3 h-3 rounded-full mb-2 ${step.active ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                <span className={`text-xs font-bold ${step.active ? 'text-emerald-700' : 'text-slate-500'}`}>{step.name}</span>
                <span className="text-[10px] uppercase mt-1 text-slate-400">{step.active ? 'Completed' : 'Pending'}</span>
              </div>
              {idx < arr.length - 1 && (
                <div className={`h-1 w-6 rounded-full shrink-0 ${step.active && arr[idx+1].active ? 'bg-emerald-400' : 'bg-slate-200'}`} />
              )}
            </React.Fragment>
          ))}
        </div>
      </section>

    </div>
  );
};

export default Dashboard;
