import '@copilotkit/react-core/v2/styles.css';
import './agent.css';
import { createRoot } from 'react-dom/client';
import { AgentApp } from './App';

const MOUNT_ID = 'wagtail-mcp-agent-root';

function mount(): void {
  const container = document.getElementById(MOUNT_ID);
  if (!container) {
    throw new Error(
      `wagtail-mcp agent: mount point #${MOUNT_ID} not found in the document.`,
    );
  }

  const endpoint = container.dataset.endpoint;
  const csrfToken = container.dataset.csrfToken;
  if (!endpoint || !csrfToken) {
    throw new Error(
      `wagtail-mcp agent: #${MOUNT_ID} is missing its data-endpoint / data-csrf-token attributes.`,
    );
  }

  createRoot(container).render(
    <AgentApp endpoint={endpoint} csrfToken={csrfToken} />,
  );
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mount, { once: true });
} else {
  mount();
}
