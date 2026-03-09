'use client';

import { useState, useEffect, useRef } from 'react';

interface Story {
    id: string;
    title: string;
    priority: number;
    passes: boolean;
    description?: string;
    acceptanceCriteria?: string[];
}

interface Prd {
    project: string;
    branchName: string;
    description: string;
    userStories: Story[];
}

interface GitCommit {
    hash: string;
    message: string;
}

export default function Home() {
    // State
    const [projectPath, setProjectPath] = useState('');
    const [isValidated, setIsValidated] = useState(false);
    const [validationError, setValidationError] = useState('');
    const [prd, setPrd] = useState<Prd | null>(null);
    const [progress, setProgress] = useState('');
    const [gitLog, setGitLog] = useState<GitCommit[]>([]);
    const [branch, setBranch] = useState('');
    const [archivePath, setArchivePath] = useState('');

    // Run state
    const [tool, setTool] = useState('antigravity-claude');
    const [maxIterations, setMaxIterations] = useState(10);
    const [isRunning, setIsRunning] = useState(false);
    const [runId, setRunId] = useState<string | null>(null);
    const [logs, setLogs] = useState<string[]>([]);
    const [currentIteration, setCurrentIteration] = useState(0);

    const eventSourceRef = useRef<EventSource | null>(null);
    const logsEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll logs
    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    // Validate project path
    const handleValidate = async () => {
        try {
            const res = await fetch('/api/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: projectPath }),
            });
            const data = await res.json();

            if (data.valid) {
                setIsValidated(true);
                setValidationError('');
                loadProjectData();
            } else {
                setIsValidated(false);
                setValidationError(data.error || 'Invalid project path');
            }
        } catch (err) {
            setValidationError('Failed to validate path');
        }
    };

    // Load project data
    const loadProjectData = async () => {
        try {
            // Load PRD
            const prdRes = await fetch(`/api/prd?path=${encodeURIComponent(projectPath)}`);
            if (prdRes.ok) {
                setPrd(await prdRes.json());
            }

            // Load progress
            const progressRes = await fetch(`/api/progress?path=${encodeURIComponent(projectPath)}`);
            if (progressRes.ok) {
                const data = await progressRes.json();
                setProgress(data.content || '');
            }

            // Load git info
            const gitRes = await fetch(`/api/git?path=${encodeURIComponent(projectPath)}`);
            if (gitRes.ok) {
                const data = await gitRes.json();
                setGitLog(data.log || []);
                setBranch(data.branch || '');
            }
        } catch (err) {
            console.error('Failed to load project data:', err);
        }
    };

    // Start run
    const handleRun = async () => {
        try {
            const res = await fetch('/api/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: projectPath, tool, maxIterations }),
            });
            const data = await res.json();

            if (data.runId) {
                setRunId(data.runId);
                setIsRunning(true);
                setLogs([]);
                setCurrentIteration(0);

                // Connect to SSE stream
                const es = new EventSource(`/api/stream?runId=${data.runId}`);
                eventSourceRef.current = es;

                es.onmessage = (event) => {
                    const line = event.data;
                    setLogs(prev => [...prev, line]);

                    // Parse iteration from log
                    const iterMatch = line.match(/Iteration (\d+) of/);
                    if (iterMatch) {
                        setCurrentIteration(parseInt(iterMatch[1], 10));
                    }

                    // Check for completion
                    if (line.includes('COMPLETE') || line.includes('completed all tasks')) {
                        loadProjectData();
                    }
                };

                es.onerror = () => {
                    setIsRunning(false);
                    es.close();
                    loadProjectData();
                };

                es.addEventListener('done', () => {
                    setIsRunning(false);
                    es.close();
                    loadProjectData();
                });
            }
        } catch (err) {
            console.error('Failed to start run:', err);
        }
    };

    // Stop run
    const handleStop = async () => {
        if (!runId) return;

        try {
            await fetch('/api/stop', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ runId }),
            });

            setIsRunning(false);
            eventSourceRef.current?.close();
            setLogs(prev => [...prev, `\n--- Stopped at iteration ${currentIteration} ---`]);
        } catch (err) {
            console.error('Failed to stop run:', err);
        }
    };

    // Find next story
    const nextStory = prd?.userStories
        .filter(s => !s.passes)
        .sort((a, b) => a.priority - b.priority)[0];

    // Format log line with colors
    const formatLogLine = (line: string, index: number) => {
        let className = '';
        if (line.includes('===') || line.includes('Iteration')) {
            className = 'iteration';
        } else if (line.includes('ERROR') || line.includes('FAILED') || line.includes('error')) {
            className = 'error';
        } else if (line.includes('PASSED') || line.includes('complete') || line.includes('COMPLETE')) {
            className = 'success';
        }
        return <div key={index} className={className}>{line}</div>;
    };

    return (
        <div className="container">
            <header className="header">
                <span style={{ fontSize: '2.5rem' }}>🤖</span>
                <h1>Ralph UI</h1>
                <span style={{ color: 'var(--text-secondary)', marginLeft: 'auto' }}>
                    Autonomous AI Agent Loop
                </span>
            </header>

            {/* Project Input */}
            <div className="card" style={{ marginBottom: '1.5rem' }}>
                <h2>Project Path</h2>
                <div className="input-group">
                    <input
                        type="text"
                        placeholder="Enter absolute path to project..."
                        value={projectPath}
                        onChange={(e) => setProjectPath(e.target.value)}
                        disabled={isRunning}
                    />
                    <button onClick={handleValidate} disabled={!projectPath || isRunning}>
                        Validate
                    </button>
                </div>
                {validationError && (
                    <div style={{ color: 'var(--error)', fontSize: '0.9rem' }}>{validationError}</div>
                )}
                {isValidated && (
                    <div className="status-badge success">✓ Valid project</div>
                )}
            </div>

            {isValidated && (
                <div className="grid">
                    {/* Run Panel */}
                    <div className="card">
                        <h2>Run Ralph</h2>
                        <div className="run-panel">
                            <div className="run-field">
                                <label>Tool</label>
                                <select value={tool} onChange={(e) => setTool(e.target.value)} disabled={isRunning}>
                                    <option value="antigravity-claude">antigravity-claude</option>
                                    <option value="amp">amp</option>
                                    <option value="claude">claude</option>
                                </select>
                            </div>
                            <div className="run-field">
                                <label>Max Iterations</label>
                                <input
                                    type="number"
                                    value={maxIterations}
                                    onChange={(e) => setMaxIterations(Number(e.target.value))}
                                    min={1}
                                    max={100}
                                    style={{ width: '80px' }}
                                    disabled={isRunning}
                                />
                            </div>
                            <div className="run-actions">
                                {!isRunning ? (
                                    <button onClick={handleRun} disabled={!nextStory}>
                                        ▶ Run
                                    </button>
                                ) : (
                                    <button className="danger" onClick={handleStop}>
                                        ■ Stop
                                    </button>
                                )}
                            </div>
                        </div>
                        {isRunning && (
                            <>
                                <div className="progress-bar">
                                    <div
                                        className="progress-bar-fill"
                                        style={{ width: `${(currentIteration / maxIterations) * 100}%` }}
                                    />
                                </div>
                                <div className="iteration-indicator">
                                    Iteration {currentIteration} of {maxIterations}
                                </div>
                            </>
                        )}
                    </div>

                    {/* Next Story */}
                    <div className="card">
                        <h2>Next Story</h2>
                        {nextStory ? (
                            <div>
                                <strong>{nextStory.id}</strong> - {nextStory.title}
                                <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.5rem' }}>
                                    Priority: {nextStory.priority}
                                </div>
                            </div>
                        ) : (
                            <div className="status-badge success">All stories complete!</div>
                        )}
                    </div>

                    {/* Live Logs */}
                    <div className="card full-width">
                        <h2>
                            Live Logs
                            {isRunning && <span className="pulse" style={{ marginLeft: '0.5rem' }}>●</span>}
                        </h2>
                        <div className="log-viewer">
                            {logs.length === 0 ? (
                                <div style={{ color: 'var(--text-secondary)' }}>Logs will appear here...</div>
                            ) : (
                                logs.map((line, i) => formatLogLine(line, i))
                            )}
                            <div ref={logsEndRef} />
                        </div>
                    </div>

                    {/* Stories Table */}
                    <div className="card full-width">
                        <h2>User Stories</h2>
                        {prd && (
                            <table className="stories-table">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Title</th>
                                        <th>Priority</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {prd.userStories.map((story) => (
                                        <tr key={story.id}>
                                            <td>{story.id}</td>
                                            <td>{story.title}</td>
                                            <td>{story.priority}</td>
                                            <td>
                                                <span className={`status-badge ${story.passes ? 'success' : 'pending'}`}>
                                                    {story.passes ? '✓ Pass' : '○ Pending'}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>

                    {/* Git Info */}
                    <div className="card">
                        <h2>Git Status</h2>
                        <div style={{ marginBottom: '1rem' }}>
                            <strong>Branch:</strong> <code className="branch-name">{branch || 'N/A'}</code>
                        </div>
                        <div><strong>Recent Commits</strong></div>
                        {gitLog.length > 0 ? (
                            <ul className="git-log">
                                {gitLog.slice(0, 5).map((commit, i) => (
                                    <li key={i}>
                                        <span className="hash">{commit.hash}</span>
                                        {commit.message}
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.5rem' }}>
                                No commits yet
                            </div>
                        )}
                    </div>

                    {/* Progress */}
                    <div className="card">
                        <h2>Progress Log</h2>
                        <div className="log-viewer" style={{ maxHeight: '200px' }}>
                            <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                                {progress || 'No progress logged yet.'}
                            </pre>
                        </div>
                        <button
                            className="secondary"
                            style={{ marginTop: '1rem' }}
                            onClick={loadProjectData}
                        >
                            ↻ Refresh
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
