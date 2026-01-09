import Link from 'next/link';
import { useState } from 'react';

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <nav className="bg-white shadow-lg sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Logo and primary nav */}
          <div className="flex">
            <Link href="/" className="flex items-center">
              <span className="text-2xl font-bold text-blue-600">FUT Hub</span>
            </Link>

            {/* Desktop Navigation */}
            <div className="hidden md:ml-10 md:flex md:space-x-8">
              <Link href="/traders" className="inline-flex items-center px-1 pt-1 text-gray-900 hover:text-blue-600 transition-colors">
                Traders
              </Link>
              <Link href="/signals" className="inline-flex items-center px-1 pt-1 text-gray-900 hover:text-blue-600 transition-colors">
                Signals
              </Link>
              <Link href="/community" className="inline-flex items-center px-1 pt-1 text-gray-900 hover:text-blue-600 transition-colors">
                Community
              </Link>
              <Link href="/tools" className="inline-flex items-center px-1 pt-1 text-gray-900 hover:text-blue-600 transition-colors">
                Tools
              </Link>
              <Link href="/servers" className="inline-flex items-center px-1 pt-1 text-gray-900 hover:text-blue-600 transition-colors">
                Discord Servers
              </Link>
            </div>
          </div>

          {/* Right side - Auth buttons */}
          <div className="hidden md:flex md:items-center md:space-x-4">
            <Link href="/login" className="text-gray-700 hover:text-gray-900 px-3 py-2">
              Login
            </Link>
            <Link href="/signup" className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">
              Sign Up
            </Link>
          </div>

          {/* Mobile menu button */}
          <div className="flex items-center md:hidden">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="inline-flex items-center justify-center p-2 rounded-md text-gray-700 hover:text-gray-900 hover:bg-gray-100"
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
        <div className="md:hidden">
          <div className="pt-2 pb-3 space-y-1">
            <Link href="/traders" className="block pl-3 pr-4 py-2 border-l-4 border-transparent text-gray-700 hover:bg-gray-50 hover:border-blue-600">
              Traders
            </Link>
            <Link href="/signals" className="block pl-3 pr-4 py-2 border-l-4 border-transparent text-gray-700 hover:bg-gray-50 hover:border-blue-600">
              Signals
            </Link>
            <Link href="/community" className="block pl-3 pr-4 py-2 border-l-4 border-transparent text-gray-700 hover:bg-gray-50 hover:border-blue-600">
              Community
            </Link>
            <Link href="/tools" className="block pl-3 pr-4 py-2 border-l-4 border-transparent text-gray-700 hover:bg-gray-50 hover:border-blue-600">
              Tools
            </Link>
            <Link href="/servers" className="block pl-3 pr-4 py-2 border-l-4 border-transparent text-gray-700 hover:bg-gray-50 hover:border-blue-600">
              Discord Servers
            </Link>
          </div>
          <div className="pt-4 pb-3 border-t border-gray-200">
            <div className="flex items-center px-4 space-x-3">
              <Link href="/login" className="text-gray-700 hover:text-gray-900">
                Login
              </Link>
              <Link href="/signup" className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
                Sign Up
              </Link>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
