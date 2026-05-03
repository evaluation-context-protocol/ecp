import React, { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchEvaluationDetails } from '../services/api.js';
import RunButton from '../components/RunButton';

function EvaluationDetail() {
  const { id } = useParams();
  const [evaluation, setEvaluation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    const loadEvaluation = async () => {
      try {
        const data = await fetchEvaluationDetails(id);
        setEvaluation(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadEvaluation();
  }, [id]);

  if (loading) return <div>Loading evaluation details...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!evaluation) return <div>Evaluation not found</div>;

  return (
    <div className="evaluation-detail">
      <Link to="/">← Back to evaluations</Link>
      <h2>{evaluation.name}</h2>
      <p>{evaluation.description}</p>
      <p>Status: {evaluation.status}</p>
      <div className="evaluation-metadata">
        <small>Created: {evaluation.created_at}</small>
        <small>Updated: {evaluation.updated_at}</small>
      </div>

      <RunButton evaluationId={evaluation.id} onResult={setResult} />

      {result && (
        <div className="evaluation-results">
          <h3>Results</h3>
          <p>Success: {result.success ? 'Yes' : 'No'}</p>
          <p>Output: {result.output}</p>
          {result.error && <p>Error: {result.error}</p>}
          {result.metrics && (
            <div>
              <h4>Metrics</h4>
              <pre>{JSON.stringify(result.metrics, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default EvaluationDetail;