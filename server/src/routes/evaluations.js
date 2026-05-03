const express = require('express');
const ECPClient = require('../ecp-client');
const { authenticate } = require('../auth');

const router = express.Router();
const ecpClient = new ECPClient();

// GET /api/evaluations - List evaluations
router.get('/evaluations', authenticate, async (req, res) => {
  try {
    const data = await ecpClient.getEvaluations();
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: { code: 'FETCH_ERROR', message: error.message } });
  }
});

// GET /api/evaluations/:id - Get evaluation details
router.get('/evaluations/:id', authenticate, async (req, res) => {
  try {
    const data = await ecpClient.getEvaluation(req.params.id);
    res.json(data);
  } catch (error) {
    if (error.message.includes('not found')) {
      res.status(404).json({ error: { code: 'NOT_FOUND', message: 'Evaluation not found' } });
    } else {
      res.status(500).json({ error: { code: 'FETCH_ERROR', message: error.message } });
    }
  }
});

// POST /api/evaluations/:id/run - Run evaluation
router.post('/evaluations/:id/run', authenticate, async (req, res) => {
  try {
    const data = await ecpClient.runEvaluation(req.params.id);
    res.status(202).json(data);
  } catch (error) {
    res.status(500).json({ error: { code: 'RUN_ERROR', message: error.message } });
  }
});

// GET /api/jobs/:jobId - Get job status
router.get('/jobs/:jobId', authenticate, async (req, res) => {
  try {
    const data = await ecpClient.getJobStatus(req.params.jobId);
    res.json(data);
  } catch (error) {
    res.status(500).json({ error: { code: 'STATUS_ERROR', message: error.message } });
  }
});

module.exports = router;