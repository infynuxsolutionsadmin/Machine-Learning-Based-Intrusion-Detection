import React from 'react';
import { Menu, Search, Bell } from 'lucide-react';
import { useLocation } from 'react-router-dom';

const Navbar = ({ toggleSidebar }) => {
  const location = useLocation();
  const path = location.pathname;
  
  let pageTitle = 'Dashboard';
  let pageSubtitle = 'Real-time MANET intelligence & overview';

  if (path === '/simulation') {
    pageTitle = 'Simulation Control';
    pageSubtitle = 'Configure parameters & run network simulations';
  } else if (path === '/network') {
    pageTitle = 'Network Topology';
    pageSubtitle = 'Interactive topology & secure routing paths';
  } else if (path === '/ml-detection') {
    pageTitle = 'ML Detection';
    pageSubtitle = 'Classical ML & LSTM trust score classification';
  } else if (path === '/prevention') {
    pageTitle = 'Prevention';
    pageSubtitle = 'Threat mitigation & automated node isolation';
  } else if (path === '/route-recovery') {
    pageTitle = 'Route Recovery';
    pageSubtitle = 'Secure alternative route convergence';
  } else if (path === '/performance') {
    pageTitle = 'Performance Metrics';
    pageSubtitle = 'Network QoS evaluation: PDR, delay & throughput';
  }

  // Format today's date cleanly like the reference image "Friday, December 15th 2023"
  const todayFormatted = new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  }).format(new Date());

  return (
    <header className="py-6 px-4 sm:px-6 lg:px-8 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3">
        <button 
          className="lg:hidden text-slate-600 hover:text-slate-900 bg-white p-2.5 rounded-2xl shadow-xs border border-slate-200/80 transition-colors focus:outline-none" 
          onClick={toggleSidebar}
          aria-label="Toggle Navigation"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            {pageTitle}
          </h1>
          <p className="text-xs sm:text-sm font-medium text-slate-500 mt-0.5">
            {todayFormatted} • {pageSubtitle}
          </p>
        </div>
      </div>

      {/* Top Right Controls (Search, Notification Bell, User Avatar Chip) */}
      <div className="flex items-center gap-3">
        {/* Search circle icon */}
        {/* <button 
          className="w-10 h-10 rounded-full bg-white border border-slate-200/80 shadow-xs flex items-center justify-center text-slate-500 hover:text-slate-900 hover:border-slate-300 transition-all focus:outline-none"
          title="Search"
          aria-label="Search"
        >
          <Search className="w-4 h-4" />
        </button> */}

        {/* Notifications circle icon with indicator */}
        <button 
          className="w-10 h-10 rounded-full bg-white border border-slate-200/80 shadow-xs flex items-center justify-center text-slate-500 hover:text-slate-900 hover:border-slate-300 transition-all relative focus:outline-none"
          title="Notifications"
          aria-label="Notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-2.5 right-2.5 w-2 h-2 rounded-full bg-rose-500 ring-2 ring-white"></span>
        </button>

        {/* User Profile */}
        <div className="hidden sm:flex items-center gap-3 pl-2">
          <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 p-0.5 shadow-xs">
            <div className="w-full h-full rounded-full bg-white flex items-center justify-center font-bold text-xs text-indigo-700 uppercase">
              A
            </div>
          </div>
          <div className="text-left hidden md:block">
            <div className="font-bold text-sm text-slate-900 leading-tight">Admin</div>
            {/* <div className="text-[11px] font-medium text-slate-400">Admin Operator</div> */}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Navbar;
