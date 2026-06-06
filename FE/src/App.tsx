import { useEffect, useState } from "react";
import { CaseDetailPage } from "./pages/CaseDetailPage";
import { CaseListPage } from "./pages/CaseListPage";
import { SessionDeskPage } from "./pages/SessionDeskPage";
import { AgentLoggerPage } from "./pages/AgentLoggerPage";
import { parseRoute, type AppRoute } from "./routing";

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => parseRoute());

  useEffect(() => {
    const syncRoute = () => setRoute(parseRoute());
    window.addEventListener("popstate", syncRoute);
    if (window.location.pathname === "/") {
      window.history.replaceState(null, "", "/cases");
      syncRoute();
    }
    return () => window.removeEventListener("popstate", syncRoute);
  }, []);

  function navigate(path: string) {
    window.history.pushState(null, "", path);
    setRoute(parseRoute(path));
  }

  if (route.name === "caseDetail") {
    return <CaseDetailPage caseId={route.caseId} onNavigate={navigate} />;
  }

  if (route.name === "sessionDesk") {
    return <SessionDeskPage sessionId={route.sessionId} onNavigate={navigate} />;
  }

  if (route.name === "agentLogger") {
    return <AgentLoggerPage onNavigate={navigate} />;
  }

  return <CaseListPage onNavigate={navigate} />;
}
