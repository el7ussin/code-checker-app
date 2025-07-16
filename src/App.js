import React, { useState, useCallback, useMemo } from 'react';

// Main App Component
const App = () => {
    // State management
    const [files, setFiles] = useState([]);
    const [analysisResults, setAnalysisResults] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    // --- Core Analysis Logic ---

    const analyzeCode = useCallback((fileContents) => {
        setIsLoading(true);
        setError(null);
        setAnalysisResults(null);

        fetch('http://localhost:5000/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(fileContents),
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log("Analysis Results:", data);
            setAnalysisResults(data);
        })
        .catch(e => {
            console.error("Analysis Error:", e);
            setError("Failed to analyze the code. Check if the backend server is running.");
        })
        .finally(() => {
            setIsLoading(false);
        });
    }, []);


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

        Promise.all(filePromises)
            .then(fileContents => {
                analyzeCode(fileContents);
            })
            .catch(err => {
                console.error("File Reading Error:", err);
                setError("Could not read the uploaded files.");
            });
    };

    // --- UI Components ---

    const FileUploadArea = () => (
        <div className="bg-white p-8 rounded-xl shadow-lg text-center">
            <h2 className="text-2xl font-bold text-gray-800 mb-2">Upload Your Flask Project</h2>
            <p className="text-gray-500 mb-6">Select one or more .py files to analyze.</p>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 hover:border-indigo-500 transition-colors">
                <input
                    type="file"
                    multiple
                    accept=".py"
                    onChange={handleFileChange}
                    className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                />
                {files.length > 0 && <p className="mt-4 text-sm text-gray-600">{files.length} file(s) selected.</p>}
            </div>
            <button
                onClick={handleAnalyzeClick}
                disabled={isLoading || files.length === 0}
                className="mt-6 w-full bg-indigo-600 text-white font-bold py-3 px-6 rounded-lg hover:bg-indigo-700 disabled:bg-indigo-300 disabled:cursor-not-allowed transition-all duration-300 transform hover:scale-105 flex items-center justify-center"
            >
                {isLoading ? (
                    <>
                        <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Analyzing...
                    </>
                ) : "Analyze Code"}
            </button>
            {error && <p className="mt-4 text-red-500 text-sm">{error}</p>}
        </div>
    );

    const PylintReport = ({ pylintData }) => {
        // NEW: State to manage which issue types are visible
        const [filters, setFilters] = useState({
            error: true,
            warning: true,
            convention: true,
            refactor: true,
        });

        const handleFilterChange = (event) => {
            const { name, checked } = event.target;
            setFilters(prevFilters => ({
                ...prevFilters,
                [name]: checked,
            }));
        };

        const processedData = useMemo(() => {
            if (!pylintData || !Array.isArray(pylintData)) return null;

            // NEW: Filter messages based on the filter state
            const filteredMessages = pylintData.filter(msg => filters[msg.type]);

            const summary = { error: 0, warning: 0, convention: 0, refactor: 0, fatal: 0 };
            const messagesByFile = {};

            // Use the original data for summary stats, but filtered data for display
            pylintData.forEach(msg => {
                summary[msg.type] = (summary[msg.type] || 0) + 1;
            });

            filteredMessages.forEach(msg => {
                const fileName = msg.path?.replace('temp_uploads\\', '') || 'general';
                if (!messagesByFile[fileName]) messagesByFile[fileName] = [];
                messagesByFile[fileName].push(msg);
            });

            const score = Math.max(0, 10 - (summary.error * 1) - (summary.warning * 0.5) - (summary.convention * 0.1) - (summary.refactor * 0.1)).toFixed(2);

            return { summary, messagesByFile, score };
        }, [pylintData, filters]);

        if (!pylintData || pylintData.length === 0) return <div className="bg-white p-6 rounded-xl shadow-md"><h3 className="text-xl font-semibold text-green-600">✅ Pylint: No Issues Found</h3></div>;

        const { summary, messagesByFile, score } = processedData;

        const getIssueTypeStyling = (type) => ({
            error: { icon: '❌', color: 'bg-red-100 text-red-800' },
            warning: { icon: '⚠️', color: 'bg-yellow-100 text-yellow-800' },
            convention: { icon: '📝', color: 'bg-blue-100 text-blue-800' },
            refactor: { icon: '🔧', color: 'bg-purple-100 text-purple-800' },
            fatal: { icon: '💥', color: 'bg-gray-800 text-white' }
        }[type] || { icon: '➡️', color: 'bg-gray-100 text-gray-800' });

        return (
            <div className="bg-white p-6 rounded-xl shadow-lg">
                <h2 className="text-2xl font-bold text-gray-800 mb-4">Pylint Code Quality Report</h2>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
                    <div className="bg-indigo-600 text-white p-4 rounded-lg text-center"><p className="text-sm font-bold">SCORE</p><p className="text-4xl font-light">{score}<span className="text-lg">/10</span></p></div>
                    <div className={`${getIssueTypeStyling('error').color} p-4 rounded-lg text-center`}><p className="text-sm font-bold">ERRORS</p><p className="text-4xl font-light">{summary.error}</p></div>
                    <div className={`${getIssueTypeStyling('warning').color} p-4 rounded-lg text-center`}><p className="text-sm font-bold">WARNINGS</p><p className="text-4xl font-light">{summary.warning}</p></div>
                    <div className={`${getIssueTypeStyling('convention').color} p-4 rounded-lg text-center`}><p className="text-sm font-bold">CONVENTION</p><p className="text-4xl font-light">{summary.convention}</p></div>
                    <div className={`${getIssueTypeStyling('refactor').color} p-4 rounded-lg text-center`}><p className="text-sm font-bold">REFACTOR</p><p className="text-4xl font-light">{summary.refactor}</p></div>
                </div>

                {/* NEW: Filter Checkboxes */}
                <div className="bg-gray-100 p-4 rounded-lg mb-6 flex items-center justify-center space-x-4">
                    <span className="font-semibold text-gray-700">Show:</span>
                    {Object.keys(filters).map(filterName => (
                        <label key={filterName} className="flex items-center space-x-2 capitalize cursor-pointer">
                            <input
                                type="checkbox"
                                name={filterName}
                                checked={filters[filterName]}
                                onChange={handleFilterChange}
                                className="h-4 w-4 rounded text-indigo-600 focus:ring-indigo-500 border-gray-300"
                            />
                            <span>{filterName}</span>
                        </label>
                    ))}
                </div>

                 {Object.keys(messagesByFile).length > 0 ? Object.entries(messagesByFile).map(([fileName, messages]) => (
                    <div key={fileName} className="mb-4">
                        <h3 className="text-lg font-semibold text-gray-700 mb-2 border-b pb-1">File: {fileName}</h3>
                        <ul className="space-y-2">
                            {messages.map((msg, index) => (
                                <li key={index} className="flex items-start text-sm">
                                    <span className={`font-mono text-xs font-bold px-2 py-1 rounded-md mr-3 ${getIssueTypeStyling(msg.type).color}`}>{msg.line}:{msg.column}</span>
                                    <div className="flex-grow"><p className="font-medium text-gray-700">{msg.message} <span className="text-gray-400">({msg.symbol})</span></p></div>
                                </li>
                            ))}
                        </ul>
                    </div>
                 )) : <p className="text-center text-gray-500 py-4">No issues match the current filter.</p>}
            </div>
        )
    };

    const BanditReport = ({ banditData }) => {
        const processedData = useMemo(() => {
            if (!banditData || banditData.length === 0) return null;
            const summary = { HIGH: 0, MEDIUM: 0, LOW: 0 };
            banditData.forEach(issue => summary[issue.issue_severity]++);
            return { summary, issues: banditData };
        }, [banditData]);

        if (!processedData) return <div className="bg-white p-6 rounded-xl shadow-md"><h3 className="text-xl font-semibold text-green-600">✅ Bandit: No Security Issues Found</h3></div>;

        const { summary, issues } = processedData;

        const getSeverityStyling = (severity) => ({
            HIGH: 'bg-red-500 text-white',
            MEDIUM: 'bg-yellow-400 text-black',
            LOW: 'bg-blue-300 text-black',
        }[severity] || 'bg-gray-300');

        return (
            <div className="bg-gray-800 text-white p-6 rounded-xl shadow-lg">
                <h2 className="text-2xl font-bold mb-4">Bandit Security Report</h2>
                 <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                    <div className="bg-red-700 p-4 rounded-lg text-center"><p className="text-sm font-bold">HIGH</p><p className="text-4xl font-light">{summary.HIGH}</p></div>
                    <div className="bg-yellow-500 p-4 rounded-lg text-center"><p className="text-sm font-bold">MEDIUM</p><p className="text-4xl font-light">{summary.MEDIUM}</p></div>
                    <div className="bg-blue-500 p-4 rounded-lg text-center"><p className="text-sm font-bold">LOW</p><p className="text-4xl font-light">{summary.LOW}</p></div>
                </div>
                <ul className="space-y-3">
                    {issues.map((issue, index) => (
                        <li key={index} className="bg-gray-700 p-3 rounded-md">
                            <p className="font-semibold">{issue.issue_text}</p>
                            <div className="flex items-center justify-between text-xs mt-1 text-gray-300">
                                <span>{issue.filename.replace('temp_uploads\\', '')} (Line: {issue.line_number})</span>
                                <span className={`px-2 py-0.5 rounded-full font-bold text-xs ${getSeverityStyling(issue.issue_severity)}`}>{issue.issue_severity}</span>
                            </div>
                        </li>
                    ))}
                </ul>
            </div>
        )
    };

    const ResultsDashboard = () => (
        <div className="mt-12 space-y-8">
            <PylintReport pylintData={analysisResults?.pylint} />
            <BanditReport banditData={analysisResults?.bandit} />
        </div>
    );

    return (
        <div className="bg-gray-50 min-h-screen font-sans">
            <div className="container mx-auto p-4 sm:p-6 lg:p-8">
                <header className="text-center mb-12">
                    <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-800">
                        Flask Code <span className="text-indigo-600">Auditor</span>
                    </h1>
                    <p className="mt-4 text-lg text-gray-600 max-w-2xl mx-auto">
                        Powered by Pylint (Code Quality) and Bandit (Security).
                    </p>
                </header>

                <main>
                    <FileUploadArea />
                    {isLoading && (
                         <div className="text-center p-8">
                            <div className="w-16 h-16 border-4 border-dashed rounded-full animate-spin border-indigo-600 mx-auto"></div>
                            <p className="text-gray-600 mt-4">Performing deep code analysis...</p>
                        </div>
                    )}
                    {!isLoading && analysisResults && <ResultsDashboard />}
                </main>

                <footer className="text-center mt-16 text-sm text-gray-500">
                    <p>Built with React, Flask & Tailwind CSS.</p>
                </footer>
            </div>
        </div>
    );
};

export default App;