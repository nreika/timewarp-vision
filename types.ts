
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

export enum AppState {
  IDLE = 'IDLE',
  CAPTURING = 'CAPTURING',
  ANALYZING = 'ANALYZING',
  GENERATING = 'GENERATING',
  ERROR = 'ERROR'
}
