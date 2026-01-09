import Link from 'next/link';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [user, setUser] = useState(null);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    // Check if user is logged in
    const token = localStorage.getItem('auth_token');
    if (token) {
      try {
        // Decode JWT to get user info
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
    setUserMenuOpen(false);
    router.push('/');
  };

  return (
    <nav className="bg-gradient-to-r from-green-700 via-green-600 to-emerald-700 shadow-2xl sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Logo and primary nav */}
          <div className="flex">
            <Link href="/" className="flex items-center space-x-2">
              <span className="text-3xl">⚽</span>
              <span className="text-2xl font-black text-yellow-400 drop-shadow-lg">
                FUT Hub
              </span>
            </Link>

            {/* Desktop Navigation */}
            <div className="hidden md:ml-10 md:flex md:space-x-8">
              <Link href="/traders" className="inline-flex items-center px-1 pt-1 text-white hover:text-yellow-400 transition-colors font-bold border-b-2 border-transparent hover:border-yellow-400">
                Traders
              </Link>
              <Link href="/signals" className="inline-flex items-center px-1 pt-1 text-white hover:text-yellow-400 transition-colors font-bold border-b-2 border-transparent hover:border-yellow-400">
                Signals
              </Link>
              <Link href="/community" className="inline-flex items-center px-1 pt-1 text-white hover:text-yellow-400 transition-colors font-bold border-b-2 border-transparent hover:border-yellow-400">
                Community
              </Link>
            </div>
          </div>

          {/* Right side - Auth buttons or User menu */}
          <div className="hidden md:flex md:items-center md:space-x-4">
            {user ? (
              <div className="relative">
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-white/10 transition-colors"
                >
                  <img
                    src={user.avatar || 'https://cdn.discordapp.com/embed/avatars/0.png'}
                    alt={user.username}
                    className="w-8 h-8 rounded-full ring-2 ring-yellow-400"
                  />
                  <span className="font-bold text-white">{user.username}</span>
                  <svg className="w-4 h-4 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-2xl border border-gray-200 py-1 z-50">
                    <Link href="/dashboard" className="block px-4 py-2 text-gray-700 hover:bg-green-50 hover:text-green-700 font-medium">
                      📊 Dashboard
                    </Link>
                    <Link href="/settings" className="block px-4 py-2 text-gray-700 hover:bg-green-50 hover:text-green-700 font-medium">
                      ⚙️ Settings
                    </Link>
                    <div className="border-t border-gray-200 my-1"></div>
                    <button
                      onClick={handleLogout}
                      className="block w-full text-left px-4 py-2 text-red-600 hover:bg-red-50 font-medium"
                    >
                      🚪 Logout
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <>
                <Link href="/login" className="text-white hover:text-yellow-400 px-4 py-2 font-bold transition-colors">
                  Login
                </Link>
                <Link href="/signup" className="bg-yellow-400 text-gray-900 px-6 py-2 rounded-lg hover:bg-yellow-300 transition-all shadow-lg hover:shadow-xl font-black">
                  Sign Up
                </Link>
              </>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="flex items-center md:hidden">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="inline-flex items-center justify-center p-2 rounded-md text-white hover:text-yellow-400 hover:bg-white/10"
            >
              <span className="sr-only">Open main menu</span>
              {mobileMenuOpen ? (
                <svg className="block h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="block h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-white border-t border-green-200">
          <div className="pt-2 pb-3 space-y-1">
            <Link href="/traders" className="block pl-3 pr-4 py-2 text-gray-700 hover:bg-green-50 hover:text-green-700 font-bold">
              Traders
            </Link>
            <Link href="/signals" className="block pl-3 pr-4 py-2 text-gray-700 hover:bg-green-50 hover:text-green-700 font-bold">
              Signals
            </Link>
            <Link href="/community" className="block pl-3 pr-4 py-2 text-gray-700 hover:bg-green-50 hover:text-green-700 font-bold">
              Community
            </Link>
          </div>

          {user ? (
            <div className="pt-4 pb-3 border-t border-gray-200">
              <div className="flex items-center px-4 mb-3">
                <img
                  src={user.avatar || 'https://cdn.discordapp.com/embed/avatars/0.png'}
                  alt={user.username}
                  className="w-10 h-10 rounded-full ring-2 ring-green-500"
                />
                <div className="ml-3">
                  <div className="text-base font-bold text-gray-800">{user.username}</div>
                  <div className="text-sm text-gray-500">{user.email}</div>
                </div>
              </div>
              <div className="space-y-1">
                <Link href="/dashboard" className="block px-4 py-2 text-gray-700 hover:bg-green-50 hover:text-green-700 font-medium">
                  📊 Dashboard
                </Link>
                <Link href="/settings" className="block px-4 py-2 text-gray-700 hover:bg-green-50 hover:text-green-700 font-medium">
                  ⚙️ Settings
                </Link>
                <button
                  onClick={handleLogout}
                  className="block w-full text-left px-4 py-2 text-red-600 hover:bg-red-50 font-medium"
                >
                  🚪 Logout
                </button>
              </div>
            </div>
          ) : (
            <div className="pt-4 pb-3 border-t border-gray-200">
              <div className="flex items-center px-4 space-x-3">
                <Link href="/login" className="flex-1 text-center text-gray-700 hover:text-gray-900 px-4 py-2 border border-gray-300 rounded-lg font-bold">
                  Login
                </Link>
                <Link href="/signup" className="flex-1 text-center bg-yellow-400 text-gray-900 px-4 py-2 rounded-lg hover:bg-yellow-300 font-black shadow-lg">
                  Sign Up
                </Link>
              </div>
            </div>
          )}
        </div>
      )}
    </nav>
  );
}
