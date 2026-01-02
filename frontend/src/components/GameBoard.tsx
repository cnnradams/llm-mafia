import { useWebSocket } from '../hooks/useWebSocket';
import PlayerCard from './PlayerCard';
import DiscussionView from './DiscussionView';
import VotingView from './VotingView';
import ActionPanel from './ActionPanel';
import { GameState, Player } from '../api/client';

interface GameBoardProps {
  gameId: string;
  playerId: string | null;
}

export default function GameBoard({ gameId, playerId }: GameBoardProps) {
  const { gameState, connected } = useWebSocket(gameId);

  if (!gameState) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading game...</p>
        </div>
      </div>
    );
  }

  const currentPlayer = gameState.players.find(p => p.player_id === playerId);
  const isMyTurn = gameState.current_speaker_id === playerId && currentPlayer?.is_human;

  const getPhaseLabel = () => {
    if (gameState.is_complete) {
      return `Game Over - ${gameState.winner} Wins!`;
    }
    if (gameState.phase === 'DAY_DISCUSSION') {
      return `Day ${gameState.day} - Discussion`;
    }
    if (gameState.phase === 'DAY_VOTING') {
      return `Day ${gameState.day} - Voting`;
    }
    if (gameState.phase === 'NIGHT') {
      return `Night ${gameState.day}`;
    }
    return gameState.phase;
  };

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-md p-4 mb-4">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold">Mafia Game</h1>
            <div className="text-right">
              <div className="text-lg font-semibold">{getPhaseLabel()}</div>
              <div className={`text-sm ${connected ? 'text-green-600' : 'text-red-600'}`}>
                {connected ? 'Connected' : 'Disconnected'}
              </div>
            </div>
          </div>
          {gameState.day_summary && (
            <div className="mt-4 p-3 bg-blue-50 rounded border border-blue-200">
              <h3 className="font-semibold text-blue-900 mb-2">Previous Day Summary:</h3>
              <p className="text-sm text-blue-800">{gameState.day_summary}</p>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Left: Players */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-md p-4">
              <h2 className="text-xl font-bold mb-4">Players</h2>
              <div className="space-y-2">
                {gameState.players.map(player => (
                  <PlayerCard
                    key={player.player_id}
                    player={player}
                    isCurrentSpeaker={gameState.current_speaker_id === player.player_id}
                    isMe={player.player_id === playerId}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Center: Discussion/Voting */}
          <div className="lg:col-span-1">
            {gameState.phase === 'DAY_VOTING' && gameState.voting_state ? (
              <VotingView gameState={gameState} playerId={playerId} />
            ) : (
              <DiscussionView gameState={gameState} playerId={playerId} />
            )}
          </div>

          {/* Right: Actions */}
          <div className="lg:col-span-1">
            {currentPlayer && currentPlayer.is_human && (
              <ActionPanel
                gameState={gameState}
                playerId={playerId!}
                isMyTurn={isMyTurn || false}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

