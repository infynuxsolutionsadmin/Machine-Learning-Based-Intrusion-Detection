import React, { useState, useEffect } from 'react';
import { fetchMetricsComparison } from '../services/apiService';
import { Activity, AlertCircle, TrendingUp, TrendingDown, Minus, Info } from 'lucide-react';

const PerformanceMetrics = () => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = () => {
    fetchMetricsComparison()
      .then(setSummary)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
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
        Loading performance data...
      </div>
    </div>
  );
  
  if (error) return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 max-w-xl mx-auto mt-10">
      <h3 className="text-lg font-bold text-red-800 mb-2 flex items-center gap-2">Unable to load data</h3>
      <p className="text-slate-500">{error}</p>
    </div>
  );

  if (!summary) return <div className="p-8 text-slate-500 font-medium">No performance data available from backend.</div>;

  const a = summary.attack || {};
  const b = summary.baseline || {}; // "baseline" acts as the prevention/safe state in this context

  const getPdr = (obj) => obj.pdr_percent !== undefined ? obj.pdr_percent : null;
  const getDelay = (obj) => obj.mean_delay_ms !== undefined ? obj.mean_delay_ms : null;
  const getThroughput = (obj) => obj.throughput_kbps !== undefined ? obj.throughput_kbps / 1000 : null; // Mbps
  const getLoss = (obj) => (obj.tx_packets !== undefined && obj.tx_packets > 0) ? ((obj.tx_packets - obj.rx_packets) / obj.tx_packets * 100) : null;

  const pdrA = getPdr(a);
  const pdrB = getPdr(b);
  const thrA = getThroughput(a);
  const thrB = getThroughput(b);
  const delA = getDelay(a);
  const delB = getDelay(b);
  const lossA = getLoss(a);
  const lossB = getLoss(b);

  const hasComparisonData = (pdrA !== null && pdrB !== null);

  const formatThroughput = (val) => {
    if (val === null || val === undefined) return 'N/A';
    if (val === 0) return '0.00';
    if (val > 0 && val < 0.01) return parseFloat(val.toPrecision(2)).toString();
    return val.toFixed(2);
  };

  const renderTrend = (valA, valB, isHigherBetter = true) => {
    if (valA === null || valB === null) return null;
    const diff = valB - valA;
    if (diff === 0) return <span className="flex items-center gap-1 text-slate-500"><Minus className="w-4 h-4" /> 0.0</span>;
    
    const isGood = isHigherBetter ? diff > 0 : diff < 0;
    const colorClass = isGood ? 'text-emerald-600' : 'text-red-600';
    const Icon = diff > 0 ? TrendingUp : TrendingDown;
    
    return (
      <span className={`flex items-center gap-1 font-bold ${colorClass}`}>
        <Icon className="w-4 h-4" /> {Math.abs(diff).toFixed(2)}
      </span>
    );
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      
      {/* Page Header */}
      <div className="mb-8 border-b border-slate-200 pb-5">
        <h1 className="text-3xl font-black text-slate-800 flex items-center gap-3">
          <Activity className="w-8 h-8 text-blue-600" />
          Performance Metrics
        </h1>
        <p className="text-slate-500 font-medium text-lg mt-1">Network performance evaluation under attack and prevention</p>
      </div>

      {/* Top Cards (Using Prevention / Baseline data for primary display) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <div>
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 block">Packet Delivery Ratio</span>
            <span className="text-[10px] text-slate-400 font-medium leading-tight block mb-3 h-6">Successfully delivered packets</span>
          </div>
          <p className="text-3xl font-bold text-slate-800">
            {pdrB !== null ? pdrB.toFixed(1) + '%' : 'N/A'}
          </p>
        </div>
        
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <div>
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 block">Throughput</span>
            <span className="text-[10px] text-slate-400 font-medium leading-tight block mb-3 h-6">Data delivery rate</span>
          </div>
          <p className="text-3xl font-bold text-slate-800">
            {thrB !== null ? formatThroughput(thrB) + ' Mbps' : 'N/A'}
          </p>
        </div>
        
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <div>
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 block">End-to-End Delay</span>
            <span className="text-[10px] text-slate-400 font-medium leading-tight block mb-3 h-6">Average packet delivery delay</span>
          </div>
          <p className="text-3xl font-bold text-slate-800">
            {delB !== null ? delB.toFixed(1) + ' ms' : 'N/A'}
          </p>
        </div>
        
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <div>
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1 block">Packet Loss</span>
            <span className="text-[10px] text-slate-400 font-medium leading-tight block mb-3 h-6">Packets not successfully delivered</span>
          </div>
          <p className="text-3xl font-bold text-slate-800">
            {lossB !== null ? lossB.toFixed(1) + '%' : 'N/A'}
          </p>
        </div>
      </div>

      {/* Performance Comparison Table */}
      {/* Performance Comparison (Vertical Charts) */}
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-200">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-8 gap-4 border-b border-slate-50 pb-6">
          <h3 className="font-bold text-slate-800 text-xl flex items-center gap-2">
            Performance Comparison
          </h3>
          <div className="flex items-center gap-6 text-xs font-bold text-slate-500">
            <div className="flex items-center gap-2"><div className="w-3.5 h-3.5 rounded bg-red-400 shadow-sm"></div> Attack</div>
            <div className="flex items-center gap-2"><div className="w-3.5 h-3.5 rounded bg-emerald-400 shadow-sm"></div> Prevention</div>
          </div>
        </div>
        
        {hasComparisonData ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
             {/* PDR */}
             <div className="flex flex-col h-[280px] bg-slate-50/50 rounded-xl p-5 border border-slate-100 shadow-sm">
               <div className="text-sm font-bold text-slate-700 text-center mb-6">Packet Delivery Ratio (%)</div>
               <div className="flex-1 flex items-end justify-center gap-8 md:gap-12">
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-14">
                     <span className="text-xs font-bold text-slate-700">{pdrA.toFixed(1)}%</span>
                     <div className="w-full bg-red-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: `${pdrA}%`, minHeight: '4px' }}></div>
                     <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-1">Attack</span>
                  </div>
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-14">
                     <span className="text-xs font-bold text-slate-700">{pdrB.toFixed(1)}%</span>
                     <div className="w-full bg-emerald-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: `${pdrB}%`, minHeight: '4px' }}></div>
                     <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-1">Prevention</span>
                  </div>
               </div>
             </div>

             {/* Throughput */}
             <div className="flex flex-col h-[280px] bg-slate-50/50 rounded-xl p-5 border border-slate-100 shadow-sm">
               <div className="text-sm font-bold text-slate-700 text-center mb-6">Throughput (Mbps)</div>
               <div className="flex-1 flex items-end justify-center gap-8 md:gap-12">
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-14">
                     <span className="text-xs font-bold text-slate-700">{formatThroughput(thrA)}</span>
                     <div className="w-full bg-red-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: `${Math.min((thrA / Math.max(thrA, thrB, 0.1)) * 100, 100)}%`, minHeight: '4px' }}></div>
                     <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-1">Attack</span>
                  </div>
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-14">
                     <span className="text-xs font-bold text-slate-700">{formatThroughput(thrB)}</span>
                     <div className="w-full bg-emerald-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: `${Math.min((thrB / Math.max(thrA, thrB, 0.1)) * 100, 100)}%`, minHeight: '4px' }}></div>
                     <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-1">Prevention</span>
                  </div>
               </div>
             </div>
             
             {/* End-to-End Delay */}
             <div className="flex flex-col h-[280px] bg-slate-50/50 rounded-xl p-5 border border-slate-100 shadow-sm">
               <div className="text-sm font-bold text-slate-700 text-center mb-6">End-to-End Delay (ms)</div>
               <div className="flex-1 flex items-end justify-center gap-8 md:gap-12">
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-14">
                     <span className="text-xs font-bold text-slate-700">{delA.toFixed(1)}</span>
                     <div className="w-full bg-red-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: `${Math.min((delA / Math.max(delA, delB, 0.1)) * 100, 100)}%`, minHeight: '4px' }}></div>
                     <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-1">Attack</span>
                  </div>
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-14">
                     <span className="text-xs font-bold text-slate-700">{delB.toFixed(1)}</span>
                     <div className="w-full bg-emerald-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: `${Math.min((delB / Math.max(delA, delB, 0.1)) * 100, 100)}%`, minHeight: '4px' }}></div>
                     <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-1">Prevention</span>
                  </div>
               </div>
             </div>
             
             {/* Packet Loss */}
             <div className="flex flex-col h-[280px] bg-slate-50/50 rounded-xl p-5 border border-slate-100 shadow-sm">
               <div className="text-sm font-bold text-slate-700 text-center mb-6">Packet Loss (%)</div>
               <div className="flex-1 flex items-end justify-center gap-8 md:gap-12">
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-14">
                     <span className="text-xs font-bold text-slate-700">{lossA.toFixed(1)}%</span>
                     <div className="w-full bg-red-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: `${Math.min(lossA, 100)}%`, minHeight: '4px' }}></div>
                     <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-1">Attack</span>
                  </div>
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-14">
                     <span className="text-xs font-bold text-slate-700">{lossB.toFixed(1)}%</span>
                     <div className="w-full bg-emerald-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: `${Math.min(lossB, 100)}%`, minHeight: '4px' }}></div>
                     <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-1">Prevention</span>
                  </div>
               </div>
             </div>

          </div>
        ) : (
          <div className="py-16 text-center text-slate-500 flex flex-col items-center justify-center gap-3 bg-slate-50 rounded-xl border border-slate-100">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-10 h-10 text-slate-300"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
            <span className="font-medium">Comparison data unavailable from backend.</span>
          </div>
        )}
      </div>

      {/* Metric Definitions */}
      <div className="bg-slate-50 rounded-2xl p-6 border border-slate-200 mt-8">
        <h3 className="text-sm font-bold text-slate-700 mb-4 uppercase tracking-wider flex items-center gap-2">
          <Info className="w-4 h-4 text-blue-500" /> Metric Definitions
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="font-bold text-slate-800 block mb-1">PDR</span>
            <span className="text-slate-600 leading-relaxed">Percentage of packets successfully delivered.</span>
          </div>
          <div>
            <span className="font-bold text-slate-800 block mb-1">Throughput</span>
            <span className="text-slate-600 leading-relaxed">Rate of successfully delivered data.</span>
          </div>
          <div>
            <span className="font-bold text-slate-800 block mb-1">End-to-End Delay</span>
            <span className="text-slate-600 leading-relaxed">Average time taken for packets to reach the destination.</span>
          </div>
          <div>
            <span className="font-bold text-slate-800 block mb-1">Packet Loss</span>
            <span className="text-slate-600 leading-relaxed">Percentage of packets that were not successfully delivered.</span>
          </div>
        </div>
      </div>
      
    </div>
  );
};

export default PerformanceMetrics;
