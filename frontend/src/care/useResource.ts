import { useCallback, useEffect, useRef, useState } from "react";
import { get } from "../api";

export function useResource<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const sequence = useRef(0);
  const reload = useCallback(async () => {
    const current = ++sequence.current;
    setLoading(true);
    setError("");
    try {
      const result = await get<T>(path);
      if (sequence.current === current) setData(result);
    } catch (error) {
      if (sequence.current === current)
        setError(error instanceof Error ? error.message : "Please try again.");
    } finally {
      if (sequence.current === current) setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    setData(null);
    void reload();
    return () => {
      sequence.current++;
    };
  }, [reload]);
  return { data, error, loading, reload };
}
