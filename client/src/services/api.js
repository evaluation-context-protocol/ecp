import axios from 'axios';

const API_BASE = '/api';

export async function fetchEvaluations() {
  const response = await axios.get(`${API_BASE}/evaluations`, {
    headers: {
      Authorization: 'Bearer sample-token'
    }
  });
  return response.data;
}

export async function fetchEvaluationDetails(id) {
  const response = await axios.get(`${API_BASE}/evaluations/${id}`, {
    headers: {
      Authorization: 'Bearer sample-token'
    }
  });
  return response.data;
}

export async function runEvaluation(id) {
  const response = await axios.post(`${API_BASE}/evaluations/${id}/run`, {}, {
    headers: {
      Authorization: 'Bearer sample-token'
    }
  });
  return response.data;
}

export async function fetchJobStatus(jobId) {
  const response = await axios.get(`${API_BASE}/jobs/${jobId}`, {
    headers: {
      Authorization: 'Bearer sample-token'
    }
  });
  return response.data;
}
