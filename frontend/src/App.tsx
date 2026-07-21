import { BrowserRouter, Route, Routes } from "react-router-dom";

function LoginPlaceholder() {
  return <p>Login page (Task 16)</p>;
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPlaceholder />} />
        <Route path="*" element={<LoginPlaceholder />} />
      </Routes>
    </BrowserRouter>
  );
}
