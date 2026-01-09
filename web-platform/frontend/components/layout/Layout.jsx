import Navbar from './Navbar';
import Head from 'next/head';

export default function Layout({ children, title = 'FUT Hub' }) {
  return (
    <>
      <Head>
        <title>{title}</title>
        <meta name="description" content="FUT Hub - Premium FUT Trading Platform" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div className="min-h-screen flex flex-col">
        <Navbar />

        <main className="flex-grow">
          {children}
        </main>

        <footer className="bg-gray-800 text-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
              <div>
                <h3 className="text-lg font-semibold mb-4">FUT Hub</h3>
                <p className="text-gray-400 text-sm">
                  Premium FUT trading platform connecting traders with the community.
                </p>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-4 uppercase">Platform</h4>
                <ul className="space-y-2 text-sm">
                  <li><a href="/traders" className="text-gray-400 hover:text-white">Browse Traders</a></li>
                  <li><a href="/signals" className="text-gray-400 hover:text-white">Trading Signals</a></li>
                  <li><a href="/community" className="text-gray-400 hover:text-white">Community</a></li>
                  <li><a href="/tools" className="text-gray-400 hover:text-white">Free Tools</a></li>
                </ul>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-4 uppercase">Support</h4>
                <ul className="space-y-2 text-sm">
                  <li><a href="/help" className="text-gray-400 hover:text-white">Help Center</a></li>
                  <li><a href="/terms" className="text-gray-400 hover:text-white">Terms of Service</a></li>
                  <li><a href="/privacy" className="text-gray-400 hover:text-white">Privacy Policy</a></li>
                  <li><a href="/contact" className="text-gray-400 hover:text-white">Contact Us</a></li>
                </ul>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-4 uppercase">Connect</h4>
                <ul className="space-y-2 text-sm">
                  <li><a href="#" className="text-gray-400 hover:text-white">Discord</a></li>
                  <li><a href="#" className="text-gray-400 hover:text-white">Twitter</a></li>
                  <li><a href="#" className="text-gray-400 hover:text-white">YouTube</a></li>
                </ul>
              </div>
            </div>

            <div className="mt-8 pt-8 border-t border-gray-700 text-center text-sm text-gray-400">
              <p>&copy; 2025 FUT Hub. All rights reserved.</p>
            </div>
          </div>
        </footer>
      </div>
    </>
  );
}
