const express = require('express');
const cors = require('cors');
const path = require('path');
const evaluationRoutes = require('./routes/evaluations');

const app = express();
const PORT = process.env.PORT || 6277;

// Middleware
app.use(cors());
app.use(express.json());

// API routes
app.use('/api', evaluationRoutes);

// Serve static files from client build
app.use(express.static(path.join(__dirname, '../../client/dist')));

// Basic health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', message: 'ECP Inspector server is running' });
});

// Catch all handler: send back index.html for client-side routing
app.get(/./, (req, res) => {
  res.sendFile(path.join(__dirname, '../../client/dist/index.html'));
});

// Start server
app.listen(PORT, () => {
  console.log(`ECP Inspector server running on port ${PORT}`);
});

module.exports = app;