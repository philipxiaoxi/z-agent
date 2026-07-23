import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider } from "antd";
import ChatPage from "./routes/chat/ChatPage";
import AuthGuard from "./components/auth/AuthGuard";

export default function App() {
  return (
    <ConfigProvider>
      <BrowserRouter>
        <AuthGuard>
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
          </Routes>
        </AuthGuard>
      </BrowserRouter>
    </ConfigProvider>
  );
}
