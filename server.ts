
import express from 'express';
import { createServer as createViteServer } from 'vite';
import path from 'path';
import fs from 'fs';
import cors from 'cors';
import dgram from 'dgram';

interface CaptureEvent {
  type: 'capture.saved';
  sceneKey: string;
  sceneIndex: number | null;
  label: string;
  filename: string;
  absolutePath: string;
  normalizedPath: string;
  relativePath: string;
  url: string;
  latestImagePath: string;
  latestImageNormalizedPath: string;
  latestImageUrl: string;
  savedAt: string;
  size: number;
}

interface LatestScenesManifest {
  updatedAt: string;
  scenes: Record<string, CaptureEvent>;
}

async function startServer() {
  const app = express();
  const PORT = Number(process.env.PORT || '3000');
  const HMR_PORT = Number(process.env.HMR_PORT || '24679');

  // Ensure captures directory exists
  const capturesDir = path.join(process.cwd(), 'captures');
  if (!fs.existsSync(capturesDir)) {
    fs.mkdirSync(capturesDir);
  }

  const latestMetaPath = path.join(capturesDir, 'latest.json');
  const latestScenesMetaPath = path.join(capturesDir, 'latest_scenes.json');
  const touchDesignerBridgeEnabled = (process.env.TOUCHDESIGNER_BRIDGE_ENABLED ?? 'true').toLowerCase() !== 'false';
  const touchDesignerHost = process.env.TOUCHDESIGNER_UDP_HOST || '127.0.0.1';
  const touchDesignerPort = Number(process.env.TOUCHDESIGNER_UDP_PORT || '9989');
  const udpClient = dgram.createSocket('udp4');
  const normalizePath = (filePath: string) => filePath.replace(/\\/g, '/');
  const normalizeSceneKey = (value: unknown, fallbackLabel: unknown) => {
    const rawValue = String(value || '').trim();
    if (rawValue) {
      return rawValue.replace(/[^a-zA-Z0-9_-]/g, '') || 'scene';
    }

    const rawLabel = String(fallbackLabel || 'scene').replace(/\s+/g, '');
    return rawLabel.replace(/[^a-zA-Z0-9_-]/g, '') || 'scene';
  };
  const readLatestScenesManifest = (): LatestScenesManifest => {
    if (!fs.existsSync(latestScenesMetaPath)) {
      return { updatedAt: '', scenes: {} };
    }

    try {
      return JSON.parse(fs.readFileSync(latestScenesMetaPath, 'utf8')) as LatestScenesManifest;
    } catch (error) {
      console.error('Failed to parse latest scenes metadata:', error);
      return { updatedAt: '', scenes: {} };
    }
  };

  const publishCapture = (payload: CaptureEvent) => {
    const latestScenesManifest = readLatestScenesManifest();
    latestScenesManifest.updatedAt = payload.savedAt;
    latestScenesManifest.scenes[payload.sceneKey] = payload;

    fs.writeFileSync(latestMetaPath, JSON.stringify(payload, null, 2), 'utf8');
    fs.writeFileSync(latestScenesMetaPath, JSON.stringify(latestScenesManifest, null, 2), 'utf8');

    if (!touchDesignerBridgeEnabled) {
      return;
    }

    udpClient.send(Buffer.from(JSON.stringify(payload)), touchDesignerPort, touchDesignerHost, (error) => {
      if (error) {
        console.error('Failed to notify TouchDesigner:', error);
      }
    });
  };

  app.use(cors());
  app.use(express.json({ limit: '50mb' }));
  app.use('/captures', express.static(capturesDir));

  app.get('/api/latest-capture', (_req, res) => {
    if (!fs.existsSync(latestMetaPath)) {
      return res.status(404).json({ error: 'No captures have been saved yet' });
    }

    try {
      const payload = JSON.parse(fs.readFileSync(latestMetaPath, 'utf8'));
      res.json(payload);
    } catch (error) {
      console.error('Failed to read latest capture metadata:', error);
      res.status(500).json({ error: 'Failed to read latest capture metadata' });
    }
  });

  app.get('/api/latest-captures', (_req, res) => {
    try {
      res.json(readLatestScenesManifest());
    } catch (error) {
      console.error('Failed to read latest scenes metadata:', error);
      res.status(500).json({ error: 'Failed to read latest scenes metadata' });
    }
  });

  // API to save images
  app.post('/api/save-image', (req, res) => {
    const { image, label, sceneKey, sceneIndex } = req.body;
    if (!image) {
      return res.status(400).json({ error: 'No image data provided' });
    }

    try {
      const base64Data = image.replace(/^data:image\/\w+;base64,/, "");
      const buffer = Buffer.from(base64Data, 'base64');
      const safeLabel = String(label || 'timeline').replace(/\s+/g, '_');
      const safeSceneKey = normalizeSceneKey(sceneKey, label);
      const filename = `timewarp_${safeLabel}_${Date.now()}.png`;
      const filePath = path.join(capturesDir, filename);
      const publicUrl = `/captures/${filename}`;
      const payload: CaptureEvent = {
        type: 'capture.saved',
        sceneKey: safeSceneKey,
        sceneIndex: Number.isInteger(sceneIndex) ? Number(sceneIndex) : null,
        label: safeLabel,
        filename,
        absolutePath: filePath,
        normalizedPath: normalizePath(filePath),
        relativePath: normalizePath(path.relative(process.cwd(), filePath)),
        url: publicUrl,
        latestImagePath: filePath,
        latestImageNormalizedPath: normalizePath(filePath),
        latestImageUrl: publicUrl,
        savedAt: new Date().toISOString(),
        size: buffer.length
      };

      fs.writeFileSync(filePath, buffer);
      publishCapture(payload);

      console.log(`Saved image to: ${filePath}`);
      res.json({ success: true, capture: payload });
    } catch (error) {
      console.error('Failed to save image:', error);
      res.status(500).json({ error: 'Failed to save image' });
    }
  });

  // Vite middleware for development
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: {
        middlewareMode: true,
        hmr: {
          port: HMR_PORT
        }
      },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running on http://localhost:${PORT}`);
    console.log(`Images will be saved to: ${capturesDir}`);
    console.log('TouchDesigner will receive the newest timestamped file path for each scene.');
    console.log(`Vite HMR port: ${HMR_PORT}`);
    console.log(
      `TouchDesigner bridge: ${touchDesignerBridgeEnabled ? `udp://${touchDesignerHost}:${touchDesignerPort}` : 'disabled'}`
    );
  });
}

startServer();
