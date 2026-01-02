const API_BASE_URL = '/api';

export interface CreateGameRequest {
  player_count?: number;
  llm_models: Array<{
    model_name: string;
    persona?: string;
  }>;
  human_player_name?: string;
}

export interface Player {
  player_id: string;
  name: string;
  role?: string;
  team?: string;
  is_alive: boolean;
  is_human: boolean;
  model_name?: string;
}

export interface GameState {
  game_id: string;
  phase: string;
  day: number;
  players: Player[];
  current_speaker_id: string | null;
  nominations: Record<string, string[]>;
  voting_state: {
    nominee1_id: string;
    nominee2_id: string;
    votes: Record<string, string>;
  } | null;
  winner: string | null;
  is_complete: boolean;
  day_summary: string | null;
}

export async function createGame(request: CreateGameRequest): Promise<{ game_id: string; players: Player[] }> {
  const response = await fetch(`${API_BASE_URL}/games`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error('Failed to create game');
  }
  return response.json();
}

export async function getGameState(gameId: string, playerId?: string): Promise<GameState> {
  const url = new URL(`${API_BASE_URL}/games/${gameId}`);
  if (playerId) {
    url.searchParams.set('player_id', playerId);
  }
  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error('Failed to get game state');
  }
  return response.json();
}

export async function startGame(gameId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/games/${gameId}/start`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('Failed to start game');
  }
}

export async function submitAction(
  gameId: string,
  playerId: string,
  actionType: string,
  data?: {
    message?: string;
    target_id?: string;
    nominee_id?: string;
    night_action_type?: string;
  }
): Promise<{ success: boolean; message?: string }> {
  const response = await fetch(`${API_BASE_URL}/games/${gameId}/actions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      player_id: playerId,
      action_type: actionType,
      ...data,
    }),
  });
  if (!response.ok) {
    throw new Error('Failed to submit action');
  }
  return response.json();
}

