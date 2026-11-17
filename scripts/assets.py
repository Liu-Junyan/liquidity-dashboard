"""Version the built asset graph so cached modules cannot cross frontend releases."""
import hashlib
import re
from pathlib import Path


def version_assets(directory):
    """Run once on a fresh build copy; never rewrite the checked-in sources."""
    directory = Path(directory)
    paths = sorted(path for path in (directory / 'assets').rglob('*') if path.is_file())
    digest = hashlib.sha256()
    for path in [directory / 'index.html', *paths]:
        digest.update(path.relative_to(directory).as_posix().encode() + b'\0')
        digest.update(path.read_bytes() + b'\0')
    version = digest.hexdigest()[:20]
    index = directory / 'index.html'
    index.write_text(re.sub(
        r'((?:src|href)=["\'])(\./assets/[^"\'?]+)(["\'])',
        lambda match: f'{match[1]}{match[2]}?v={version}{match[3]}',
        index.read_text(encoding='utf-8')), encoding='utf-8')
    # The entry-point query alone is insufficient: each static import has its
    # own cache key. Apply the same version to the full local module graph.
    for path in (directory / 'assets').glob('*.js'):
        path.write_text(re.sub(
            r'(\bfrom\s*|\bimport\s*)(["\'])(\./[^"\'?]+\.js)\2',
            lambda match: f'{match[1]}{match[2]}{match[3]}?v={version}{match[2]}',
            path.read_text(encoding='utf-8')), encoding='utf-8')
    return version
