import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { fetchEvaluations } from '../services/api.js';

function EvaluationList() {
  const [evaluations, setEvaluations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchEvaluationsList();
  }, []);

  const fetchEvaluationsList = async () => {
    try {
      const data = await fetchEvaluations();
      setEvaluations(data.evaluations || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div>Loading evaluations...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className="evaluation-list">
      <h2>Available Evaluations</h2>
      {evaluations.length === 0 ? (
        <p>No evaluations available</p>
      ) : (
        <ul>
          {evaluations.map((evaluation) => (
            <li key={evaluation.id}>
              <Link to={`/evaluations/${evaluation.id}`}>
                <h3>{evaluation.name}</h3>
              </Link>
              <p>{evaluation.description}</p>
              <span>Status: {evaluation.status}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default EvaluationList;