import { NextRequest } from 'next/server';
import type { RunState } from '@/app/api/run/route';

const STEP_MAP: Record<string, number> = {
  ingest: 1, redact: 2, classify: 3, rank_themes: 4,
  quote_select: 5, action_gen: 6, pulse_note: 7, email_draft: 8,
};

function stageToStepUpdate(run: RunState & { step?: number; name?: string }): string | null {
  if (run.completed) {
    if (run.stage === 'error') {
      return JSON.stringify({ completed: true, error: run.error });
    }
    return JSON.stringify({ completed: true });
  }

  let stepId: number | undefined;
  let state: 'active' | 'done' | 'error' = 'active';

  if (run.stage === 'pipeline') {
    // Orchestrator emits: step_start / step_done with numeric step + name
    const stepNum = (run as unknown as Record<string, unknown>).step;
    const name    = (run as unknown as Record<string, unknown>).name;
    stepId = typeof stepNum === 'number' ? stepNum
           : typeof name   === 'string'  ? STEP_MAP[name]
           : undefined;
    if (run.event === 'step_done')  state = 'done';
    if (run.event === 'step_start') state = 'active';
    if (run.event === 'run_error')  state = 'error';
  } else {
    // Module-level events: e.g. classify_complete, quote_select_done
    stepId = STEP_MAP[run.stage];
    if (run.event.includes('complete') || run.event.includes('done')) state = 'done';
    if (run.event.includes('error')) state = 'error';
  }

  if (!stepId) return null;

  const detail = (run as unknown as Record<string, unknown>).detail as string | undefined;
  return JSON.stringify({ step: stepId, state, detail: run.error ?? detail });
}

export async function GET(req: NextRequest) {
  const runId = req.nextUrl.searchParams.get('runId') ?? null;
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      let ticks = 0;
      const MAX_TICKS = 1440; // 12 min at 500ms

      const interval = setInterval(() => {
        ticks++;

        // Drain queued events for this specific runId
        const queue: RunState[] = global.pipelineQueue ?? [];
        while (queue.length > 0) {
          // Peek to check runId before shifting
          if (runId && queue[0].runId !== runId) {
            queue.shift(); // discard stale event from a different run
            continue;
          }
          const run = queue.shift()!;
          const payload = stageToStepUpdate(run as RunState & { step?: number; name?: string });
          if (payload) {
            controller.enqueue(encoder.encode(`data: ${payload}\n\n`));
            if (run.completed) {
              clearInterval(interval);
              controller.close();
              return;
            }
          }
        }

        if (ticks >= MAX_TICKS) {
          clearInterval(interval);
          controller.close();
        }
      }, 500);

      req.signal.addEventListener('abort', () => {
        clearInterval(interval);
        controller.close();
      });
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
