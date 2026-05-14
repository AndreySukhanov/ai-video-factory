import { API_V1_BASE_URL } from '@/lib/apiBase';

export interface PipelineTemplatePayload {
  version: number;
  ideaForm: {
    idea: string;
    genre: string;
    episodesCount: number;
    duration: number;
    aspectRatio: string;
    model: string;
  };
  episodeOverrides?: Array<{
    number: number;
    model?: string;
    duration?: number;
  }>;
  imageModel?: string;
  storyboardSeed?: number | null;
  anchorPromptHint?: string;
}

export interface PipelineTemplate {
  id: number;
  name: string;
  description: string | null;
  payload: PipelineTemplatePayload;
  created_at: string | null;
  updated_at: string | null;
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export async function listTemplates(): Promise<PipelineTemplate[]> {
  return jsonOrThrow(await fetch(`${API_V1_BASE_URL}/pipeline-templates/`));
}

export async function createTemplate(payload: {
  name: string;
  description?: string;
  payload: PipelineTemplatePayload;
}): Promise<PipelineTemplate> {
  return jsonOrThrow(
    await fetch(`${API_V1_BASE_URL}/pipeline-templates/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  );
}

export async function deleteTemplate(id: number): Promise<void> {
  const res = await fetch(`${API_V1_BASE_URL}/pipeline-templates/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Delete failed (${res.status})`);
  }
}
