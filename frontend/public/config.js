/**
 * Runtime configuration loader for Call Analytics Frontend
 * 
 * This script runs before the React app loads and injects configuration
 * into window.__CONFIG__ so the app can access it.
 * 
 * This allows the frontend to work on any backend URL without rebuilding.
 */

(function initializeConfig() {
  // Determine API URL from environment or fallback to relative path
  const apiUrl = process.env.VITE_API_URL || '/api';
  
  // Set global config object
  window.__CONFIG__ = {
    API_URL: apiUrl,
    ADMIN_USERNAME: 'admin',
    // Add more config as needed
  };

  // Log configuration (safe - doesn't expose secrets)
  console.info('[Call Analytics] Configuration loaded:', {
    API_URL: window.__CONFIG__.API_URL,
  });
})();
