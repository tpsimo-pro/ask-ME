import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AuthGuard } from "./components/AuthGuard";
import { AuthProvider } from "./context/AuthContext";
import { AuthCallbackPage } from "./pages/AuthCallbackPage";
import { LoginPage } from "./pages/LoginPage";

function HomePlaceholder() {
  return <p>Analyze page (Task 18)</p>;
}

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
                <HomePlaceholder />
              </AuthGuard>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
