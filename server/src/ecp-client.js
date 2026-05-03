// API client for communicating with ECP runtime
const axios = require('axios'); // Assume axios is installed, or use fetch

// TODO: Install axios or use built-in fetch
// For now, mock implementations

class ECPClient {
  constructor(baseUrl = 'http://localhost:3000') { // Assume ECP runtime URL
    this.baseUrl = baseUrl;
  }

  async getEvaluations() {
    try {
      // Mock data for now
      return {
        evaluations: [
          {
            id: 'eval-1',
            name: 'Sample Evaluation 1',
            description: 'A sample evaluation for testing',
            status: 'ready',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
          }
        ]
      };
    } catch (error) {
      throw new Error(`Failed to fetch evaluations: ${error.message}`);
    }
  }

  async getEvaluation(id) {
    try {
      // Mock data
      if (id === 'eval-1') {
        return {
          id: 'eval-1',
          name: 'Sample Evaluation 1',
          description: 'A sample evaluation for testing',
          status: 'ready',
          results: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        };
      }
      throw new Error('Evaluation not found');
    } catch (error) {
      throw new Error(`Failed to fetch evaluation ${id}: ${error.message}`);
    }
  }

  async runEvaluation(id) {
    try {
      // Mock running
      return {
        job_id: `job-${Date.now()}`,
        status: 'running',
        message: 'Evaluation started successfully'
      };
    } catch (error) {
      throw new Error(`Failed to run evaluation ${id}: ${error.message}`);
    }
  }

  async getJobStatus(jobId) {
    try {
      // Mock status
      return {
        job_id: jobId,
        status: 'completed',
        results: {
          success: true,
          output: 'Evaluation completed successfully',
          metrics: { duration_ms: 1500 }
        }
      };
    } catch (error) {
      throw new Error(`Failed to get job status ${jobId}: ${error.message}`);
    }
  }
}

module.exports = ECPClient;