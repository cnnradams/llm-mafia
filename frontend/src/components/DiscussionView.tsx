import { useEffect, useRef } from 'react';
import { GameState } from '../api/client';

interface DiscussionViewProps {
  gameState: GameState;
  playerId: string | null;
}

export default function DiscussionView({ gameState, playerId }: DiscussionViewProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [gameState]);

  // Fetch events to show chat messages
  // For now, we'll show a simple view. In a full implementation, we'd fetch events.
  const currentDay = gameState.day;
  const phase = gameState.phase;

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <h2 className="text-xl font-bold mb-4">Discussion</h2>
      <div className="space-y-2 min-h-[400px] max-h-[600px] overflow-y-auto">
        {gameState.nominations && Object.keys(gameState.nominations).length > 0 && (
          <div className="mb-4 p-3 bg-yellow-50 rounded border border-yellow-200">
            <h3 className="font-semibold mb-2">Nominations:</h3>
            {Object.entries(gameState.nominations).map(([targetId, nominators]) => {
              const target = gameState.players.find(p => p.player_id === targetId);
              const nominatorNames = nominators
                .map(nid => gameState.players.find(p => p.player_id === nid)?.name)
                .filter(Boolean);
              
              if (!target) return null;
              
              return (
                <div key={targetId} className="text-sm mb-1">
                  <span className="font-semibold">{target.name}</span> nominated by:{' '}
                  {nominatorNames.join(', ')}
                </div>
              );
            })}
          </div>
        )}
        
        {phase === 'DAY_DISCUSSION' && (
          <div className="text-center text-gray-500 py-8">
            <p>Discussion in progress...</p>
            <p className="text-sm mt-2">
              {gameState.current_speaker_id ? (
                <>
                  {gameState.players.find(p => p.player_id === gameState.current_speaker_id)?.name}'s turn to speak
                </>
              ) : (
                'Waiting for next speaker'
              )}
            </p>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}

