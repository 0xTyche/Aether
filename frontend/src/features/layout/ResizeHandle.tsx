/** Vertical 4px drag handle between two columns.
 *
 * Pure-DOM mouse handling — no library. The handle reports a delta in
 * pixels via the supplied callback. The caller is responsible for
 * deciding what to do with it (typically: adjust a panel width and
 * clamp via the UI store).
 */

import { useEffect, useRef } from "react";

interface ResizeHandleProps {
  /** Whether positive deltas should widen the LEFT or RIGHT panel.
   *  - "left":  delta = +(cursor moves right) widens the left panel
   *  - "right": delta = -(cursor moves right) widens the right panel
   */
  side: "left" | "right";
  onDelta: (deltaPx: number) => void;
  ariaLabel?: string;
}

export function ResizeHandle({ side, onDelta, ariaLabel }: ResizeHandleProps) {
  const draggingRef = useRef(false);
  const lastXRef = useRef(0);
  const sideRef = useRef(side);
  const onDeltaRef = useRef(onDelta);

  // Keep mutable refs in sync so the window-level listeners stay current
  // without re-binding on every render.
  sideRef.current = side;
  onDeltaRef.current = onDelta;

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!draggingRef.current) return;
      const dx = e.clientX - lastXRef.current;
      lastXRef.current = e.clientX;
      const signedDelta = sideRef.current === "left" ? dx : -dx;
      onDeltaRef.current(signedDelta);
    };
    const onUp = () => {
      if (!draggingRef.current) return;
      draggingRef.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  function onMouseDown(e: React.MouseEvent) {
    e.preventDefault();
    draggingRef.current = true;
    lastXRef.current = e.clientX;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={ariaLabel ?? "Resize panel"}
      tabIndex={-1}
      onMouseDown={onMouseDown}
      className="h-full w-1 cursor-col-resize bg-border hover:bg-accent/60 active:bg-accent transition-colors"
      style={{ touchAction: "none" }}
    />
  );
}
