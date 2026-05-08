
export interface Target {
  x: number;
  y: number;
}

export interface PredictionItem {
  predictedImage: string;
  predictionText: string;
  label: string;
}

export interface PredictionData {
  originalImage: string;
  items: PredictionItem[];
  timestamp: number;
}

export type TouchDesignerBridgeStatus =
  | 'idle'
  | 'starting'
  | 'waiting-answer'
  | 'streaming'
  | 'stopped'
  | 'error';

export interface TouchDesignerBridgeState {
  status: TouchDesignerBridgeStatus;
  sessionId: string;
  error: string | null;
  isConnected: boolean;
}

export enum AppState {
  IDLE = 'IDLE',
  CAPTURING = 'CAPTURING',
  ANALYZING = 'ANALYZING',
  GENERATING = 'GENERATING',
  ERROR = 'ERROR'
}
