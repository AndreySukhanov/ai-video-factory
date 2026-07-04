'use client';

import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
    children: React.ReactNode;
    /** Feature name for the error message */
    featureName?: string;
}

interface State {
    error: Error | null;
}

/**
 * Granular error boundary for heavy features (generation wizard, etc.):
 * a crash inside the feature doesn't take down the whole route — a local
 * fallback with a remount button is shown instead.
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
                            className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-700 px-4 py-2 rounded-lg text-sm text-white transition-colors"
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
