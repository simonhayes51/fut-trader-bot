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
    <nav className="bg-black border-b border-purple-500/20 shadow-2xl sticky top-0 z-50 backdrop-blur-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Logo and primary nav */}
          <div className="flex">
            <Link href="/" className="flex items-center space-x-2">
              <span className="text-3xl">⚽</span>
              <span className="text-2xl font-black bg-gradient-to-r from-pink-500 to-purple-500 bg-clip-text text-transparent drop-shadow-lg">
                FUT Hub
              </span>
            </Link>

            {/* Desktop Navigation */}
            <div className="hidden md:ml-10 md:flex md:space-x-6">
              <Link href="/feed" className="inline-flex items-center px-3 py-1 text-purple-300 hover:text-purple-100 transition-colors font-bold border-b-2 border-transparent hover:border-purple-500">
                🔴 Live Feed
              </Link>
              <Link href="/traders" className="inline-flex items-center px-3 py-1 text-purple-300 hover:text-purple-100 transition-colors font-bold border-b-2 border-transparent hover:border-purple-500">
                Traders
              </Link>
              <Link href="/signals" className="inline-flex items-center px-3 py-1 text-purple-300 hover:text-purple-100 transition-colors font-bold border-b-2 border-transparent hover:border-purple-500">
                Signals
              </Link>
              <Link href="/community" className="inline-flex items-center px-3 py-1 text-purple-300 hover:text-purple-100 transition-colors font-bold border-b-2 border-transparent hover:border-purple-500">
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
                  className="flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-purple-900/30 transition-colors border border-purple-500/20"
                >
                  <img
                    src={user.avatar || 'https://cdn.discordapp.com/embed/avatars/0.png'}
                    alt={user.username}
                    className="w-8 h-8 rounded-full ring-2 ring-purple-500"
                  />
                  <span className="font-bold text-white">{user.username}</span>
                  <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-gray-900 border border-purple-500/20 rounded-lg shadow-2xl py-1 z-50">
                    <Link href="/feed" className="block px-4 py-2 text-purple-300 hover:bg-purple-900/30 hover:text-white font-medium">
                      🔴 Live Feed
                    </Link>
                    <Link href="/dashboard" className="block px-4 py-2 text-purple-300 hover:bg-purple-900/30 hover:text-white font-medium">
                      📊 Dashboard
                    </Link>
                    <Link href="/settings" className="block px-4 py-2 text-purple-300 hover:bg-purple-900/30 hover:text-white font-medium">
                      ⚙️ Settings
                    </Link>
                    <div className="border-t border-purple-500/20 my-1"></div>
                    <button
                      onClick={handleLogout}
                      className="block w-full text-left px-4 py-2 text-pink-400 hover:bg-purple-900/30 font-medium"
                    >
                      🚪 Logout
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <>
                <Link href="/login" className="text-purple-300 hover:text-white px-4 py-2 font-bold transition-colors">
                  Login
                </Link>
                <Link href="/signup" className="bg-gradient-to-r from-pink-500 to-purple-500 text-white px-6 py-2 rounded-lg hover:from-pink-600 hover:to-purple-600 transition-all shadow-lg hover:shadow-pink-500/50 font-bold">
                  Sign Up
                </Link>
              </>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="flex items-center md:hidden">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="inline-flex items-center justify-center p-2 rounded-md text-white hover:text-purple-400 hover:bg-purple-900/30"
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
        <div className="md:hidden bg-gray-900 border-t border-purple-500/20">
          <div className="pt-2 pb-3 space-y-1">
            <Link href="/feed" className="block pl-3 pr-4 py-2 text-purple-300 hover:bg-purple-900/30 hover:text-white font-bold">
              🔴 Live Feed
            </Link>
            <Link href="/traders" className="block pl-3 pr-4 py-2 text-purple-300 hover:bg-purple-900/30 hover:text-white font-bold">
              Traders
            </Link>
            <Link href="/signals" className="block pl-3 pr-4 py-2 text-purple-300 hover:bg-purple-900/30 hover:text-white font-bold">
              Signals
            </Link>
            <Link href="/community" className="block pl-3 pr-4 py-2 text-purple-300 hover:bg-purple-900/30 hover:text-white font-bold">
              Community
            </Link>
          </div>

          {user ? (
            <div className="pt-4 pb-3 border-t border-purple-500/20">
              <div className="flex items-center px-4 mb-3">
                <img
                  src={user.avatar || 'https://cdn.discordapp.com/embed/avatars/0.png'}
                  alt={user.username}
                  className="w-10 h-10 rounded-full ring-2 ring-purple-500"
                />
                <div className="ml-3">
                  <div className="text-base font-bold text-white">{user.username}</div>
                  <div className="text-sm text-purple-400">{user.email}</div>
                </div>
              </div>
              <div className="space-y-1">
                <Link href="/dashboard" className="block px-4 py-2 text-purple-300 hover:bg-purple-900/30 hover:text-white font-medium">
                  📊 Dashboard
                </Link>
                <Link href="/settings" className="block px-4 py-2 text-purple-300 hover:bg-purple-900/30 hover:text-white font-medium">
                  ⚙️ Settings
                </Link>
                <button
                  onClick={handleLogout}
                  className="block w-full text-left px-4 py-2 text-pink-400 hover:bg-purple-900/30 font-medium"
                >
                  🚪 Logout
                </button>
              </div>
            </div>
          ) : (
            <div className="pt-4 pb-3 border-t border-purple-500/20">
              <div className="flex items-center px-4 space-x-3">
                <Link href="/login" className="flex-1 text-center text-purple-300 hover:text-white px-4 py-2 border border-purple-500/20 rounded-lg font-bold">
                  Login
                </Link>
                <Link href="/signup" className="flex-1 text-center bg-gradient-to-r from-pink-500 to-purple-500 text-white px-4 py-2 rounded-lg font-bold shadow-lg">
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
