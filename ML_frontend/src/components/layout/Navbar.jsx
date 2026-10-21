import React from 'react';
import { Menu } from 'lucide-react';
import { useLocation } from 'react-router-dom';

const Navbar = ({ toggleSidebar }) => {
  const location = useLocation();
  const path = location.pathname;
  
  let pageTitle = 'Dashboard';
  if (path === '/simulation') pageTitle = 'Simulation Control';
  else if (path === '/network') pageTitle = 'Network Topology';
  else if (path === '/ml-detection') pageTitle = 'ML Detection';
  else if (path === '/prevention') pageTitle = 'Prevention';
  else if (path === '/route-recovery') pageTitle = 'Route Recovery';
  else if (path === '/performance') pageTitle = 'Performance Metrics';

  return (
    <header className="h-20 bg-white/80 backdrop-blur-xl shadow-[0_4px_20px_-15px_rgba(0,0,0,0.1)] border-b border-slate-200/80 flex items-center px-6 lg:px-10 shrink-0 sticky top-0 z-10 transition-all">
      <button 
        className="lg:hidden mr-5 text-slate-500 hover:text-blue-600 hover:bg-slate-100 p-2 rounded-lg transition-colors focus:outline-none" 
        onClick={toggleSidebar}
      >
        <Menu className="h-6 w-6" />
      </button>
      <h1 className="text-2xl font-black text-slate-800 tracking-tight">{pageTitle}</h1>
    </header>
  );
};

export default Navbar;
