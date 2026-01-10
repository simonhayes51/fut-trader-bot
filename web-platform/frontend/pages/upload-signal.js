import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/layout/Layout';
import { api } from '../lib/api';
import toast from 'react-hot-toast';

export default function UploadSignalPage() {
  const router = useRouter();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);

  const [formData, setFormData] = useState({
    cardName: '',
    playerImage: '',
    cardType: 'Gold',
    tradeType: 'flip',
    cardRating: '',
    cardPosition: '',
    signalType: 'BUY',
    entryPriceMin: '',
    entryPriceMax: '',
    targetPrice: '',
    stopLossPrice: '',
    timeFrame: 'Quick flip',
    riskLevel: 'Medium',
    confidenceLevel: 75,
    reasoning: '',
    isPremium: false,
  });

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      router.push('/login');
      return;
    }

    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      setUser(payload);

      // Check if user is a trader
      if (!payload.is_trader) {
        toast.error('You need to be a trader to post signals');
        router.push('/feed');
      }
    } catch (error) {
      console.error('Invalid token:', error);
      localStorage.removeItem('auth_token');
      router.push('/login');
    }
  }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Validation
    if (!formData.cardName.trim()) {
      toast.error('Player name is required');
      return;
    }

    if (!formData.entryPriceMin && !formData.entryPriceMax) {
      toast.error('At least one buy price is required');
      return;
    }

    try {
      setLoading(true);

      const payload = {
        cardName: formData.cardName.trim(),
        playerImage: formData.playerImage.trim() || null,
        cardType: formData.cardType,
        tradeType: formData.tradeType,
        cardRating: formData.cardRating ? parseInt(formData.cardRating) : null,
        cardPosition: formData.cardPosition.trim() || null,
        signalType: formData.signalType,
        entryPriceMin: formData.entryPriceMin ? parseInt(formData.entryPriceMin) : null,
        entryPriceMax: formData.entryPriceMax ? parseInt(formData.entryPriceMax) : null,
        targetPrice: formData.targetPrice ? parseInt(formData.targetPrice) : null,
        stopLossPrice: formData.stopLossPrice ? parseInt(formData.stopLossPrice) : null,
        timeFrame: formData.timeFrame,
        riskLevel: formData.riskLevel,
        confidenceLevel: parseInt(formData.confidenceLevel),
        reasoning: formData.reasoning.trim() || null,
        isPremium: formData.isPremium,
      };

      const response = await api.createSignal(payload);

      toast.success('Signal posted successfully! 🚀');
      router.push(`/signals/${response.data.signal.id}`);
    } catch (error) {
      console.error('Failed to create signal:', error);
      toast.error(error.response?.data?.error || 'Failed to post signal');
    } finally {
      setLoading(false);
    }
  };

  if (!user) {
    return (
      <Layout title="Loading...">
        <div className="min-h-screen bg-black flex items-center justify-center">
          <div className="inline-block animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-cyan-500"></div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Post a Signal - FUT Hub">
      <div className="min-h-screen bg-black">
        <div className="max-w-4xl mx-auto px-4 py-12">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-4xl font-black text-white mb-2">Post a Signal 🚨</h1>
            <p className="text-gray-400">Share your trading insights with your subscribers</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Main Card */}
            <div className="bg-gradient-to-br from-gray-900 to-black rounded-2xl border border-gray-800 p-8">

              {/* Player Info Section */}
              <div className="mb-8">
                <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
                  <span>⚽</span>
                  <span>Player Info</span>
                </h2>

                <div className="space-y-4">
                  {/* Player Name */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-400 mb-2">
                      Player Name *
                    </label>
                    <input
                      type="text"
                      name="cardName"
                      value={formData.cardName}
                      onChange={handleChange}
                      placeholder="e.g. Cristiano Ronaldo"
                      required
                      className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                    />
                  </div>

                  {/* Player Image URL */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-400 mb-2">
                      Player Image URL (optional)
                    </label>
                    <input
                      type="url"
                      name="playerImage"
                      value={formData.playerImage}
                      onChange={handleChange}
                      placeholder="https://example.com/player-image.png"
                      className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                    />
                    <p className="text-xs text-gray-500 mt-1">Paste a direct link to the player card image</p>
                  </div>

                  {/* Card Type & Trade Type Grid */}
                  <div className="grid grid-cols-2 gap-4">
                    {/* Card Type */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-400 mb-2">
                        Card Type/Rarity
                      </label>
                      <select
                        name="cardType"
                        value={formData.cardType}
                        onChange={handleChange}
                        className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                      >
                        <option value="Gold">Gold</option>
                        <option value="TOTW">TOTW (Team of the Week)</option>
                        <option value="Icon">Icon</option>
                        <option value="Hero">Hero</option>
                        <option value="TOTY">TOTY (Team of the Year)</option>
                        <option value="TOTS">TOTS (Team of the Season)</option>
                        <option value="Promo">Promo Card</option>
                        <option value="Special">Special Card</option>
                        <option value="Rare">Rare</option>
                        <option value="Common">Common</option>
                      </select>
                    </div>

                    {/* Trade Type */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-400 mb-2">
                        Trade Type
                      </label>
                      <select
                        name="tradeType"
                        value={formData.tradeType}
                        onChange={handleChange}
                        className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                      >
                        <option value="flip">🔄 Quick Flip</option>
                        <option value="risky">⚠️ Risky</option>
                        <option value="investment">📈 Investment</option>
                        <option value="safe_bet">✅ Safe Bet</option>
                        <option value="snipe">⚡ Snipe</option>
                      </select>
                    </div>
                  </div>

                  {/* Rating & Position Grid */}
                  <div className="grid grid-cols-2 gap-4">
                    {/* Card Rating */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-400 mb-2">
                        Rating (optional)
                      </label>
                      <input
                        type="number"
                        name="cardRating"
                        value={formData.cardRating}
                        onChange={handleChange}
                        placeholder="85"
                        min="40"
                        max="99"
                        className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                      />
                    </div>

                    {/* Card Position */}
                    <div>
                      <label className="block text-sm font-semibold text-gray-400 mb-2">
                        Position (optional)
                      </label>
                      <input
                        type="text"
                        name="cardPosition"
                        value={formData.cardPosition}
                        onChange={handleChange}
                        placeholder="ST, CAM, CDM, etc."
                        className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Trading Info Section */}
              <div className="mb-8">
                <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
                  <span>💰</span>
                  <span>Trading Details</span>
                </h2>

                <div className="space-y-4">
                  {/* Signal Type */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-400 mb-2">
                      Signal Type
                    </label>
                    <div className="grid grid-cols-4 gap-3">
                      {['BUY', 'SELL', 'HOLD', 'AVOID'].map((type) => (
                        <button
                          key={type}
                          type="button"
                          onClick={() => setFormData(prev => ({ ...prev, signalType: type }))}
                          className={`px-4 py-3 rounded-xl font-bold transition-all ${
                            formData.signalType === type
                              ? 'bg-cyan-500 text-white'
                              : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                          }`}
                        >
                          {type}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Buy Price Range */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-semibold text-gray-400 mb-2">
                        Buy Price Min *
                      </label>
                      <input
                        type="number"
                        name="entryPriceMin"
                        value={formData.entryPriceMin}
                        onChange={handleChange}
                        placeholder="1000"
                        min="0"
                        className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-400 mb-2">
                        Buy Price Max
                      </label>
                      <input
                        type="number"
                        name="entryPriceMax"
                        value={formData.entryPriceMax}
                        onChange={handleChange}
                        placeholder="1200"
                        min="0"
                        className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                      />
                    </div>
                  </div>

                  {/* Target & Stop Loss */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-semibold text-gray-400 mb-2">
                        Target Sell Price
                      </label>
                      <input
                        type="number"
                        name="targetPrice"
                        value={formData.targetPrice}
                        onChange={handleChange}
                        placeholder="1500"
                        min="0"
                        className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-400 mb-2">
                        Stop Loss (optional)
                      </label>
                      <input
                        type="number"
                        name="stopLossPrice"
                        value={formData.stopLossPrice}
                        onChange={handleChange}
                        placeholder="900"
                        min="0"
                        className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                      />
                    </div>
                  </div>

                  {/* Time Frame & Risk Level */}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-semibold text-gray-400 mb-2">
                        Time Frame
                      </label>
                      <select
                        name="timeFrame"
                        value={formData.timeFrame}
                        onChange={handleChange}
                        className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                      >
                        <option value="Quick flip">⚡ Quick Flip (1-2 days)</option>
                        <option value="Short term">📅 Short Term (3-5 days)</option>
                        <option value="Medium term">📆 Medium Term (1-2 weeks)</option>
                        <option value="Long term">🗓️ Long Term (2+ weeks)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-semibold text-gray-400 mb-2">
                        Risk Level
                      </label>
                      <select
                        name="riskLevel"
                        value={formData.riskLevel}
                        onChange={handleChange}
                        className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                      >
                        <option value="Low">🟢 Low Risk</option>
                        <option value="Medium">🟡 Medium Risk</option>
                        <option value="High">🔴 High Risk</option>
                      </select>
                    </div>
                  </div>

                  {/* Confidence Level */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-400 mb-2">
                      Confidence Level: {formData.confidenceLevel}%
                    </label>
                    <input
                      type="range"
                      name="confidenceLevel"
                      value={formData.confidenceLevel}
                      onChange={handleChange}
                      min="0"
                      max="100"
                      step="5"
                      className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-cyan-500"
                    />
                    <div className="flex justify-between text-xs text-gray-500 mt-1">
                      <span>Not Confident</span>
                      <span>Very Confident</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Strategy Section */}
              <div className="mb-8">
                <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-2">
                  <span>📝</span>
                  <span>Strategy & Reasoning</span>
                </h2>

                <div>
                  <label className="block text-sm font-semibold text-gray-400 mb-2">
                    Explain Your Trade (optional)
                  </label>
                  <textarea
                    name="reasoning"
                    value={formData.reasoning}
                    onChange={handleChange}
                    placeholder="Why is this a good trade? What's your analysis? Any upcoming events (SBC, match, promo)?"
                    rows="6"
                    maxLength="2000"
                    className="w-full px-4 py-3 bg-gray-900/50 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all resize-none"
                  ></textarea>
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>Share your insights with your subscribers</span>
                    <span>{formData.reasoning.length}/2000</span>
                  </div>
                </div>
              </div>

              {/* Premium Toggle */}
              <div className="mb-8 p-6 bg-cyan-500/10 border border-cyan-500/20 rounded-xl">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    name="isPremium"
                    checked={formData.isPremium}
                    onChange={handleChange}
                    className="w-5 h-5 bg-gray-900 border-gray-700 rounded text-cyan-500 focus:ring-cyan-500 cursor-pointer"
                  />
                  <div>
                    <div className="font-bold text-white flex items-center gap-2">
                      <span>👑</span>
                      <span>Premium Signal (Subscribers Only)</span>
                    </div>
                    <div className="text-sm text-gray-400 mt-1">
                      Only your paid subscribers will be able to see the full details of this signal
                    </div>
                  </div>
                </label>
              </div>

              {/* Submit Buttons */}
              <div className="flex gap-4">
                <button
                  type="submit"
                  disabled={loading}
                  className="flex-1 px-8 py-4 bg-gradient-to-r from-cyan-500 to-cyan-600 text-white rounded-xl font-bold hover:from-cyan-600 hover:to-cyan-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? 'Posting...' : 'Post Signal 🚀'}
                </button>
                <button
                  type="button"
                  onClick={() => router.back()}
                  className="px-8 py-4 bg-gray-800 text-gray-300 rounded-xl font-bold hover:bg-gray-700 transition-all"
                >
                  Cancel
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </Layout>
  );
}
