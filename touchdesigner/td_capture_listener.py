import json

MOVIE_FILE_IN_OPS = {
    'sceneA': 'moviefilein_scene_a',
    'sceneB': 'moviefilein_scene_b',
    'sceneC': 'moviefilein_scene_c',
}
ORIGINAL_MOVIE_FILE_IN_OP = 'moviefilein_original'
INFO_TABLE_OP = 'capture_info'


def _set_info_table(payload, target_path):
    table = op(INFO_TABLE_OP)
    if not table:
        return

    table.clear()
    table.appendRow(['key', 'value'])
    table.appendRow(['sceneKey', payload.get('sceneKey', '')])
    table.appendRow(['label', payload.get('label', '')])
    table.appendRow(['captureId', payload.get('captureId', '')])
    table.appendRow(['filename', payload.get('filename', '')])
    table.appendRow(['savedAt', payload.get('savedAt', '')])
    table.appendRow(['targetPath', target_path])
    table.appendRow(['latestImagePath', payload.get('latestImageNormalizedPath', '')])
    table.appendRow(['sourceImagePath', payload.get('sourceImageNormalizedPath', '')])


def _get_target_movie_op(scene_key):
    target_name = MOVIE_FILE_IN_OPS.get(scene_key or '')
    if target_name and op(target_name):
        return op(target_name)
    return


def _get_original_movie_op():
    if ORIGINAL_MOVIE_FILE_IN_OP and op(ORIGINAL_MOVIE_FILE_IN_OP):
        return op(ORIGINAL_MOVIE_FILE_IN_OP)
    return


def _reload_movie(movie, file_path):
    movie.par.file = file_path
    movie.par.reloadpulse.pulse()


def onReceive(dat, rowIndex, message, bytes, peer):
    try:
        payload = json.loads(message)
    except Exception as exc:
        debug('TimeWarp bridge: invalid JSON {}'.format(exc))
        return

    scene_key = payload.get('sceneKey', '')
    target_path = payload.get('latestImageNormalizedPath') or payload.get('normalizedPath')
    source_path = payload.get('sourceImageNormalizedPath') or payload.get('sourceImageAbsolutePath')
    if not target_path and not source_path:
        debug('TimeWarp bridge: missing image paths')
        return

    target_movie = _get_target_movie_op(scene_key)
    original_movie = _get_original_movie_op()
    updated = False

    if target_path:
        if target_movie:
            _reload_movie(target_movie, target_path)
            updated = True
        else:
            debug('TimeWarp bridge: missing operator for scene {}'.format(scene_key))

    if source_path:
        if original_movie:
            _reload_movie(original_movie, source_path)
            updated = True
        else:
            debug('TimeWarp bridge: missing operator for original image')

    if not updated:
        return

    _set_info_table(payload, target_path or source_path)

    return
