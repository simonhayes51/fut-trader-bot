import Link from 'next/link';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';

export default function Sidebar() {
  const [user, setUser] = useState(null);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        setUser(payload);
      } catch (error) {
        console.error('Invalid token:', error);
        localStorage.removeItem('auth_token');
      }
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    setUser(null);
    router.push('/');
  };

  const navItems = [
    { icon: '🏠', label: 'Feed', href: '/feed', active: true },
    { icon: '🔍', label: 'Discover', href: '/traders' },
    { icon: '➕', label: 'Post Signal', href: '/upload-signal', traderOnly: true },
    { icon: '🔔', label: 'Notifications', href: '/notifications', badge: 3 },
    { icon: '🔖', label: 'Saved', href: '/saved' },
  ];

  const tools = [
    { icon: '🔍', label: 'Price Checker', href: '/tools/price-checker' },
    { icon: '📈', label: 'Market Trends', href: '/tools/market-trends' },
    { icon: '🎯', label: 'SBC Solver', href: '/tools/sbc-solver' },
    { icon: '⚽', label: 'Squad Builder', href: '/tools/squad-builder' },
  ];

  return (
    <div className="fixed left-0 top-0 h-screen w-64 bg-[#0A0A0A] border-r border-gray-800 flex flex-col">
      {/* Logo */}
      <div className="p-6">
        <Link href="/feed" className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-cyan-400 to-cyan-600 rounded-xl flex items-center justify-center">
            <span className="text-white font-black text-xl">📊</span>
          </div>
          <span className="text-white font-black text-2xl">FCHUB</span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3">
        <div className="space-y-1 mb-8">
          {navItems.map((item) => {
            // Hide trader-only items if user is not a trader
            if (item.traderOnly && (!user || !user.is_trader)) {
              return null;
            }

            return (
              <Link key={item.href} href={item.href}>
                <div className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all cursor-pointer ${
                  item.active
                    ? 'bg-cyan-500/10 text-cyan-400'
                    : 'text-gray-400 hover:bg-gray-800/50 hover:text-white'
                }`}>
                  <span className="text-xl">{item.icon}</span>
                  <span className="font-semibold">{item.label}</span>
                  {item.badge && (
                    <span className="ml-auto bg-cyan-500 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                      {item.badge}
                    </span>
                  )}
                </div>
              </Link>
            );
          })}
        </div>

        {/* Tools Section */}
        <div className="mb-8">
          <div className="px-4 mb-3 text-xs font-bold text-gray-500 uppercase tracking-wider">
            TOOLS
          </div>
          <div className="space-y-1">
            {tools.map((tool) => (
              <Link key={tool.href} href={tool.href}>
                <div className="flex items-center gap-3 px-4 py-3 rounded-xl text-gray-400 hover:bg-gray-800/50 hover:text-white transition-all cursor-pointer">
                  <span className="text-lg">{tool.icon}</span>
                  <span className="font-medium">{tool.label}</span>
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Settings & Logout */}
        <div className="space-y-1">
          <Link href="/settings">
            <div className="flex items-center gap-3 px-4 py-3 rounded-xl text-gray-400 hover:bg-gray-800/50 hover:text-white transition-all cursor-pointer">
              <span className="text-lg">⚙️</span>
              <span className="font-medium">Settings</span>
            </div>
          </Link>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-gray-400 hover:bg-gray-800/50 hover:text-white transition-all"
          >
            <span className="text-lg">🚪</span>
            <span className="font-medium">Log Out</span>
          </button>
        </div>
      </nav>

      {/* User Profile at Bottom */}
      {user && (
        <div className="p-4 border-t border-gray-800">
          <div className="flex items-center gap-3">
            <img
              src={user.avatar || 'https://cdn.discordapp.com/embed/avatars/0.png'}
              alt={user.username}
              className="w-12 h-12 rounded-full border-2 border-cyan-500"
            />
            <div className="flex-1 min-w-0">
              <div className="font-bold text-white text-sm truncate">{user.username}</div>
              <div className="text-xs text-gray-500 truncate">@{user.username.toLowerCase()}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
