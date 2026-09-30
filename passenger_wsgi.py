import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# cPanel's Application Manager starts Passenger with the system Python (3.6 on
# BigRock), so re-exec into the project's virtualenv or the standalone Python
# in ~/python312, whichever exists, where the dependencies are installed.
PYTHON_PREFIXES = [
    os.path.join(BASE_DIR, '.venv'),
    os.path.expanduser('~/python312/python'),
]


def _find_python():
    for prefix in PYTHON_PREFIXES:
        for name in ('python', 'python3.12'):
            candidate = os.path.join(prefix, 'bin', name)
            if os.path.exists(candidate):
                return prefix, candidate
    return None, None


_prefix, _python = _find_python()
if _python and os.path.realpath(sys.prefix) != os.path.realpath(_prefix):
    os.execl(_python, _python, *sys.argv)

sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from config.wsgi import application  # noqa: E402,F401
