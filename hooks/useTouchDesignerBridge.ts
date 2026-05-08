import { useCallback, useEffect, useRef, useState } from 'react';
import { TouchDesignerBridgeState } from '../types';

type PeerRole = 'browser' | 'touchdesigner';

interface IceCandidatePayload {
  candidate: string;
  sdpMid?: string | null;
  sdpMLineIndex?: number | null;
  usernameFragment?: string | null;
}

interface CandidateMessage {
  id: number;
  from: PeerRole;
  candidate: IceCandidatePayload;
  createdAt: string;
}

interface CandidateResponse {
  items: CandidateMessage[];
  lastId: number;
}

interface SessionDescriptionPayload {
  type: 'offer' | 'answer';
  sdp: string;
  updatedAt: string;
}

const ANSWER_POLL_INTERVAL_MS = 1000;
const CANDIDATE_POLL_INTERVAL_MS = 600;

const defaultState = (sessionId: string): TouchDesignerBridgeState => ({
  status: 'idle',
  sessionId,
  error: null,
  isConnected: false
});

export const normalizeTouchDesignerSessionId = (value: string) => {
  const normalized = value.trim().replace(/[^a-zA-Z0-9_-]/g, '');
  return normalized || 'timewarp-local';
};

const postJson = async <TResponse>(url: string, body: unknown) => {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<TResponse>;
};

const getJson = async <TResponse>(url: string) => {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<TResponse>;
};

export const useTouchDesignerBridge = (
  stream: MediaStream | null,
  enabled: boolean,
  rawSessionId: string
) => {
  const sessionId = normalizeTouchDesignerSessionId(rawSessionId);
  const [bridgeState, setBridgeState] = useState<TouchDesignerBridgeState>(() => defaultState(sessionId));

  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const answerPollTimerRef = useRef<number | null>(null);
  const candidatePollTimerRef = useRef<number | null>(null);
  const activeSessionIdRef = useRef<string>(sessionId);
  const remoteCandidateCursorRef = useRef(0);
  const pendingRemoteCandidatesRef = useRef<IceCandidatePayload[]>([]);

  const clearTimers = useCallback(() => {
    if (answerPollTimerRef.current !== null) {
      window.clearInterval(answerPollTimerRef.current);
      answerPollTimerRef.current = null;
    }

    if (candidatePollTimerRef.current !== null) {
      window.clearInterval(candidatePollTimerRef.current);
      candidatePollTimerRef.current = null;
    }
  }, []);

  const flushPendingRemoteCandidates = useCallback(async () => {
    const peerConnection = peerConnectionRef.current;
    if (!peerConnection?.remoteDescription) {
      return;
    }

    const pendingCandidates = [...pendingRemoteCandidatesRef.current];
    pendingRemoteCandidatesRef.current = [];

    for (const candidate of pendingCandidates) {
      try {
        await peerConnection.addIceCandidate(candidate);
      } catch (error) {
        console.error('Failed to apply TouchDesigner ICE candidate:', error);
      }
    }
  }, []);

  const stopBridge = useCallback(
    async (deleteSession = true) => {
      clearTimers();
      remoteCandidateCursorRef.current = 0;
      pendingRemoteCandidatesRef.current = [];

      const peerConnection = peerConnectionRef.current;
      if (peerConnection) {
        peerConnection.onicecandidate = null;
        peerConnection.onconnectionstatechange = null;
        peerConnection.close();
        peerConnectionRef.current = null;
      }

      if (deleteSession && activeSessionIdRef.current) {
        try {
          await fetch(`/api/touchdesigner-stream/session/${activeSessionIdRef.current}`, {
            method: 'DELETE'
          });
        } catch (error) {
          console.error('Failed to close TouchDesigner signaling session:', error);
        }
      }

      setBridgeState({
        status: enabled ? 'stopped' : 'idle',
        sessionId: activeSessionIdRef.current,
        error: null,
        isConnected: false
      });
    },
    [clearTimers, enabled]
  );

  useEffect(() => {
    setBridgeState((current) => ({
      ...current,
      sessionId
    }));
    activeSessionIdRef.current = sessionId;
  }, [sessionId]);

  useEffect(() => {
    if (!enabled) {
      void stopBridge();
      return;
    }

    if (!stream) {
      setBridgeState({
        status: 'error',
        sessionId,
        error: 'Camera stream is not ready yet.',
        isConnected: false
      });
      return;
    }

    if (stream.getVideoTracks().length === 0) {
      setBridgeState({
        status: 'error',
        sessionId,
        error: 'No video track is available to send to TouchDesigner.',
        isConnected: false
      });
      return;
    }

    let disposed = false;

    const startBridge = async () => {
      await stopBridge(false);

      try {
        setBridgeState({
          status: 'starting',
          sessionId,
          error: null,
          isConnected: false
        });

        await postJson<{ sessionId: string }>(
          '/api/touchdesigner-stream/session',
          { sessionId }
        );

        if (disposed) {
          return;
        }

        const peerConnection = new RTCPeerConnection();
        peerConnectionRef.current = peerConnection;
        activeSessionIdRef.current = sessionId;

        stream.getVideoTracks().forEach((track) => {
          peerConnection.addTrack(track, stream);
        });

        peerConnection.onicecandidate = (event) => {
          if (!event.candidate || disposed) {
            return;
          }

          void postJson(
            `/api/touchdesigner-stream/session/${sessionId}/candidates`,
            {
              from: 'browser',
              candidate: event.candidate.toJSON()
            }
          ).catch((error) => {
            console.error('Failed to publish browser ICE candidate:', error);
          });
        };

        peerConnection.onconnectionstatechange = () => {
          if (disposed) {
            return;
          }

          const { connectionState } = peerConnection;
          if (connectionState === 'connected') {
            setBridgeState({
              status: 'streaming',
              sessionId,
              error: null,
              isConnected: true
            });
            return;
          }

          if (connectionState === 'failed') {
            setBridgeState({
              status: 'error',
              sessionId,
              error: 'The WebRTC connection to TouchDesigner failed.',
              isConnected: false
            });
            return;
          }

          if (connectionState === 'disconnected' || connectionState === 'closed') {
            setBridgeState({
              status: 'stopped',
              sessionId,
              error: null,
              isConnected: false
            });
          }
        };

        const offer = await peerConnection.createOffer({
          offerToReceiveAudio: false,
          offerToReceiveVideo: false
        });
        await peerConnection.setLocalDescription(offer);

        if (!offer.sdp || disposed) {
          throw new Error('Failed to create a valid WebRTC offer.');
        }

        await postJson(
          `/api/touchdesigner-stream/session/${sessionId}/offer`,
          { type: offer.type, sdp: offer.sdp }
        );

        if (disposed) {
          return;
        }

        setBridgeState({
          status: 'waiting-answer',
          sessionId,
          error: null,
          isConnected: false
        });

        answerPollTimerRef.current = window.setInterval(() => {
          const activePeerConnection = peerConnectionRef.current;
          if (!activePeerConnection || activePeerConnection.remoteDescription) {
            return;
          }

          void getJson<{ answer: SessionDescriptionPayload | null }>(
            `/api/touchdesigner-stream/session/${sessionId}/answer`
          )
            .then(async ({ answer }) => {
              if (!answer?.sdp || !peerConnectionRef.current || disposed) {
                return;
              }

              await peerConnectionRef.current.setRemoteDescription(answer);
              await flushPendingRemoteCandidates();

              setBridgeState({
                status: 'streaming',
                sessionId,
                error: null,
                isConnected: true
              });
            })
            .catch((error) => {
              console.error('Failed to poll TouchDesigner answer:', error);
            });
        }, ANSWER_POLL_INTERVAL_MS);

        candidatePollTimerRef.current = window.setInterval(() => {
          if (disposed) {
            return;
          }

          const after = remoteCandidateCursorRef.current;

          void getJson<CandidateResponse>(
            `/api/touchdesigner-stream/session/${sessionId}/candidates?target=browser&after=${after}`
          )
            .then(async ({ items }) => {
              const activePeerConnection = peerConnectionRef.current;
              if (!activePeerConnection) {
                return;
              }

              for (const item of items) {
                remoteCandidateCursorRef.current = Math.max(remoteCandidateCursorRef.current, item.id);

                if (activePeerConnection.remoteDescription) {
                  try {
                    await activePeerConnection.addIceCandidate(item.candidate);
                  } catch (error) {
                    console.error('Failed to add TouchDesigner ICE candidate:', error);
                  }
                } else {
                  pendingRemoteCandidatesRef.current.push(item.candidate);
                }
              }
            })
            .catch((error) => {
              console.error('Failed to poll TouchDesigner ICE candidates:', error);
            });
        }, CANDIDATE_POLL_INTERVAL_MS);
      } catch (error) {
        console.error(error);
        if (disposed) {
          return;
        }

        setBridgeState({
          status: 'error',
          sessionId,
          error: error instanceof Error ? error.message : 'Failed to start TouchDesigner bridge.',
          isConnected: false
        });
      }
    };

    void startBridge();

    return () => {
      disposed = true;
      void stopBridge();
    };
  }, [clearTimers, enabled, flushPendingRemoteCandidates, sessionId, stopBridge, stream]);

  return {
    bridgeState,
    stopBridge
  };
};
