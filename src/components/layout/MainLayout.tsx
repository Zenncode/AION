import { Outlet, NavLink } from 'react-router-dom';
import {
  HiOutlineChartBar,
  HiOutlineChatBubbleLeftRight,
  HiOutlineTableCells,
  HiOutlineArrowRightOnRectangle,
} from 'react-icons/hi2';
import keycloak from '@/auth/keycloak';

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: HiOutlineChartBar },
  { to: '/copilot', label: 'Copilot', icon: HiOutlineChatBubbleLeftRight },
  { to: '/data', label: 'Data', icon: HiOutlineTableCells },
];

export default function MainLayout() {


  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-[#1a2332] border-r border-[#334155] flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-[#334155]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white">
              A
            </div>
            <span className="text-lg font-semibold tracking-tight">AION</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600/20 text-blue-400'
                    : 'text-gray-400 hover:bg-[#334155] hover:text-white'
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* User */}
        <div className="p-3 border-t border-[#334155]">
          <div className="flex items-center gap-3 px-3 py-2">
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm font-medium">
              {keycloak?.tokenParsed?.name?.[0] || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">
                {keycloak?.tokenParsed?.name || 'Local Dev'}
              </p>
              <p className="text-xs text-gray-500 truncate">
                {keycloak?.tokenParsed?.email || 'dev@aion.local'}
              </p>
            </div>
            {keycloak?.authenticated && (
              <button
                onClick={() => keycloak.logout()}
                className="p-1.5 rounded-lg text-gray-500 hover:bg-[#334155] hover:text-white transition-colors"
                title="Sign out"
              >
                <HiOutlineArrowRightOnRectangle className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
