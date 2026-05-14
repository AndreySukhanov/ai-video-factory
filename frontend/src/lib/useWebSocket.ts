import { useEffect, useState, useCallback, useRef } from 'react';
import { safeJsonParse } from '@/lib/safeJson';

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_BASE_URL || 'ws://localhost:8000/api/v1';

export interface JobUpdate {
    type: 'job_update' | 'connected' | 'heartbeat' | 'pong';
    job_id?: number;
    job_type?: string;
    status?: string;
    progress?: number;
    message?: string;
    episode_id?: number;
    scene_id?: number;
    project_id?: number;
    timestamp?: string;
}

export interface JobProgress {
    id: number;
    type: string;
    status: string;
    progress: number;
    message?: string;
    episode_id?: number;
    scene_id?: number;
    project_id?: number;
    error_text?: string;
}

interface UseWebSocketReturn {
    isConnected: boolean;
    lastUpdate: JobUpdate | null;
    jobs: Map<number, JobProgress>;
    jobsList: JobProgress[];
    connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
}

export function useProjectWebSocket(projectId: number | string): UseWebSocketReturn {
    const [isConnected, setIsConnected] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
    const [lastUpdate, setLastUpdate] = useState<JobUpdate | null>(null);
    const [jobs, setJobs] = useState<Map<number, JobProgress>>(new Map());
    const wsRef = useRef<WebSocket | null>(null);
    const connectRef = useRef<() => void>(() => {});
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            return;
        }

        setConnectionStatus('connecting');
        const wsUrl = `${WS_BASE_URL}/ws/${projectId}`;

        try {
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            ws.onopen = () => {
                console.log('🔌 WebSocket connected');
                setIsConnected(true);
                setConnectionStatus('connected');

                // Start ping interval for keep-alive
                pingIntervalRef.current = setInterval(() => {
                    if (ws.readyState === WebSocket.OPEN) {
                        ws.send('ping');
                    }
                }, 25000);
            };

            ws.onclose = () => {
                console.log('🔌 WebSocket disconnected');
                setIsConnected(false);
                setConnectionStatus('disconnected');

                // Clear ping interval
                if (pingIntervalRef.current) {
                    clearInterval(pingIntervalRef.current);
                }

                // Reconnect after delay
                reconnectTimeoutRef.current = setTimeout(() => {
                    connectRef.current();
                }, 3000);
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                setConnectionStatus('error');
            };

            ws.onmessage = (event) => {
                const data = safeJsonParse<JobUpdate | null>(event.data, null);
                if (!data) {
                    console.error('Error parsing WebSocket message: invalid payload');
                    return;
                }

                setLastUpdate(data);

                if (data.type === 'job_update' && data.job_id) {
                    setJobs(prev => {
                        const newMap = new Map(prev);
                        newMap.set(data.job_id!, {
                            id: data.job_id!,
                            type: data.job_type || '',
                            status: data.status || '',
                            progress: data.progress || 0,
                            message: data.message,
                            episode_id: data.episode_id,
                            scene_id: data.scene_id,
                            project_id: data.project_id
                        });
                        return newMap;
                    });
                }
            };
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            setConnectionStatus('error');
        }
    }, [projectId]);

    useEffect(() => {
        connectRef.current = connect;
    }, [connect]);

    useEffect(() => {
        const bootstrapTimer = setTimeout(() => {
            connectRef.current();
        }, 0);

        return () => {
            clearTimeout(bootstrapTimer);
            // Cleanup on unmount
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
            if (pingIntervalRef.current) {
                clearInterval(pingIntervalRef.current);
            }
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [connect]);

    return {
        isConnected,
        lastUpdate,
        jobs,
        jobsList: Array.from(jobs.values()),
        connectionStatus
    };
}
