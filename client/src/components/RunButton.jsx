import React, { useState, useEffect } from 'react';
import { runEvaluation, fetchJobStatus } from '../services/api.js';

function RunButton({ evaluationId, onResult }) {
  const [running, setRunning] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!jobId) return;

    const interval = setInterval(async () => {
      try {
        const jobData = await fetchJobStatus(jobId);
        setStatus(jobData.status);
        if (jobData.status === 'completed' || jobData.status === 'failed') {
          clearInterval(interval);
          setRunning(false);
          if (onResult) {
            onResult(jobData.results);
          }
        }
      } catch (err) {
        setError(err.message);
        clearInterval(interval);
        setRunning(false);
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [jobId, onResult]);

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    setStatus('starting');

    try {
      const data = await runEvaluation(evaluationId);
      setJobId(data.job_id);
      setStatus(data.status);
    } catch (err) {
      setError(err.message);
      setRunning(false);
    }
  };

  return (
    <div className="run-button">
      <button onClick={handleRun} disabled={running}>
        {running ? 'Running...' : 'Run Evaluation'}
      </button>
      {status && <p>Status: {status}</p>}
      {error && <p className="error">Error: {error}</p>}
    </div>
  );
}

export default RunButton;