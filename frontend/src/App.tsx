import { useState } from 'react';
import GameLobby from './components/GameLobby';
import GameBoard from './components/GameBoard';

function App() {
  const [gameId, setGameId] = useState<string | null>(null);
  const [playerId, setPlayerId] = useState<string | null>(null);

  if (!gameId) {
    return (
      <GameLobby
        onGameCreated={(id, pid) => {
          setGameId(id);
          setPlayerId(pid);
        }}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <GameBoard gameId={gameId} playerId={playerId} />
    </div>
  );
}

export default App;

