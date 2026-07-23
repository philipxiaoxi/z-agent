import { useEffect, useState } from "react";
import { getToken, setToken } from "../../lib/fetch";

function checkAuthRequired(): Promise<boolean> {
  return fetch("/api/auth/status")
    .then((res) => res.json())
    .then((data) => !!data.auth_required)
    .catch(() => true);
}

function verifyToken(token: string): Promise<boolean> {
  return fetch("/api/sessions/", {
    headers: { Authorization: `Bearer ${token}` },
  }).then((res) => res.ok);
}

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const [phase, setPhase] = useState<"loading" | "auth" | "ready">("loading");
  const [error, setError] = useState("");
  const [value, setValue] = useState("");

  useEffect(() => {
    checkAuthRequired().then((required) => {
      if (!required) {
        setPhase("ready");
        return;
      }
      const saved = getToken();
      if (saved) {
        verifyToken(saved).then((ok) => {
          if (ok) {
            setPhase("ready");
          } else {
            setToken("");
            setPhase("auth");
          }
        });
      } else {
        setPhase("auth");
      }
    });

    function onUnauthorized() {
      setToken("");
      setPhase("auth");
    }
    window.addEventListener("zspace:auth:unauthorized", onUnauthorized);
    return () => window.removeEventListener("zspace:auth:unauthorized", onUnauthorized);
  }, []);

  if (phase === "loading") return null;

  if (phase === "auth") {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="w-full max-w-sm">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
            <div className="text-center mb-8">
              <div className="w-12 h-12 rounded-xl bg-blue-500 flex items-center justify-center mx-auto mb-4">
                <span className="text-white text-xl font-bold">Z</span>
              </div>
              <h1 className="text-lg font-semibold text-gray-900">极同学</h1>
              <p className="text-sm text-gray-500 mt-1">NAS AI 助手</p>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (!value.trim()) return;
                setError("");
                verifyToken(value.trim()).then((ok) => {
                  if (ok) {
                    setToken(value.trim());
                    setPhase("ready");
                  } else {
                    setError("认证凭证无效");
                  }
                });
              }}
            >
              <label className="block text-sm font-medium text-gray-700 mb-1.5">请输入访问凭证</label>
              <input
                type="text"
                autoComplete="off"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="输入凭证"
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none transition mb-4"
                autoFocus
              />
              {error && <p className="text-sm text-red-500 mb-3">{error}</p>}
              <button
                type="submit"
                disabled={!value.trim()}
                className="w-full rounded-lg bg-blue-500 text-white text-sm font-medium py-2 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                确定
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
