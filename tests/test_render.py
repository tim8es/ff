import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.render import load_project, make_frame, render_video


class ShortsRendererTests(unittest.TestCase):
    def test_validates_project(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json'
            path.write_text(json.dumps({'fps': 24, 'scenes': []}), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'scenes'):
                load_project(path)

    def test_generates_real_video(self):
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            self.skipTest('ffmpeg and ffprobe unavailable')
        project = {
            'width': 360, 'height': 640, 'fps': 12,
            'scenes': [
                {'duration': 1.2, 'type': 'title', 'title': 'НЕВЕРОЯТНЫЙ ФАКТ', 'caption': 'Кубики?'},
                {'duration': 1.2, 'type': 'compare', 'title': 'КУБ VS ШАР', 'left': 'КУБ', 'right': 'ШАР'}
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'video.mp4'
            frame = make_frame(project, project['scenes'][0], 0, 0)
            self.assertEqual(frame.size, (360, 640))
            render_video(project, Path(directory), output)
            self.assertGreater(output.stat().st_size, 1000)
            proc = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(output)], text=True,capture_output=True,check=True)
            self.assertAlmostEqual(float(proc.stdout), 2.4, delta=0.3)

    def test_missing_source_image_is_not_silently_ignored(self):
        project = {'width': 360, 'height': 640, 'fps': 12, 'scenes': [{'type': 'image', 'duration': 1, 'image': 'missing.png', 'title': 'A'}]}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                render_video(project, Path(directory), Path(directory) / 'x.mp4')


if __name__ == '__main__':
    unittest.main()
