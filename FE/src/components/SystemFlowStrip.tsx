import { QUESTION_LIMIT, flowSteps } from "../constants/presentation";

type SystemFlowStripProps = {
  statusMessage: string;
  remainingQuestions: number;
};

export function SystemFlowStrip({ statusMessage, remainingQuestions }: SystemFlowStripProps) {
  return (
    <section className="system-flow panel" aria-labelledby="flow-title">
      <h2 id="flow-title">시스템 구조 흐름 <small>(내부 처리)</small></h2>
      <ol>
        {flowSteps.map((step, index) => (
          <li key={step.title}>
            <span className="flow-icon">{step.icon}</span>
            <div>
              <strong>{step.title}</strong>
              <small>{step.detail}</small>
            </div>
            {index < flowSteps.length - 1 && <b aria-hidden="true">→</b>}
          </li>
        ))}
      </ol>
      <p className="sr-status" role="status">{statusMessage} · 남은 질문 {remainingQuestions}/{QUESTION_LIMIT}</p>
    </section>
  );
}
