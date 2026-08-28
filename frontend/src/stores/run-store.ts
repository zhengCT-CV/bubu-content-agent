import { create } from "zustand";
import type { RunEvent } from "../api/types";

interface RunStore {
  events: RunEvent[];
  connected: boolean;
  push: (event: RunEvent) => void;
  setConnected: (connected: boolean) => void;
  reset: () => void;
}

export const useRunStore = create<RunStore>((set) => ({
  events: [],
  connected: false,
  push: (event) => set((state) => ({ events: [...state.events.filter((item) => item.id !== event.id), event].slice(-150) })),
  setConnected: (connected) => set({ connected }),
  reset: () => set({ events: [], connected: false }),
}));

