#!/home2/hospi5ad/python312/python/bin/python3.12
# CGI bridge for BigRock shared hosting, where Apache is not reloaded to pick
# up Application Manager (Passenger) apps. Installed to <docroot>/cgi-bin/ by
# deploy_cpanel.sh; the shebang must point at the Python that has the deps.
import os
import sys
import time
from urllib.parse import unquote
from wsgiref.handlers import CGIHandler

APP_DIR = '/home2/hospi5ad/bromade_backend'
REQUEST_LOG = os.path.join(APP_DIR, 'logs', 'requests.log')
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from passenger_wsgi import application  # noqa: E402


def _log(line):
    try:
        with open(REQUEST_LOG, 'a') as fh:
            fh.write(line + '\n')
    except OSError:
        pass


def app(environ, start_response):
    # The .htaccess rewrite routes everything through this script, so rebuild
    # the path from the original URI instead of /cgi-bin/bromade.cgi/...
    environ['SCRIPT_NAME'] = ''
    environ['PATH_INFO'] = unquote(environ.get('REQUEST_URI', '/').split('?', 1)[0])
    auth = environ.get('HTTP_AUTHORIZATION') or environ.get('REDIRECT_HTTP_AUTHORIZATION')
    if auth:
        environ['HTTP_AUTHORIZATION'] = auth

    started = time.time()
    captured = {}

    def recording_start_response(status, headers, exc_info=None):
        captured['status'] = status
        return start_response(status, headers, exc_info)

    body = b''.join(application(environ, recording_start_response))
    status = captured.get('status', '')
    line = '%s %s %s %s %.2fs ua=%s' % (
        time.strftime('%Y-%m-%d %H:%M:%S'),
        environ.get('REQUEST_METHOD', ''),
        environ.get('REQUEST_URI', ''),
        status.split(' ', 1)[0],
        time.time() - started,
        environ.get('HTTP_USER_AGENT', '')[:60],
    )
    if status[:1] in ('4', '5'):
        line += ' body=' + body[:500].decode('utf-8', 'replace').replace('\n', ' ')
    _log(line)
    return [body]


CGIHandler().run(app)
