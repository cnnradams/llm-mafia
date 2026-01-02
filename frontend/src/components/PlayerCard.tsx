import { Player } from '../api/client';

interface PlayerCardProps {
  player: Player;
  isCurrentSpeaker: boolean;
  isMe: boolean;
}

export default function PlayerCard({ player, isCurrentSpeaker, isMe }: PlayerCardProps) {
  const getStatusColor = () => {
    if (!player.is_alive) return 'bg-gray-300';
    if (isCurrentSpeaker) return 'bg-yellow-200';
    if (isMe) return 'bg-blue-200';
    return 'bg-green-100';
  };

  return (
    <div className={`p-3 rounded border-2 ${getStatusColor()} ${isCurrentSpeaker ? 'border-yellow-500' : 'border-transparent'}`}>
      <div className="flex justify-between items-start">
        <div>
          <div className="font-semibold">
            {player.name}
            {isMe && ' (You)'}
            {isCurrentSpeaker && ' 🎤'}
          </div>
          {player.role && (
            <div className="text-sm text-gray-600">
              {player.role}
            </div>
          )}
          {!player.is_alive && (
            <div className="text-sm text-red-600 font-semibold">DEAD</div>
          )}
        </div>
        <div className="text-xs text-gray-500">
          {player.is_human ? 'Human' : player.model_name?.split('/').pop()}
        </div>
      </div>
    </div>
  );
}

