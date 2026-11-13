import React, { useState, useEffect } from 'react';
import { fetchMetricsComparison } from '../services/apiService';
import { Activity, AlertCircle, TrendingUp, TrendingDown, Minus, Info, Zap, ShieldCheck } from 'lucide-react';

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
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3">
      <div className="w-10 h-10 rounded-full border-3 border-blue-600/20 border-t-blue-600 animate-spin"></div>
      <p className="text-sm font-semibold text-slate-500">Loading Performance Data...</p>
    </div>
  );
  
  if (error) return (
    <div className="dash-card p-6 rounded-3xl max-w-xl mx-auto mt-8 border-rose-200 bg-rose-50/50">
      <h3 className="text-base font-extrabold text-rose-800 mb-1 flex items-center gap-2">Unable to load data</h3>
      <p className="text-sm text-slate-500">{error}</p>
    </div>
  );

  if (!summary) return (
    <div className="dash-card p-8 rounded-3xl max-w-xl mx-auto mt-8 text-center text-slate-500 font-medium">
      No performance data available from backend. Run a simulation to evaluate QoS parameters.
    </div>
  );

  const a = summary.attack || {};
  const b = summary.baseline || {};

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
    if (diff === 0) return <span className="flex items-center gap-1 text-slate-400 font-bold text-xs"><Minus className="w-3.5 h-3.5" /> 0.0</span>;
    
    const isGood = isHigherBetter ? diff > 0 : diff < 0;
    const colorClass = isGood ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700';
    const Icon = diff > 0 ? TrendingUp : TrendingDown;
    
    return (
      <span className={`flex items-center gap-1 px-2.5 py-0.5 rounded-full font-extrabold text-xs ${colorClass}`}>
        <Icon className="w-3.5 h-3.5" /> {Math.abs(diff).toFixed(1)}
      </span>
    );
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10 animate-in fade-in duration-300">
      
      {/* Top 4 Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        
        {/* PDR (Featured Gradient Card) */}
        <div className="dash-card dash-card-hover bg-gradient-to-br from-[#3b5bf6] to-[#5b4bf6] text-white p-6 rounded-3xl flex flex-col justify-between shadow-lg shadow-blue-500/20 border-0 min-h-[160px]">
          <div className="flex items-center justify-between">
            <div className="w-11 h-11 rounded-2xl bg-white/15 backdrop-blur-md border border-white/20 flex items-center justify-center text-white">
              <ShieldCheck className="w-5 h-5" />
            </div>
            {renderTrend(pdrA, pdrB, true)}
          </div>
          <div className="mt-4">
            <span className="text-xs font-semibold text-blue-100 uppercase tracking-wider block">Packet Delivery Ratio</span>
            <div className="text-3xl font-black text-white tracking-tight mt-0.5">
              {pdrB !== null ? pdrB.toFixed(1) + '%' : 'N/A'}
            </div>
            <div className="text-xs text-blue-100/90 font-medium mt-1">Packets safely delivered</div>
          </div>
        </div>
        
        {/* Throughput */}
        <div className="dash-card dash-card-hover p-6 rounded-3xl flex flex-col justify-between min-h-[160px]">
          <div className="flex items-center justify-between">
            <div className="w-11 h-11 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <Zap className="w-5 h-5" />
            </div>
            {renderTrend(thrA, thrB, true)}
          </div>
          <div className="mt-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Network Throughput</span>
            <div className="text-3xl font-black text-slate-900 tracking-tight mt-0.5">
              {thrB !== null ? formatThroughput(thrB) : 'N/A'} <span className="text-sm font-medium text-slate-400">Mbps</span>
            </div>
            <div className="text-xs text-slate-500 font-medium mt-1">Average data transmission rate</div>
          </div>
        </div>
        
        {/* End-to-End Delay */}
        <div className="dash-card dash-card-hover p-6 rounded-3xl flex flex-col justify-between min-h-[160px]">
          <div className="flex items-center justify-between">
            <div className="w-11 h-11 rounded-2xl bg-purple-50 text-purple-600 flex items-center justify-center">
              <Activity className="w-5 h-5" />
            </div>
            {renderTrend(delA, delB, false)}
          </div>
          <div className="mt-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">End-to-End Delay</span>
            <div className="text-3xl font-black text-slate-900 tracking-tight mt-0.5">
              {delB !== null ? delB.toFixed(1) : 'N/A'} <span className="text-sm font-medium text-slate-400">ms</span>
            </div>
            <div className="text-xs text-slate-500 font-medium mt-1">Mean hop latency</div>
          </div>
        </div>
        
        {/* Packet Loss */}
        <div className="dash-card dash-card-hover p-6 rounded-3xl flex flex-col justify-between min-h-[160px]">
          <div className="flex items-center justify-between">
            <div className="w-11 h-11 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center">
              <AlertCircle className="w-5 h-5" />
            </div>
            {renderTrend(lossA, lossB, false)}
          </div>
          <div className="mt-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Packet Loss Rate</span>
            <div className="text-3xl font-black text-slate-900 tracking-tight mt-0.5">
              {lossB !== null ? lossB.toFixed(1) + '%' : 'N/A'}
            </div>
            <div className="text-xs text-slate-500 font-medium mt-1">Undelivered packets</div>
          </div>
        </div>

      </div>

      {/* Performance Comparison (Charts with Reference Aesthetic) */}
      <div className="dash-card p-6 sm:p-8 rounded-3xl">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-8 gap-4 pb-4 border-b border-slate-100">
          <div>
            <h3 className="font-extrabold text-slate-900 text-xl tracking-tight">
              Performance Comparison
            </h3>
            <p className="text-xs text-slate-400 mt-0.5 font-medium">Under attack vs protected state</p>
          </div>
          <div className="flex items-center gap-4 text-xs font-extrabold">
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-50 text-rose-700 border border-rose-200">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span> Attack
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> Prevention
            </div>
          </div>
        </div>

        {hasComparisonData ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
             {/* PDR */}
             <div className="flex flex-col h-[300px] bg-[#f8f9fe] rounded-3xl p-5 border border-slate-200/60 justify-between">
               <div className="text-xs font-extrabold text-slate-700 text-center uppercase tracking-wider">
                 Packet Delivery Ratio
               </div>
               <div className="flex-1 flex items-end justify-center gap-8 pt-6 pb-2">
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-12">
                     <span className="text-xs font-black text-rose-600">{pdrA.toFixed(1)}%</span>
                     <div className="w-full bg-gradient-to-t from-rose-600 to-rose-400 rounded-t-xl shadow-xs transition-all duration-1000" style={{ height: `${pdrA}%`, minHeight: '6px' }}></div>
                     <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">Attack</span>
                  </div>
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-12">
                     <span className="text-xs font-black text-emerald-600">{pdrB.toFixed(1)}%</span>
                     <div className="w-full bg-gradient-to-t from-emerald-600 to-emerald-400 rounded-t-xl shadow-xs transition-all duration-1000" style={{ height: `${pdrB}%`, minHeight: '6px' }}></div>
                     <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">Safe</span>
                  </div>
               </div>
             </div>

             {/* Throughput */}
             <div className="flex flex-col h-[300px] bg-[#f8f9fe] rounded-3xl p-5 border border-slate-200/60 justify-between">
               <div className="text-xs font-extrabold text-slate-700 text-center uppercase tracking-wider">
                 Throughput (Mbps)
               </div>
               <div className="flex-1 flex items-end justify-center gap-8 pt-6 pb-2">
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-12">
                     <span className="text-xs font-black text-rose-600">{formatThroughput(thrA)}</span>
                     <div className="w-full bg-gradient-to-t from-rose-600 to-rose-400 rounded-t-xl shadow-xs transition-all duration-1000" style={{ height: `${Math.min((thrA / Math.max(thrA, thrB, 0.1)) * 100, 100)}%`, minHeight: '6px' }}></div>
                     <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">Attack</span>
                  </div>
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-12">
                     <span className="text-xs font-black text-emerald-600">{formatThroughput(thrB)}</span>
                     <div className="w-full bg-gradient-to-t from-emerald-600 to-emerald-400 rounded-t-xl shadow-xs transition-all duration-1000" style={{ height: `${Math.min((thrB / Math.max(thrA, thrB, 0.1)) * 100, 100)}%`, minHeight: '6px' }}></div>
                     <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">Safe</span>
                  </div>
               </div>
             </div>
             
             {/* End-to-End Delay */}
             <div className="flex flex-col h-[300px] bg-[#f8f9fe] rounded-3xl p-5 border border-slate-200/60 justify-between">
               <div className="text-xs font-extrabold text-slate-700 text-center uppercase tracking-wider">
                 Delay (ms)
               </div>
               <div className="flex-1 flex items-end justify-center gap-8 pt-6 pb-2">
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-12">
                     <span className="text-xs font-black text-rose-600">{delA.toFixed(1)}</span>
                     <div className="w-full bg-gradient-to-t from-rose-600 to-rose-400 rounded-t-xl shadow-xs transition-all duration-1000" style={{ height: `${Math.min((delA / Math.max(delA, delB, 0.1)) * 100, 100)}%`, minHeight: '6px' }}></div>
                     <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">Attack</span>
                  </div>
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-12">
                     <span className="text-xs font-black text-emerald-600">{delB.toFixed(1)}</span>
                     <div className="w-full bg-gradient-to-t from-emerald-600 to-emerald-400 rounded-t-xl shadow-xs transition-all duration-1000" style={{ height: `${Math.min((delB / Math.max(delA, delB, 0.1)) * 100, 100)}%`, minHeight: '6px' }}></div>
                     <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">Safe</span>
                  </div>
               </div>
             </div>
             
             {/* Packet Loss */}
             <div className="flex flex-col h-[300px] bg-[#f8f9fe] rounded-3xl p-5 border border-slate-200/60 justify-between">
               <div className="text-xs font-extrabold text-slate-700 text-center uppercase tracking-wider">
                 Packet Loss (%)
               </div>
               <div className="flex-1 flex items-end justify-center gap-8 pt-6 pb-2">
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-12">
                     <span className="text-xs font-black text-rose-600">{lossA.toFixed(1)}%</span>
                     <div className="w-full bg-gradient-to-t from-rose-600 to-rose-400 rounded-t-xl shadow-xs transition-all duration-1000" style={{ height: `${Math.min(lossA, 100)}%`, minHeight: '6px' }}></div>
                     <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">Attack</span>
                  </div>
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-12">
                     <span className="text-xs font-black text-emerald-600">{lossB.toFixed(1)}%</span>
                     <div className="w-full bg-gradient-to-t from-emerald-600 to-emerald-400 rounded-t-xl shadow-xs transition-all duration-1000" style={{ height: `${Math.min(lossB, 100)}%`, minHeight: '6px' }}></div>
                     <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mt-1">Safe</span>
                  </div>
               </div>
             </div>

          </div>
        ) : (
          <div className="py-14 text-center text-slate-400 flex flex-col items-center justify-center gap-2 bg-slate-50 rounded-2xl border border-slate-100">
            <AlertCircle className="w-8 h-8 text-slate-300" />
            <span className="font-semibold text-sm">Comparison data unavailable from backend.</span>
          </div>
        )}
      </div>

      {/* Metric Definitions */}
      <div className="dash-card p-6 rounded-3xl">
        <h3 className="text-xs font-bold text-slate-400 mb-4 uppercase tracking-wider flex items-center gap-2">
          <Info className="w-4 h-4 text-blue-500" /> Metric Definitions
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 text-sm">
          <div className="p-4 rounded-2xl bg-slate-50/80 border border-slate-100">
            <span className="font-extrabold text-slate-800 block mb-1">Packet Delivery Ratio</span>
            <span className="text-xs text-slate-500 leading-relaxed font-medium">Percentage of packets generated by the source successfully delivered to destination.</span>
          </div>
          <div className="p-4 rounded-2xl bg-slate-50/80 border border-slate-100">
            <span className="font-extrabold text-slate-800 block mb-1">Throughput</span>
            <span className="text-xs text-slate-500 leading-relaxed font-medium">Rate of successfully delivered digital throughput across the MANET hops.</span>
          </div>
          <div className="p-4 rounded-2xl bg-slate-50/80 border border-slate-100">
            <span className="font-extrabold text-slate-800 block mb-1">End-to-End Delay</span>
            <span className="text-xs text-slate-500 leading-relaxed font-medium">Average time in milliseconds taken for packets to traverse the multi-hop route.</span>
          </div>
          <div className="p-4 rounded-2xl bg-slate-50/80 border border-slate-100">
            <span className="font-extrabold text-slate-800 block mb-1">Packet Loss Rate</span>
            <span className="text-xs text-slate-500 leading-relaxed font-medium">Percentage of transmitted packets dropped or intercepted during transport.</span>
          </div>
        </div>
      </div>
      
    </div>
  );
};

export default PerformanceMetrics;
