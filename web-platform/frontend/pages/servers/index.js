import { useState, useEffect } from 'react';
import Layout from '../../components/layout/Layout';
import { api } from '../../lib/api';

export default function ServersPage() {
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Mock data for now
    const mockServers = [
      {
        id: 1,
        name: 'FUT Trading Hub',
        description: 'Premium FUT trading community with daily signals and market analysis',
        member_count: 15000,
        invite_url: '#',
        icon_url: null,
        is_verified: true
      },
      {
        id: 2,
        name: 'Coin Kings',
        description: 'Learn trading from the best. Free tips and premium content available',
        member_count: 8500,
        invite_url: '#',
        icon_url: null,
        is_verified: true
      },
      {
        id: 3,
        name: 'FUT Market Watch',
        description: 'Real-time market updates and investment opportunities',
        member_count: 12000,
        invite_url: '#',
        icon_url: null,
        is_verified: false
      }
    ];

    setServers(mockServers);
    setLoading(false);
  }, []);

  return (
    <Layout title="Discord Servers - FUT Hub">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold mb-2">Discord Servers</h1>
            <p className="text-gray-600">
              Join FUT trading communities on Discord
            </p>
          </div>
          <button className="btn-primary">
            Submit Server
          </button>
        </div>

        {/* Server List */}
        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <div className="space-y-4">
            {servers.map(server => (
              <div
                key={server.id}
                className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow p-6"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-6">
                    <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white text-2xl font-bold">
                      {server.name.charAt(0)}
                    </div>

                    <div className="flex-1">
                      <div className="flex items-center mb-2">
                        <h3 className="text-xl font-semibold mr-2">
                          {server.name}
                        </h3>
                        {server.is_verified && (
                          <span className="text-blue-600" title="Verified Server">✓</span>
                        )}
                      </div>

                      <p className="text-gray-600 mb-3">
                        {server.description}
                      </p>

                      <div className="flex items-center space-x-4 text-sm text-gray-500">
                        <span className="flex items-center">
                          <span className="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
                          {server.member_count.toLocaleString()} members
                        </span>
                      </div>
                    </div>
                  </div>

                  <a
                    href={server.invite_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-primary whitespace-nowrap"
                  >
                    Join Server
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Info Banner */}
        <div className="mt-12 bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-yellow-900 mb-2">
            Want to list your server?
          </h3>
          <p className="text-yellow-700 mb-4">
            Submit your FUT trading Discord server to reach thousands of potential members.
          </p>
          <button className="bg-yellow-600 text-white px-6 py-2 rounded-lg hover:bg-yellow-700 transition-colors">
            Submit Your Server
          </button>
        </div>
      </div>
    </Layout>
  );
}
