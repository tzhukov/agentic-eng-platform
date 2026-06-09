import { useState } from 'react';
import './App.css';

function App() {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch('/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      setResponse(data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  return (
    <div className="App">
      <h1>AI Support Agent</h1>
      <form onSubmit={handleSubmit}>
        <input 
          value={query} 
          onChange={(e) => setQuery(e.target.value)} 
          placeholder="Ask me anything..." 
        />
        <button type="submit" disabled={loading}>Run</button>
      </form>
      {response && (
        <div className="result">
          <p><strong>Result:</strong> {response.result}</p>
          <p><strong>Stdout:</strong></p>
          <pre>{response.stdout}</pre>
          <p><strong>Generated Code:</strong></p>
          <pre>{response.code}</pre>
        </div>
      )}
    </div>
  );
}

export default App;
