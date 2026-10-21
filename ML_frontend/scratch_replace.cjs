const fs = require('fs');
const file = 'c:/Users/divya/OneDrive/Desktop/ML_MANET/frontend/src/pages/PerformanceMetrics.jsx';
const content = fs.readFileSync(file, 'utf8');
const lines = content.split('\n');

const newLines = [];
for (let i = 0; i < lines.length; i++) {
  if (i < 130) {
    newLines.push(lines[i]);
  } else if (i > 283) {
    newLines.push(lines[i]);
  } else if (i === 130) {
    newLines.push(lines[i]); // blank line 130
    
    // insert replacement block
    newLines.push(`      {/* Performance Comparison (Vertical Charts) */}
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
                     <div className="w-full bg-red-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: \`\${pdrA}%\`, minHeight: '4px' }}></div>
                     <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-1">Attack</span>
                  </div>
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-14">
                     <span className="text-xs font-bold text-slate-700">{pdrB.toFixed(1)}%</span>
                     <div className="w-full bg-emerald-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: \`\${pdrB}%\`, minHeight: '4px' }}></div>
                     <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-1">Prevention</span>
                  </div>
               </div>
             </div>

             {/* Throughput */}
             <div className="flex flex-col h-[280px] bg-slate-50/50 rounded-xl p-5 border border-slate-100 shadow-sm">
               <div className="text-sm font-bold text-slate-700 text-center mb-6">Throughput (Mbps)</div>
               <div className="flex-1 flex items-end justify-center gap-8 md:gap-12">
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-14">
                     <span className="text-xs font-bold text-slate-700">{thrA.toFixed(2)}</span>
                     <div className="w-full bg-red-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: \`\${Math.min((thrA / Math.max(thrA, thrB, 0.1)) * 100, 100)}%\`, minHeight: '4px' }}></div>
                     <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-1">Attack</span>
                  </div>
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-14">
                     <span className="text-xs font-bold text-slate-700">{thrB.toFixed(2)}</span>
                     <div className="w-full bg-emerald-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: \`\${Math.min((thrB / Math.max(thrA, thrB, 0.1)) * 100, 100)}%\`, minHeight: '4px' }}></div>
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
                     <div className="w-full bg-red-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: \`\${Math.min((delA / Math.max(delA, delB, 0.1)) * 100, 100)}%\`, minHeight: '4px' }}></div>
                     <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-1">Attack</span>
                  </div>
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-14">
                     <span className="text-xs font-bold text-slate-700">{delB.toFixed(1)}</span>
                     <div className="w-full bg-emerald-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: \`\${Math.min((delB / Math.max(delA, delB, 0.1)) * 100, 100)}%\`, minHeight: '4px' }}></div>
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
                     <div className="w-full bg-red-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: \`\${Math.min(lossA, 100)}%\`, minHeight: '4px' }}></div>
                     <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-1">Attack</span>
                  </div>
                  <div className="flex flex-col items-center gap-2 h-full justify-end w-14">
                     <span className="text-xs font-bold text-slate-700">{lossB.toFixed(1)}%</span>
                     <div className="w-full bg-emerald-400 rounded-t shadow-sm transition-all duration-1000" style={{ height: \`\${Math.min(lossB, 100)}%\`, minHeight: '4px' }}></div>
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
`);
  }
}

fs.writeFileSync(file, newLines.join('\n'), 'utf8');
console.log('SUCCESS');
