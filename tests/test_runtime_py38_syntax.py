"""Every tracked runtime .py file parses as Python 3.8 syntax, so the kit mounts on older hosts
(an f-string with a backslash in its expression broke kit_agent.py on 3.8-3.11)."""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def runtime_files():
    try:
        out = subprocess.run(['git', 'ls-files', 'runtime/*.py', 'runtime/**/*.py'], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        out = []
    files = sorted({ROOT / name for name in out}) or sorted((ROOT / 'runtime').rglob('*.py'))
    return [path for path in files if path.is_file()]


def pep701_only(path):
    """f-string expressions that only Python 3.12+ accepts (PEP 701). ``feature_version`` does not
    reject these on a 3.12+ interpreter, so look for them directly: a backslash or a comment inside
    the braces. On 3.8-3.11 ast.parse above already fails on them."""
    if sys.version_info < (3, 12):  # older parsers reject these themselves; their f-string positions are unreliable
        return
    source = path.read_text(encoding='utf-8')
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FormattedValue):
            segment = ast.get_source_segment(source, node.value) or ''
            if '\\' in segment:
                yield node.lineno, 'backslash inside an f-string expression (needs Python 3.12)'
            elif '#' in segment and not any(isinstance(n, ast.Constant) and isinstance(n.value, str)
                                            and '#' in n.value for n in ast.walk(node.value)):
                yield node.lineno, 'comment inside an f-string expression (needs Python 3.12)'


class RuntimeParsesOnPython38(unittest.TestCase):
    def test_every_runtime_file_parses_as_3_8(self):
        files = runtime_files()
        self.assertTrue(files, 'no runtime .py files found')
        failed = []
        for path in files:
            try:
                ast.parse(path.read_text(encoding='utf-8'), filename=str(path), feature_version=(3, 8))
            except SyntaxError as exc:
                failed.append(f'{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}')
                continue
            failed.extend(f'{path.relative_to(ROOT)}:{line}: {msg}' for line, msg in pep701_only(path))
        self.assertEqual(failed, [], 'runtime files that Python 3.8 cannot parse')


if __name__ == '__main__':
    unittest.main()
