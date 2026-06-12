/** A monotonically-increasing seconds counter that drives layer animations.
 *
 *  Re-renders the caller at ~20 fps (50 ms). Cheaper than rAF for the
 *  small handful of marker pulses we drive, and avoids dropping frames
 *  on slower hardware.
 */

import { useEffect, useState } from "react";

export function useAnimationPhase(): number {
  const [phase, setPhase] = useState(0);
  useEffect(() => {
    const t0 = performance.now();
    const id = setInterval(() => {
      setPhase((performance.now() - t0) / 1000);
    }, 50);
    return () => clearInterval(id);
  }, []);
  return phase;
}
