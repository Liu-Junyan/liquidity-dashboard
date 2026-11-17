import re
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.assets import version_assets
from scripts.registry import ROOT


class AssetCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def build_copy(self, name):
        directory = self.root / name
        shutil.copytree(ROOT / 'site', directory)
        return directory

    def test_html_and_transitive_modules_share_versioned_relative_urls(self):
        directory = self.build_copy('build')
        version = version_assets(directory)
        html = (directory / 'index.html').read_text()
        urls = re.findall(r'(?:src|href)=["\'](\./assets/[^"\']+)', html)
        self.assertTrue(urls)
        self.assertTrue(all(url.endswith(f'?v={version}') for url in urls))
        for module in (directory / 'assets').glob('*.js'):
            imports = re.findall(r'from ["\']([^"\']+)', module.read_text())
            for reference in imports:
                self.assertTrue(reference.endswith(f'?v={version}'))
                self.assertTrue((module.parent / reference.split('?')[0]).is_file())
        self.assertIn('../data/${name}.json', (directory / 'assets/app.js').read_text())
        self.assertNotIn('?v=', (ROOT / 'site/index.html').read_text())

    def test_dependency_change_invalidates_entry_point_and_all_imports(self):
        first = self.build_copy('first')
        second = self.build_copy('second')
        dependency = second / 'assets/zh-CN.js'
        dependency.write_text(dependency.read_text() + '\n// A new frontend release.\n')
        before, after = version_assets(first), version_assets(second)
        self.assertNotEqual(before, after)
        self.assertIn(f'app.js?v={after}', (second / 'index.html').read_text())
        self.assertIn(f'./zh-CN.js?v={after}', (second / 'assets/data.js').read_text())

    def test_same_assets_have_stable_versions_while_data_is_revalidated(self):
        first, second = self.build_copy('first'), self.build_copy('second')
        (second / 'data/catalog.json').write_text('{}')
        self.assertEqual(version_assets(first), version_assets(second))
        self.assertIn("{cache: 'no-cache'}", (second / 'assets/app.js').read_text())


if __name__ == '__main__':
    unittest.main()
