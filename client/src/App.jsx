import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import EvaluationDetail from './pages/EvaluationDetail';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/evaluations/:id" element={<EvaluationDetail />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;