import { useState, useEffect } from 'react';
import { api } from '../../lib/api';

export default function PortfolioWidget() {
  const [portfolio, setPortfolio] = useState({
    totalValue: 4250000,
    invested: 3200000,
    profit: 1050000,
    profitPercent: 12.5,
    activeSignals: 12,
    winRate: 87,
    recentTrades: [
      { player: 'Mbappé', profit: 180000, positive: true },
      { player: 'Haaland', profit: 95000, positive: true },
      { player: 'Salah', profit: -25000, positive: false },
    ]
  });

  return (
    <div className="space-y-6">
      {/* Portfolio Card */}
      <div className="bg-gradient-to-br from-gray-900 to-black rounded-2xl border border-gray-800 p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2 text-cyan-400">
            <span className="text-xl">💼</span>
            <span className="font-bold">Your Portfolio</span>
          </div>
          <button className="text-cyan-400 text-sm font-semibold hover:text-cyan-300">
            View All
          </button>
        </div>

        {/* Total Value */}
        <div className="mb-6">
          <div className="text-gray-400 text-sm mb-1">Total Value</div>
          <div className="flex items-baseline gap-2">
            <div className="text-3xl font-black text-white">
              {portfolio.totalValue.toLocaleString()}
            </div>
            <div className="text-green-400 text-sm font-bold flex items-center gap-1">
              <span>📈</span>
              <span>+{portfolio.profitPercent}%</span>
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <div className="flex items-center gap-1 text-gray-400 text-xs mb-1">
              <span>💰</span>
              <span>Invested</span>
            </div>
            <div className="text-xl font-bold text-white">
              {(portfolio.invested / 1000000).toFixed(1)}M
            </div>
          </div>
          <div>
            <div className="flex items-center gap-1 text-gray-400 text-xs mb-1">
              <span>💎</span>
              <span>Profit</span>
            </div>
            <div className="text-xl font-bold text-green-400">
              {(portfolio.profit / 1000000).toFixed(1)}M
            </div>
          </div>
          <div>
            <div className="flex items-center gap-1 text-gray-400 text-xs mb-1">
              <span>🔥</span>
              <span>Active</span>
            </div>
            <div className="text-xl font-bold text-white">{portfolio.activeSignals}</div>
          </div>
          <div>
            <div className="flex items-center gap-1 text-gray-400 text-xs mb-1">
              <span>🎯</span>
              <span>Win Rate</span>
            </div>
            <div className="text-xl font-bold text-white">{portfolio.winRate}%</div>
          </div>
        </div>

        {/* Recent Trades */}
        <div>
          <div className="text-gray-400 text-xs font-bold uppercase mb-3">RECENT</div>
          <div className="space-y-2">
            {portfolio.recentTrades.map((trade, idx) => (
              <div key={idx} className="flex items-center justify-between">
                <span className="text-white text-sm">{trade.player}</span>
                <span className={`text-sm font-bold ${trade.positive ? 'text-green-400' : 'text-red-400'}`}>
                  {trade.positive ? '+' : ''}{(trade.profit / 1000).toFixed(0)}K
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Subscriptions Card */}
      <div className="bg-gradient-to-br from-gray-900 to-black rounded-2xl border border-gray-800 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="font-bold text-white">Subscriptions</div>
          <button className="text-cyan-400 text-2xl hover:text-cyan-300">+</button>
        </div>

        <div className="space-y-3">
          {/* All Posts Option */}
          <div className="flex items-center gap-3 p-3 bg-cyan-500/10 border border-cyan-500/20 rounded-xl cursor-pointer hover:bg-cyan-500/20 transition-all">
            <div className="w-10 h-10 bg-gradient-to-br from-cyan-400 to-cyan-600 rounded-full flex items-center justify-center text-white font-black">
              ALL
            </div>
            <div>
              <div className="text-white font-semibold text-sm">All Posts</div>
              <div className="text-gray-400 text-xs">From all traders</div>
            </div>
          </div>

          {/* Individual Trader Subscriptions */}
          <div className="flex items-center gap-3 p-3 rounded-xl cursor-pointer hover:bg-gray-800/50 transition-all group">
            <div className="relative">
              <img
                src="https://cdn.discordapp.com/embed/avatars/1.png"
                alt="FlipKingFC"
                className="w-10 h-10 rounded-full border-2 border-orange-500"
              />
              <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-[#0A0A0A]"></div>
            </div>
            <div className="flex-1">
              <div className="text-white font-semibold text-sm">FlipKingFC</div>
              <div className="text-gray-400 text-xs">Quick Flips</div>
            </div>
            <button className="text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity">
              ⚙️
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
