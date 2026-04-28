// LiveKit JS SDK wrapper. Pure module — no React.
// F2.md §4.2 — owns the raw connect/publish/subscribe primitives so that
// `use-livekit-voice.ts` can stay focused on state-machine concerns.

import {
  LocalAudioTrack,
  RemoteAudioTrack,
  RemoteTrack,
  Room,
  RoomEvent,
  Track,
  createLocalAudioTrack,
} from "livekit-client";

/** Errors thrown by this wrapper, distinguished by class for typed catches. */
export class MicPermissionError extends Error {
  override name = "MicPermissionError";
}

export class ConnectError extends Error {
  override name = "ConnectError";
}

export class AgentTimeoutError extends Error {
  override name = "AgentTimeoutError";
  constructor(public readonly timeoutMs: number) {
    super(`Agent did not publish audio within ${timeoutMs}ms`);
  }
}

export interface VoiceRoomHandle {
  /** Connected LiveKit Room. */
  room: Room;
  /** The published local microphone track. */
  micTrack: LocalAudioTrack;
  /** Resolves when the agent's first remote audio track is subscribed. */
  agentTrack$: Promise<RemoteAudioTrack>;
}

export interface ConnectOptions {
  /** Max ms to wait for the agent's first audio track. Default 8000 (F2 §5.2). */
  agentAudioTimeoutMs?: number;
}

/**
 * Acquire mic, connect to the LiveKit room, publish mic, and resolve a handle
 * containing the room, mic track, and a promise that fires when the agent
 * publishes its audio track.
 *
 * Throws `MicPermissionError` if mic access is denied (no token fetched yet —
 * fail-fast lets the caller skip the network round-trip).
 * Throws `ConnectError` if room.connect() rejects.
 *
 * Caller is responsible for calling `disconnectVoiceRoom(handle)` to clean up.
 */
export async function connectToVoiceRoom(
  token: string,
  wsUrl: string,
  opts: ConnectOptions = {},
): Promise<VoiceRoomHandle> {
  const agentAudioTimeoutMs = opts.agentAudioTimeoutMs ?? 8000;

  // 1. Mic permission first — fail fast before any network.
  let micTrack: LocalAudioTrack;
  try {
    micTrack = await createLocalAudioTrack({
      echoCancellation: true,
      noiseSuppression: true,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    throw new MicPermissionError(msg);
  }

  // 2. Build & connect Room.
  const room = new Room();

  // Wire the agent-track promise BEFORE connect so we don't miss an early publish.
  const agentTrack$ = waitForAgentAudioTrack(room, agentAudioTimeoutMs);

  try {
    await room.connect(wsUrl, token);
  } catch (err) {
    micTrack.stop();
    const msg = err instanceof Error ? err.message : String(err);
    throw new ConnectError(msg);
  }

  // 3. Publish mic.
  try {
    await room.localParticipant.publishTrack(micTrack);
  } catch (err) {
    micTrack.stop();
    await room.disconnect().catch(() => {});
    const msg = err instanceof Error ? err.message : String(err);
    throw new ConnectError(`publishTrack failed: ${msg}`);
  }

  return { room, micTrack, agentTrack$ };
}

/**
 * Promise that resolves with the first remote audio track or rejects with
 * `AgentTimeoutError` after `timeoutMs`. Detaches its event listeners on
 * resolve/reject to avoid leaks.
 */
function waitForAgentAudioTrack(
  room: Room,
  timeoutMs: number,
): Promise<RemoteAudioTrack> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      reject(new AgentTimeoutError(timeoutMs));
    }, timeoutMs);

    const onSubscribed = (track: RemoteTrack) => {
      if (track.kind !== Track.Kind.Audio) return;
      cleanup();
      resolve(track as RemoteAudioTrack);
    };

    const cleanup = () => {
      clearTimeout(timer);
      room.off(RoomEvent.TrackSubscribed, onSubscribed);
    };

    room.on(RoomEvent.TrackSubscribed, onSubscribed);
  });
}

/** Cleanly tear down a voice room handle. Safe to call multiple times. */
export async function disconnectVoiceRoom(
  handle: VoiceRoomHandle | null,
): Promise<void> {
  if (!handle) return;
  try {
    handle.micTrack.stop();
  } catch {
    /* best effort */
  }
  try {
    await handle.room.disconnect();
  } catch {
    /* best effort */
  }
}
