"""Regression tests for the gate's release decisions, with Blender and FFmpeg replaced by test doubles."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from continuation import final_gate as gate


class GateTest(unittest.TestCase):
    def setUp(self):
        scratch = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(scratch)
        self.here = self.root / 'continuation'
        self.film = self.root / 'film'
        self.review = self.here / 'review'
        self.here.mkdir()
        (self.film / 'lib').mkdir(parents=True)
        self.upstream = self.film / 'lib' / 'common.py'
        self.upstream.write_text('# upstream')
        (self.film / 'shotlist.json').write_text('{"shots":[{"id":"3E"}]}')
        for script in set(gate.SCRIPTS.values()):
            (self.here / script).touch()
        self.enterContext(patch.multiple(gate, HERE=self.here, FILM=self.film, REVIEW=self.review))
        self.enterContext(patch.object(gate, 'tool_id', return_value='test tools'))
        self.blender = self.enterContext(patch.object(gate, 'run_blender', side_effect=self.render))
        self.ffmpeg = self.enterContext(patch.object(gate, 'ffmpeg', side_effect=self.measure))
        self.enterContext(patch.object(gate, 'exposure_findings', return_value={}))

    def scene(self, shot):
        actors = {}
        if shot not in gate.TITLES:
            actors['Rival_root'] = {'cut_frames': [self.frame() for _ in range(3)]}
            if shot not in {'9L', '9E'}:
                actors['Car'] = {'cut_frames': [self.frame() for _ in range(3)]}
        return {'shot': shot, 'frames': [1, 3], 'findings': [], 'manifest': actors, 'cam_mount': None}

    @staticmethod
    def frame(edge=True):
        return {'visible': True, 'edge': edge, 'surfaces': ['road'], 'gap': 0.0}

    def render(self, script, shot, args, log):
        log.write_text('rendered')
        if '--probe' in args:
            Path(args[args.index('--probe') + 1]).write_text(json.dumps(self.scene(shot)))
        else:
            folder = Path(args[args.index('--outdir') + 1])
            for name in (('0001.jpg', '0003.jpg') if '--jpg' in args else ('0001.png', '0002.png', '0003.png')):
                (folder / name).write_bytes(b'image')
        return 0

    @staticmethod
    def measure(args, cwd):
        if args[-1] == '-':
            return 'lavfi.signalstats.YAVG=100\n' * 2
        Path(args[-1]).write_bytes(b'contact sheet')
        return ''

    def cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['final_gate.py', *map(str, args)]), redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                result = gate.main()
            except SystemExit as error:
                result = error.code
        return result, stdout.getvalue() + stderr.getvalue()

    def shot(self, command, shot='8A', *options):
        return self.cli(command, self.here / gate.SCRIPTS[shot], shot, *options)

    def approve(self, shot='8A', *options):
        return self.cli('review', shot, '--approve', 'Checked the preview', '--reviewer', 'Test reviewer', *options)

    def store_scene(self, shot, scene=None):
        gate.save(shot, {'version': gate.VERSION, 'source': gate.source_id(), 'tools': gate.tool_id(),
                         'scene': self.scene(shot) if scene is None else scene})

    def check_cuts(self, *clips):
        edl = self.root / 'edit.json'
        edl.write_text(json.dumps({'clips': [dict(shot=shot, **bounds) for shot, bounds in clips]}))
        return self.cli('cuts', edl)

    def test_successful_preview_approval_and_final(self):
        self.assertEqual(self.shot('preview')[0], 0)
        self.assertEqual(self.approve()[0], 0)
        self.assertEqual(self.shot('final')[0], 0)
        self.assertEqual(gate.load('8A')['final']['frames'], 3)

    def test_zero_frames_and_incomplete_qc_cannot_be_approved(self):
        def empty_render(script, shot, args, log):
            if '--probe' in args:
                return self.render(script, shot, args, log)
            log.write_text('done')
            return 0

        self.blender.side_effect = empty_render
        self.assertIn('expected 2 complete frames', self.shot('preview')[1])
        self.assertEqual(self.approve()[0], 2)
        self.blender.side_effect = self.render
        self.ffmpeg.side_effect = lambda args, cwd: '' if args[-1] == '-' else self.measure(args, cwd)
        self.assertIn('black-frame scan measured 0 of 2', self.shot('preview')[1])
        self.assertEqual(self.approve()[0], 2)

    def test_incomplete_exposure_output_is_an_execution_failure(self):
        with patch.object(gate.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '0001.jpg\n  PASS\n', '')):
            with self.assertRaisesRegex(ValueError, 'did not report every sample'):
                ORIGINAL_EXPOSURE('8A', [self.root / '0001.jpg', self.root / '0003.jpg'])

    def test_approval_rejects_other_script_and_changed_artifacts(self):
        self.assertEqual(self.shot('preview')[0], 0)
        self.assertEqual(self.approve()[0], 0)
        other = self.root / 'duel.py'
        other.touch()
        self.assertIn('must use', self.cli('final', other, '8A')[1])
        (self.film / 'tests' / 'gate' / '8A_sheet.jpg').write_bytes(b'replaced')
        self.assertIn('preview artifact changed', self.shot('final')[1])

    def test_changed_upstream_code_invalidates_preview_and_cuts(self):
        self.assertEqual(self.shot('preview')[0], 0)
        self.assertEqual(self.approve()[0], 0)
        self.upstream.write_text('# changed upstream')
        self.assertIn('source code or tools changed', self.shot('final')[1])
        result, message = self.check_cuts(('8A', {}))
        self.assertEqual(result, 1)
        self.assertIn('missing or stale scene probe', message)

    def test_scene_options_and_exact_exception_ids(self):
        scene = self.scene('9L')
        scene['findings'] = ['floating:Rival_root:f1-3:20cm']
        with patch.object(self, 'scene', return_value=scene):
            self.assertEqual(self.shot('preview', '9L', '--fog', '0')[0], 0)
        self.assertEqual(self.approve('9L')[0], 2)
        self.assertEqual(self.approve('9L', '--accepted', 'floating: Partial ID')[0], 2)
        self.assertEqual(self.approve('9L', '--accepted', f"{scene['findings'][0]}: Intended action")[0], 0)
        self.assertIn('must use the scene options', self.shot('final', '9L')[1])

    def test_failed_final_clears_approval_and_leaves_previous_frames(self):
        self.assertEqual(self.shot('preview')[0], 0)
        self.assertEqual(self.approve()[0], 0)
        previous = self.film / 'renders' / '8A' / '0001.png'
        previous.parent.mkdir(parents=True)
        previous.write_bytes(b'old frame')

        def failed_render(script, shot, args, log):
            log.write_text('renderer stopped')
            return 17

        self.blender.side_effect = failed_render
        self.assertEqual(self.shot('final')[0], 2)
        self.assertEqual(previous.read_bytes(), b'old frame')
        self.assertNotIn('approval', gate.load('8A'))


    def test_completed_final_replaces_the_whole_previous_sequence(self):
        self.assertEqual(self.shot('preview')[0], 0)
        self.assertEqual(self.approve()[0], 0)
        output = self.film / 'renders' / '8A'
        output.mkdir(parents=True)
        (output / '0099.png').write_bytes(b'obsolete frame')
        self.assertEqual(self.shot('final')[0], 0)
        self.assertEqual(sorted(p.name for p in output.iterdir()), ['0001.png', '0002.png', '0003.png'])
        self.assertFalse(any(p.name.startswith('.') for p in output.parent.iterdir()))

    def test_failed_folder_publication_restores_the_previous_sequence(self):
        self.assertEqual(self.shot('preview')[0], 0)
        self.assertEqual(self.approve()[0], 0)
        output = self.film / 'renders' / '8A'
        output.mkdir(parents=True)
        (output / '0001.png').write_bytes(b'previous first frame')
        (output / '0002.png').write_bytes(b'previous second frame')
        rename = Path.rename

        def fail_stage_move(path, destination):
            if path.name.startswith('.8A-') and '-previous-' not in path.name:
                raise PermissionError('simulated stage publication failure')
            return rename(path, destination)

        with patch.object(Path, 'rename', autospec=True, side_effect=fail_stage_move):
            self.assertEqual(self.shot('final')[0], 2)
        self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()},
                         {'0001.png': b'previous first frame', '0002.png': b'previous second frame'})
        self.assertNotIn('approval', gate.load('8A'))
        self.assertFalse(any(p.name.startswith('.') for p in output.parent.iterdir()))

    def test_cut_requires_evidence_and_trim_coverage(self):
        result, message = self.check_cuts(('8A', {}))
        self.assertEqual(result, 1)
        self.assertIn('missing or stale scene probe', message)
        self.store_scene('8A')
        self.assertIn('outside the probed frames', self.check_cuts(('8A', {'out': 4}))[1])
        invalid = self.scene('8A')
        invalid['manifest'] = {}
        self.store_scene('8A', invalid)
        self.assertIn('incomplete or mismatched scene probe', self.check_cuts(('8A', {}))[1])

    def test_story_transition_carries_actor_and_end_card_is_outside_story(self):
        self.store_scene('9D')
        arrival = self.scene('9L')
        arrival['manifest']['Rival_root']['cut_frames'][1]['edge'] = False
        self.store_scene('9L', arrival)
        self.store_scene('0E')
        result, message = self.check_cuts(('3E', {}), ('9D', {}), ('9L', {'in': 2}), ('0E', {}))
        self.assertEqual(result, 0, message)
        self.assertIn('3 extension clips checked, 1 upstream clips excluded', message)
        self.store_scene('9E')
        self.assertIn('place-changes-on-a-plain-cut', self.check_cuts(('9D', {}), ('9E', {}))[1])

    def test_shot_id_cannot_escape_review_directory(self):
        self.assertEqual(self.approve('../sentinel')[0], 2)
        self.assertFalse((self.here / 'sentinel.json').exists())


ORIGINAL_EXPOSURE = gate.exposure_findings

if __name__ == '__main__':
    unittest.main()
