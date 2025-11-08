import React from 'react';
import { ConversationTurn } from '../types';

interface ConversationTurnCardProps {
    turn: ConversationTurn;
    score?: number;
    onDelete?: (id: string) => void;
    highlight?: string;
}

const ConversationTurnCard: React.FC<ConversationTurnCardProps> = ({
    turn,
    score,
    onDelete,
    highlight
}) => {
    const formatDate = (timestamp: string) => {
        return new Date(timestamp).toLocaleString();
    };

    const highlightText = (text: string, query?: string) => {
        if (!query) return text;
        const parts = text.split(new RegExp(`(${query})`, 'gi'));
        return parts.map((part, i) =>
            part.toLowerCase() === query.toLowerCase() ? (
                <mark key={i} style={{ backgroundColor: '#ffeb3b', padding: '0 2px' }}>
                    {part}
                </mark>
            ) : (
                part
            )
        );
    };

    return (
        <div
            style={{
                border: '1px solid #e0e0e0',
                borderRadius: '8px',
                padding: '16px',
                marginBottom: '12px',
                backgroundColor: '#fff',
                boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            }}
        >
            {/* Header */}
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '12px',
                    paddingBottom: '8px',
                    borderBottom: '1px solid #f0f0f0',
                }}
            >
                <div style={{ fontSize: '12px', color: '#666' }}>
                    <strong>Session:</strong> {turn.session_id} • <strong>Turn:</strong> #{turn.turn_number}
                    {score !== undefined && (
                        <>
                            {' '}
                            • <strong>Score:</strong>{' '}
                            <span
                                style={{
                                    color: score > 0.7 ? 'green' : score > 0.5 ? 'orange' : 'red',
                                    fontWeight: 'bold',
                                }}
                            >
                                {(score * 100).toFixed(0)}%
                            </span>
                        </>
                    )}
                </div>
                <div style={{ fontSize: '11px', color: '#999' }}>{formatDate(turn.timestamp)}</div>
            </div>

            {/* User Message */}
            <div style={{ marginBottom: '12px' }}>
                <div
                    style={{
                        fontSize: '12px',
                        color: '#1976d2',
                        fontWeight: '600',
                        marginBottom: '4px',
                    }}
                >
                    👤 User:
                </div>
                <div
                    style={{
                        padding: '8px 12px',
                        backgroundColor: '#e3f2fd',
                        borderRadius: '4px',
                        fontSize: '14px',
                        lineHeight: '1.5',
                    }}
                >
                    {highlightText(turn.user_message, highlight)}
                </div>
            </div>

            {/* Assistant Message */}
            <div>
                <div
                    style={{
                        fontSize: '12px',
                        color: '#7b1fa2',
                        fontWeight: '600',
                        marginBottom: '4px',
                    }}
                >
                    🤖 Assistant:
                </div>
                <div
                    style={{
                        padding: '8px 12px',
                        backgroundColor: '#f3e5f5',
                        borderRadius: '4px',
                        fontSize: '14px',
                        lineHeight: '1.5',
                    }}
                >
                    {highlightText(turn.assistant_message, highlight)}
                </div>
            </div>

            {/* Footer */}
            <div
                style={{
                    marginTop: '12px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                }}
            >
                <div style={{ fontSize: '11px', color: '#999' }}>
                    ID: {turn.id.substring(0, 8)}... • Extracted: {turn.extracted ? '✅' : '⏳'}
                </div>
                {onDelete && (
                    <button
                        onClick={() => onDelete(turn.id)}
                        style={{
                            padding: '4px 12px',
                            fontSize: '12px',
                            backgroundColor: '#f44336',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                        }}
                    >
                        Delete
                    </button>
                )}
            </div>
        </div>
    );
};

export default ConversationTurnCard;
