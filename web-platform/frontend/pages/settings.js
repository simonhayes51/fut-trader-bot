import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/layout/Layout';
import { api } from '../lib/api';
import toast from 'react-hot-toast';

export default function Settings() {
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [activeTab, setActiveTab] = useState('profile');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      router.push('/login');
      return;
    }

    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      setUser(payload);
      setLoading(false);
    } catch (error) {
      console.error('Invalid token:', error);
      localStorage.removeItem('auth_token');
      router.push('/login');
    }
  }, []);

  if (loading) {
    return (
      <Layout title="Settings">
        <div className="min-h-screen flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-600"></div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Settings - FUT Hub">
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <div className="bg-gradient-to-r from-green-600 to-emerald-600 text-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <h1 className="text-3xl font-bold">⚙️ Account Settings</h1>
            <p className="text-green-100 mt-2">Manage your profile, subscriptions, and preferences</p>
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
            {/* Sidebar Navigation */}
            <div className="lg:col-span-1">
              <div className="bg-white rounded-xl shadow-lg overflow-hidden sticky top-8">
                <div className="p-6 border-b border-gray-200">
                  <div className="flex items-center space-x-3">
                    <img
                      src={user?.avatar || '/default-avatar.png'}
                      alt={user?.username}
                      className="w-16 h-16 rounded-full border-2 border-green-500"
                    />
                    <div>
                      <h3 className="font-bold text-gray-900">{user?.username}</h3>
                      <span className="text-sm text-green-600">✓ Premium Member</span>
                    </div>
                  </div>
                </div>

                <nav className="p-2">
                  <button
                    onClick={() => setActiveTab('profile')}
                    className={`w-full text-left px-4 py-3 rounded-lg font-medium transition-colors mb-1 ${
                      activeTab === 'profile'
                        ? 'bg-green-100 text-green-700'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    👤 Profile
                  </button>
                  <button
                    onClick={() => setActiveTab('subscriptions')}
                    className={`w-full text-left px-4 py-3 rounded-lg font-medium transition-colors mb-1 ${
                      activeTab === 'subscriptions'
                        ? 'bg-green-100 text-green-700'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    💎 Subscriptions
                  </button>
                  <button
                    onClick={() => setActiveTab('notifications')}
                    className={`w-full text-left px-4 py-3 rounded-lg font-medium transition-colors mb-1 ${
                      activeTab === 'notifications'
                        ? 'bg-green-100 text-green-700'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    🔔 Notifications
                  </button>
                  <button
                    onClick={() => setActiveTab('security')}
                    className={`w-full text-left px-4 py-3 rounded-lg font-medium transition-colors ${
                      activeTab === 'security'
                        ? 'bg-green-100 text-green-700'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    🔒 Security
                  </button>
                </nav>
              </div>
            </div>

            {/* Main Content */}
            <div className="lg:col-span-3">
              {/* Profile Tab */}
              {activeTab === 'profile' && (
                <div className="bg-white rounded-xl shadow-lg p-8">
                  <h2 className="text-2xl font-bold text-gray-900 mb-6">Profile Information</h2>

                  <div className="space-y-6">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Username
                      </label>
                      <input
                        type="text"
                        value={user?.username || ''}
                        disabled
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-gray-50 text-gray-500"
                      />
                      <p className="text-xs text-gray-500 mt-1">Username cannot be changed</p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Email Address
                      </label>
                      <input
                        type="email"
                        value={user?.email || ''}
                        disabled
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-gray-50 text-gray-500"
                      />
                      <p className="text-xs text-gray-500 mt-1">Linked to your Discord account</p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Discord ID
                      </label>
                      <input
                        type="text"
                        value={user?.discord_id || ''}
                        disabled
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg bg-gray-50 text-gray-500"
                      />
                    </div>

                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <p className="text-sm text-blue-800">
                        💡 Your profile is managed through Discord. To update your username or avatar,
                        update them in Discord and log in again.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Subscriptions Tab */}
              {activeTab === 'subscriptions' && (
                <div className="bg-white rounded-xl shadow-lg p-8">
                  <h2 className="text-2xl font-bold text-gray-900 mb-6">Your Subscriptions</h2>

                  <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-dashed border-blue-300 rounded-xl p-12 text-center">
                    <span className="text-6xl mb-4 block">💎</span>
                    <h3 className="text-xl font-bold text-gray-900 mb-2">
                      No Active Subscriptions
                    </h3>
                    <p className="text-gray-600 mb-6">
                      Subscribe to elite traders to unlock exclusive signals and premium content
                    </p>
                    <button
                      onClick={() => router.push('/traders')}
                      className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-8 py-3 rounded-lg font-semibold hover:from-blue-700 hover:to-indigo-700 transition-all shadow-lg"
                    >
                      Browse Pro Traders
                    </button>
                  </div>

                  <div className="mt-8 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <h3 className="font-semibold text-yellow-900 mb-2">
                      ⚡ Coming Soon: Subscription Management
                    </h3>
                    <p className="text-sm text-yellow-800">
                      Soon you'll be able to manage all your subscriptions, view billing history,
                      and cancel subscriptions directly from this page.
                    </p>
                  </div>
                </div>
              )}

              {/* Notifications Tab */}
              {activeTab === 'notifications' && (
                <div className="bg-white rounded-xl shadow-lg p-8">
                  <h2 className="text-2xl font-bold text-gray-900 mb-6">Notification Preferences</h2>

                  <div className="space-y-6">
                    <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                      <div>
                        <h3 className="font-semibold text-gray-900">New Signal Alerts</h3>
                        <p className="text-sm text-gray-500">Get notified when traders post new signals</p>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" className="sr-only peer" defaultChecked />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600"></div>
                      </label>
                    </div>

                    <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                      <div>
                        <h3 className="font-semibold text-gray-900">Signal Updates</h3>
                        <p className="text-sm text-gray-500">Updates on signals you're following</p>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" className="sr-only peer" defaultChecked />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600"></div>
                      </label>
                    </div>

                    <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                      <div>
                        <h3 className="font-semibold text-gray-900">Email Notifications</h3>
                        <p className="text-sm text-gray-500">Receive updates via email</p>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" className="sr-only peer" />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600"></div>
                      </label>
                    </div>

                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mt-6">
                      <p className="text-sm text-yellow-800">
                        💡 Notification settings are currently view-only. Full functionality coming soon!
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Security Tab */}
              {activeTab === 'security' && (
                <div className="bg-white rounded-xl shadow-lg p-8">
                  <h2 className="text-2xl font-bold text-gray-900 mb-6">Security Settings</h2>

                  <div className="space-y-6">
                    <div className="bg-green-50 border border-green-200 rounded-lg p-6">
                      <div className="flex items-start space-x-4">
                        <span className="text-3xl">🔒</span>
                        <div>
                          <h3 className="font-semibold text-green-900 mb-2">
                            Secured with Discord OAuth
                          </h3>
                          <p className="text-sm text-green-800">
                            Your account is protected by Discord's authentication system.
                            No passwords are stored on FUT Hub.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="border border-gray-200 rounded-lg p-6">
                      <h3 className="font-semibold text-gray-900 mb-2">Connected Accounts</h3>
                      <div className="flex items-center justify-between mt-4">
                        <div className="flex items-center space-x-3">
                          <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
                            <span className="text-xl">💬</span>
                          </div>
                          <div>
                            <p className="font-medium text-gray-900">Discord</p>
                            <p className="text-sm text-gray-500">Connected as {user?.username}</p>
                          </div>
                        </div>
                        <span className="text-green-600 font-medium">✓ Connected</span>
                      </div>
                    </div>

                    <div className="border border-gray-200 rounded-lg p-6">
                      <h3 className="font-semibold text-gray-900 mb-4">Account Actions</h3>
                      <button
                        onClick={() => {
                          if (confirm('Are you sure you want to log out?')) {
                            localStorage.removeItem('auth_token');
                            router.push('/');
                          }
                        }}
                        className="w-full bg-gray-600 text-white py-3 rounded-lg font-semibold hover:bg-gray-700 transition-colors"
                      >
                        Log Out
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
