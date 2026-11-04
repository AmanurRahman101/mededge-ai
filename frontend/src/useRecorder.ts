import { useCallback, useEffect, useRef, useState } from "react";
import { concatPcm, downsample, wavFromPcm16 } from "./audio";

export function useRecorder() {
  const [recording, setRecording] = useState(false);
  const [starting, setStarting] = useState(false);
  const [audio, setAudio] = useState<Blob | null>(null);
  const [error, setError] = useState("");
  const gear = useRef<{
    stream: MediaStream;
    context: AudioContext;
    node: AudioWorkletNode;
    source: MediaStreamAudioSourceNode;
    sink: GainNode;
    timer: number;
  } | null>(null);
  const alive = useRef(true);
  const chunks = useRef<Int16Array[]>([]);
  const samples = useRef(0);
  const startingRef = useRef(false);
  const stopRef = useRef<() => void>(() => {});
  const dispose = useCallback(() => {
    const current = gear.current;
    if (!current) return;
    gear.current = null;
    window.clearTimeout(current.timer);
    current.node.port.onmessage = null;
    current.source.disconnect();
    current.node.disconnect();
    current.sink.disconnect();
    current.stream.getTracks().forEach((track) => track.stop());
    void current.context.close();
  }, []);
  const stop = useCallback(() => {
    if (!gear.current) return;
    dispose();
    setRecording(false);
    if (samples.current > 0) setAudio(wavFromPcm16(concatPcm(chunks.current)));
    else {
      setAudio(null);
      setError("No audio was captured. Check your microphone and try again.");
    }
    chunks.current = [];
    samples.current = 0;
  }, [dispose]);
  stopRef.current = stop;
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      dispose();
    };
  }, [dispose]);
  async function start() {
    if (gear.current || startingRef.current) return;
    startingRef.current = true;
    setStarting(true);
    setError("");
    setAudio(null);
    chunks.current = [];
    samples.current = 0;
    let stream: MediaStream | undefined;
    let context: AudioContext | undefined;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!alive.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      context = new AudioContext();
      await context.audioWorklet.addModule("/pcm16-worklet.js");
      if (!alive.current) {
        stream.getTracks().forEach((track) => track.stop());
        void context.close();
        return;
      }
      const source = context.createMediaStreamSource(stream);
      const node = new AudioWorkletNode(context, "pcm16");
      const sink = context.createGain();
      sink.gain.value = 0;
      source.connect(node);
      node.connect(sink);
      sink.connect(context.destination);
      const rate = context.sampleRate;
      node.port.onmessage = (message: MessageEvent<Float32Array>) => {
        const part = downsample(message.data, rate);
        const remaining = 180 * 24000 - samples.current;
        if (remaining <= 0) {
          stopRef.current();
          return;
        }
        const bounded = part.subarray(0, remaining);
        chunks.current.push(bounded);
        samples.current += bounded.length;
        if (samples.current >= 180 * 24000) stopRef.current();
      };
      const timer = window.setTimeout(() => stopRef.current(), 180_000);
      gear.current = { stream, context, node, source, sink, timer };
      setRecording(true);
    } catch (caught) {
      stream?.getTracks().forEach((track) => track.stop());
      if (context) void context.close();
      if (alive.current)
        setError(
          caught instanceof Error
            ? `Microphone unavailable: ${caught.message}`
            : "Microphone unavailable.",
        );
    } finally {
      startingRef.current = false;
      if (alive.current) setStarting(false);
    }
  }
  return {
    audio,
    recording,
    starting,
    error,
    start,
    stop,
    discard: () => {
      setAudio(null);
      setError("");
    },
    useBlob: (blob: Blob) => {
      setAudio(blob);
      setError("");
    },
  };
}
