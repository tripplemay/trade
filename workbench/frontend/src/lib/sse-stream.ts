/**
 * Minimal SSE-over-fetch parser (B022 F011).
 *
 * `EventSource` only supports GET; the workbench's POST /api/snapshots/refresh
 * pushes back a streaming `text/event-stream` body which this helper
 * parses on the client. Each completed event (lines terminated by a
 * blank line) is forwarded to ``onEvent`` as a parsed JSON object.
 *
 * Keeps zero dependencies — the SSE format we accept is the tight
 * subset the FastAPI handler emits: `data: <json>\n\n` with no event
 * type, id, or retry fields.
 */

export type SseEvent = Record<string, unknown>;

export interface StreamSseOptions {
  body?: BodyInit;
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

export async function streamSse(
  url: string,
  options: StreamSseOptions,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json", ...options.headers },
    body: options.body,
    signal: options.signal,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Response body is not streamable");
  }
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // SSE events end on a blank line.
    let index = buffer.indexOf("\n\n");
    while (index >= 0) {
      const chunk = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      const payload = extractDataPayload(chunk);
      if (payload !== null) {
        try {
          onEvent(JSON.parse(payload) as SseEvent);
        } catch {
          // ignore malformed payloads — keep the stream alive
        }
      }
      index = buffer.indexOf("\n\n");
    }
  }
}

function extractDataPayload(chunk: string): string | null {
  const lines = chunk.split("\n");
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("data: ")) {
      dataLines.push(line.slice("data: ".length));
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length));
    }
  }
  if (dataLines.length === 0) return null;
  return dataLines.join("\n");
}
