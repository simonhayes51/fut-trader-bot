import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';

export default function StoriesRow() {
  const router = useRouter();
  const [stories, setStories] = useState([
    { id: 'you', username: 'Your Story', avatar: null, hasStory: false, isLive: false },
    { id: '1', username: 'FlipKingFC', avatar: 'https://cdn.discordapp.com/embed/avatars/1.png', hasStory: true, isLive: true },
    { id: '2', username: 'SBCMaster', avatar: 'https://cdn.discordapp.com/embed/avatars/2.png', hasStory: true, isLive: false },
    { id: '3', username: 'MetaTrader', avatar: 'https://cdn.discordapp.com/embed/avatars/3.png', hasStory: true, isLive: false },
    { id: '4', username: 'IconInvest...', avatar: 'https://cdn.discordapp.com/embed/avatars/4.png', hasStory: true, isLive: false },
    { id: '5', username: 'CoinKing', avatar: 'https://cdn.discordapp.com/embed/avatars/5.png', hasStory: true, isLive: false },
    { id: '6', username: 'FlipQueen', avatar: 'https://cdn.discordapp.com/embed/avatars/0.png', hasStory: true, isLive: false },
  ]);

  return (
    <div className="bg-gradient-to-br from-gray-900 to-black rounded-2xl border border-gray-800 p-6">
      <div className="flex gap-6 overflow-x-auto pb-2" style={{ scrollbarWidth: 'none' }}>
        {stories.map((story) => (
          <div
            key={story.id}
            onClick={() => story.id !== 'you' && router.push(`/traders/${story.id}`)}
            className="flex flex-col items-center gap-2 cursor-pointer group flex-shrink-0"
          >
            <div className="relative">
              {/* Story Ring */}
              <div className={`w-20 h-20 rounded-full p-[3px] ${
                story.hasStory
                  ? 'bg-gradient-to-br from-cyan-400 via-cyan-500 to-cyan-600'
                  : 'bg-gray-700'
              }`}>
                <div className="w-full h-full rounded-full bg-[#0A0A0A] p-[3px]">
                  <img
                    src={story.avatar || 'https://cdn.discordapp.com/embed/avatars/0.png'}
                    alt={story.username}
                    className="w-full h-full rounded-full object-cover"
                  />
                </div>
              </div>

              {/* Add Story Plus */}
              {story.id === 'you' && !story.hasStory && (
                <div className="absolute bottom-0 right-0 w-6 h-6 bg-cyan-500 rounded-full border-2 border-[#0A0A0A] flex items-center justify-center">
                  <span className="text-white text-xs font-bold">+</span>
                </div>
              )}

              {/* Live Indicator */}
              {story.isLive && (
                <div className="absolute -top-1 left-1/2 transform -translate-x-1/2">
                  <div className="bg-red-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full border-2 border-[#0A0A0A] flex items-center gap-1">
                    <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse"></span>
                    LIVE
                  </div>
                </div>
              )}
            </div>

            {/* Username */}
            <div className="text-xs text-gray-400 font-medium text-center group-hover:text-white transition-colors">
              {story.username}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
