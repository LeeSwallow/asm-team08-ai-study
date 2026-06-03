import { ScenarioSelectScreen } from "../components/ScenarioSelectScreen";
import { useCases } from "../hooks/useCases";
import { loadStoredSessionId } from "../storage";
import { caseDetailPath, sessionPath } from "../routing";

type CaseListPageProps = {
  onNavigate: (path: string) => void;
};

export function CaseListPage({ onNavigate }: CaseListPageProps) {
  const { cases, busy, statusMessage } = useCases();
  const resumableSessionId = loadStoredSessionId();

  return (
    <ScenarioSelectScreen
      cases={cases}
      statusMessage={statusMessage}
      busy={busy}
      resumableSessionId={resumableSessionId}
      onOpenCase={(caseId) => onNavigate(caseDetailPath(caseId))}
      onResumeSession={resumableSessionId ? () => onNavigate(sessionPath(resumableSessionId)) : undefined}
    />
  );
}
