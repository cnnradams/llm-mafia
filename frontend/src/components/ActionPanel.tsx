import { useState } from 'react';
import { GameState, submitAction } from '../api/client';

interface ActionPanelProps {
  gameState: GameState;
  playerId: string;
  isMyTurn: boolean;
}

export default function ActionPanel({ gameState, playerId, isMyTurn }: ActionPanelProps) {
  const [message, setMessage] = useState('');
  const [selectedTarget, setSelectedTarget] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentPlayer = gameState.players.find(p => p.player_id === playerId);
  const alivePlayers = gameState.players.filter(p => p.is_alive && p.player_id !== playerId);

  const handleAction = async (actionType: string, data?: any) => {
    setLoading(true);
    setError(null);

    try {
      const result = await submitAction(gameState.game_id, playerId, actionType, data);
      if (!result.success) {
        setError(result.message || 'Action failed');
      } else {
        setMessage('');
        setSelectedTarget('');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit action');
    } finally {
      setLoading(false);
    }
  };

  if (gameState.is_complete) {
    return (
      <div className="bg-white rounded-lg shadow-md p-4">
        <h2 className="text-xl font-bold mb-4">Game Over</h2>
        <div className="text-center text-lg font-semibold">
          {gameState.winner} Wins!
        </div>
      </div>
    );
  }

  if (gameState.phase === 'DAY_DISCUSSION') {
    if (!isMyTurn) {
      return (
        <div className="bg-white rounded-lg shadow-md p-4">
          <h2 className="text-xl font-bold mb-4">Actions</h2>
          <div className="text-center text-gray-500">
            Waiting for your turn...
          </div>
        </div>
      );
    }

    return (
      <div className="bg-white rounded-lg shadow-md p-4">
        <h2 className="text-xl font-bold mb-4">Your Turn</h2>
        
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded mb-4 text-sm">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Speak</label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              placeholder="Share your thoughts..."
              rows={3}
            />
            <button
              onClick={() => handleAction('SPEAK', { message })}
              disabled={loading || !message.trim()}
              className="mt-2 w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-400"
            >
              Speak
            </button>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Nominate Player</label>
            <select
              value={selectedTarget}
              onChange={(e) => setSelectedTarget(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="">Select a player</option>
              {alivePlayers.map(player => (
                <option key={player.player_id} value={player.player_id}>
                  {player.name}
                </option>
              ))}
            </select>
            <button
              onClick={() => handleAction('NOMINATE', { target_id: selectedTarget })}
              disabled={loading || !selectedTarget}
              className="mt-2 w-full bg-red-600 text-white py-2 px-4 rounded-md hover:bg-red-700 disabled:bg-gray-400"
            >
              Nominate
            </button>
          </div>

          <button
            onClick={() => handleAction('PASS')}
            disabled={loading}
            className="w-full bg-gray-600 text-white py-2 px-4 rounded-md hover:bg-gray-700 disabled:bg-gray-400"
          >
            Pass
          </button>
        </div>
      </div>
    );
  }

  if (gameState.phase === 'DAY_VOTING' && gameState.voting_state) {
    const hasVoted = gameState.voting_state.votes[playerId];
    
    return (
      <div className="bg-white rounded-lg shadow-md p-4">
        <h2 className="text-xl font-bold mb-4">Vote</h2>
        
        {hasVoted ? (
          <div className="text-center text-green-600 font-semibold">
            You have already voted
          </div>
        ) : (
          <div className="space-y-3">
            <button
              onClick={() => handleAction('VOTE', { nominee_id: gameState.voting_state!.nominee1_id })}
              disabled={loading}
              className="w-full bg-red-600 text-white py-3 px-4 rounded-md hover:bg-red-700 disabled:bg-gray-400 text-lg font-semibold"
            >
              Vote: {gameState.players.find(p => p.player_id === gameState.voting_state!.nominee1_id)?.name}
            </button>
            <button
              onClick={() => handleAction('VOTE', { nominee_id: gameState.voting_state!.nominee2_id })}
              disabled={loading}
              className="w-full bg-red-600 text-white py-3 px-4 rounded-md hover:bg-red-700 disabled:bg-gray-400 text-lg font-semibold"
            >
              Vote: {gameState.players.find(p => p.player_id === gameState.voting_state!.nominee2_id)?.name}
            </button>
          </div>
        )}
      </div>
    );
  }

  if (gameState.phase === 'NIGHT') {
    const role = currentPlayer?.role;
    
    if (role === 'MAFIA') {
      return (
        <div className="bg-white rounded-lg shadow-md p-4">
          <h2 className="text-xl font-bold mb-4">Night Action</h2>
          <div className="space-y-3">
            <label className="block text-sm font-medium">Choose kill target:</label>
            <select
              value={selectedTarget}
              onChange={(e) => setSelectedTarget(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="">Select a target</option>
              {alivePlayers.filter(p => p.player_id !== playerId).map(player => (
                <option key={player.player_id} value={player.player_id}>
                  {player.name}
                </option>
              ))}
            </select>
            <button
              onClick={() => handleAction('NIGHT_ACTION', { night_action_type: 'KILL', target_id: selectedTarget })}
              disabled={loading || !selectedTarget}
              className="w-full bg-red-600 text-white py-2 px-4 rounded-md hover:bg-red-700 disabled:bg-gray-400"
            >
              Kill
            </button>
          </div>
        </div>
      );
    }
    
    if (role === 'DOCTOR') {
      return (
        <div className="bg-white rounded-lg shadow-md p-4">
          <h2 className="text-xl font-bold mb-4">Night Action</h2>
          <div className="space-y-3">
            <label className="block text-sm font-medium">Choose player to save:</label>
            <select
              value={selectedTarget}
              onChange={(e) => setSelectedTarget(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="">Select a player</option>
              {alivePlayers.map(player => (
                <option key={player.player_id} value={player.player_id}>
                  {player.name}
                </option>
              ))}
            </select>
            <button
              onClick={() => handleAction('NIGHT_ACTION', { night_action_type: 'SAVE', target_id: selectedTarget })}
              disabled={loading || !selectedTarget}
              className="w-full bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 disabled:bg-gray-400"
            >
              Save
            </button>
          </div>
        </div>
      );
    }
    
    if (role === 'DETECTIVE') {
      return (
        <div className="bg-white rounded-lg shadow-md p-4">
          <h2 className="text-xl font-bold mb-4">Night Action</h2>
          <div className="space-y-3">
            <label className="block text-sm font-medium">Choose player to investigate:</label>
            <select
              value={selectedTarget}
              onChange={(e) => setSelectedTarget(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="">Select a player</option>
              {alivePlayers.map(player => (
                <option key={player.player_id} value={player.player_id}>
                  {player.name}
                </option>
              ))}
            </select>
            <button
              onClick={() => handleAction('NIGHT_ACTION', { night_action_type: 'INVESTIGATE', target_id: selectedTarget })}
              disabled={loading || !selectedTarget}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-400"
            >
              Investigate
            </button>
          </div>
        </div>
      );
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <h2 className="text-xl font-bold mb-4">Actions</h2>
      <div className="text-center text-gray-500">
        No actions available
      </div>
    </div>
  );
}

