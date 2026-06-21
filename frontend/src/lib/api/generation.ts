import { API_V1_BASE_URL } from '@/lib/apiBase';

export type GenerationModel = 'kling' | 'minimax' | 'laozhang' | 'gemini' | 'vertex' | 'seedance' | 'wavespeed' | 'wavespeed-standard' | 'wavespeed-v15' | 'fal';

export interface SeriesPlanRequest {
  idea: string;
  genre: string;
  episodes_count: number;
  duration: number;
  aspect_ratio: string;
  llm_model?: 'deepseek' | 'opus' | 'opus-4.7' | null;
}

export interface SeriesPlanEpisode {
  number: number;
  title: string;
  synopsis: string;
  prompt: string;
  anchor_prompt?: string;
  variable_prompt?: string;
}

export interface SeriesPlanResponse {
  success: boolean;
  series_title?: string;
  logline?: string;
  character_card?: string;
  voice_description?: string;
  anchor_prompt?: string;
  episodes: SeriesPlanEpisode[];
  error?: string;
}

export interface GenerateClipRequest {
  prompt: string;
  duration: number;
  aspect_ratio: string;
  model: GenerationModel;
  reference_image_url?: string;
  last_frame_image_url?: string;
  reference_images?: string[];
  negative_prompt?: string;
  seed?: number;
  quality_mode?: 'fast' | 'standard';
  generate_audio?: boolean;
  variants_count?: number;
  use_timestamps?: boolean;
  narrative_structure?: string;
}

export interface GenerateClipResponse {
  success: boolean;
  video_url?: string;
  variants?: string[];
  status: string;
  quality_mode?: string;
  error?: string;
}

export interface ReviewCreateRequest {
  video_url: string;
  title: string;
  description: string;
  tags: string[];
  project_id?: number | null;
}

export interface ExtractFrameRequest {
  video_url: string;
}

export interface ExtractFrameResponse {
  success: boolean;
  frame_url?: string;
  error?: string;
}

// Bypass Next.js 16 fetch instrumentation completely.
// Next.js patches window.fetch AND the Response constructor, causing
// "Cannot read properties of undefined (reading 'logs')" errors.
// Solution: use XMLHttpRequest and parse JSON directly — never touch Response.
function xhrJson<T>(url: string, init?: RequestInit): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(init?.method || 'GET', url);
    // Set headers
    xhr.setRequestHeader('Content-Type', 'application/json');
    const headers = init?.headers as Record<string, string> | undefined;
    if (headers) {
      Object.entries(headers).forEach(([k, v]) => xhr.setRequestHeader(k, v));
    }
    xhr.onload = () => {
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        data = {};
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data as T);
      } else {
        const detail = typeof data?.detail === 'string' ? data.detail : 'Request failed';
        reject(new Error(detail));
      }
    };
    xhr.onerror = () => reject(new Error('Network error'));
    xhr.ontimeout = () => reject(new Error('Request timeout'));
    xhr.timeout = 600000; // 10 min for long video generation
    xhr.send(init?.body as string | null || null);
  });
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  if (typeof window !== 'undefined' && typeof XMLHttpRequest !== 'undefined') {
    return xhrJson<T>(url, init);
  }
  // SSR fallback — use native fetch
  const res = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : 'Request failed';
    throw new Error(detail);
  }
  return data as T;
}

export async function generateSeriesPlan(payload: SeriesPlanRequest): Promise<SeriesPlanResponse> {
  return requestJson<SeriesPlanResponse>(`${API_V1_BASE_URL}/episodes/generate-series`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function generateEpisodeClip(payload: GenerateClipRequest): Promise<GenerateClipResponse> {
  return requestJson<GenerateClipResponse>(`${API_V1_BASE_URL}/episodes/generate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export interface MergeVideosRequest {
  video_urls: string[];
}

export interface MergeVideosResponse {
  success: boolean;
  merged_video_url?: string;
  total_duration?: number;
  error?: string;
}

export async function mergeVideos(payload: MergeVideosRequest): Promise<MergeVideosResponse> {
  return requestJson<MergeVideosResponse>(`${API_V1_BASE_URL}/episodes/merge`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function extractLastFrame(payload: ExtractFrameRequest): Promise<ExtractFrameResponse> {
  return requestJson<ExtractFrameResponse>(`${API_V1_BASE_URL}/episodes/extract-last-frame`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export interface ExtendVideoRequest {
  video_url: string;
  prompt: string;
  extensions_count?: number;
  aspect_ratio?: string;
  model?: string;
  quality_mode?: 'fast' | 'standard';
}

export interface ExtendVideoResponse {
  success: boolean;
  extended_video_url?: string;
  total_duration?: number;
  segments_count?: number;
  error?: string;
}

export async function extendVideo(payload: ExtendVideoRequest): Promise<ExtendVideoResponse> {
  return requestJson<ExtendVideoResponse>(`${API_V1_BASE_URL}/episodes/extend`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export type ImageModel = 'gemini' | 'seedream' | 'flux';

export interface StoryboardRequest {
  anchor_prompt: string;
  character_card?: string;
  episode_prompts: string[];
  aspect_ratio?: string;
  seed?: number;
  image_model?: ImageModel;
  reference_image_urls?: string[];
  visual_audit?: boolean;
}

export interface FrameAuditReport {
  index: number;
  score: number;
  mismatches: string[];
  regenerated: boolean;
}

export interface StoryboardResponse {
  success: boolean;
  keyframes: string[];
  seed?: number;
  audit?: FrameAuditReport[];
  error?: string;
}

export async function generateStoryboard(payload: StoryboardRequest): Promise<StoryboardResponse> {
  return requestJson<StoryboardResponse>(`${API_V1_BASE_URL}/episodes/storyboard`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export interface StoryboardFrameRequest {
  anchor_prompt: string;
  character_card?: string;
  episode_prompt: string;
  aspect_ratio?: string;
  seed?: number;
  image_model?: ImageModel;
  reference_image_urls?: string[];
}

export interface StoryboardFrameResponse {
  success: boolean;
  frame_url?: string;
  seed?: number;
  error?: string;
}

export async function regenerateStoryboardFrame(payload: StoryboardFrameRequest): Promise<StoryboardFrameResponse> {
  return requestJson<StoryboardFrameResponse>(`${API_V1_BASE_URL}/episodes/storyboard/frame`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createReviewItem(payload: ReviewCreateRequest): Promise<void> {
  await requestJson(`${API_V1_BASE_URL}/review/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// --- TTS / Voiceover (Phase 1) ---

export type VoiceoverProvider = 'elevenlabs' | 'openai';

export interface WordTiming {
  word: string;
  start: number;
  end: number;
}

export interface VoiceoverRequest {
  text: string;
  provider?: VoiceoverProvider;
  voice_id?: string;
  episode_id?: number;
  video_url?: string;
  mute_original?: boolean;
}

export interface VoiceoverResponse {
  success: boolean;
  audio_url?: string;
  words: WordTiming[];
  duration_sec?: number;
  provider?: string;
  video_with_voiceover_url?: string;
  error?: string;
}

export async function generateVoiceover(payload: VoiceoverRequest): Promise<VoiceoverResponse> {
  return requestJson<VoiceoverResponse>(`${API_V1_BASE_URL}/episodes/voiceover`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// --- Captions burn-in (Phase 2) ---

export type CaptionStyle = 'modern' | 'neon' | 'bold' | 'minimal' | 'cinematic';
export type CaptionMode = 'word_pop' | 'karaoke_line';

export interface CaptionsRequest {
  video_url: string;
  words: WordTiming[];
  style?: CaptionStyle;
  mode?: CaptionMode;
  episode_id?: number;
}

export interface CaptionsResponse {
  success: boolean;
  video_with_captions_url?: string;
  error?: string;
}

export async function burnCaptions(payload: CaptionsRequest): Promise<CaptionsResponse> {
  return requestJson<CaptionsResponse>(`${API_V1_BASE_URL}/episodes/captions`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// --- Background music (Phase 3) ---

export interface MusicTrack {
  id: string;
  display_name: string;
  mood: string;
  url: string;
  duration_sec?: number;
  credit?: string;
}

export interface MusicTracksResponse {
  tracks: MusicTrack[];
}

export interface AddMusicRequest {
  video_url: string;
  track_id: string;
  volume?: number;
  loop_music?: boolean;
  fade_in?: number;
  fade_out?: number;
  episode_id?: number;
}

export interface AddMusicResponse {
  success: boolean;
  video_with_music_url?: string;
  error?: string;
}

export async function listMusicTracks(mood?: string): Promise<MusicTracksResponse> {
  const qs = mood ? `?mood=${encodeURIComponent(mood)}` : '';
  return requestJson<MusicTracksResponse>(`${API_V1_BASE_URL}/episodes/music/tracks${qs}`, {
    method: 'GET',
  });
}

export async function addMusicToVideo(payload: AddMusicRequest): Promise<AddMusicResponse> {
  return requestJson<AddMusicResponse>(`${API_V1_BASE_URL}/episodes/music`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// --- Image upload (multipart/form-data, NOT JSON) ---

export interface UploadImageResponse {
  success: boolean;
  url: string;
  local_url: string;
  external_url?: string;
  size: number;
  original_size: number;
}

export async function uploadImage(file: File): Promise<UploadImageResponse> {
  const formData = new FormData();
  formData.append('file', file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_V1_BASE_URL}/upload/image`);
    xhr.onload = () => {
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        data = {};
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data as unknown as UploadImageResponse);
      } else {
        reject(new Error(typeof data?.detail === 'string' ? data.detail : 'Upload failed'));
      }
    };
    xhr.onerror = () => reject(new Error('Network error'));
    xhr.timeout = 60000;
    xhr.ontimeout = () => reject(new Error('Upload timeout'));
    // Do NOT set Content-Type — browser sets multipart boundary automatically
    xhr.send(formData);
  });
}
