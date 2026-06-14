import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { mkdir, writeFile, readFile } from 'fs/promises';
import path from 'path';
import { randomUUID } from 'crypto';

const PROJECT_ROOT = path.resolve(process.cwd(), '..');
const PYTHON_BIN = process.platform === 'win32'
  ? path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe')
  : 'python3';

const MCP_SERVER_URL = process.env.MCP_SERVER_URL
  ?? 'https://mcp-server-google-695514226672.europe-west1.run.app';

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
  // eslint-disable-next-line no-var
  var pipelineQueue: RunState[];
  // eslint-disable-next-line no-var
  var csvMeta: { email: string; appName: string } | undefined;
}

async function sendEmailViaMcp(email: string, appName: string): Promise<void> {
  const emailFile = path.join(PROJECT_ROOT, 'outputs', 'email_draft.txt');
  let body = '';
  try {
    body = await readFile(emailFile, 'utf8');
  } catch {
    // email draft not written — skip silently
    return;
  }

  const apiKey = process.env.MCP_API_KEY ?? '';
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (apiKey) headers['X-Api-Key'] = apiKey;

  const subject = `Review Pulse Report — ${appName}`;

  try {
    await fetch(`${MCP_SERVER_URL}/create_email_draft`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ to: email, subject, body }),
      signal: AbortSignal.timeout(20_000),
    });
  } catch {
    // non-fatal — email delivery failure does not break results
  }
}

export async function POST() {
  if (activeRunId) {
    return NextResponse.json({ error: 'A pipeline run is already in progress' }, { status: 409 });
  }

  const runId = randomUUID();
  activeRunId = runId;

  global.pipelineRun = { runId, stage: '', event: 'started', completed: false };
  global.pipelineQueue = [];

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
    for (const raw of chunk.toString().split('\n')) {
      const line = raw.trim();
      if (!line) continue;
      try {
        const parsed = JSON.parse(line);
        const state: RunState = { runId, ...parsed, completed: false };
        global.pipelineRun = state;
        global.pipelineQueue.push(state);
      } catch {
        // non-JSON stdout line — ignore
      }
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

  child.on('close', async (code: number | null) => {
    activeRunId = null;
    console.log('[pipeline close] code:', code, 'stderr:', stderrBuf.slice(0, 500));
    if (code === 0) {
      const doneState: RunState = { runId, stage: 'done', event: 'done', completed: true };
      global.pipelineRun = doneState;
      global.pipelineQueue.push(doneState);

      // Send email to the CSV uploader if metadata was captured
      const meta = global.csvMeta;
      if (meta?.email) {
        await sendEmailViaMcp(meta.email, meta.appName);
      }
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
