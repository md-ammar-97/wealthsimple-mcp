import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import { randomUUID } from 'crypto';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');
const VENV_PYTHON  = path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe');

let activeRunId: string | null = null;

export interface RunState {
  runId: string;
  stage: string;
  event: string;
  detail?: string;
  error?: string;
  completed: boolean;
}

declare global {
  // eslint-disable-next-line no-var
  var pipelineRun: RunState | undefined;
}

export async function POST() {
  if (activeRunId) {
    return NextResponse.json({ error: 'A pipeline run is already in progress' }, { status: 409 });
  }

  const runId = randomUUID();
  activeRunId = runId;

  global.pipelineRun = { runId, stage: '', event: 'started', completed: false };

  const child = spawn(VENV_PYTHON, ['-m', 'pulse.cli', 'run'], {
    cwd: PROJECT_ROOT,
    env: { ...process.env },
  });

  child.stdout.on('data', (chunk: Buffer) => {
    const line = chunk.toString().trim();
    if (!line) return;
    try {
      const parsed = JSON.parse(line);
      global.pipelineRun = { runId, ...parsed, completed: false };
    } catch {
      // plain text line — ignore
    }
  });

  child.stderr.on('data', (chunk: Buffer) => {
    const msg = chunk.toString().trim();
    if (msg) {
      global.pipelineRun = { runId, stage: 'error', event: 'error', error: msg, completed: false };
    }
  });

  child.on('close', (code: number | null) => {
    activeRunId = null;
    if (code === 0) {
      global.pipelineRun = { runId, stage: 'done', event: 'done', completed: true };
    } else {
      global.pipelineRun = {
        runId,
        stage: 'error',
        event: 'error',
        error: `Process exited with code ${code}`,
        completed: false,
      };
    }
  });

  return NextResponse.json({ runId });
}
