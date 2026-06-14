import { NextRequest } from 'next/server';

const STEP_MAP: Record<string, number> = {
  ingest: 1, redact: 2, classify: 3, rank_themes: 4,
  quote_select: 5, action_gen: 6, pulse_note: 7, email_draft: 8,
};

function stageToStepUpdate(run: {
  stage: string; event: string;
  name?: string; step?: number;
  detail?: string; error?: string; completed: boolean;
}) {
  if (run.completed) return JSON.stringify({ completed: true });

  let stepId: number | undefined;
  let state: 'active' | 'done' | 'error' = 'active';

  if (run.stage === 'pipeline') {
    // Orchestrator meta-events:
    //   step_start → {"stage":"pipeline","event":"step_start","step":N,"name":"ingest"}
    //   step_done  → {"stage":"pipeline","event":"step_done","step":N,...}
    stepId = typeof run.step === 'number' ? run.step : (run.name ? STEP_MAP[run.name] : undefined);
    if (run.event === 'step_done') state = 'done';
    if (run.event === 'step_start') state = 'active';
    if (run.event === 'run_error') state = 'error';
  } else {
    // Module-level events: e.g. classify_complete, quote_select_complete, ingest_complete
    stepId = STEP_MAP[run.stage];
    if (run.event.includes('complete') || run.event.includes('done')) state = 'done';
    if (run.event.includes('error')) state = 'error';
  }

  if (!stepId) return null;
  return JSON.stringify({ step: stepId, state, detail: run.error ?? run.detail });
}

export async function GET(req: NextRequest) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      let lastEvent = '';
      let ticks = 0;
      const MAX_TICKS = 1440; // 12min timeout at 500ms intervals

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
