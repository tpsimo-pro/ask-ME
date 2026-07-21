import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AuthGuard } from "./components/AuthGuard";
import { AuthProvider } from "./context/AuthContext";
import { AnalyzePage } from "./pages/AnalyzePage";
import { AuthCallbackPage } from "./pages/AuthCallbackPage";
import { HistoryPage } from "./pages/HistoryPage";
import { LoginPage } from "./pages/LoginPage";

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route
            path="/"
            element={
              <AuthGuard>
                <AnalyzePage />
              </AuthGuard>
            }
          />
          <Route
            path="/historico"
            element={
              <AuthGuard>
                <HistoryPage />
              </AuthGuard>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
