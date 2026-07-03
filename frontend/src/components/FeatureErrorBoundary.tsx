'use client';

import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
    children: React.ReactNode;
    /** Название фичи для сообщения об ошибке */
    featureName?: string;
}

interface State {
    error: Error | null;
}

/**
 * Гранулярный error boundary для тяжёлых фич (визард генерации и т.п.):
 * падение внутри фичи не рушит весь маршрут — показывается локальная
 * заглушка с кнопкой повторного монтирования.
 */
export default class FeatureErrorBoundary extends React.Component<Props, State> {
    state: State = { error: null };

    static getDerivedStateFromError(error: Error): State {
        return { error };
    }

    componentDidCatch(error: Error, info: React.ErrorInfo) {
        console.error(`[ErrorBoundary${this.props.featureName ? `:${this.props.featureName}` : ''}]`, error, info.componentStack);
    }

    render() {
        if (this.state.error) {
            return (
                <div className="min-h-[40vh] flex items-center justify-center p-8">
                    <div className="max-w-md text-center">
                        <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto mb-4" />
                        <p className="text-white font-semibold mb-1">
                            {this.props.featureName || 'Component'} crashed
                        </p>
                        <p className="text-sm text-gray-400 mb-4 break-words">{this.state.error.message}</p>
                        <button
                            onClick={() => this.setState({ error: null })}
                            className="inline-flex items-center gap-2 bg-purple-600 hover:bg-purple-700 px-4 py-2 rounded-lg text-sm text-white transition-colors"
                        >
                            <RefreshCw className="w-4 h-4" />
                            Reload
                        </button>
                    </div>
                </div>
            );
        }
        return this.props.children;
    }
}
