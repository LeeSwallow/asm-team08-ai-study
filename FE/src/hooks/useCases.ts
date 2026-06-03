import { useEffect, useState } from "react";
import { getCases } from "../api";
import type { CaseSummary } from "../types";
import { createActionTimer } from "../utils/observability";

export function useCases() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [busy, setBusy] = useState(true);
  const [statusMessage, setStatusMessage] = useState("사건 파일을 불러오는 중입니다.");

  useEffect(() => {
    const done = createActionTimer({ component: "CaseListPage", action: "load_cases" });
    getCases()
      .then((items) => {
        setCases(items);
        setStatusMessage("사건 파일 준비 완료");
        done({ level: "info" });
      })
      .catch((error: unknown) => {
        setCases([]);
        setStatusMessage("사건 목록 API 실패: BE 공개 사건 파일 없이는 자동 세션을 시작하지 않습니다.");
        done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
      })
      .finally(() => setBusy(false));
  }, []);

  return { cases, busy, statusMessage };
}
