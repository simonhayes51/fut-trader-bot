export default function Achievements() {
  const achievements = [
    { id: '1', icon: '🔥', label: '7 Day Streak', progress: 100, color: 'from-orange-500 to-red-500' },
    { id: '2', icon: '🏆', label: 'First Win', progress: 100, color: 'from-yellow-500 to-orange-500' },
    { id: '3', icon: '⭐', label: 'Rising Star', progress: 75, color: 'from-cyan-500 to-blue-500' },
    { id: '4', icon: '🎯', label: 'Sharp Shooter', progress: 75, color: 'from-green-500 to-emerald-500' },
    { id: '5', icon: '👑', label: 'Top 100', progress: 45, color: 'from-purple-500 to-pink-500' },
  ];

  return (
    <div className="bg-gradient-to-br from-gray-900 to-black rounded-2xl border border-gray-800 p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🏆</span>
          <span className="text-white font-bold text-lg">Achievements</span>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-gray-400">⚡ Level:</span>
            <span className="text-white font-bold">24</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-400">⭐ XP:</span>
            <span className="text-white font-bold">12,450</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-400">📊 Rank:</span>
            <span className="text-cyan-400 font-bold">#847</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-4">
        {achievements.map((achievement) => (
          <div
            key={achievement.id}
            className="flex flex-col items-center gap-2 p-4 bg-gray-900/50 rounded-xl border border-gray-800 hover:border-gray-700 transition-all cursor-pointer group relative"
          >
            {/* Badge Icon */}
            <div className={`w-16 h-16 rounded-xl bg-gradient-to-br ${achievement.color} flex items-center justify-center text-3xl group-hover:scale-110 transition-transform`}>
              {achievement.icon}
            </div>

            {/* Label */}
            <div className="text-xs text-gray-400 text-center font-medium group-hover:text-white transition-colors">
              {achievement.label}
            </div>

            {/* Progress Badge */}
            <div className="absolute -top-2 -right-2 bg-yellow-500 text-black text-[10px] font-black px-2 py-0.5 rounded-full">
              {achievement.progress}%
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
