import json

MOVIE_FILE_IN_OPS = {
    'sceneA': 'moviefilein_scene_a',
    'sceneB': 'moviefilein_scene_b',
    'sceneC': 'moviefilein_scene_c',
}
INFO_TABLE_OP = 'capture_info'


def _set_info_table(payload, target_path):
    table = op(INFO_TABLE_OP)
    if not table:
        return

    table.clear()
    table.appendRow(['key', 'value'])
    table.appendRow(['sceneKey', payload.get('sceneKey', '')])
    table.appendRow(['label', payload.get('label', '')])
    table.appendRow(['filename', payload.get('filename', '')])
    table.appendRow(['savedAt', payload.get('savedAt', '')])
    table.appendRow(['targetPath', target_path])
    table.appendRow(['latestImagePath', payload.get('latestImageNormalizedPath', '')])


def _get_target_movie_op(scene_key):
    target_name = MOVIE_FILE_IN_OPS.get(scene_key or '')
    if target_name and op(target_name):
        return op(target_name)
    return


def onReceive(dat, rowIndex, message, bytes, peer):
    try:
        payload = json.loads(message)
    except Exception as exc:
        debug('TimeWarp bridge: invalid JSON {}'.format(exc))
        return

    scene_key = payload.get('sceneKey', '')
    movie = _get_target_movie_op(scene_key)
    if not movie:
        debug('TimeWarp bridge: missing operator for scene {}'.format(scene_key))
        return

    target_path = payload.get('latestImageNormalizedPath') or payload.get('normalizedPath')
    if not target_path:
        debug('TimeWarp bridge: missing image path')
        return

    movie.par.file = target_path
    movie.par.reloadpulse.pulse()
    _set_info_table(payload, target_path)

    return
