import { NextRequest, NextResponse } from 'next/server';
import { writeFile, mkdir } from 'fs/promises';
import path from 'path';

const DATA_INPUT_DIR = path.resolve(process.cwd(), '..', 'data', 'input');

declare global {
  // eslint-disable-next-line no-var
  var csvMeta: { email: string; appName: string } | undefined;
}

export async function POST(req: NextRequest) {
  try {
    const form = await req.formData();
    const file    = form.get('file')    as File | null;
    const email   = (form.get('email')   as string | null)?.trim()   ?? '';
    const appName = (form.get('appName') as string | null)?.trim()   ?? '';

    if (!file)  return NextResponse.json({ error: 'No file provided' }, { status: 400 });
    if (!email) return NextResponse.json({ error: 'Email is required' }, { status: 400 });

    const bytes = await file.arrayBuffer();
    const buf = Buffer.from(bytes);

    await mkdir(DATA_INPUT_DIR, { recursive: true });
    await writeFile(path.join(DATA_INPUT_DIR, 'reviews.csv'), buf);

    // Store in global so the run route can pick it up when the pipeline finishes
    global.csvMeta = { email, appName: appName || file.name.replace(/\.csv$/i, '') };

    return NextResponse.json({ ok: true, filename: file.name, size: buf.length });
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}
