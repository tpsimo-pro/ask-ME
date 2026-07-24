import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AuthGuard } from "./components/AuthGuard";
import { NavBar } from "./components/NavBar";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import { AnalyzePage } from "./pages/AnalyzePage";
import { AuthCallbackPage } from "./pages/AuthCallbackPage";
import { HistoryPage } from "./pages/HistoryPage";
import { LoginPage } from "./pages/LoginPage";

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/auth/callback" element={<AuthCallbackPage />} />
            <Route
              path="/"
              element={
                <AuthGuard>
                  <NavBar />
                  <AnalyzePage />
                </AuthGuard>
              }
            />
            <Route
              path="/historico"
              element={
                <AuthGuard>
                  <NavBar />
                  <HistoryPage />
                </AuthGuard>
              }
            />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
