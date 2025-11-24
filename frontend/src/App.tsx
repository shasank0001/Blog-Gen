import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '@/context/AuthContext';
import { ProtectedRoute } from '@/components/custom/ProtectedRoute';
import { Layout } from '@/components/custom/Layout';
import { Dashboard } from '@/pages/Dashboard';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { KnowledgeBase } from '@/pages/KnowledgeBase';

import { GenerationWizard } from '@/pages/GenerationWizard';
import { Profiles } from '@/pages/Profiles';
import { History } from '@/pages/History';

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="min-h-screen bg-background font-sans antialiased">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/" element={<Dashboard />} />
                <Route path="/generate" element={<GenerationWizard />} />
                <Route path="/knowledge" element={<KnowledgeBase />} />
                <Route path="/profiles" element={<Profiles />} />
                <Route path="/history" element={<History />} />
              </Route>
            </Route>
            
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
