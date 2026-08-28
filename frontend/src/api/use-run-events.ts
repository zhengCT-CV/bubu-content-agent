import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { RunEvent } from "./types";
import { useRunStore } from "../stores/run-store";

const eventNames = ["run.started", "node.started", "token.delta", "artifact.ready", "interrupt.waiting", "run.completed", "run.failed"];

export function useRunEvents(threadId?: string | null) {
  const queryClient = useQueryClient();
  const push = useRunStore((state) => state.push);
  const setConnected = useRunStore((state) => state.setConnected);

  useEffect(() => {
    if (!threadId) return;
    const source = new EventSource(api.eventUrl(threadId));
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    const handler = (raw: Event) => {
      const event = JSON.parse((raw as MessageEvent).data) as RunEvent;
      push(event);
      void queryClient.invalidateQueries({ queryKey: ["run", threadId] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["project", event.project_id] });
    };
    eventNames.forEach((name) => source.addEventListener(name, handler));
    return () => {
      eventNames.forEach((name) => source.removeEventListener(name, handler));
      source.close();
      setConnected(false);
    };
  }, [push, queryClient, setConnected, threadId]);
}
