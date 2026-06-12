/**
 * Generic React error boundary.
 *
 * Catches render-time exceptions thrown by any descendant and renders
 * a graceful inline error state instead of letting the exception
 * unmount the whole page subtree (which leaves the user with a blank
 * background — the bug surfaced in QA 2026-05-15 on /finder).
 *
 * Intentionally tiny: no telemetry, no retry button rendered by
 * default. Wrap the smallest reasonable subtree so a crash in one
 * panel doesn't take down the rest of the page.
 */

import { Alert } from "@mantine/core";
import { IconAlertTriangle } from "@tabler/icons-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

/**
 * ErrorBoundary is a class component, so it can't use the `useT` hook.
 * It reads the persisted language straight from localStorage instead —
 * good enough for the rare error path.
 */
function lang(): "it" | "en" {
  try {
    return localStorage.getItem("fob_lang") === "en" ? "en" : "it";
  } catch {
    return "it";
  }
}

interface Props {
  children: ReactNode;
  /** Optional label shown in the alert title. */
  label?: string;
  /** Optional custom fallback. If omitted, a Mantine Alert is rendered. */
  fallback?: (error: Error) => ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Log to console so the dev tools still surface the stack — the UI
    // shows a friendly message but we don't want to hide the trace from
    // anyone debugging in production via DevTools.
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", this.props.label ?? "(unlabeled)", error, info);
  }

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error);
    return (
      <Alert
        color="red"
        variant="light"
        icon={<IconAlertTriangle size={16} />}
        title={
          this.props.label ??
          (lang() === "en" ? "Rendering error" : "Errore di rendering")
        }
      >
        {lang() === "en"
          ? "Something went wrong while rendering this section. Try reloading the page. Technical detail:"
          : "Qualcosa è andato storto durante il rendering di questa sezione. Prova a ricaricare la pagina. Dettaglio tecnico:"}
        &nbsp;
        <code>{error.message}</code>
      </Alert>
    );
  }
}
