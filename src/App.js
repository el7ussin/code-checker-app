import React, { useState, useEffect } from 'react'; // 'useCallback' has been removed

// Main App Component
const App = () => {
    // --- State Management ---
    const [page, setPage] = useState('login'); // 'login', 'register', 'dashboard', 'history'
    const [currentUser, setCurrentUser] = useState(null);
    const [error, setError] = useState('');

    // --- API URL Logic ---
    const API_URL = process.env.NODE_ENV === 'production' 
        ? 'https://code-checker-app.onrender.com' 
        : 'http://localhost:5000';

    // Check login status when the app loads
    useEffect(() => {
        fetch(`${API_URL}/status`, { credentials: 'include' })
            .then(res => res.ok ? res.json() : Promise.reject('Failed to connect'))
            .then(data => {
                if (data.logged_in) {
                    setCurrentUser(data.username);
                    setPage('dashboard');
                }
            })
            .catch(() => setError("Could not connect to the backend server. Is it running?"));
    }, []); // API_URL removed from dependency array

    const handleLogout = () => {
        fetch(`${API_URL}/logout`, { method: 'POST', credentials: 'include' })
            .then(() => {
                setCurrentUser(null);
                setPage('login');
            });
    };

    // --- Page Components ---

    const LoginPage = () => {
        const [username, setUsername] = useState('');
        const [password, setPassword] = useState('');

        const handleSubmit = (e) => {
            e.preventDefault();
            setError('');
            fetch(`${API_URL}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
                credentials: 'include'
            })
            .then(res => res.json().then(data => ({ status: res.status, body: data })))
            .then(({ status, body }) => {
                if (status === 200) {
                    setCurrentUser(body.username);
                    setPage('dashboard');
                } else {
                    setError(body.error || 'Login failed.');
                }
            });
        };

        return (
            <div className="max-w-md mx-auto mt-10">
                <form onSubmit={handleSubmit} className="bg-white p-8 rounded-xl shadow-lg">
                    <h2 className="text-2xl font-bold text-center mb-6">Login</h2>
                    {error && <p className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</p>}
                    <div className="mb-4"><label className="block text-gray-700 mb-2">Username</label><input type="text" value={username} onChange={e => setUsername(e.target.value)} className="w-full p-2 border rounded" required /></div>
                    <div className="mb-6"><label className="block text-gray-700 mb-2">Password</label><input type="password" value={password} onChange={e => setPassword(e.target.value)} className="w-full p-2 border rounded" required /></div>
                    <button type="submit" className="w-full bg-indigo-600 text-white p-3 rounded hover:bg-indigo-700">Login</button>
                    <p className="text-center mt-4">Don't have an account? <button type="button" onClick={() => setPage('register')} className="text-indigo-600 hover:underline">Register</button></p>
                </form>
            </div>
        );
    };

    const RegisterPage = () => {
        const [username, setUsername] = useState('');
        const [password, setPassword] = useState('');

        const handleSubmit = (e) => {
            e.preventDefault();
            setError('');
            fetch(`${API_URL}/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            })
            .then(res => res.json().then(data => ({ status: res.status, body: data })))
            .then(({ status, body }) => {
                if (status === 201) {
                    alert("Registration successful! Please log in.");
                    setPage('login');
                } else {
                    setError(body.error || 'Registration failed.');
                }
            });
        };

        return (
             <div className="max-w-md mx-auto mt-10">
                <form onSubmit={handleSubmit} className="bg-white p-8 rounded-xl shadow-lg">
                    <h2 className="text-2xl font-bold text-center mb-6">Register</h2>
                    {error && <p className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</p>}
                    <div className="mb-4"><label className="block text-gray-700 mb-2">Username</label><input type="text" value={username} onChange={e => setUsername(e.target.value)} className="w-full p-2 border rounded" required /></div>
                    <div className="mb-6"><label className="block text-gray-700 mb-2">Password</label><input type="password" value={password} onChange={e => setPassword(e.target.value)} className="w-full p-2 border rounded" required /></div>
                    <button type="submit" className="w-full bg-indigo-600 text-white p-3 rounded hover:bg-indigo-700">Register</button>
                    <p className="text-center mt-4">Already have an account? <button type="button" onClick={() => setPage('login')} className="text-indigo-600 hover:underline">Login</button></p>
                </form>
            </div>
        );
    };
    
    // This is the full Dashboard component, including all reports
    const DashboardPage = () => {
        const [files, setFiles] = useState([]);
        const [fileContents, setFileContents] = useState([]);
        const [analysisResults, setAnalysisResults] = useState(null);
        const [isLoading, setIsLoading] = useState(false);
        const [dashboardError, setDashboardError] = useState('');
        const [isSuggestionModalOpen, setIsSuggestionModalOpen] = useState(false);
        const [suggestionContent, setSuggestionContent] = useState('');
        const [isSuggestionLoading, setIsSuggestionLoading] = useState(false);
        const [isCodeModalOpen, setIsCodeModalOpen] = useState(false);
        const [codeModalContent, setCodeModalContent] = useState({ fileName: '', content: '' });

        const handleAnalyzeClick = () => {
            if (files.length === 0) {
                setDashboardError("Please upload at least one Python file.");
                return;
            }
            setIsLoading(true);
            setDashboardError('');
            setAnalysisResults(null);

            const filePromises = files.map(file => new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = (e) => resolve({ fileName: file.name, content: e.target.result });
                reader.onerror = reject;
                reader.readAsText(file);
            }));

            Promise.all(filePromises).then(filesWithContent => {
                setFileContents(filesWithContent);
                fetch(`${API_URL}/analyze`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(filesWithContent),
                })
                .then(res => res.ok ? res.json() : Promise.reject('Analysis failed.'))
                .then(data => setAnalysisResults(data))
                .catch(err => setDashboardError(err.toString()))
                .finally(() => setIsLoading(false));
            });
        };

        const handleSaveReport = () => {
            if (!analysisResults) return;
            fetch(`${API_URL}/save-report`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(analysisResults),
                credentials: 'include'
            })
            .then(res => res.json())
            .then(data => {
                if(data.message) alert("Report saved successfully!");
            });
        };

        const handleGetSuggestion = (issue) => {
            setIsSuggestionModalOpen(true);
            setIsSuggestionLoading(true);
            setSuggestionContent('');
            const fileName = issue.path?.replace(/\\/g, '/').split('/').pop() || issue.filename?.replace(/\\/g, '/').split('/').pop();
            const relevantFile = fileContents.find(f => f.fileName === fileName);
            const lines = relevantFile ? relevantFile.content.split('\n') : [];
            const startLine = Math.max(0, (issue.line || issue.line_number) - 5);
            const endLine = Math.min(lines.length, (issue.line || issue.line_number) + 5);
            const codeContext = lines.slice(startLine, endLine).join('\n');
            const errorMessage = issue.message || issue.issue_text;
            fetch(`${API_URL}/get-suggestion`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ errorMessage, codeContext }),
            })
            .then(res => res.ok ? res.json() : Promise.reject('Failed to fetch suggestion.'))
            .then(data => {
                if (data.error) throw new Error(data.error);
                setSuggestionContent(data.suggestion);
            })
            .catch(err => setSuggestionContent(`<strong>Error:</strong><br/>${err.message || err}`))
            .finally(() => setIsSuggestionLoading(false));
        };

        const handleViewCode = (fileName) => {
            const file = fileContents.find(f => f.fileName === fileName);
            if (file) {
                setCodeModalContent(file);
                setIsCodeModalOpen(true);
            }
        };

        return (
            <>
                <SuggestionModal isOpen={isSuggestionModalOpen} isLoading={isSuggestionLoading} content={suggestionContent} onClose={() => setIsSuggestionModalOpen(false)} />
                <CodeViewerModal isOpen={isCodeModalOpen} file={codeModalContent} onClose={() => setIsCodeModalOpen(false)} />
                <div className="bg-white p-8 rounded-xl shadow-lg text-center">
                    <h2 className="text-2xl font-bold text-gray-800 mb-2">Upload & Analyze</h2>
                    <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 hover:border-indigo-500 transition-colors">
                        <input type="file" multiple accept=".py" onChange={e => setFiles(Array.from(e.target.files))} className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100" />
                    </div>
                    <button onClick={handleAnalyzeClick} disabled={isLoading} className="mt-6 w-full bg-indigo-600 text-white p-3 rounded hover:bg-indigo-700 disabled:bg-indigo-300">
                        {isLoading ? 'Analyzing...' : 'Analyze Code'}
                    </button>
                    {dashboardError && <p className="mt-4 text-red-500 text-sm">{dashboardError}</p>}
                </div>

                {analysisResults && (
                    <div className="mt-8 space-y-8">
                         <div className="text-center mb-4">
                            <button onClick={handleSaveReport} className="bg-green-600 text-white px-6 py-2 rounded-full hover:bg-green-700">
                                Save This Report
                            </button>
                        </div>
                        <RadonReport radonData={analysisResults.radon} />
                        <PylintReport pylintData={analysisResults.pylint} onGetSuggestion={handleGetSuggestion} onViewCode={handleViewCode} />
                        <BanditReport banditData={analysisResults.bandit} onGetSuggestion={handleGetSuggestion} onViewCode={handleViewCode} />
                    </div>
                )}
            </>
        );
    };

    const HistoryPage = () => {
        const [reports, setReports] = useState([]);
        const [isLoading, setIsLoading] = useState(true);

        useEffect(() => {
            fetch(`${API_URL}/get-reports`, { credentials: 'include' })
                .then(res => res.json())
                .then(data => {
                    setReports(data);
                    setIsLoading(false);
                });
        }, []); // API_URL removed from dependency array

        if (isLoading) return <p>Loading history...</p>;

        return (
            <div className="bg-white p-8 rounded-xl shadow-lg">
                <h2 className="text-2xl font-bold mb-6">Analysis History</h2>
                <div className="space-y-4">
                    {reports.length > 0 ? reports.map(report => (
                        <div key={report.id} className="border p-4 rounded-lg">
                            <p className="font-semibold">Report from: {report.timestamp}</p>
                        </div>
                    )) : <p>No saved reports found.</p>}
                </div>
            </div>
        );
    };

    const NavBar = () => (
        <nav className="bg-white shadow-md p-4 mb-8 flex justify-between items-center">
            <h1 className="text-xl font-bold text-indigo-600">Flask Code Auditor</h1>
            {currentUser && (
                <div className="flex items-center space-x-4">
                    <span className="text-gray-700">Welcome, {currentUser}</span>
                    <button onClick={() => setPage('dashboard')} className="hover:underline">Dashboard</button>
                    <button onClick={() => setPage('history')} className="hover:underline">History</button>
                    <button onClick={handleLogout} className="bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600">Logout</button>
                </div>
            )}
        </nav>
    );

    // --- Main Render Logic ---
    return (
        <div className="bg-gray-50 min-h-screen font-sans">
            <NavBar />
            <div className="container mx-auto p-4">
                {page === 'login' && <LoginPage />}
                {page === 'register' && <RegisterPage />}
                {currentUser && page === 'dashboard' && <DashboardPage />}
                {currentUser && page === 'history' && <HistoryPage />}
            </div>
        </div>
    );
};

// --- All Report and Modal Components ---

const SuggestionModal = ({ isOpen, isLoading, content, onClose }) => {
    if (!isOpen) return null;
    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
            <div className="bg-white rounded-lg shadow-2xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
                <div className="flex justify-between items-center mb-4"><h3 className="text-xl font-bold text-gray-800">AI Suggestion</h3><button onClick={onClose} className="text-gray-500 hover:text-gray-800 text-2xl font-bold">&times;</button></div>
                {isLoading ? <div className="text-center p-8"><p>🤖 Getting suggestion from AI...</p></div> : <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: content.replace(/\n/g, '<br />').replace(/```python/g, '<pre class="bg-gray-800 text-white p-4 rounded-lg"><code>').replace(/```/g, '</code></pre>') }} />}
            </div>
        </div>
    );
};

const CodeViewerModal = ({ isOpen, file, onClose }) => {
    if (!isOpen) return null;
    const highlightSyntax = (code) => {
        const keywords = ['def', 'return', 'if', 'elif', 'else', 'for', 'in', 'while', 'import', 'from', 'as', 'try', 'except', 'finally', 'with', 'class', 'pass', 'continue', 'break'];
        let highlightedCode = code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        highlightedCode = highlightedCode.replace(/(#.*$)/gm, '<span class="text-gray-500">$&</span>');
        highlightedCode = highlightedCode.replace(/(".*?"|'.*?')/g, '<span class="text-green-400">$&</span>');
        keywords.forEach(keyword => {
            highlightedCode = highlightedCode.replace(new RegExp(`\\b${keyword}\\b`, 'g'), `<span class="text-indigo-400 font-bold">${keyword}</span>`);
        });
        return highlightedCode;
    };
    return (
         <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
            <div className="bg-gray-800 text-white rounded-lg shadow-2xl p-6 w-full max-w-4xl max-h-[90vh] flex flex-col">
                <div className="flex justify-between items-center mb-4 flex-shrink-0"><h3 className="text-xl font-bold">Viewing: {file.fileName}</h3><button onClick={onClose} className="text-gray-400 hover:text-white text-2xl font-bold">&times;</button></div>
                <pre className="flex-grow overflow-auto bg-gray-900 p-4 rounded-md"><code dangerouslySetInnerHTML={{ __html: highlightSyntax(file.content) }} /></pre>
            </div>
        </div>
    );
};

const PylintReport = ({ pylintData, onGetSuggestion, onViewCode }) => {
    if (!pylintData || pylintData.length === 0) return <div className="bg-white p-6 rounded-xl shadow-md"><h3 className="text-xl font-semibold text-green-600">✅ Pylint: No Issues Found</h3></div>;
    return (
        <div className="bg-white p-6 rounded-xl shadow-lg">
            <h2 className="text-2xl font-bold text-gray-800 mb-4">Pylint Code Quality Report</h2>
            {Object.entries(pylintData.reduce((acc, msg) => {
                const fileName = msg.path?.replace(/\\/g, '/').split('/').pop() || 'general';
                if (!acc[fileName]) acc[fileName] = [];
                acc[fileName].push(msg);
                return acc;
            }, {})).map(([fileName, messages]) => (
                <div key={fileName} className="mb-4">
                    <div className="flex justify-between items-center mb-2 border-b pb-1"><h3 className="text-lg font-semibold text-gray-700">File: {fileName}</h3><button onClick={() => onViewCode(fileName)} className="text-xs bg-gray-200 hover:bg-gray-300 font-semibold px-3 py-1 rounded-full">View Code</button></div>
                    <ul className="space-y-2">
                        {messages.map((msg, index) => (
                            <li key={index} className="flex items-start text-sm justify-between">
                                <div className="flex-grow mr-4"><p className="font-medium text-gray-700">{msg.message} <span className="text-gray-400">({msg.symbol})</span></p><p className="text-xs text-gray-500">Line: {msg.line}</p></div>
                                <button onClick={() => onGetSuggestion(msg)} className="text-xs bg-indigo-100 text-indigo-700 hover:bg-indigo-200 font-semibold px-3 py-1 rounded-full whitespace-nowrap">✨ Get Suggestion</button>
                            </li>
                        ))}
                    </ul>
                </div>
            ))}
        </div>
    );
};
    
const BanditReport = ({ banditData, onGetSuggestion, onViewCode }) => {
    if (!banditData || banditData.length === 0) return <div className="bg-white p-6 rounded-xl shadow-md"><h3 className="text-xl font-semibold text-green-600">✅ Bandit: No Security Issues Found</h3></div>;
    return (
        <div className="bg-gray-800 text-white p-6 rounded-xl shadow-lg">
            <h2 className="text-2xl font-bold mb-4">Bandit Security Report</h2>
            <ul className="space-y-3">
                {banditData.map((issue, index) => (
                    <li key={index} className="bg-gray-700 p-3 rounded-md">
                        <p className="font-semibold">{issue.issue_text}</p>
                        <div className="flex items-center justify-between mt-2">
                            <span className="text-xs text-gray-300">{issue.filename.replace(/\\/g, '/').split('/').pop()} (Line: {issue.line_number})</span>
                            <div><button onClick={() => onViewCode(issue.filename.replace(/\\/g, '/').split('/').pop())} className="text-xs bg-gray-500 hover:bg-gray-400 font-semibold px-3 py-1 rounded-full whitespace-nowrap mr-2">View Code</button><button onClick={() => onGetSuggestion(issue)} className="text-xs bg-gray-600 hover:bg-gray-500 font-semibold px-3 py-1 rounded-full whitespace-nowrap">✨ Get Suggestion</button></div>
                        </div>
                    </li>
                ))}
            </ul>
        </div>
    );
};

const RadonReport = ({ radonData }) => {
    if (!radonData || radonData.length === 0) return <div className="bg-white p-6 rounded-xl shadow-md"><h3 className="text-xl font-semibold text-green-600">✅ Radon: No Functions Found</h3></div>;
    const sortedFunctions = [...radonData].sort((a, b) => b.complexity - a.complexity);
    const getRankStyling = (rank) => ({'A': 'bg-green-500 text-white', 'B': 'bg-blue-500 text-white', 'C': 'bg-yellow-500 text-black', 'D': 'bg-orange-500 text-white', 'E': 'bg-red-500 text-white', 'F': 'bg-red-700 text-white'}[rank] || 'bg-gray-400');
    return (
         <div className="bg-white p-6 rounded-xl shadow-lg">
            <h2 className="text-2xl font-bold text-gray-800 mb-4">Radon Complexity Report</h2>
            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50"><tr><th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Function</th><th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">File</th><th scope="col" className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Complexity</th><th scope="col" className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Rank</th></tr></thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {sortedFunctions.map((func, index) => (
                            <tr key={index}><td className="px-6 py-4 whitespace-nowrap"><code className="text-sm text-gray-900">{func.name}</code></td><td className="px-6 py-4 whitespace-nowrap"><span className="text-sm text-gray-500">{func.file_path}</span></td><td className="px-6 py-4 text-center"><span className="text-lg font-semibold text-gray-900">{func.complexity}</span></td><td className="px-6 py-4 text-center"><span className={`px-3 py-1 text-xs font-bold rounded-full ${getRankStyling(func.rank)}`}>{func.rank}</span></td></tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default App;