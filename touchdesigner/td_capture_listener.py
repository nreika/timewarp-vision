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
    'sceneD': 'moviefilein_scene_d',
    'sceneE': 'moviefilein_scene_e',
    'sceneF': 'moviefilein_scene_f',
    'sceneG': 'moviefilein_scene_g',
    'sceneH': 'moviefilein_scene_h',
    'sceneI': 'moviefilein_scene_i',
    'sceneJ': 'moviefilein_scene_j',
}
ORIGINAL_MOVIE_FILE_IN_OP = 'moviefilein_original'
INFO_TABLE_OP = 'capture_info'
LATEST_CAPTURES_URL = 'http://127.0.0.1:3000/api/latest-captures'
AUTO_RECOVER_FROM_MANIFEST = True
RELOAD_RETRY_FRAMES = (1, 6)

START_GENERATION_BUTTON_PATH = '/project1/start_generation_btn'
START_GENERATION_KEYBOARD_OP_PATHS = ('/project1/keyboardin1',)
START_GENERATION_KEY_CHANNELS = ('1', 'k1', 'num1', 'numpad1')
GENERATION_COUNT_OP_PATH = '/project1/generation_count'
DEFAULT_IMAGE_COUNT = 3
MIN_IMAGE_COUNT = 1
MAX_IMAGE_COUNT = 10

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
STREAM_KEYBOARD_OP_PATHS = ('/project1/keyboardin1',)
START_STREAM_KEY_CHANNELS = ('0', 'k0', 'num0', 'numpad0')
STOP_STREAM_KEY_CHANNELS = ('9', 'k9', 'num9', 'numpad9')

KNOWN_SCENE_KEYS = tuple(sorted(MOVIE_FILE_IN_OPS))


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
        'payload': {},
    }


SCENE_STATES = {scene_key: _new_scene_state() for scene_key in KNOWN_SCENE_KEYS}
BATCH_STATE = {
    'captureId': '',
    'receivedSceneKeys': set(),
    'expectedImageCount': DEFAULT_IMAGE_COUNT,
    'isReady': False,
    'completedAt': '',
}


def _utc_timestamp():
    return '{}Z'.format(datetime.utcnow().isoformat())


def _td_op(name):
    return op(name) if name else None


def _clamp_image_count(value):
    try:
        numeric_value = int(round(float(value)))
    except Exception:
        return DEFAULT_IMAGE_COUNT

    return max(MIN_IMAGE_COUNT, min(MAX_IMAGE_COUNT, numeric_value))


def _read_generation_count():
    count_op = _td_op(GENERATION_COUNT_OP_PATH)
    if count_op is None:
        return DEFAULT_IMAGE_COUNT

    try:
        if hasattr(count_op, 'numChans') and count_op.numChans > 0:
            channels = count_op.chans()
            if channels:
                return _clamp_image_count(channels[0].eval())
    except Exception:
        pass

    par = getattr(getattr(count_op, 'par', None), 'value0', None)
    if par is None:
        panel = getattr(count_op, 'panel', None)
        if panel is None:
            return DEFAULT_IMAGE_COUNT

        for attr_name in ('value', 'state', 'select'):
            panel_value = getattr(panel, attr_name, None)
            if panel_value is None:
                continue

            try:
                raw_value = panel_value.eval() if hasattr(panel_value, 'eval') else panel_value
                return _clamp_image_count(raw_value)
            except Exception:
                continue

        return DEFAULT_IMAGE_COUNT

    try:
        return _clamp_image_count(par.eval())
    except Exception:
        return DEFAULT_IMAGE_COUNT


def _expected_scene_count():
    return min(len(KNOWN_SCENE_KEYS), _clamp_image_count(BATCH_STATE.get('expectedImageCount', DEFAULT_IMAGE_COUNT)))


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


def _reset_batch(capture_id='', expected_image_count=DEFAULT_IMAGE_COUNT):
    BATCH_STATE.update({
        'captureId': capture_id or '',
        'receivedSceneKeys': set(),
        'expectedImageCount': _clamp_image_count(expected_image_count),
        'isReady': False,
        'completedAt': '',
    })

    for scene_key in KNOWN_SCENE_KEYS:
        SCENE_STATES[scene_key] = _new_scene_state(capture_id or '')


def _register_scene(capture_id, scene_key, saved_at, expected_image_count):
    capture_id = capture_id or ''
    if capture_id != BATCH_STATE['captureId']:
        _reset_batch(capture_id, expected_image_count)
    else:
        BATCH_STATE['expectedImageCount'] = _clamp_image_count(expected_image_count)

    if scene_key in SCENE_STATES:
        BATCH_STATE['receivedSceneKeys'].add(scene_key)

    BATCH_STATE['isReady'] = len(BATCH_STATE['receivedSceneKeys']) >= _expected_scene_count()
    if BATCH_STATE['isReady']:
        BATCH_STATE['completedAt'] = saved_at or _utc_timestamp()


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
        ['batch.captureId', BATCH_STATE['captureId']],
        ['batch.receivedSceneKeys', ','.join(sorted(BATCH_STATE['receivedSceneKeys']))],
        ['batch.receivedSceneCount', len(BATCH_STATE['receivedSceneKeys'])],
        ['batch.expectedSceneCount', _expected_scene_count()],
        ['batch.isReady', int(BATCH_STATE['isReady'])],
        ['batch.completedAt', BATCH_STATE['completedAt']],
    ]

    for scene_key in KNOWN_SCENE_KEYS:
        state = SCENE_STATES[scene_key]
        rows.extend([
            ['{}.ready'.format(scene_key), int(bool(state['ready']))],
            ['{}.label'.format(scene_key), state['label']],
            ['{}.targetPath'.format(scene_key), state['targetPath']],
            ['{}.savedAt'.format(scene_key), state['savedAt']],
        ])

    table.clear()
    for row in rows:
        table.appendRow(row)


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

    _register_scene(
        payload.get('captureId', ''),
        scene_key,
        payload.get('savedAt', ''),
        payload.get('expectedImageCount', DEFAULT_IMAGE_COUNT)
    )
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
    _sync_info_table(payload, target_path or source_path)
    return True


def resync_latest_scenes(expected_capture_id=''):
    manifest = _fetch_latest_manifest()
    scenes = manifest.get('scenes', {}) if isinstance(manifest, dict) else {}
    payloads = []
    for payload in scenes.values():
        if not isinstance(payload, dict):
            continue
        if expected_capture_id and payload.get('captureId', '') != expected_capture_id:
            continue
        payloads.append(payload)

    payloads.sort(
        key=lambda item: item.get('sceneIndex', 0)
        if isinstance(item.get('sceneIndex', 0), int)
        else 0
    )
    for payload in payloads:
        _apply_capture_payload(payload)
    return bool(payloads)


def request_capture():
    image_count = _read_generation_count()
    if CONTROL_TRANSPORT.lower() == 'udp':
        payload = {
            'type': 'capture',
            'sessionId': SESSION_ID,
            'imageCount': image_count,
        }
        _send_udp_json(CONTROL_UDP_HOST, CONTROL_UDP_PORT, payload)
        _debug(
            'Queued remote capture command via udp://{}:{} (imageCount={}).'.format(
                CONTROL_UDP_HOST,
                CONTROL_UDP_PORT,
                image_count
            )
        )
        return payload

    url = '{}/api/touchdesigner-control/session/{}/capture'.format(
        SERVER_BASE_URL.rstrip('/'),
        SESSION_ID
    )
    response = _post_json(url, {'imageCount': image_count})
    command_id = response.get('command', {}).get('id', '?')
    _debug('Queued remote capture command via HTTP #{} (imageCount={}).'.format(command_id, image_count))
    return response


def _channel_name(channel):
    try:
        return str(channel.name).lower()
    except Exception:
        return ''


def _channel_owner_path(channel):
    owner = getattr(channel, 'owner', None)
    return getattr(owner, 'path', '') if owner is not None else ''


def _is_start_generation_key(channel):
    channel_name = _channel_name(channel)
    if channel_name not in START_GENERATION_KEY_CHANNELS:
        return False

    owner_path = _channel_owner_path(channel)
    return not START_GENERATION_KEYBOARD_OP_PATHS or owner_path in START_GENERATION_KEYBOARD_OP_PATHS


def _matches_stream_key(channel, channel_names):
    channel_name = _channel_name(channel)
    if channel_name not in channel_names:
        return False

    owner_path = _channel_owner_path(channel)
    return not STREAM_KEYBOARD_OP_PATHS or owner_path in STREAM_KEYBOARD_OP_PATHS


def _handle_panel_off_to_on(panelValue):
    owner_path = panelValue.owner.path

    if owner_path == START_GENERATION_BUTTON_PATH:
        return request_capture()
    if owner_path == START_STREAM_BUTTON_PATH:
        return start_stream()
    if owner_path == STOP_STREAM_BUTTON_PATH:
        return stop_stream()

    return


def _handle_chop_off_to_on(channel):
    if not _is_start_generation_key(channel):
        if _matches_stream_key(channel, START_STREAM_KEY_CHANNELS):
            _debug(
                'Starting WebRTC receiver from key "{}" on {}.'.format(
                    _channel_name(channel),
                    _channel_owner_path(channel) or '<unknown>'
                )
            )
            return start_stream()

        if _matches_stream_key(channel, STOP_STREAM_KEY_CHANNELS):
            _debug(
                'Stopping WebRTC receiver from key "{}" on {}.'.format(
                    _channel_name(channel),
                    _channel_owner_path(channel) or '<unknown>'
                )
            )
            return stop_stream()

        return

    _debug(
        'Queued remote capture command from key "{}" on {}.'.format(
            _channel_name(channel),
            _channel_owner_path(channel) or '<unknown>'
        )
    )
    return request_capture()


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


def onOffToOn(*args):
    if len(args) == 1:
        return _handle_panel_off_to_on(args[0])
    if len(args) >= 4:
        return _handle_chop_off_to_on(args[0])
    return


def whileOn(*args):
    return


def onOnToOff(*args):
    return


def whileOff(*args):
    return


def onValueChange(*args):
    return
