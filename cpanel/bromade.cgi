#!/home2/hospi5ad/python312/python/bin/python3.12
# CGI bridge for BigRock shared hosting, where Apache is not reloaded to pick
# up Application Manager (Passenger) apps. Installed to <docroot>/cgi-bin/ by
# deploy_cpanel.sh; the shebang must point at the Python that has the deps.
import os
import sys
from urllib.parse import unquote
from wsgiref.handlers import CGIHandler

APP_DIR = '/home2/hospi5ad/bromade_backend'
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from passenger_wsgi import application  # noqa: E402


def app(environ, start_response):
    # The .htaccess rewrite routes everything through this script, so rebuild
    # the path from the original URI instead of /cgi-bin/bromade.cgi/...
    environ['SCRIPT_NAME'] = ''
    environ['PATH_INFO'] = unquote(environ.get('REQUEST_URI', '/').split('?', 1)[0])
    auth = environ.get('HTTP_AUTHORIZATION') or environ.get('REDIRECT_HTTP_AUTHORIZATION')
    if auth:
        environ['HTTP_AUTHORIZATION'] = auth
    return application(environ, start_response)


CGIHandler().run(app)
