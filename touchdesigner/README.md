# TouchDesigner Setup

This project now supports two different TouchDesigner integrations:

1. Browser camera to TouchDesigner over WebRTC for live video
2. Saved prediction image notifications over UDP when files are written into `captures`

## Live Browser Camera Feed (WebRTC)

Use this when the browser should keep the webcam and TouchDesigner should receive the same live feed remotely.

### TouchDesigner network

1. Create a `WebRTC DAT` named `webrtc1`
2. Create a `Text DAT` and paste in `td_webrtc_receiver.py`
3. Point the `WebRTC DAT` `Callbacks DAT` parameter to that script
4. Optional: create a `Table DAT` named `webrtc_tracks` to log remote tracks
5. Create a `Video Stream In TOP`
6. Set the TOP to use the `WebRTC DAT` connection once the remote track appears
7. In the browser app, open the `TouchDesigner_Bridge` panel and press `START_WEBRTC_STREAM`
8. In TouchDesigner, run `op('td_webrtc_receiver').module.start('timewarp-local', 'webrtc1')`

### Optional: Start/Stop Buttons

If you want to start and stop the receiver without typing into Textport, add a tiny control panel:

1. Create two `Button COMP`s named `start_stream_btn` and `stop_stream_btn`
2. Set both buttons to a momentary type
3. Create a `Panel Execute DAT`
4. Paste in `td_webrtc_panel_controls.py`
5. In the `Panel Execute DAT` parameters:
   - `Panels`: `/project1/start_stream_btn /project1/stop_stream_btn`
   - `Panel Value`: `state`
   - `Off to On`: `On`
6. Edit the constants at the top of `td_webrtc_panel_controls.py` if your paths differ

If your `Panels` field is easier to use with one button at a time, use two `Panel Execute DAT`s instead:

- `start_stream_exec` monitors `/project1/start_stream_btn`
- `stop_stream_exec` monitors `/project1/stop_stream_btn`
- both can use the same `td_webrtc_panel_controls.py`
- keep `Panel Value` as `state` and `Off to On` as `On`

With the defaults in this repository:

- pressing `start_stream_btn` runs:
  `op('/project1/webrtc1_callbacks1').module.start('timewarp-local', '/project1/webrtc1', '/project1/webrtc1_callbacks1')`
- pressing `stop_stream_btn` runs:
  `op('/project1/webrtc1_callbacks1').module.stop()`

### Signaling API

The receiver script polls the local Node server:

- `GET /api/touchdesigner-stream/session/<sessionId>/offer`
- `POST /api/touchdesigner-stream/session/<sessionId>/answer`
- `GET /api/touchdesigner-stream/session/<sessionId>/candidates?target=touchdesigner`
- `POST /api/touchdesigner-stream/session/<sessionId>/candidates`

Default session ID:

- `timewarp-local`

### Notes

- This setup lets the browser keep `getUserMedia()` ownership, which avoids webcam conflicts
- The sample script is meant for local experimentation and should be a good base if you later want to harden reconnection logic
- If TouchDesigner runs on another machine, you may need extra WebRTC network configuration such as STUN/TURN

## Saved Prediction Image Notifications (UDP)

This project can notify TouchDesigner in real time whenever a new prediction image is written into `captures`.

## What the server sends

The Node server sends one UDP JSON message per saved image to `127.0.0.1:9989` by default.

Each message contains:

- The scene key (`sceneA`, `sceneB`, `sceneC`)
- The saved image path
- A normalized forward-slash path for Windows
- The newest timestamped file path for that scene
- The label and timestamp

## TouchDesigner network

1. Add a `UDP In DAT`
2. Set `Port` to `9989`
3. Set `Row/Callback Format` to `One Per Message`
4. Create a `Text DAT` and paste in `td_capture_listener.py`
5. Point the `UDP In DAT` `Callbacks DAT` parameter at that script
6. Create three `Movie File In TOP` operators named `moviefilein_scene_a`, `moviefilein_scene_b`, `moviefilein_scene_c`
7. Create one more `Movie File In TOP` named `moviefilein_original` if you also want to display the captured source image
8. Optional: keep a fallback single `Movie File In TOP` named `moviefilein1`
9. Optional: create a `Table DAT` named `capture_info`

When a message arrives, the callback uses `sceneKey` to update the matching generated-image `Movie File In TOP` to the newest timestamped file and pulses `reloadpulse`. If `moviefilein_original` exists, it also loads the saved source image used for that generation.

## Notes

- The app currently saves three timeline images per capture, so TouchDesigner will receive three messages in sequence.
- The same source image is shared by those three timeline messages, so `moviefilein_original` will keep showing the single captured frame for that prediction batch.
- Images are stored with timestamped names such as `timewarp_Timeline_A_1776160553565.png`.
- `captures/latest_scenes.json` keeps track of which timestamped file is currently newest for each scene.
- If a UDP packet is missed, you can recover the newest state from `captures/latest_scenes.json` or `http://localhost:3000/api/latest-captures`.

## GitHub Workflow

For GitHub-backed project management, keep the TouchDesigner-side source files in this `touchdesigner/` folder:

- `td_capture_listener.py`
- exported `.tox` components if you modularize the network
- `.toe` project checkpoints only when you want an intentional binary snapshot

The generated files in `captures/` are ignored by Git, so repository history stays focused on source files rather than prediction output images.
