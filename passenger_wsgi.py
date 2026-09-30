import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# cPanel's Application Manager starts Passenger with the system Python, so
# re-exec into the project's virtualenv where the dependencies are installed.
VENV_DIR = os.path.join(BASE_DIR, '.venv')
VENV_PYTHON = os.path.join(VENV_DIR, 'bin', 'python')
if os.path.exists(VENV_PYTHON) and os.path.realpath(sys.prefix) != os.path.realpath(VENV_DIR):
    os.execl(VENV_PYTHON, VENV_PYTHON, *sys.argv)

sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from config.wsgi import application  # noqa: E402,F401
