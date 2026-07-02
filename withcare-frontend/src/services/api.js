// Real backend SSE streaming client

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

/**
 * Stream a chat request to the backend.
 * Calls onChunk(chunk) for every SSE event.
 * Calls onDone(carePlan) when the done event arrives.
 * Calls onError(message) on error events or network failures.
 */
export async function streamChat({ message, sessionId, userId, location, coordinates, familyProfile, forMember, history }, { onChunk, onDone, onError }) {
  try {
    const response = await fetch(`${BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        session_id: sessionId,
        user_id: userId || '',
        location: location || '',
        coordinates: coordinates || null,
        family_profile: familyProfile || [],
        for_member: forMember || 'self',
        language: 'en',
        history: history || [],
      }),
    });

    if (!response.ok) {
      onError(`Server error: ${response.status}`);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep incomplete line

      let eventType = null;
      for (const line of lines) {
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
          const raw = line.slice(5).trim();
          if (!raw) continue;
          try {
            const chunk = JSON.parse(raw);
            onChunk(chunk);
            if (chunk.type === 'done') onDone(chunk.content);
            if (chunk.type === 'error') onError(chunk.content);
          } catch {
            // ignore malformed lines
          }
        }
      }
    }
  } catch (err) {
    onError(err.message || 'Network error — is the backend running?');
  }
}
