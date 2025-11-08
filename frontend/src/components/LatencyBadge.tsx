import React from 'react';

interface LatencyBadgeProps {
    latencyMs: number;
    targetMs?: number; // Default 100ms target
    label?: string;
}

const LatencyBadge: React.FC<LatencyBadgeProps> = ({ latencyMs, targetMs = 100, label = 'Latency' }) => {
    // Determine color based on performance
    const getColor = () => {
        if (latencyMs < targetMs) return 'green';
        if (latencyMs < targetMs * 2) return 'yellow';
        return 'red';
    };

    const getEmoji = () => {
        if (latencyMs < targetMs) return '🟢';
        if (latencyMs < targetMs * 2) return '🟡';
        return '🔴';
    };

    const getLabel = () => {
        if (latencyMs < targetMs) return 'Fast';
        if (latencyMs < targetMs * 2) return 'OK';
        return 'Slow';
    };

    const color = getColor();
    const emoji = getEmoji();
    const performanceLabel = getLabel();

    return (
        <div
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '4px 12px',
                borderRadius: '16px',
                backgroundColor: color === 'green' ? '#d4edda' : color === 'yellow' ? '#fff3cd' : '#f8d7da',
                border: `1px solid ${color === 'green' ? '#c3e6cb' : color === 'yellow' ? '#ffeaa7' : '#f5c6cb'}`,
                fontSize: '14px',
                fontWeight: '500',
            }}
        >
            <span>{emoji}</span>
            <span style={{ color: '#333' }}>
                {label}: <strong>{latencyMs.toFixed(0)}ms</strong> ({performanceLabel})
            </span>
        </div>
    );
};

export default LatencyBadge;
