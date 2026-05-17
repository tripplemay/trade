/**
 * Shared helpers for the chart wrappers (B022 F004).
 *
 * Each wrapper exposes an `exportPng()` ref method that resolves to a
 * Blob a parent can post into a download anchor or attach to a report.
 * lightweight-charts and ECharts produce the PNG via different paths —
 * canvas screenshot vs dataURL — but both funnel through these two
 * helpers so the call site always gets a Blob (or null when the
 * underlying chart hasn't mounted yet / a test environment lacks
 * canvas support).
 */

export interface ChartHandle {
  /** Resolves to a PNG Blob, or null when the chart hasn't rendered yet. */
  exportPng(): Promise<Blob | null>;
}

export function canvasToPngBlob(canvas: HTMLCanvasElement): Promise<Blob | null> {
  return new Promise((resolve) => {
    if (typeof canvas.toBlob !== "function") {
      // happy-dom / jsdom may stub a canvas without `toBlob`; tests
      // catch this branch by mocking the chart instance directly.
      resolve(null);
      return;
    }
    canvas.toBlob((blob) => resolve(blob), "image/png");
  });
}

export async function dataUrlToPngBlob(dataUrl: string): Promise<Blob | null> {
  try {
    const response = await fetch(dataUrl);
    return await response.blob();
  } catch {
    return null;
  }
}
