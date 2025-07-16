import React, { useState, useCallback } from 'react';

// Main App Component
const App = () => {
    // State management
    const [files, setFiles] = useState([]);
    const [fileContents, setFileContents] = useState([]); // Store file content for context
    const [analysisResults, setAnalysisResults] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    // State for the AI suggestion modal
    const [isSuggestionModalOpen, setIsSuggestionModalOpen] = useState(false);
    const [suggestionContent, setSuggestionContent] = useState('');
    const [isSuggestionLoading, setIsSuggestionLoading] = useState(false);

    // --- Core Analysis Logic ---

    const analyzeCode = useCallback((filesWithContent) => {
        setIsLoading(true);
        setError(null);
        setAnalysisResults(null);
        setFileContents(filesWithContent); // Save file contents for context

        const apiUrl = 'https://code-checker-app.onrender.com/analyze';

        fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(filesWithContent),
        })
        .then(res => res.ok ? res.json() : Promise.reject('Network response was not ok'))
        .then(data => setAnalysisResults(data))
        .catch(e => setError("Failed to analyze the code. Check if the backend server is running."))
        .finally(() => setIsLoading(false));
    }, []);

    // Function to get AI suggestion
    const handleGetSuggestion = useCallback((issue) => {
        setIsSuggestionModalOpen(true);
        setIsSuggestionLoading(true);
        setSuggestionContent('');

        const relevantFile = fileContents.find(f => f.fileName === issue.path?.replace(/\\/g, '/').split('/').pop() || f.fileName === issue.filename?.replace(/\\/g, '/').split('/').pop());
        const lines = relevantFile ? relevantFile.content.split('\n') : [];
        const startLine = Math.max(0, (issue.line || issue.line_number) - 5);
        const endLine = Math.min(lines.length, (issue.line || issue.line_number) + 5);
        const codeContext = lines.slice(startLine, endLine).join('\n');
        
        const errorMessage = issue.message || issue.issue_text;

        const apiUrl = 'https://code-checker-app.onrender.com/get-suggestion';

        fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ errorMessage, codeContext }),
        })
        .then(res => res.ok ? res.json() : Promise.reject('Failed to fetch suggestion.'))
        .then(data => {
            if (data.error) throw new Error(data.error);
            setSuggestionContent(data.suggestion);
        })
        .catch(err => {
            // THIS IS THE FIX: Handle both Error objects and simple strings
            const errorMessage = err.message || err;
            setSuggestionContent(`<strong>Error:</strong><br/>${errorMessage}`);
        })
        .finally(() => setIsSuggestionLoading(false));

    }, [fileContents]);


    // --- Event Handlers ---

    const handleFileChange = (event) => {
        setFiles(Array.from(event.target.files));
        setAnalysisResults(null);
        setError(null);
    };

    const handleAnalyzeClick = () => {
        if (files.length === 0) {
            setError("Please upload at least one Python file.");
            return;
        }
        const filePromises = files.map(file => {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = (e) => resolve({ fileName: file.name, content: e.target.result });
                reader.onerror = (e) => reject(e);
                reader.readAsText(file);
            });
        });
        Promise.all(filePromises).then(analyzeCode);
    };
    
    // --- UI Components ---
    
    const FileUploadArea = () => (
        <div className="bg-white p-8 rounded-xl shadow-lg text-center">
            <h2 className="text-2xl font-bold text-gray-800 mb-2">Upload Your Flask Project</h2>
            <p className="text-gray-500 mb-6">Select one or more .py files to analyze.</p>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 hover:border-indigo-500 transition-colors">
                <input type="file" multiple accept=".py" onChange={handleFileChange} className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100" />
                {files.length > 0 && <p className="mt-4 text-sm text-gray-600">{files.length} file(s) selected.</p>}
            </div>
            <button onClick={handleAnalyzeClick} disabled={isLoading || files.length === 0} className="mt-6 w-full bg-indigo-600 text-white font-bold py-3 px-6 rounded-lg hover:bg-indigo-700 disabled:bg-indigo-300 disabled:cursor-not-allowed transition-all duration-300 transform hover:scale-105 flex items-center justify-center">
                {isLoading ? 'Analyzing...' : "Analyze Code"}
            </button>
            {error && <p className="mt-4 text-red-500 text-sm">{error}</p>}
        </div>
    );
    
    const PylintReport = ({ pylintData, onGetSuggestion }) => {
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
                        <h3 className="text-lg font-semibold text-gray-700 mb-2 border-b pb-1">File: {fileName}</h3>
                        <ul className="space-y-2">
                            {messages.map((msg, index) => (
                                <li key={index} className="flex items-start text-sm justify-between">
                                    <div className="flex-grow mr-4">
                                        <p className="font-medium text-gray-700">{msg.message} <span className="text-gray-400">({msg.symbol})</span></p>
                                        <p className="text-xs text-gray-500">Line: {msg.line}</p>
                                    </div>
                                    <button onClick={() => onGetSuggestion(msg)} className="text-xs bg-indigo-100 text-indigo-700 hover:bg-indigo-200 font-semibold px-3 py-1 rounded-full whitespace-nowrap">
                                        ✨ Get Suggestion
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </div>
                ))}
            </div>
        );
    };
    
    const BanditReport = ({ banditData, onGetSuggestion }) => {
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
                                <button onClick={() => onGetSuggestion(issue)} className="text-xs bg-gray-600 hover:bg-gray-500 font-semibold px-3 py-1 rounded-full whitespace-nowrap">
                                    ✨ Get Suggestion
                                </button>
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
        const getRankStyling = (rank) => ({
            'A': 'bg-green-500 text-white', 'B': 'bg-blue-500 text-white', 'C': 'bg-yellow-500 text-black',
            'D': 'bg-orange-500 text-white', 'E': 'bg-red-500 text-white', 'F': 'bg-red-700 text-white'
        }[rank] || 'bg-gray-400');
        return (
             <div className="bg-white p-6 rounded-xl shadow-lg">
                <h2 className="text-2xl font-bold text-gray-800 mb-4">Radon Complexity Report</h2>
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Function</th>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">File</th>
                                <th scope="col" className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Complexity</th>
                                <th scope="col" className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Rank</th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {sortedFunctions.map((func, index) => (
                                <tr key={index}>
                                    <td className="px-6 py-4 whitespace-nowrap"><code className="text-sm text-gray-900">{func.name}</code></td>
                                    <td className="px-6 py-4 whitespace-nowrap"><span className="text-sm text-gray-500">{func.file_path}</span></td>
                                    <td className="px-6 py-4 text-center"><span className="text-lg font-semibold text-gray-900">{func.complexity}</span></td>
                                    <td className="px-6 py-4 text-center"><span className={`px-3 py-1 text-xs font-bold rounded-full ${getRankStyling(func.rank)}`}>{func.rank}</span></td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    };

    const SuggestionModal = ({ isOpen, isLoading, content, onClose }) => {
        if (!isOpen) return null;
        return (
            <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
                <div className="bg-white rounded-lg shadow-2xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-xl font-bold text-gray-800">AI Suggestion</h3>
                        <button onClick={onClose} className="text-gray-500 hover:text-gray-800 text-2xl font-bold">&times;</button>
                    </div>
                    {isLoading ? (
                        <div className="text-center p-8">
                            <div className="w-10 h-10 border-4 border-dashed rounded-full animate-spin border-indigo-600 mx-auto"></div>
                            <p className="text-gray-600 mt-4">🤖 Getting suggestion from AI...</p>
                        </div>
                    ) : (
                        <div className="prose max-w-none" dangerouslySetInnerHTML={{ __html: content.replace(/\n/g, '<br />').replace(/```python/g, '<pre class="bg-gray-800 text-white p-4 rounded-lg"><code>').replace(/```/g, '</code></pre>') }} />
                    )}
                </div>
            </div>
        );
    };

    const ResultsDashboard = () => (
        <div className="mt-12 space-y-8">
            <RadonReport radonData={analysisResults?.radon} />
            <PylintReport pylintData={analysisResults?.pylint} onGetSuggestion={handleGetSuggestion} />
            <BanditReport banditData={analysisResults?.bandit} onGetSuggestion={handleGetSuggestion} />
        </div>
    );

    return (
        <div className="bg-gray-50 min-h-screen font-sans">
            <SuggestionModal isOpen={isSuggestionModalOpen} isLoading={isSuggestionLoading} content={suggestionContent} onClose={() => setIsSuggestionModalOpen(false)} />
            <div className="container mx-auto p-4 sm:p-6 lg:p-8">
                <header className="text-center mb-12">
                    <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-800">Flask Code <span className="text-indigo-600">Auditor</span></h1>
                    <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">Powered by Pylint, Bandit, Radon, and AI.</p>
                </header>
                <main>
                    <FileUploadArea />
                    {isLoading && <div className="text-center p-8"><div className="w-16 h-16 border-4 border-dashed rounded-full animate-spin border-indigo-600 mx-auto"></div><p className="text-gray-600 mt-4">Performing deep code analysis...</p></div>}
                    {!isLoading && analysisResults && <ResultsDashboard />}
                </main>
                <footer className="text-center mt-16 text-sm text-gray-500"><p>Built with React, Flask & Tailwind CSS.</p></footer>
            </div>
        </div>
    );
};

export default App;