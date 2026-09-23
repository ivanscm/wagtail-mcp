import { HttpAgent } from '@ag-ui/client';
import {
  CopilotChat,
  CopilotKitProvider,
  useDefaultRenderTool,
} from '@copilotkit/react-core/v2';
import { useMemo } from 'react';

/** CopilotKit agent id. Local to the browser; not a server route. */
const AGENT_ID = 'wagtail-mcp-agent';

export interface AgentAppProps {
  /** AG-UI HTTP endpoint (POST RunAgentInput, responds with an SSE event stream). */
  endpoint: string;
  /** Wagtail CSRF token, sent as X-CSRFToken on every agent request. */
  csrfToken: string;
}

function AgentChat() {
  // Default card for every bridged tool. Without a renderer, calls are blank.
  useDefaultRenderTool();

  return <CopilotChat agentId={AGENT_ID} className="wagtail-mcp-agent__chat" />;
}

export function AgentApp({ endpoint, csrfToken }: AgentAppProps) {
  const agent = useMemo(
    () =>
      new HttpAgent({
        agentId: AGENT_ID,
        url: endpoint,
        headers: { 'X-CSRFToken': csrfToken },
      }),
    [endpoint, csrfToken],
  );

  return (
    <div className="wagtail-mcp-agent">
      <CopilotKitProvider
        agents__unsafe_dev_only={{ [AGENT_ID]: agent }}
        enableInspector={false}
      >
        <AgentChat />
      </CopilotKitProvider>
    </div>
  );
}
