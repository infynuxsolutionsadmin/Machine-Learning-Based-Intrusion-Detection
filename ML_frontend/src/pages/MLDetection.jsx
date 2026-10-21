import React, { useState, useEffect } from 'react';
import { fetchMLFeatures, fetchMLModels, fetchMLMetrics, fetchDynamicTrust, fetchSimulationStatus, fetchPreventionSummary } from '../services/apiService';
import { BrainCircuit, Fingerprint, Activity, AlertTriangle, CheckCircle, ShieldAlert, Database, ArrowDown, Network } from 'lucide-react';

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
    <div className="p-8 max-w-7xl mx-auto flex items-center justify-center min-h-[50vh]">
      <div className="text-slate-500 font-medium text-lg flex items-center gap-3">
        <span className="w-5 h-5 rounded-full border-2 border-slate-300 border-t-blue-600 animate-spin"></span>
        Loading ML Detection Data...
      </div>
    </div>
  );
  
  if (error) return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 max-w-xl mx-auto mt-10">
      <h3 className="text-lg font-bold text-red-800 mb-2 flex items-center gap-2">Unable to load ML data</h3>
      <p className="text-slate-500">{error}</p>
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
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      
      {/* Page Header */}
      <div className="mb-8 border-b border-slate-200 pb-5">
        <h1 className="text-3xl font-black text-slate-800 flex items-center gap-3">
          <BrainCircuit className="w-8 h-8 text-blue-600" />
          ML Detection
        </h1>
        <p className="text-slate-500 font-medium text-lg mt-1">Classical ML and LSTM-based malicious node detection</p>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Accuracy</span>
          <p className="text-3xl font-bold text-blue-600">
            {rfMetrics ? (rfMetrics.Accuracy * 100).toFixed(1) + '%' : 'N/A'}
          </p>
        </div>
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Precision</span>
          <p className="text-3xl font-bold text-slate-800">
            {rfMetrics ? (rfMetrics.Precision * 100).toFixed(1) + '%' : 'N/A'}
          </p>
        </div>
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Recall</span>
          <p className="text-3xl font-bold text-slate-800">
            {rfMetrics ? (rfMetrics.Recall * 100).toFixed(1) + '%' : 'N/A'}
          </p>
        </div>
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">F1 Score</span>
          <p className="text-3xl font-bold text-slate-800">
            {rfMetrics ? (rfMetrics.F1 * 100).toFixed(1) + '%' : 'N/A'}
          </p>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column - Model Perf & LSTM Eval */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Model Performance Chart */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
            <h3 className="font-bold text-slate-800 mb-6 flex items-center gap-2">
              <Activity className="w-5 h-5 text-blue-500" /> Model Performance Comparison
            </h3>
            
            <div className="overflow-x-auto mt-2">
              <table className="w-full text-left border-collapse min-w-[400px]">
                <thead>
                  <tr className="border-b-2 border-slate-100 text-xs uppercase tracking-wider">
                    <th className="pb-3 px-4 font-bold text-slate-500">Model</th>
                    <th className="pb-3 px-4 font-bold text-blue-600 text-right">Accuracy</th>
                    <th className="pb-3 px-4 font-bold text-purple-600 text-right">Precision</th>
                    <th className="pb-3 px-4 font-bold text-emerald-600 text-right">Recall</th>
                    <th className="pb-3 px-4 font-bold text-amber-600 text-right">F1 Score</th>
                  </tr>
                </thead>
                <tbody>
                  {models?.models?.map((modelName, idx) => {
                    const mData = metrics?.metrics?.[modelName];
                    if (!mData) return null;
                    return (
                      <tr key={idx} className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                        <td className="py-4 px-4 font-bold text-slate-800 whitespace-nowrap">{modelName}</td>
                        <td className="py-4 px-4 text-right">
                          <span className="font-mono text-sm font-semibold text-slate-700 bg-slate-100 px-2.5 py-1 rounded-md">{(mData.Accuracy * 100).toFixed(1)}%</span>
                        </td>
                        <td className="py-4 px-4 text-right">
                          <span className="font-mono text-sm font-semibold text-slate-700 bg-slate-100 px-2.5 py-1 rounded-md">{(mData.Precision * 100).toFixed(1)}%</span>
                        </td>
                        <td className="py-4 px-4 text-right">
                          <span className="font-mono text-sm font-semibold text-slate-700 bg-slate-100 px-2.5 py-1 rounded-md">{(mData.Recall * 100).toFixed(1)}%</span>
                        </td>
                        <td className="py-4 px-4 text-right">
                          <span className="font-mono text-sm font-semibold text-slate-700 bg-slate-100 px-2.5 py-1 rounded-md">{(mData.F1 * 100).toFixed(1)}%</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="mt-8 text-center text-xs text-slate-400 italic">Models evaluated on MANET baseline datasets</div>
          </div>

          {/* LSTM Trust Evaluation */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
            <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-indigo-500" /> LSTM Trust Evaluation
            </h3>
            
            {!isSimulationCompleted ? (
              <p className="text-slate-500 italic text-sm py-4">No completed simulation available.</p>
            ) : !hasTrustData ? (
              <p className="text-slate-500 italic text-sm py-4">LSTM Trust Evaluation data unavailable for this run.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs uppercase text-slate-500 tracking-wider">
                      <th className="pb-3 px-4 font-semibold">Node ID</th>
                      <th className="pb-3 px-4 font-semibold">Trust Score</th>
                      <th className="pb-3 px-4 font-semibold">Classification</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trust.nodes.map((p, i) => {
                      const isMalicious = p.predicted_malicious === true || p.predicted_malicious === 1 || p.malicious === true || p.is_malicious === 1;
                      const score = p.predicted_trust_score ?? p.trust_score ?? 0;
                      return (
                        <tr key={i} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                          <td className="py-3 px-4 font-bold text-slate-700">{p.node}</td>
                          <td className="py-3 px-4">
                            <span className="font-mono text-sm bg-slate-100 px-2 py-1 rounded text-slate-600">
                              {score.toFixed(3)}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            {isMalicious ? (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-red-100 text-red-700 border border-red-200">
                                <AlertTriangle className="w-3 h-3" /> Malicious
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-700 border border-emerald-200">
                                <CheckCircle className="w-3 h-3" /> Safe
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
        </div>

        {/* Right Column - Summaries & Workflow */}
        <div className="space-y-6">
          
          {/* Detection Summary */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
            <h3 className="font-bold text-slate-800 mb-5 flex items-center gap-2">
              <Database className="w-5 h-5 text-slate-500" /> Detection Summary
            </h3>
            
            <div className="space-y-4">
              <div className="flex justify-between items-center pb-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600">Dataset Rows</span>
                <span className="font-bold text-slate-800">{simStatus?.classical_ml?.dataset_rows ?? 'N/A'}</span>
              </div>
              <div className="flex justify-between items-center pb-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600">Prediction Count</span>
                <span className="font-bold text-slate-800">{predictionCount}</span>
              </div>
              <div className="flex justify-between items-center pb-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600">Safe Nodes</span>
                <span className="font-bold text-emerald-600">{safeNodesCount}</span>
              </div>
              <div className="flex justify-between items-center pb-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600">Source Node</span>
                <span className="font-bold text-slate-800">{simStatus?.sourceNode ?? 'N/A'}</span>
              </div>
              <div className="flex justify-between items-center pb-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600">Destination Node</span>
                <span className="font-bold text-slate-800">{simStatus?.destinationNode ?? 'N/A'}</span>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-slate-100">
              <span className="text-sm font-bold text-slate-700 block mb-3">Detected Malicious Nodes</span>
              {!isSimulationCompleted ? (
                <span className="text-slate-400 text-sm italic">Pending simulation</span>
              ) : maliciousNodes.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {maliciousNodes.map(node => (
                    <span key={node} className="bg-red-500 text-white font-bold text-sm px-3 py-1 rounded-md shadow-sm">
                      Node {node}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-sm font-bold bg-emerald-50 text-emerald-600 border border-emerald-200">
                  <CheckCircle className="w-4 h-4" /> None Detected
                </span>
              )}
              <p className="text-[11px] text-slate-400 mt-3 font-medium">Nodes identified for prevention and trust-based routing exclusion.</p>
            </div>
          </div>

          {/* Detection Workflow */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
            <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
              <Network className="w-5 h-5 text-slate-500" /> Detection Workflow
            </h3>
            
            <div className="flex flex-col">
              {[
                { label: 'Dataset Generated', active: isSimulationCompleted },
                { label: 'Classical ML Analysis', active: isSimulationCompleted },
                { label: 'LSTM Prediction', active: hasTrustData },
                { label: 'Trust Evaluation', active: hasTrustData },
                { label: 'Malicious Identification', active: isSimulationCompleted },
                { label: 'Prevention / Routing', active: summary?.recovery_success !== undefined }
              ].map((step, idx, arr) => (
                <div key={idx} className="flex gap-4">
                  <div className="flex flex-col items-center">
                    <div className={`z-10 flex-shrink-0 flex items-center justify-center w-6 h-6 rounded-full border-2 bg-white ${step.active ? 'border-emerald-500 text-emerald-500' : 'border-slate-300 text-slate-300'}`}>
                      {step.active ? <CheckCircle className="w-3.5 h-3.5" /> : <div className="w-2 h-2 rounded-full bg-slate-200"></div>}
                    </div>
                    {idx < arr.length - 1 && (
                      <div className="w-0.5 h-6 bg-slate-200 my-1"></div>
                    )}
                  </div>
                  <div className={`font-semibold text-sm pt-0.5 ${step.active ? 'text-slate-700' : 'text-slate-400'}`}>
                    {step.label}
                  </div>
                </div>
              ))}
            </div>
            {!isSimulationCompleted && (
              <p className="text-center text-xs text-slate-400 italic mt-4">Available after simulation</p>
            )}
          </div>

          {/* Features Used */}
          {/* <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
            <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
              <Fingerprint className="w-5 h-5 text-slate-500" /> Features Used
            </h3>
            {features?.selected_features?.length > 0 ? (
              <ul className="space-y-2">
                {features.selected_features.map((f, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm font-medium text-slate-600 bg-slate-50 px-3 py-2 rounded-lg border border-slate-100">
                    <div className="w-1.5 h-1.5 bg-blue-400 rounded-full"></div>
                    {f}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-500 italic text-sm">No data available.</p>
            )}
          </div> */}

        </div>
      </div>
    </div>
  );
};

export default MLDetection;

