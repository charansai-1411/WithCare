// Real backend SSE streaming client

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

/**
 * Stream a chat request to the backend.
 * Calls onChunk(chunk) for every SSE event.
 * Calls onDone(carePlan) when the done event arrives.
 * Calls onError(message) on error events or network failures.
 */
export async function streamChat({ message, sessionId, userId, location, coordinates, familyProfile, forMember, history, attachmentDocIds, connectors, connectorTokens }, { onChunk, onDone, onError }) {
  // Guard against a stalled backend: if no data arrives for IDLE_MS, abort the stream so
  // the UI can recover instead of spinning forever. The timer resets on every chunk, so a
  // long-but-progressing response is never cut off.
  const controller = new AbortController();
  const IDLE_MS = 45000;
  let idleTimer;
  const armIdle = () => { clearTimeout(idleTimer); idleTimer = setTimeout(() => controller.abort(), IDLE_MS); };

  try {
    armIdle();
    const response = await fetch(`${BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
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
        attachment_document_ids: attachmentDocIds || [],
        connected_connectors: connectors || [],
        connector_tokens: connectorTokens || {},
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
      armIdle(); // progress — reset the stall timer

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
    if (err.name === 'AbortError') {
      onError('The assistant is taking too long to respond — please try again.');
    } else {
      onError(err.message || 'Network error — is the backend running?');
    }
  } finally {
    clearTimeout(idleTimer);
  }
}
