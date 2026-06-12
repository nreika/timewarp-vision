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

If you prefer to share one callbacks DAT across multiple TouchDesigner operators, `td_capture_listener.py` now also includes compatible `Panel Execute DAT` callbacks for these buttons.

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
10. Optional: create one `Constant CHOP` named `ready_state_all`
11. Optional: create three `Constant CHOP` operators named `fade_trigger_scene_a`, `fade_trigger_scene_b`, `fade_trigger_scene_c`
12. Optional: create one `Constant CHOP` named `display_timing`

If you see `Cannot find function named: onReceive`, your `UDP In DAT` is pointing at the wrong script. The callback DAT for the UDP listener must be `td_capture_listener.py`, not `td_webrtc_panel_controls.py` or `td_capture_panel_controls.py`.

When a message arrives, the callback now does four things:

- It reloads the matching generated-image `Movie File In TOP` with the newest timestamped file.
- If `moviefilein_original` exists, it also reloads the captured source image.
- It tracks which of `sceneA` / `sceneB` / `sceneC` have arrived for the current `captureId`.
- It raises a shared `ready` state only after all three scene messages for the same `captureId` have arrived.
- It updates `capture_info` with both the newest payload and per-scene ready state.
- If one UDP message is missed, it can recover the latest batch from `http://127.0.0.1:3000/api/latest-captures`.

By default, once all three scene images for the same `captureId` arrive, TouchDesigner automatically starts revealing them. The reveal signal stays high for 5 seconds and then returns to `0`, so you can use a `Filter CHOP` to create a soft fade in and fade out. If `display_timing` exists, the listener reads `fade_seconds` and `hide_delay_seconds` from that CHOP instead of using the defaults.

If `ready_state_all` exists, the callback writes `value0 = 1` only when all three timeline images for the current capture batch have arrived. This is useful for a single "all assets ready" lamp or for enabling your display buttons.

This is intentionally not tied to `sceneA`, `sceneB`, or `sceneC` individually. The app saves those three images in parallel, so there is no guaranteed rule like "when sceneC arrives, the batch is complete". Instead, `td_capture_listener.py` counts the received scene keys for each `captureId` and only flips `ready_state_all` high when all expected scene keys are present.

### Manual Display Buttons

To decide the reveal timing in TouchDesigner, add a small control panel:

1. Optional: create three `Button COMP`s named `display_scene_a_btn`, `display_scene_b_btn`, `display_scene_c_btn`
2. Optional: create one more `Button COMP` named `display_latest_ready_btn`
3. Set the buttons to a momentary type
4. Create a `Panel Execute DAT`
5. Paste in `td_capture_panel_controls.py`
6. In the `Panel Execute DAT` parameters:
   - `Panels`: `/project1/display_scene_a_btn /project1/display_scene_b_btn /project1/display_scene_c_btn /project1/display_latest_ready_btn /project1/start_generation_btn`
   - `Panel Value`: `state`
   - `Off to On`: `On`
7. Edit the constants at the top of `td_capture_panel_controls.py` if your paths differ

If you want fewer DATs to manage, you can reuse `td_capture_listener.py` for this `Panel Execute DAT` too. It now implements the same button callbacks directly.

If you do not create `display_latest_ready_btn` or `start_generation_btn`, remove those paths from the `Panels` field.

With the defaults in this repository:

- pressing `display_scene_a_btn` runs `op('/project1/td_capture_listener1').module.display_scene('sceneA')`
- pressing `display_scene_b_btn` runs `op('/project1/td_capture_listener1').module.display_scene('sceneB')`
- pressing `display_scene_c_btn` runs `op('/project1/td_capture_listener1').module.display_scene('sceneC')`
- pressing `display_latest_ready_btn` runs `op('/project1/td_capture_listener1').module.display_latest_ready_scene()`

`display_scene()` fires the fade trigger immediately for that one scene. Separately, when the current capture batch becomes complete, `td_capture_listener.py` automatically triggers all three scene fades.

For a visible reveal, make sure `fade_trigger_scene_a` / `b` / `c` exist or point `FADE_TRIGGER_OPS` at your own trigger operators.

### Optional: Trigger Generation from TouchDesigner

You can also start a new prediction batch from TouchDesigner:

1. Create a `Button COMP` named `start_generation_btn`
2. Keep the browser app open and allow camera access
3. In the browser sidebar, keep `Session_ID` aligned with the `SESSION_ID` constant in `td_capture_panel_controls.py` or `td_capture_listener.py`
4. Keep `CONTROL_TRANSPORT = 'udp'` in `td_capture_panel_controls.py` or `td_capture_listener.py`
5. Press `start_generation_btn`

With the defaults in this repository, that button sends this UDP JSON packet to the local Node server:

```json
{
  "type": "capture",
  "sessionId": "timewarp-local"
}
```

Default UDP control destination:

- host: `127.0.0.1`
- port: `9990`

The Node server listens for that packet, pushes the same internal capture command queue used by the HTTP endpoint, and the browser app polls that queue while its camera stream is ready. In other words, the UDP button triggers the same capture flow as the on-screen `Initiate_Scan` button.

If you prefer the previous HTTP method, set `CONTROL_TRANSPORT = 'http'` in `td_capture_panel_controls.py` or `td_capture_listener.py`. In that mode the same button calls:

- `POST /api/touchdesigner-control/session/<sessionId>/capture`

### Optional: Control Reveal Timing in TouchDesigner

If you want to adjust both values inside TouchDesigner, use one shared `Constant CHOP`:

1. Create `display_timing` as a `Constant CHOP`
2. Rename channel 1 to `fade_seconds`
3. Rename channel 2 to `hide_delay_seconds`
4. Set `fade_seconds` to how long the reveal should take, for example `2`
5. Set `hide_delay_seconds` to how long after the reveal starts the trigger should return to `0`, for example `5`

Then wire the reveal itself like this for each screen:

1. Create `fade_trigger_scene_a` as a `Constant CHOP`
2. Connect it to a `Filter CHOP`
3. Drag `display_timing/fade_seconds` onto that `Filter CHOP` `Filter Width` parameter as a reference or export
4. Use the filtered channel to drive the generated image opacity, for example with a `Level TOP` `Opacity` parameter or a `Cross TOP`
5. Repeat the same pattern for `sceneB` and `sceneC`

`td_capture_listener.py` reads `display_timing/hide_delay_seconds` automatically, so you only need to wire `fade_seconds` into the `Filter CHOP` width on the TouchDesigner side.

In other words:

- new image saved by the app
- UDP message reaches TouchDesigner
- `td_capture_listener.py` reloads the image and records that scene as received for the current `captureId`
- once `sceneA`, `sceneB`, and `sceneC` are all present for that same `captureId`, `ready_state_all` rises to `1`
- the listener automatically drives each `fade_trigger_scene_x` high
- after `display_timing/hide_delay_seconds` seconds, the listener drives those trigger channels back to `0`
- `fade_trigger_scene_x` rises from `0` to `1`
- `Filter CHOP` width follows `display_timing/fade_seconds`, so both the rise and the return use that timing

If you want a different trigger style, edit the constants at the top of `td_capture_listener.py`:

- `READY_STATUS_OP`: optional shared batch-ready indicator operator
- `DISPLAY_TIMING_OP`: optional timing-control CHOP, default is `display_timing`
- `FADE_TRIGGER_OPS`: which operator is used for each scene
- `FADE_TRIGGER_VALUE_PARM`: which numeric parameter to drive, default is `value0`
- `FADE_TRIGGER_RESET_VALUE`: value written before the trigger
- `FADE_TRIGGER_ACTIVE_VALUE`: value written on the trigger frame
- `AUTO_DISPLAY_ON_BATCH_READY`: whether to reveal all screens automatically once the batch is complete
- `DEFAULT_FADE_SECONDS`: fallback reveal duration when `display_timing` is missing
- `DEFAULT_HIDE_DELAY_SECONDS`: fallback delay before returning to `0` when `display_timing` is missing

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
