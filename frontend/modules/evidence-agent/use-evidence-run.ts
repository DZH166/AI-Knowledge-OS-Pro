"use client";

import { useEffect, useSyncExternalStore } from "react";

import type { RunController, RunControllerSnapshot } from "./run-controller";

const subscribeToNothing = () => () => undefined;
const getNullSnapshot = () => null;

export function useEvidenceRun(controller: RunController | null): RunControllerSnapshot | null {
  const snapshot = useSyncExternalStore(
    controller?.subscribe ?? subscribeToNothing,
    controller?.getSnapshot ?? getNullSnapshot,
    controller?.getSnapshot ?? getNullSnapshot
  );

  useEffect(() => {
    if (!controller) return;
    void controller.connect().catch(() => undefined);
    return () => controller.disconnect();
  }, [controller]);

  return snapshot;
}
