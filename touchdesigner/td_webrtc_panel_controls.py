RECEIVER_DAT_PATH = '/project1/webrtc1_callbacks1'
WEBRTC_DAT_PATH = '/project1/webrtc1'
SESSION_ID = 'timewarp-local'

START_BUTTON_PATH = '/project1/start_stream_btn'
STOP_BUTTON_PATH = '/project1/stop_stream_btn'


def _debug(message):
    print('[TD WebRTC Controls] {}'.format(message))


def _receiver_dat():
    receiver_dat = op(RECEIVER_DAT_PATH)
    if receiver_dat is None:
        raise ValueError('Receiver DAT "{}" was not found.'.format(RECEIVER_DAT_PATH))
    return receiver_dat


def _receiver_module():
    return _receiver_dat().module


def start_stream():
    receiver_dat = _receiver_dat()
    _debug('Starting WebRTC receiver.')
    return _receiver_module().start(SESSION_ID, WEBRTC_DAT_PATH, receiver_dat.path)


def stop_stream():
    _debug('Stopping WebRTC receiver.')
    return _receiver_module().stop()


def onReceive(dat, rowIndex, message, bytes, peer):
    _debug(
        'This DAT is a Panel Execute callback, not a UDP In callback. '
        'Assign td_capture_listener.py to your UDP In DAT Callbacks DAT.'
    )
    return


def onOffToOn(panelValue):
    owner_path = panelValue.owner.path

    if owner_path == START_BUTTON_PATH:
        start_stream()
    elif owner_path == STOP_BUTTON_PATH:
        stop_stream()

    return


def whileOn(panelValue):
    return


def onOnToOff(panelValue):
    return


def whileOff(panelValue):
    return


def onValueChange(panelValue, prev):
    return
