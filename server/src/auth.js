// Simple session token authentication middleware
const authenticate = (req, res, next) => {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: { code: 'AUTH_MISSING', message: 'Authorization header missing or invalid' } });
  }

  const token = authHeader.substring(7); // Remove 'Bearer '

  // For now, accept any token (in production, validate against stored tokens)
  // TODO: Implement proper token validation
  if (!token || token.length < 10) {
    return res.status(401).json({ error: { code: 'AUTH_INVALID', message: 'Invalid session token' } });
  }

  // Token is valid, proceed
  req.sessionToken = token;
  next();
};

module.exports = { authenticate };