import axios from "axios";
import { API_V1_BASE_URL } from "@/lib/apiBase";

export const api = axios.create({
    baseURL: API_V1_BASE_URL,
});

export interface Project {
    id: number;
    title: string;
    logline: string;
    genre: string;
    target_platform: string;
    status: string;
    created_at: string;
    episodes?: Episode[];
    characters?: Character[];
}

export interface Character {
    id: number;
    name: string;
    role: string;
    description: string;
    reference_image_url?: string;
}

export interface Episode {
    id: number;
    number: number;
    title: string;
    synopsis: string;
    status: string;
    hook?: string;
    scenes?: Scene[];
}

export interface Scene {
    id: number;
    number: number;
    what_happens: string;
    visual_prompt: string;
    assets?: Asset[];
}

export interface Asset {
    id: number;
    type: string;
    url: string;
}

export const fetchProjects = async (): Promise<Project[]> => {
    const response = await api.get("/projects/");
    return response.data;
};

export const createProject = async (data: Record<string, unknown>): Promise<Project> => {
    const response = await api.post("/projects/", data);
    return response.data;
};

export const fetchProject = async (id: string): Promise<Project> => {
    const response = await api.get(`/projects/${id}/`);
    return response.data;
};

export const fetchProjectFull = async (id: string): Promise<Project> => {
    const response = await api.get(`/projects/${id}/full/`);
    return response.data;
};

// Episode generation types
export interface EpisodeGenerateRequest {
    prompt: string;
    duration: number;
    aspect_ratio?: string;
    reference_image_url?: string | null;
}

export interface EpisodeGenerateResponse {
    success: boolean;
    video_url?: string;
    status: string;
    duration?: number;
    generation_time?: number;
    error?: string;
}

// Upload image for reference
export const uploadImage = async (file: File): Promise<{ url: string; filename: string }> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/upload/image', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

// Generate episode from prompt and optional reference image
export const generateEpisode = async (request: EpisodeGenerateRequest): Promise<EpisodeGenerateResponse> => {
    const response = await api.post('/episodes/generate', request);
    return response.data;
};

// Series generation types (Story Mode)
export interface SeriesGenerateRequest {
    idea: string;
    genre: string;
    episodes_count: number;
    duration: number;
    aspect_ratio: string;
}

export interface EpisodePromptData {
    number: number;
    title: string;
    synopsis: string;
    prompt: string;
}

export interface SeriesGenerateResponse {
    success: boolean;
    series_title?: string;
    logline?: string;
    genre?: string;
    episodes: EpisodePromptData[];
    error?: string;
}

// Generate series structure from idea (Story Mode)
export const generateSeries = async (request: SeriesGenerateRequest): Promise<SeriesGenerateResponse> => {
    const response = await api.post('/episodes/generate-series', request);
    return response.data;
};
