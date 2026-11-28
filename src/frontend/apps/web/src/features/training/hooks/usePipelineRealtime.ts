"use client";

import { useEffect, useRef, useState } from "react";
import type { MqttClient } from "mqtt";
import type {
  PipelineData,
  PipelineJobFinishedEvent,
  PipelineRealtimeEvent,
} from "@automl/domain";
import {
  getMqttBrokerUrl,
  getMqttCredentials,
} from "@/features/notifications/hooks/useNotificationSocket";
import { isJobTerminal } from "../utils/pipelineGraphBuilder";
import {
  applyPipelineEvent,
  mergePipelineWithSnapshot,
} from "../utils/pipelineRealtimeReducer";

export { applyPipelineEvent, mergePipelineWithSnapshot };

export type PipelineMqttStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected"
  | "error";

export interface UsePipelineRealtimeOptions {
  /** Set false when the job is already terminal so no MQTT connection is opened. */
  enabled?: boolean;
  /** Invoked when MQTT reconnects after a disconnect so caller can refetch snapshot. */
  onReconnect?: () => void;
  /** Invoked when `job_finished` arrives so caller can refetch final full snapshot (trials/holdout). */
  onJobFinished?: (event: PipelineJobFinishedEvent) => void;
}

export interface UsePipelineRealtimeResult {
  pipeline: PipelineData | undefined;
  mqttStatus: PipelineMqttStatus;
  /** True when realtime updates are needed but MQTT is unavailable (enables 5s fallback polling). */
  shouldPollFallback: boolean;
  lastSeq: number;
  lastEventAt: string | null;
}

export function usePipelineRealtime(
  jobId: string | null,
  initial?: PipelineData,
  options: UsePipelineRealtimeOptions = {},
): UsePipelineRealtimeResult {
  const { enabled = true, onReconnect, onJobFinished } = options;

  const [pipeline, setPipeline] = useState<PipelineData | undefined>(initial);
  const [mqttStatus, setMqttStatus] = useState<PipelineMqttStatus>("idle");
  const [lastSeqState, setLastSeqState] = useState<number>(0);
  const [lastEventAt, setLastEventAt] = useState<string | null>(null);

  const lastSeqRef = useRef<number>(0);
  const prevJobIdRef = useRef<string | null>(jobId);
  const onReconnectRef = useRef(onReconnect);
  const onJobFinishedRef = useRef(onJobFinished);

  onReconnectRef.current = onReconnect;
  onJobFinishedRef.current = onJobFinished;

  // Reset tracking when navigating to a different jobId
  useEffect(() => {
    if (prevJobIdRef.current !== jobId) {
      prevJobIdRef.current = jobId;
      lastSeqRef.current = 0;
      setLastSeqState(0);
      setLastEventAt(null);
      setPipeline(initial);
    }
  }, [jobId, initial]);

  // Merge incoming API snapshots cleanly with live MQTT state
  useEffect(() => {
    if (!initial) return;
    if (typeof initial.seq === "number" && initial.seq > lastSeqRef.current) {
      lastSeqRef.current = initial.seq;
      setLastSeqState(initial.seq);
    }
    setPipeline((prev) => mergePipelineWithSnapshot(prev, initial));
  }, [initial]);

  const terminal = isJobTerminal(pipeline?.status) || isJobTerminal(initial?.status);
  const shouldConnect = Boolean(jobId) && enabled && !terminal;

  useEffect(() => {
    if (!shouldConnect || !jobId) {
      setMqttStatus("idle");
      return;
    }

    const brokerUrl = getMqttBrokerUrl();
    const { username, password } = getMqttCredentials();
    const topic = `jobs/${jobId}/pipeline`;
    const clientId = `hautoml_pipeline_${jobId.slice(0, 8)}_${Math.random().toString(16).slice(2, 8)}`;

    let isDisposed = false;
    let hasConnectedOnce = false;
    let client: MqttClient | null = null;

    setMqttStatus("connecting");

    const connectPipelineMqtt = async () => {
      try {
        const mqttModule = await import("mqtt");
        const mqttLib = mqttModule.default ?? mqttModule;
        if (isDisposed) return;

        client = mqttLib.connect(brokerUrl, {
          clientId,
          username,
          password,
          clean: true,
          reconnectPeriod: 5000,
          connectTimeout: 8000,
          keepalive: 30,
        });
      } catch (err) {
        console.warn("[PipelineMQTT] Không thể khởi tạo kết nối MQTT WebSocket:", err);
        if (!isDisposed) setMqttStatus("error");
        return;
      }

      if (isDisposed) {
        client.end(true);
        return;
      }

      client.on("connect", () => {
        if (isDisposed || !client) return;
        const isReconnect = hasConnectedOnce;
        hasConnectedOnce = true;
        setMqttStatus("connected");

        client.subscribe(topic, { qos: 1 }, (err) => {
          if (err) {
            console.warn(`[PipelineMQTT] Lỗi subscribe topic ${topic}:`, err);
          }
        });

        if (isReconnect) {
          onReconnectRef.current?.();
        }
      });

      client.on("message", (receivedTopic, buf) => {
        if (isDisposed || receivedTopic !== topic) return;
        try {
          const parsed = JSON.parse(buf.toString()) as PipelineRealtimeEvent;
          if (!parsed || typeof parsed !== "object" || !("event" in parsed)) return;

          if (typeof parsed.seq === "number") {
            if (parsed.seq <= lastSeqRef.current) return;
            lastSeqRef.current = parsed.seq;
            setLastSeqState(parsed.seq);
          }

          setLastEventAt(parsed.at ?? new Date().toISOString());
          setPipeline((prev) => applyPipelineEvent(prev, parsed));

          if (parsed.event === "job_finished") {
            onJobFinishedRef.current?.(parsed);
          }
        } catch (err) {
          console.warn("[PipelineMQTT] Lỗi parse event JSON:", err);
        }
      });

      client.on("reconnect", () => {
        if (!isDisposed) setMqttStatus("reconnecting");
      });

      client.on("offline", () => {
        if (!isDisposed) setMqttStatus("disconnected");
      });

      client.on("close", () => {
        if (!isDisposed) setMqttStatus("disconnected");
      });

      client.on("error", (err) => {
        console.warn("[PipelineMQTT] Lỗi kết nối broker:", err.message);
        if (!isDisposed) setMqttStatus("error");
      });
    };

    void connectPipelineMqtt();

    return () => {
      isDisposed = true;
      if (client) {
        try {
          client.unsubscribe(topic);
        } catch {
          // ignore unsubscribe errors during teardown
        }
        client.end(true);
      }
    };
  }, [jobId, shouldConnect]);

  const shouldPollFallback = shouldConnect && mqttStatus !== "connected";

  return {
    pipeline,
    mqttStatus,
    shouldPollFallback,
    lastSeq: lastSeqState,
    lastEventAt,
  };
}
