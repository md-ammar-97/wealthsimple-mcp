import { NextResponse } from 'next/server';
import { execSync } from 'child_process';
import path from 'path';
import { existsSync } from 'fs';
import { readFile } from 'fs/promises';

export async function GET() {
  const PROJECT_ROOT = path.resolve(process.cwd(), '..');

  let pythonVersion = 'not found';
  let pulseInstalled = false;
  let torchInstalled = false;

  try { pythonVersion = execSync('python3 --version', { encoding: 'utf8' }).trim(); } catch { /**/ }
  try { execSync('python3 -c "import pulse"', { cwd: PROJECT_ROOT, encoding: 'utf8' }); pulseInstalled = true; } catch { /**/ }
  try { execSync('python3 -c "import torch"', { encoding: 'utf8' }); torchInstalled = true; } catch { /**/ }

  const outputsDir = path.join(PROJECT_ROOT, 'outputs');
  const dataInputDir = path.join(PROJECT_ROOT, 'data', 'input');

  let runSummaryContent: unknown = null;
  try {
    runSummaryContent = JSON.parse(
      await readFile(path.join(outputsDir, 'run_summary.json'), 'utf8'),
    );
  } catch { /* file missing or unreadable */ }

  const g = global as Record<string, unknown>;

  return NextResponse.json({
    cwd: process.cwd(),
    projectRoot: PROJECT_ROOT,
    platform: process.platform,
    nodeVersion: process.version,
    pythonVersion,
    pulseInstalled,
    torchInstalled,
    outputsDirExists: existsSync(outputsDir),
    dataInputDirExists: existsSync(dataInputDir),
    runSummaryExists: existsSync(path.join(outputsDir, 'run_summary.json')),
    runSummaryContent,
    reviewsCsvExists: existsSync(path.join(dataInputDir, 'reviews.csv')),
    pipelineRunState: g.pipelineRun ?? null,
    pipelineQueueLength: (g.pipelineQueue as unknown[] | undefined)?.length ?? 0,
    env: {
      GROQ_API_KEY: process.env.GROQ_API_KEY ? '***set***' : 'NOT SET',
      GEMINI_API_KEY: process.env.GEMINI_API_KEY ? '***set***' : 'NOT SET',
      NODE_ENV: process.env.NODE_ENV,
    },
  });
}
