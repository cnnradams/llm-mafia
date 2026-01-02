import { GameState } from '../api/client';

interface VotingViewProps {
  gameState: GameState;
  playerId: string | null;
}

export default function VotingView({ gameState, playerId }: VotingViewProps) {
  if (!gameState.voting_state) {
    return null;
  }

  const nominee1 = gameState.players.find(p => p.player_id === gameState.voting_state!.nominee1_id);
  const nominee2 = gameState.players.find(p => p.player_id === gameState.voting_state!.nominee2_id);
  const currentPlayer = gameState.players.find(p => p.player_id === playerId);
  const hasVoted = currentPlayer && gameState.voting_state.votes[currentPlayer.player_id];

  if (!nominee1 || !nominee2) {
    return null;
  }

  const votes1 = Object.values(gameState.voting_state.votes).filter(v => v === nominee1.player_id).length;
  const votes2 = Object.values(gameState.voting_state.votes).filter(v => v === nominee2.player_id).length;

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <h2 className="text-xl font-bold mb-4">Voting</h2>
      <div className="space-y-4">
        <div className="text-center text-lg font-semibold mb-4">
          Choose who to eliminate:
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div className={`p-4 rounded border-2 ${hasVoted && gameState.voting_state.votes[currentPlayer!.player_id] === nominee1.player_id ? 'border-blue-500 bg-blue-50' : 'border-gray-300'}`}>
            <div className="font-semibold text-lg mb-2">{nominee1.name}</div>
            <div className="text-sm text-gray-600 mb-2">Votes: {votes1}</div>
          </div>
          
          <div className={`p-4 rounded border-2 ${hasVoted && gameState.voting_state.votes[currentPlayer!.player_id] === nominee2.player_id ? 'border-blue-500 bg-blue-50' : 'border-gray-300'}`}>
            <div className="font-semibold text-lg mb-2">{nominee2.name}</div>
            <div className="text-sm text-gray-600 mb-2">Votes: {votes2}</div>
          </div>
        </div>

        {hasVoted && (
          <div className="text-center text-sm text-green-600 font-semibold">
            You have voted
          </div>
        )}

        <div className="text-sm text-gray-600">
          Total votes: {Object.keys(gameState.voting_state.votes).length} / {gameState.players.filter(p => p.is_alive).length}
        </div>
      </div>
    </div>
  );
}

