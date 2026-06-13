import json
import socket

try:
    from urllib.request import Request, urlopen
except ImportError:
    from urllib2 import Request, urlopen


LISTENER_DAT_PATH = '/project1/td_capture_listener1'
SERVER_BASE_URL = 'http://127.0.0.1:3000'
SESSION_ID = 'timewarp-local'
REQUEST_TIMEOUT_SECONDS = 2.0
CONTROL_TRANSPORT = 'udp'
CONTROL_UDP_HOST = '127.0.0.1'
CONTROL_UDP_PORT = 9990


START_GENERATION_BUTTON_PATH = '/project1/start_generation_btn'
START_GENERATION_KEYBOARD_OP_PATHS = ('/project1/keyboardin1',)
START_GENERATION_KEY_CHANNELS = ('1', 'k1', 'num1', 'numpad1')


def _debug(message):
    print('[TD Capture Controls] {}'.format(message))


def _listener_dat():
    listener_dat = op(LISTENER_DAT_PATH)
    if listener_dat is None:
        raise ValueError('Listener DAT "{}" was not found.'.format(LISTENER_DAT_PATH))
    return listener_dat


def _listener_module():
    return _listener_dat().module


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


def display_scene(scene_key):
    _debug('Displaying {}.'.format(scene_key))
    return _listener_module().display_scene(scene_key)


def display_latest_ready_scene():
    _debug('Displaying latest ready scene.')
    return _listener_module().display_latest_ready_scene()


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


def _handle_panel_off_to_on(panelValue):
    owner_path = panelValue.owner.path

    if owner_path == START_GENERATION_BUTTON_PATH:
        return request_capture()

    return


def _handle_chop_off_to_on(channel):
    if not _is_start_generation_key(channel):
        return

    _debug(
        'Queued remote capture command from key "{}" on {}.'.format(
            _channel_name(channel),
            _channel_owner_path(channel) or '<unknown>'
        )
    )
    return request_capture()


def onReceive(dat, rowIndex, message, bytes, peer):
    _debug(
        'This DAT is a Panel Execute callback, not a UDP In callback. '
        'Assign td_capture_listener.py to your UDP In DAT Callbacks DAT.'
    )
    return


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
