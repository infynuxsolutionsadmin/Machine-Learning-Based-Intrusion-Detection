import React, { useState, useEffect } from 'react';
import { 
  fetchMLFeatures, fetchMLModels, fetchMLMetrics, 
  fetchDynamicTrust, fetchSimulationStatus, fetchPreventionSummary 
} from '../services/apiService';
import { 
  Activity, AlertTriangle, CheckCircle, 
  ShieldAlert, Database, Target, Award, BarChart2
} from 'lucide-react';

const MLDetection = () => {
  const [features, setFeatures] = useState(null);
  const [models, setModels] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [trust, setTrust] = useState(null);
  const [simStatus, setSimStatus] = useState(null);
  const [summary, setSummary] = useState(null);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = () => {
    Promise.allSettled([
      fetchMLFeatures(),
      fetchMLModels(),
      fetchMLMetrics(),
      fetchDynamicTrust(),
      fetchSimulationStatus(),
      fetchPreventionSummary()
    ]).then(([featRes, modRes, metRes, trustRes, simRes, sumRes]) => {
      let anyError = false;
      if (featRes.status === 'fulfilled') setFeatures(featRes.value); else anyError = true;
      if (modRes.status === 'fulfilled') setModels(modRes.value); else anyError = true;
      if (metRes.status === 'fulfilled') setMetrics(metRes.value); else anyError = true;
      if (trustRes.status === 'fulfilled') setTrust(trustRes.value); else anyError = true;
      if (simRes.status === 'fulfilled') setSimStatus(simRes.value); else anyError = true;
      if (sumRes.status === 'fulfilled') setSummary(sumRes.value); else anyError = true;

      if (anyError && !featRes.value && !modRes.value && !metRes.value) {
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
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3">
      <div className="w-10 h-10 rounded-full border-3 border-blue-600/20 border-t-blue-600 animate-spin"></div>
      <p className="text-sm font-semibold text-slate-500">Loading ML Detection Data...</p>
    </div>
  );
  
  if (error) return (
    <div className="dash-card p-6 rounded-3xl max-w-xl mx-auto mt-8 border-rose-200 bg-rose-50/50">
      <h3 className="text-base font-extrabold text-rose-800 mb-1 flex items-center gap-2">Unable to load ML data</h3>
      <p className="text-sm text-slate-500">{error}</p>
    </div>
  );

  const rfMetrics = metrics?.metrics?.RandomForest || null;
  const isSimulationCompleted = simStatus?.status === 'completed';
  const hasTrustData = trust?.nodes && trust.nodes.length > 0;
  
  const maliciousNodes = simStatus?.maliciousNodes || [];
  const nNodes = simStatus?.nNodes || 0;
  const safeNodesCount = isSimulationCompleted ? Math.max(0, nNodes - maliciousNodes.length) : 'N/A';
  const predictionCount = hasTrustData ? trust.nodes.length : 'N/A';

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10 animate-in fade-in duration-300">
      
      {/* 1. Metrics Row (4 Reference Stat Cards - Kept exactly as they are) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        
        {/* Card 1: Accuracy (Featured Gradient Card) */}
        <div className="dash-card dash-card-hover bg-gradient-to-br from-[#3b5bf6] to-[#5b4bf6] text-white p-6 rounded-3xl flex flex-col justify-between shadow-lg shadow-blue-500/20 border-0 min-h-[160px]">
          <div className="flex items-center justify-between">
            <div className="w-11 h-11 rounded-2xl bg-white/15 backdrop-blur-md border border-white/20 flex items-center justify-center text-white">
              <Award className="w-5 h-5" />
            </div>
            <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-emerald-400/20 text-emerald-200 border border-emerald-400/30">
              Primary Metric
            </span>
          </div>
          <div className="mt-4">
            <span className="text-xs font-semibold text-blue-100 uppercase tracking-wider block">Model Accuracy</span>
            <div className="text-3xl font-black text-white tracking-tight mt-0.5">
              {rfMetrics ? (rfMetrics.Accuracy * 100).toFixed(1) + '%' : 'N/A'}
            </div>
            <div className="text-xs text-blue-100/90 font-medium mt-1">RandomForest Classifier</div>
          </div>
        </div>

        {/* Card 2: Precision */}
        <div className="dash-card dash-card-hover p-6 rounded-3xl flex flex-col justify-between min-h-[160px]">
          <div className="flex items-center justify-between">
            <div className="w-11 h-11 rounded-2xl bg-purple-50 text-purple-600 flex items-center justify-center">
              <Target className="w-5 h-5" />
            </div>
            <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-purple-100 text-purple-700">
              Precision
            </span>
          </div>
          <div className="mt-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Detection Precision</span>
            <div className="text-3xl font-black text-slate-900 tracking-tight mt-0.5">
              {rfMetrics ? (rfMetrics.Precision * 100).toFixed(1) + '%' : 'N/A'}
            </div>
            <div className="text-xs text-slate-500 font-medium mt-1">Positive predictive value</div>
          </div>
        </div>

        {/* Card 3: Recall */}
        <div className="dash-card dash-card-hover p-6 rounded-3xl flex flex-col justify-between min-h-[160px]">
          <div className="flex items-center justify-between">
            <div className="w-11 h-11 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <Activity className="w-5 h-5" />
            </div>
            <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-emerald-100 text-emerald-700">
              Recall
            </span>
          </div>
          <div className="mt-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Detection Recall</span>
            <div className="text-3xl font-black text-slate-900 tracking-tight mt-0.5">
              {rfMetrics ? (rfMetrics.Recall * 100).toFixed(1) + '%' : 'N/A'}
            </div>
            <div className="text-xs text-slate-500 font-medium mt-1">True positive identification</div>
          </div>
        </div>

        {/* Card 4: F1 Score */}
        <div className="dash-card dash-card-hover p-6 rounded-3xl flex flex-col justify-between min-h-[160px]">
          <div className="flex items-center justify-between">
            <div className="w-11 h-11 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <BarChart2 className="w-5 h-5" />
            </div>
            <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-amber-100 text-amber-700">
              F1 Harmonic
            </span>
          </div>
          <div className="mt-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">F1 Score</span>
            <div className="text-3xl font-black text-slate-900 tracking-tight mt-0.5">
              {rfMetrics ? (rfMetrics.F1 * 100).toFixed(1) + '%' : 'N/A'}
            </div>
            <div className="text-xs text-slate-500 font-medium mt-1">Balanced harmonic mean</div>
          </div>
        </div>

      </div>

      {/* 2. Model Performance Comparison (FULL AVAILABLE CONTENT WIDTH) */}
      <div className="dash-card p-6 rounded-3xl w-full">
        <div className="flex items-center justify-between mb-5 pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-extrabold text-slate-900">Model Performance Comparison</h3>
              <p className="text-xs text-slate-400">Benchmarked classical classifiers</p>
            </div>
          </div>
          <div className="px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-bold">
            Benchmark ▾
          </div>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[420px]">
            <thead>
              <tr className="border-b border-slate-100 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                <th className="pb-3 px-4">Model</th>
                <th className="pb-3 px-4 text-right">Accuracy</th>
                <th className="pb-3 px-4 text-right">Precision</th>
                <th className="pb-3 px-4 text-right">Recall</th>
                <th className="pb-3 px-4 text-right">F1 Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50 text-sm">
              {models?.models?.map((modelName, idx) => {
                const mData = metrics?.metrics?.[modelName];
                if (!mData) return null;
                return (
                  <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-4 font-bold text-slate-800 whitespace-nowrap flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                      {modelName}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2.5 py-1 rounded-full">
                        {(mData.Accuracy * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <span className="font-mono text-xs font-bold text-purple-700 bg-purple-50 px-2.5 py-1 rounded-full">
                        {(mData.Precision * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <span className="font-mono text-xs font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full">
                        {(mData.Recall * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <span className="font-mono text-xs font-bold text-amber-700 bg-amber-50 px-2.5 py-1 rounded-full">
                        {(mData.F1 * 100).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="mt-4 pt-3 border-t border-slate-100 text-center text-xs text-slate-400 font-medium">
          Models evaluated on MANET baseline datasets
        </div>
      </div>

      {/* 3. Lower Row: LSTM Trust Evaluation & Detection Summary (Side-by-Side & Responsive Stacking) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        
        {/* Left: LSTM Trust Evaluation */}
        <div className="dash-card p-6 rounded-3xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-5 pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                  <ShieldAlert className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-slate-900">LSTM Trust Evaluation</h3>
                  <p className="text-xs text-slate-400">Dynamic sequential trust predictions</p>
                </div>
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-indigo-100 text-indigo-700">
                Recurrent Engine
              </span>
            </div>
            
            {!isSimulationCompleted ? (
              <p className="text-slate-400 italic text-sm py-6 text-center">No completed simulation available.</p>
            ) : !hasTrustData ? (
              <p className="text-slate-400 italic text-sm py-6 text-center">LSTM Trust Evaluation data unavailable for this run.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-100 text-[11px] font-bold uppercase text-slate-400 tracking-wider">
                      <th className="pb-3 px-4">Node ID</th>
                      <th className="pb-3 px-4">Trust Score</th>
                      <th className="pb-3 px-4 text-right">Classification</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50 text-sm">
                    {trust.nodes.map((p, i) => {
                      const isMalicious = p.predicted_malicious === true || p.predicted_malicious === 1 || p.malicious === true || p.is_malicious === 1;
                      const score = p.predicted_trust_score ?? p.trust_score ?? 0;
                      return (
                        <tr key={i} className="hover:bg-slate-50/80 transition-colors">
                          <td className="py-3 px-4 font-bold text-slate-800">
                            Node {p.node}
                          </td>
                          <td className="py-3 px-4">
                            <span className="font-mono text-xs font-bold bg-slate-100 px-2.5 py-1 rounded-md text-slate-700">
                              {score.toFixed(3)}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right">
                            {isMalicious ? (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-700">
                                <AlertTriangle className="w-3.5 h-3.5" /> Malicious
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-700">
                                <CheckCircle className="w-3.5 h-3.5" /> Safe
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-400 font-medium">
            Sequential sliding window evaluation for dynamic malicious mitigation
          </div>
        </div>

        {/* Right: Detection Summary */}
        <div className="dash-card p-6 rounded-3xl flex flex-col justify-between self-start">
          <div>
            <div className="flex items-center gap-2.5 mb-5 pb-3 border-b border-slate-100">
              <div className="w-9 h-9 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center">
                <Database className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-extrabold text-slate-900">Detection Summary</h3>
                <p className="text-xs text-slate-400">Current run telemetry & predictions</p>
              </div>
            </div>
            
            <div className="space-y-3.5">
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Dataset Rows</span>
                <span className="font-bold text-slate-900">{simStatus?.classical_ml?.dataset_rows ?? 'N/A'}</span>
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Prediction Count</span>
                <span className="font-bold text-slate-900">{predictionCount}</span>
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Safe Nodes</span>
                <span className="font-bold text-emerald-600">{safeNodesCount}</span>
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Source Node</span>
                <span className="font-bold text-slate-900">{simStatus?.sourceNode ?? 'N/A'}</span>
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Destination Node</span>
                <span className="font-bold text-slate-900">{simStatus?.destinationNode ?? 'N/A'}</span>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block mb-2.5">
                Detected Malicious Nodes
              </span>
              {!isSimulationCompleted ? (
                <span className="text-slate-400 text-xs italic">Pending simulation</span>
              ) : maliciousNodes.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {maliciousNodes.map(node => (
                    <span key={node} className="bg-rose-500 text-white font-extrabold text-xs px-3 py-1 rounded-full shadow-xs">
                      Node {node}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-700">
                  <CheckCircle className="w-3.5 h-3.5" /> None Detected
                </span>
              )}
              <p className="text-[11px] text-slate-400 mt-3 font-medium leading-relaxed">
                Nodes identified for automated prevention and secure routing exclusion.
              </p>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-400 font-medium">
            Real-time policy enforcement applied to forward routing tables
          </div>
        </div>

      </div>

    </div>
  );
};

export default MLDetection;
