import { NextRequest } from 'next/server';

const STEP_MAP: Record<string, number> = {
  ingest: 1, redact: 2, classify: 3, rank_themes: 4,
  quote_select: 5, action_gen: 6, pulse_note: 7, email_draft: 8,
};

function stageToStepUpdate(run: { stage: string; event: string; detail?: string; error?: string; completed: boolean }) {
  if (run.completed) return JSON.stringify({ completed: true });

  const stepId = STEP_MAP[run.stage];
  if (!stepId) return null;

  let state: 'active' | 'done' | 'error' = 'active';
  if (run.event === 'complete') state = 'done';
  if (run.event === 'error') state = 'error';

  return JSON.stringify({
    step: stepId,
    state,
    detail: run.error ?? run.detail,
  });
}

export async function GET(req: NextRequest) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      let lastEvent = '';
      let ticks = 0;
      const MAX_TICKS = 600; // 5min timeout at 500ms intervals

      const interval = setInterval(() => {
        ticks++;
        const run = global.pipelineRun;
        if (!run) return;

        const payload = stageToStepUpdate(run);
        if (!payload || payload === lastEvent) {
          if (ticks >= MAX_TICKS) {
            clearInterval(interval);
            controller.close();
          }
          return;
        }
        lastEvent = payload;

        controller.enqueue(encoder.encode(`data: ${payload}\n\n`));

        if (run.completed) {
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
