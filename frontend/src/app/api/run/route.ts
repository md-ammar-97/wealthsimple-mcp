import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { mkdir, writeFile } from 'fs/promises';
import path from 'path';
import { randomUUID } from 'crypto';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');
// On Linux (Render) use system python3; on Windows use the local venv
const PYTHON_BIN = process.platform === 'win32'
  ? path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe')
  : 'python3';

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

  const OUTPUTS_DIR = path.resolve(PROJECT_ROOT, 'outputs');
  await mkdir(OUTPUTS_DIR, { recursive: true });
  await writeFile(
    path.join(OUTPUTS_DIR, 'run_summary.json'),
    JSON.stringify({ run_id: runId, status: 'running', started_at: new Date().toISOString() }),
  );

  const child = spawn(PYTHON_BIN, ['-m', 'pulse.cli', 'run', '--input', 'data/input/reviews.csv'], {
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

  let stderrBuf = '';
  child.stderr.on('data', (chunk: Buffer) => {
    const msg = chunk.toString().trim();
    if (msg) {
      stderrBuf += msg + '\n';
      console.error('[pipeline stderr]', msg);
      global.pipelineRun = { runId, stage: 'error', event: 'error', error: msg, completed: false };
    }
  });

  child.on('error', (err: Error) => {
    activeRunId = null;
    console.error('[pipeline spawn error]', err.message, 'PYTHON_BIN:', PYTHON_BIN, 'CWD:', PROJECT_ROOT);
    global.pipelineRun = { runId, stage: 'error', event: 'error', error: err.message, completed: false };
  });

  child.on('close', (code: number | null) => {
    activeRunId = null;
    console.log('[pipeline close] code:', code, 'stderr:', stderrBuf.slice(0, 500));
    if (code === 0) {
      global.pipelineRun = { runId, stage: 'done', event: 'done', completed: true };
    } else {
      global.pipelineRun = {
        runId,
        stage: 'error',
        event: 'error',
        error: stderrBuf.trim() || `Process exited with code ${code}`,
        completed: false,
      };
    }
  });

  return NextResponse.json({ runId });
}
