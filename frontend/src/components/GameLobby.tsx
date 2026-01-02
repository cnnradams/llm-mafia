import { useState } from 'react';
import { createGame, startGame } from '../api/client';

interface GameLobbyProps {
  onGameCreated: (gameId: string, playerId: string) => void;
}

export default function GameLobby({ onGameCreated }: GameLobbyProps) {
  const [playerName, setPlayerName] = useState('');
  const [selectedModels, setSelectedModels] = useState<string[]>(['anthropic/claude-3.5-sonnet']);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const availableModels = [
    'anthropic/claude-3.5-sonnet',
    'openai/gpt-4',
    'openai/gpt-3.5-turbo',
    'google/gemini-pro',
    'meta-llama/llama-2-70b-chat',
  ];

  const handleCreateGame = async () => {
    if (!playerName.trim()) {
      setError('Please enter your name');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await createGame({
        player_count: 8,
        llm_models: selectedModels.map(model => ({ model_name: model })),
        human_player_name: playerName,
      });

      // Start the game
      await startGame(result.game_id);

      // Find human player ID
      const humanPlayer = result.players.find(p => p.is_human);
      if (humanPlayer) {
        onGameCreated(result.game_id, humanPlayer.player_id);
      } else {
        setError('Failed to find player ID');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create game');
    } finally {
      setLoading(false);
    }
  };

  const toggleModel = (model: string) => {
    setSelectedModels(prev =>
      prev.includes(model)
        ? prev.filter(m => m !== model)
        : [...prev, model]
    );
  };

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full">
        <h1 className="text-3xl font-bold text-center mb-6">Mafia Game</h1>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Your Name
            </label>
            <input
              type="text"
              value={playerName}
              onChange={(e) => setPlayerName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter your name"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Select LLM Models (for AI players)
            </label>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {availableModels.map(model => (
                <label key={model} className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedModels.includes(model)}
                    onChange={() => toggleModel(model)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">{model}</span>
                </label>
              ))}
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <button
            onClick={handleCreateGame}
            disabled={loading || !playerName.trim() || selectedModels.length === 0}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {loading ? 'Creating Game...' : 'Create Game'}
          </button>
        </div>
      </div>
    </div>
  );
}

