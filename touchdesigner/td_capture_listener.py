import json
import socket
from datetime import datetime
try:
    from urllib.request import Request, urlopen
except ImportError:
    from urllib2 import Request, urlopen

SCRIPT_DAT_PATH = me.path
MOVIE_FILE_IN_OPS = {
    'sceneA': 'moviefilein_scene_a',
    'sceneB': 'moviefilein_scene_b',
    'sceneC': 'moviefilein_scene_c',
}
ORIGINAL_MOVIE_FILE_IN_OP = 'moviefilein_original'
INFO_TABLE_OP = 'capture_info'
READY_STATUS_OP = 'ready_state_all'
DISPLAY_TIMING_OP = 'display_timing'
FADE_TRIGGER_OPS = {
    'sceneA': 'fade_trigger_scene_a',
    'sceneB': 'fade_trigger_scene_b',
    'sceneC': 'fade_trigger_scene_c',
}
DISPLAY_SECONDS_CHANNEL = 'fade_seconds'
HIDE_DELAY_SECONDS_CHANNEL = 'hide_delay_seconds'
FADE_TRIGGER_VALUE_PARM = 'value0'
FADE_TRIGGER_RESET_VALUE = 0
FADE_TRIGGER_ACTIVE_VALUE = 1
AUTO_DISPLAY_ON_BATCH_READY = True
DEFAULT_HIDE_DELAY_SECONDS = 5.0
DEFAULT_FADE_SECONDS = 2.0
LATEST_CAPTURES_URL = 'http://127.0.0.1:3000/api/latest-captures'
AUTO_RECOVER_FROM_MANIFEST = True
ALLOW_REDISPLAY_LOADED_SCENE = False
RELOAD_RETRY_FRAMES = (1, 6)

DISPLAY_BUTTON_PATHS = {
    '/project1/display_scene_a_btn': 'sceneA',
    '/project1/display_scene_b_btn': 'sceneB',
    '/project1/display_scene_c_btn': 'sceneC',
}
DISPLAY_LATEST_READY_BUTTON_PATH = '/project1/display_latest_ready_btn'
START_GENERATION_BUTTON_PATH = '/project1/start_generation_btn'

CONTROL_TRANSPORT = 'udp'
CONTROL_UDP_HOST = '127.0.0.1'
CONTROL_UDP_PORT = 9990
SERVER_BASE_URL = 'http://127.0.0.1:3000'
REQUEST_TIMEOUT_SECONDS = 2.0

RECEIVER_DAT_PATH = '/project1/webrtc1_callbacks1'
WEBRTC_DAT_PATH = '/project1/webrtc1'
SESSION_ID = 'timewarp-local'
START_STREAM_BUTTON_PATH = '/project1/start_stream_btn'
STOP_STREAM_BUTTON_PATH = '/project1/stop_stream_btn'

EXPECTED_SCENE_KEYS = tuple(sorted(MOVIE_FILE_IN_OPS))


def _debug(message):
    print('[TD Capture Listener] {}'.format(message))


debug = _debug


def _new_scene_state(capture_id=''):
    return {
        'ready': False,
        'label': '',
        'captureId': capture_id,
        'targetPath': '',
        'sourcePath': '',
        'savedAt': '',
        'lastDisplayedAt': '',
        'payload': {},
    }


SCENE_STATES = {scene_key: _new_scene_state() for scene_key in EXPECTED_SCENE_KEYS}
BATCH_STATE = {
    'captureId': '',
    'receivedSceneKeys': set(),
    'isReady': False,
    'completedAt': '',
}
LAST_AUTO_DISPLAY_CAPTURE_ID = ''
def _utc_timestamp():
    return '{}Z'.format(datetime.utcnow().isoformat())


def _delay_frames(seconds):
    return max(1, int(round((getattr(me.time, 'rate', 60) or 60) * max(0, seconds))))


def _td_op(name):
    return op(name) if name else None
def _read_chop_channel(op_name, channel_name, default_value):
    chop = _td_op(op_name)
    if not chop:
        return default_value

    try:
        return float(chop[channel_name][0])
    except Exception:
        return default_value


def _fade_seconds():
    return _read_chop_channel(DISPLAY_TIMING_OP, DISPLAY_SECONDS_CHANNEL, DEFAULT_FADE_SECONDS)
def _hide_delay_seconds():
    return _read_chop_channel(DISPLAY_TIMING_OP, HIDE_DELAY_SECONDS_CHANNEL, DEFAULT_HIDE_DELAY_SECONDS)
def _set_par_value(target_op, par_name, value):
    if not target_op:
        return False

    par = getattr(target_op.par, par_name, None)
    if par is None:
        return False

    par.val = value
    return True


def _pulse_reload(target_op_path):
    target_op = op(target_op_path)
    if target_op and getattr(target_op.par, 'reloadpulse', None) is not None:
        target_op.par.reloadpulse.pulse()


def _reload_movie(op_name, file_path):
    movie = _td_op(op_name)
    if not movie:
        return False

    movie.par.file = file_path
    _pulse_reload(movie.path)

    for delay_frames in RELOAD_RETRY_FRAMES:
        run(
            "mod = op({!r}).module if op({!r}) else None\n"
            "mod._pulse_reload({!r}) if mod else None".format(
                SCRIPT_DAT_PATH,
                SCRIPT_DAT_PATH,
                movie.path
            ),
            delayFrames=delay_frames
        )
    return True
def _resolve_path(payload, keys):
    for key in keys:
        value = payload.get(key, '')
        if value:
            return value
    return ''


def _fetch_latest_manifest():
    if not LATEST_CAPTURES_URL:
        return {}

    try:
        with urlopen(LATEST_CAPTURES_URL, timeout=1.0) as response:
            raw_body = response.read().decode('utf-8')
    except Exception:
        return {}

    try:
        return json.loads(raw_body) if raw_body else {}
    except Exception:
        return {}


def _post_json(url, payload):
    body = json.dumps(payload).encode('utf-8')
    request = Request(
        url,
        data=body,
        headers={'Content-Type': 'application/json'}
    )
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        raw_body = response.read().decode('utf-8')

    if not raw_body:
        return {}
    return json.loads(raw_body)


def _send_udp_json(host, port, payload):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(json.dumps(payload).encode('utf-8'), (host, port))
    finally:
        sock.close()


def _receiver_dat():
    receiver_dat = op(RECEIVER_DAT_PATH)
    if receiver_dat is None:
        raise ValueError('Receiver DAT "{}" was not found.'.format(RECEIVER_DAT_PATH))
    return receiver_dat


def _receiver_module():
    return _receiver_dat().module


def _reset_batch(capture_id=''):
    BATCH_STATE.update({
        'captureId': capture_id or '',
        'receivedSceneKeys': set(),
        'isReady': False,
        'completedAt': '',
    })

    for scene_key in EXPECTED_SCENE_KEYS:
        SCENE_STATES[scene_key] = _new_scene_state(capture_id or '')


def _register_scene(capture_id, scene_key, saved_at):
    capture_id = capture_id or ''
    if capture_id != BATCH_STATE['captureId']:
        _reset_batch(capture_id)

    if scene_key in SCENE_STATES:
        BATCH_STATE['receivedSceneKeys'].add(scene_key)

    BATCH_STATE['isReady'] = len(BATCH_STATE['receivedSceneKeys']) == len(EXPECTED_SCENE_KEYS)
    if BATCH_STATE['isReady']:
        BATCH_STATE['completedAt'] = saved_at or _utc_timestamp()


def _sync_ready_signal():
    ready_op = _td_op(READY_STATUS_OP)
    if not ready_op:
        return

    if not _set_par_value(
        ready_op,
        FADE_TRIGGER_VALUE_PARM,
        1 if BATCH_STATE['isReady'] else 0
    ):
        debug(
            'TimeWarp bridge: missing ready value parameter {} on {}'.format(
                FADE_TRIGGER_VALUE_PARM,
                ready_op.path
            )
        )


def _sync_info_table(payload, target_path):
    table = _td_op(INFO_TABLE_OP)
    if not table:
        return

    rows = [
        ['key', 'value'],
        ['sceneKey', payload.get('sceneKey', '')],
        ['label', payload.get('label', '')],
        ['captureId', payload.get('captureId', '')],
        ['filename', payload.get('filename', '')],
        ['savedAt', payload.get('savedAt', '')],
        ['targetPath', target_path],
        ['latestImagePath', payload.get('latestImageNormalizedPath', '')],
        ['sourceImagePath', payload.get('sourceImageNormalizedPath', '')],
        ['fadeTriggerOp', FADE_TRIGGER_OPS.get(payload.get('sceneKey', ''), '')],
        ['batch.captureId', BATCH_STATE['captureId']],
        ['batch.receivedSceneKeys', ','.join(sorted(BATCH_STATE['receivedSceneKeys']))],
        ['batch.receivedSceneCount', len(BATCH_STATE['receivedSceneKeys'])],
        ['batch.expectedSceneCount', len(EXPECTED_SCENE_KEYS)],
        ['batch.isReady', int(BATCH_STATE['isReady'])],
        ['batch.completedAt', BATCH_STATE['completedAt']],
        ['timing.fadeSeconds', _fade_seconds()],
        ['timing.hideDelaySeconds', _hide_delay_seconds()],
        ['timing.sourceOp', DISPLAY_TIMING_OP],
    ]

    for scene_key in EXPECTED_SCENE_KEYS:
        state = SCENE_STATES[scene_key]
        rows.extend([
            ['{}.ready'.format(scene_key), int(bool(state['ready']))],
            ['{}.label'.format(scene_key), state['label']],
            ['{}.targetPath'.format(scene_key), state['targetPath']],
            ['{}.savedAt'.format(scene_key), state['savedAt']],
            ['{}.lastDisplayedAt'.format(scene_key), state['lastDisplayedAt']],
        ])

    table.clear()
    for row in rows:
        table.appendRow(row)


def _trigger_fade(scene_key):
    trigger_name = FADE_TRIGGER_OPS.get(scene_key, '')
    trigger_op = _td_op(trigger_name)
    if not trigger_op:
        debug(
            'TimeWarp bridge: missing fade trigger operator for {} ({})'.format(
                scene_key,
                trigger_name or 'unset'
            )
        )
        return False

    if not _set_par_value(trigger_op, FADE_TRIGGER_VALUE_PARM, FADE_TRIGGER_ACTIVE_VALUE):
        debug(
            'TimeWarp bridge: missing fade value parameter {} on {}'.format(
                FADE_TRIGGER_VALUE_PARM,
                trigger_op.path
            )
        )
        return False

    hide_delay_seconds = _hide_delay_seconds()
    if hide_delay_seconds > 0:
        run(
            (
                "listener = op({!r})\n"
                "target = op({!r})\n"
                "state = listener.module.SCENE_STATES.get({!r}) if listener else None\n"
                "par = getattr(target.par, {!r}, None) if target else None\n"
                "if state and par is not None and state.get('captureId') == {!r}:\n"
                "    par.val = {!r}\n"
            ).format(
                SCRIPT_DAT_PATH,
                trigger_op.path,
                scene_key,
                FADE_TRIGGER_VALUE_PARM,
                SCENE_STATES[scene_key]['captureId'],
                FADE_TRIGGER_RESET_VALUE
            ),
            delayFrames=_delay_frames(hide_delay_seconds)
        )
    return True


def _maybe_auto_display():
    global LAST_AUTO_DISPLAY_CAPTURE_ID
    capture_id = BATCH_STATE['captureId']
    if not AUTO_DISPLAY_ON_BATCH_READY or not BATCH_STATE['isReady'] or not capture_id or LAST_AUTO_DISPLAY_CAPTURE_ID == capture_id:
        return

    LAST_AUTO_DISPLAY_CAPTURE_ID = capture_id
    for ready_scene_key in EXPECTED_SCENE_KEYS:
        display_scene(ready_scene_key)


def _apply_capture_payload(payload):
    scene_key = payload.get('sceneKey', '')
    if scene_key not in SCENE_STATES:
        return False

    target_path = _resolve_path(
        payload,
        ('latestImagePath', 'latestImageNormalizedPath', 'absolutePath', 'normalizedPath')
    )
    source_path = _resolve_path(
        payload,
        ('sourceImageAbsolutePath', 'sourceImageNormalizedPath')
    )
    if not target_path and not source_path:
        debug('TimeWarp bridge: missing image paths')
        return False

    if target_path and not _reload_movie(MOVIE_FILE_IN_OPS.get(scene_key, ''), target_path):
        debug('TimeWarp bridge: missing operator for scene {}'.format(scene_key))

    if source_path and not _reload_movie(ORIGINAL_MOVIE_FILE_IN_OP, source_path):
        debug('TimeWarp bridge: missing operator for original image')

    _register_scene(payload.get('captureId', ''), scene_key, payload.get('savedAt', ''))
    state = SCENE_STATES[scene_key]
    state.update({
        'ready': True,
        'label': payload.get('label', ''),
        'captureId': payload.get('captureId', ''),
        'targetPath': target_path,
        'sourcePath': source_path,
        'savedAt': payload.get('savedAt', ''),
        'payload': payload,
    })
    _sync_ready_signal()
    _sync_info_table(payload, target_path or source_path)
    _maybe_auto_display()
    return True


def resync_latest_scenes(expected_capture_id=''):
    manifest = _fetch_latest_manifest()
    scenes = manifest.get('scenes', {}) if isinstance(manifest, dict) else {}
    payloads = []
    for scene_key in EXPECTED_SCENE_KEYS:
        payload = scenes.get(scene_key)
        if not isinstance(payload, dict):
            continue
        if expected_capture_id and payload.get('captureId', '') != expected_capture_id:
            continue
        payloads.append(payload)

    for payload in payloads:
        _apply_capture_payload(payload)
    return bool(payloads)


def display_scene(scene_key):
    state = SCENE_STATES.get(scene_key)
    if not state or not state['targetPath']:
        debug('TimeWarp bridge: no loaded scene is ready for {}'.format(scene_key))
        return False

    if not BATCH_STATE['isReady'] and not ALLOW_REDISPLAY_LOADED_SCENE:
        debug('TimeWarp bridge: capture batch {} is not complete yet'.format(BATCH_STATE['captureId']))
        return False

    if not state['ready'] and not ALLOW_REDISPLAY_LOADED_SCENE:
        debug('TimeWarp bridge: scene {} is not marked ready'.format(scene_key))
        return False

    if not _trigger_fade(scene_key):
        return False

    state['lastDisplayedAt'] = _utc_timestamp()
    _sync_info_table(state['payload'], state['targetPath'])
    return True


def display_latest_ready_scene():
    ready_scene_keys = [
        scene_key for scene_key, state in SCENE_STATES.items()
        if state['ready'] and state['targetPath']
    ]
    if not ready_scene_keys:
        debug('TimeWarp bridge: no ready scene is waiting for display')
        return False

    latest_scene_key = max(ready_scene_keys, key=lambda key: SCENE_STATES[key]['savedAt'])
    return display_scene(latest_scene_key)


def request_capture():
    if CONTROL_TRANSPORT.lower() == 'udp':
        payload = {
            'type': 'capture',
            'sessionId': SESSION_ID,
        }
        _send_udp_json(CONTROL_UDP_HOST, CONTROL_UDP_PORT, payload)
        _debug(
            'Queued remote capture command via udp://{}:{}.'.format(
                CONTROL_UDP_HOST,
                CONTROL_UDP_PORT
            )
        )
        return payload

    url = '{}/api/touchdesigner-control/session/{}/capture'.format(
        SERVER_BASE_URL.rstrip('/'),
        SESSION_ID
    )
    response = _post_json(url, {})
    command_id = response.get('command', {}).get('id', '?')
    _debug('Queued remote capture command via HTTP #{}.'.format(command_id))
    return response


def start_stream():
    receiver_dat = _receiver_dat()
    _debug('Starting WebRTC receiver.')
    return _receiver_module().start(SESSION_ID, WEBRTC_DAT_PATH, receiver_dat.path)


def stop_stream():
    _debug('Stopping WebRTC receiver.')
    return _receiver_module().stop()


def onReceive(dat, rowIndex, message, bytes, peer):
    try:
        payload = json.loads(message)
    except Exception as exc:
        debug('TimeWarp bridge: invalid JSON {}'.format(exc))
        return

    if not _apply_capture_payload(payload):
        debug('TimeWarp bridge: unsupported capture payload')
        return

    if AUTO_RECOVER_FROM_MANIFEST and not BATCH_STATE['isReady']:
        resync_latest_scenes(payload.get('captureId', ''))


def onOffToOn(panelValue):
    owner_path = panelValue.owner.path

    if owner_path in DISPLAY_BUTTON_PATHS:
        return display_scene(DISPLAY_BUTTON_PATHS[owner_path])
    if owner_path == DISPLAY_LATEST_READY_BUTTON_PATH:
        return display_latest_ready_scene()
    if owner_path == START_GENERATION_BUTTON_PATH:
        return request_capture()
    if owner_path == START_STREAM_BUTTON_PATH:
        return start_stream()
    if owner_path == STOP_STREAM_BUTTON_PATH:
        return stop_stream()

    return


def whileOn(panelValue):
    return


def onOnToOff(panelValue):
    return


def whileOff(panelValue):
    return


def onValueChange(panelValue, prev):
    return
