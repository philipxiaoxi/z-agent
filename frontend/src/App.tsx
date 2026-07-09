import { useEffect, useState } from "react";
import { api } from "./services/api";

function App() {
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.get("/system/health").then((res) => {
      setMessage(res.data.status);
    });
  }, []);

  return (
    <div className="app">
      <h1>zspace-agent</h1>
      <p>backend status: {message || "connecting..."}</p>
    </div>
  );
}

export default App;
