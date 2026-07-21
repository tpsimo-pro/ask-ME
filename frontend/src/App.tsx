import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AuthGuard } from "./components/AuthGuard";
import { AuthProvider } from "./context/AuthContext";

function LoginPlaceholder() {
  return <p>Login page (Task 16)</p>;
}

function HomePlaceholder() {
  return <p>Analyze page (Task 18)</p>;
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPlaceholder />} />
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
