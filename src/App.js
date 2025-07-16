import React, { useState, useEffect } from 'react';

// Main App Component
const App = () => {
    // --- State Management ---
    const [page, setPage] = useState('login');
    const [currentUser, setCurrentUser] = useState(null);
    const [error, setError] = useState('');

    // --- API URL Logic ---
    const API_URL = process.env.NODE_ENV === 'production' 
        ? 'https://code-checker-app.onrender.com' 
        : 'http://localhost:5000';

    // Check login status and handle redirect from GitHub
    useEffect(() => {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('error')) {
            setError("GitHub login failed. Please try again.");
            window.history.replaceState({}, document.title, "/");
        }
        
        fetch(`${API_URL}/status`, { credentials: 'include' })
            .then(res => res.ok ? res.json() : Promise.reject('Failed to connect'))
            .then(data => {
                if (data.logged_in) {
                    setCurrentUser(data.username);
                    setPage('dashboard');
                    window.history.replaceState({}, document.title, "/");
                }
            })
            .catch(() => {});
    }, []);

    const handleLogout = () => {
        fetch(`${API_URL}/logout`, { method: 'POST', credentials: 'include' })
            .then(() => {
                setCurrentUser(null);
                setPage('login');
            });
    };

    // --- Page Components ---

    const LoginPage = () => {
        const handleGitHubLogin = () => {
            window.location.href = `${API_URL}/login/github`;
        };

        return (
            <div className="max-w-md mx-auto mt-20">
                <div className="bg-white p-8 rounded-xl shadow-lg text-center">
                    <h1 className="text-3xl font-extrabold text-gray-800">Flask Code Auditor</h1>
                    <p className="text-gray-500 mt-2 mb-8">Analyze your code quality, security, and complexity.</p>
                    {error && <p className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</p>}
                    
                    <button onClick={handleGitHubLogin} className="w-full bg-gray-800 text-white p-3 rounded-lg hover:bg-gray-900 flex items-center justify-center text-lg font-semibold">
                        <svg className="w-6 h-6 mr-3" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path fillRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.168 6.839 9.492.5.092.682-.217.682-.482 0-.237-.009-.868-.014-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.031-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.378.203 2.398.1 2.651.64.7 1.03 1.595 1.03 2.688 0 3.848-2.338 4.695-4.566 4.943.359.308.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.001 10.001 0 0022 12c0-5.523-4.477-10-10-10z" clipRule="evenodd" /></svg>
                        Login with GitHub
                    </button>
                </div>
            </div>
        );
    };
    
    const DashboardPage = () => {
        const [repos, setRepos] = useState([]);
        const [selectedRepo, setSelectedRepo] = useState('');
        const [analysisResults, setAnalysisResults] = useState(null);
        const [isLoading, setIsLoading] = useState(false);
        const [isReposLoading, setIsReposLoading] = useState(true);

        useEffect(() => {
            fetch(`${API_URL}/get-repos`, { credentials: 'include' })
                .then(res => res.json())
                .then(data => {
                    if (data && !data.error) setRepos(data);
                })
                .finally(() => setIsReposLoading(false));
        }, []);

        const handleAnalyzeClick = () => {
            if (!selectedRepo) return;
            setIsLoading(true);
            setAnalysisResults(null);
            fetch(`${API_URL}/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ repoName: selectedRepo }),
                credentials: 'include'
            })
            .then(res => res.json())
            .then(data => setAnalysisResults(data))
            .finally(() => setIsLoading(false));
        };

        return (
            <>
                <div className="bg-white p-8 rounded-xl shadow-lg text-center">
                    <h2 className="text-2xl font-bold text-gray-800 mb-2">Analyze a Repository</h2>
                    <p className="text-gray-500 mb-6">Select one of your GitHub repositories to analyze.</p>
                    
                    {isReposLoading ? <p>Loading repositories...</p> : (
                        <div className="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4">
                            <select value={selectedRepo} onChange={e => setSelectedRepo(e.target.value)} className="w-full p-3 border rounded-lg bg-gray-50">
                                <option value="">-- Select a Repository --</option>
                                {repos.map(repo => <option key={repo.name} value={repo.name}>{repo.name}</option>)}
                            </select>
                            <button onClick={handleAnalyzeClick} disabled={isLoading || !selectedRepo} className="bg-indigo-600 text-white p-3 rounded-lg hover:bg-indigo-700 disabled:bg-indigo-300 whitespace-nowrap font-semibold">
                                {isLoading ? 'Analyzing...' : 'Analyze Repo'}
                            </button>
                        </div>
                    )}
                </div>

                {isLoading && <div className="text-center p-8"><div className="w-16 h-16 border-4 border-dashed rounded-full animate-spin border-indigo-600 mx-auto"></div><p className="text-gray-600 mt-4">Cloning repository and running analysis...</p></div>}

                {analysisResults && (
                    <div className="mt-8 space-y-8">
                        <RadonReport radonData={analysisResults.radon} />
                        <PylintReport pylintData={analysisResults.pylint} />
                        <BanditReport banditData={analysisResults.bandit} />
                    </div>
                )}
            </>
        );
    };

    const NavBar = () => (
        <nav className="bg-white shadow-md p-4 mb-8 flex justify-between items-center">
            <h1 className="text-xl font-bold text-indigo-600">Flask Code Auditor</h1>
            {currentUser && (
                <div className="flex items-center space-x-4">
                    <span className="text-gray-700">Welcome, {currentUser}</span>
                    <button onClick={() => setPage('dashboard')} className="hover:underline">Dashboard</button>
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
                {currentUser && page === 'dashboard' && <DashboardPage />}
            </div>
        </div>
    );
};

// --- All Report and Modal Components ---

const PylintReport = ({ pylintData }) => {
    if (!pylintData || pylintData.length === 0) return null;
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
                    <h3 className="text-lg font-semibold text-gray-700 mb-2 border-b pb-1">File: {fileName}</h3>
                    <ul className="space-y-2">
                        {messages.map((msg, index) => (
                            <li key={index} className="flex items-start text-sm">
                                <div className="flex-grow mr-4"><p className="font-medium text-gray-700">{msg.message} <span className="text-gray-400">({msg.symbol})</span></p><p className="text-xs text-gray-500">Line: {msg.line}</p></div>
                            </li>
                        ))}
                    </ul>
                </div>
            ))}
        </div>
    );
};
    
const BanditReport = ({ banditData }) => {
    if (!banditData || banditData.length === 0) return null;
    return (
        <div className="bg-gray-800 text-white p-6 rounded-xl shadow-lg">
            <h2 className="text-2xl font-bold mb-4">Bandit Security Report</h2>
            <ul className="space-y-3">
                {banditData.map((issue, index) => (
                    <li key={index} className="bg-gray-700 p-3 rounded-md">
                        <p className="font-semibold">{issue.issue_text}</p>
                        <div className="flex items-center justify-between mt-2">
                            <span className="text-xs text-gray-300">{issue.filename.replace(/\\/g, '/').split('/').pop()} (Line: {issue.line_number})</span>
                        </div>
                    </li>
                ))}
            </ul>
        </div>
    );
};

const RadonReport = ({ radonData }) => {
    if (!radonData || radonData.length === 0) return null;
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