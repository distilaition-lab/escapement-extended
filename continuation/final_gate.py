"""Build and verify shot evidence, record a director's review, and render approved shots."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory

HERE = Path(__file__).resolve().parent
FILM = HERE.parent / 'film'
REVIEW = HERE / 'review'
BLENDER = Path(os.environ.get('BLENDER', r'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe')).resolve()
PYTHON = BLENDER.parent / '5.2' / 'python' / 'bin' / 'python.exe'
VERSION = 1
TITLES = {'0T', '0E'}
GARAGE = {'9L', '9E', '9F'}
DUEL = {f'8{letter}' for letter in 'ABCDEFGH'}
CRASH = {'9A', '9B', '9C', '9D', '9V', '9W', '9G'}
DAY = {'7A'} | DUEL | CRASH
SCRIPTS = {
    **dict.fromkeys(TITLES, 'title.py'),
    '7A': 'shot_7a.py',
    **dict.fromkeys(DUEL, 'duel.py'),
    **dict.fromkeys(CRASH, 'finale.py'),
    **dict.fromkeys(GARAGE, 'garage.py'),
}
WARNINGS = re.compile(r'\b(?:error|traceback|warning|failed|not found|shadow buffer full)\b', re.I)


def require_shot(shot):
    if shot not in SCRIPTS:
        raise ValueError(f'unknown extension shot {shot!r}')


def require_script(script, shot):
    require_shot(shot)
    expected = HERE / SCRIPTS[shot]
    if Path(script).resolve() != expected.resolve():
        raise ValueError(f'{shot} must use {expected}')
    return expected


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as output:
        temp = Path(output.name)
        try:
            json.dump(value, output, indent=2)
        except Exception:
            output.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def load(shot):
    require_shot(shot)
    path = REVIEW / f'{shot}.json'
    return read_json(path) if path.is_file() else {}


def save(shot, record):
    require_shot(shot)
    write_json(REVIEW / f'{shot}.json', record)


@contextmanager
def shot_lock(shot):
    """The operating system releases the lock even when a process is interrupted."""
    require_shot(shot)
    REVIEW.mkdir(parents=True, exist_ok=True)
    with (REVIEW / f'{shot}.lock').open('a+b') as lock:
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError(f'{shot} already has a gate operation in progress') from error
        yield


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    return digest(path.read_bytes())


def source_id():
    """Hash the extension and upstream source trees, including the patched toolkit."""
    files = [FILM / 'shotlist.json']
    for folder in (HERE, FILM / 'lib', FILM / 'shots', FILM / 'tools'):
        files.extend(folder.glob('*.py'))
    paths = [(path.relative_to(HERE.parent).as_posix(), file_digest(path)) for path in sorted(files)]
    return digest(json.dumps(paths).encode())


def tool_id():
    tools = [BLENDER, PYTHON]
    for name in ('ffmpeg', 'ffprobe'):
        executable = shutil.which(name)
        if not executable:
            raise ValueError(f'{name} must be on PATH')
        tools.append(Path(executable).resolve())
    identities = []
    for path in tools:
        stat = path.stat()
        identities.append((str(path), stat.st_size, stat.st_mtime_ns))
    return digest(json.dumps([identities, os.environ.get('RB_NO_MB')]).encode())


def scene_options(shot, fog):
    if fog is None:
        return []
    if shot not in GARAGE:
        raise ValueError('--fog is available on garage shots only')
    return ['--fog', '0'] if fog == '0' else []


def run_blender(script, shot, args, log):
    env = dict(os.environ, BLENDER=str(BLENDER))
    command = [PYTHON, FILM / 'tools' / 'rb.py', script, '--', '--shot', shot, *args]
    with log.open('w', encoding='utf-8') as output:
        return subprocess.run(command, cwd=FILM, env=env, stdout=output, stderr=subprocess.STDOUT).returncode


def scan(log):
    return [line.strip()[:200] for line in log.read_text(encoding='utf-8', errors='replace').splitlines()
            if WARNINGS.search(line) and 'DIRECTOR NOTE' not in line
            and 'plane probe disabled' not in line.lower()]


def validate_probe(data, shot):
    expected = set() if shot in TITLES else {'Rival_root'}
    if shot not in TITLES | {'9L', '9E'}:
        expected.add('Car')
    bounds = data.get('frames')
    if not isinstance(bounds, list) or len(bounds) != 2:
        raise ValueError(f'missing scene frame range for {shot}')
    first, last = bounds
    manifest = data.get('manifest')
    if (data.get('shot') != shot or type(first) is not int or type(last) is not int or not 1 <= first <= last
            or not isinstance(manifest, dict) or set(manifest) != expected
            or not isinstance(data.get('findings'), list) or not all(isinstance(f, str) for f in data['findings'])
            or 'cam_mount' not in data or data['cam_mount'] not in expected | {None}):
        raise ValueError(f'incomplete or mismatched scene probe for {shot}')
    for actor, facts in manifest.items():
        frames = facts.get('cut_frames') if isinstance(facts, dict) else None
        if not isinstance(frames, list) or len(frames) != last - first + 1:
            raise ValueError(f'incomplete per-frame probe data for {shot}/{actor}')
        for frame in frames:
            if (not isinstance(frame, dict) or type(frame.get('visible')) is not bool
                    or type(frame.get('edge')) is not bool or not isinstance(frame.get('surfaces'), list)
                    or any(s is not None and not isinstance(s, str) for s in frame['surfaces'])
                    or 'gap' not in frame
                    or (frame['gap'] is not None and not isinstance(frame['gap'], (float, int)))):
                raise ValueError(f'invalid per-frame probe data for {shot}/{actor}')


def run_probe(script, shot, options):
    out = REVIEW / f'{shot}_probe.json'
    log = REVIEW / f'{shot}_probe.log'
    out.unlink(missing_ok=True)
    rc = run_blender(script, shot, ['--probe', str(out), *options], log)
    warnings = scan(log)
    if rc or warnings or not out.is_file():
        raise ValueError(f'{shot} scene probe failed (exit {rc}, warnings {warnings[:3]}). See {log}')
    data = read_json(out)
    validate_probe(data, shot)
    return data


def start_record(shot, options):
    old = load(shot)
    record = {'version': VERSION, 'open': old.get('open', []), 'options': options}
    save(shot, record)
    record.update(source=source_id(), tools=tool_id())
    return record


def require_current(record):
    if record.get('version') != VERSION or 'source' not in record or 'tools' not in record:
        raise ValueError('no current gate evidence; run a fresh preview or probe')
    if record['source'] != source_id() or record['tools'] != tool_id():
        raise ValueError('source code or tools changed; run a fresh preview or probe')


def probe(script, shot, options):
    record = start_record(shot, options)
    record['scene'] = run_probe(script, shot, options)
    require_current(record)
    save(shot, record)
    print(f"[gate] {shot}: {len(record['scene']['findings'])} scene findings")
    for finding in record['scene']['findings']:
        print(f'  {finding}')


def frame_names(scene, suffix, step=1):
    first, last = scene['frames']
    return [f'{n:04d}{suffix}' for n in range(first, last + 1, step)]


def verify_frames(outdir, names):
    paths = [outdir / name for name in names]
    actual = {path.name for path in outdir.glob(f'*{paths[0].suffix}')}
    if actual != set(names) or any(not p.is_file() or p.stat().st_size == 0 for p in paths):
        raise ValueError(f'expected {len(names)} complete frames in {outdir}, found {len(actual)}')
    return paths


def ffmpeg(args, cwd):
    result = subprocess.run(['ffmpeg', *args], cwd=cwd, capture_output=True, text=True, encoding='utf-8',
                            errors='replace')
    if result.returncode:
        raise ValueError(f'FFmpeg failed (exit {result.returncode}): {result.stderr.strip()}')
    return result.stderr


def concat_file(path, paths):
    # Only use known, generated basenames. FFmpeg's safe-path checks stay enabled.
    path.write_text(''.join(f'file {frame.name}\n' for frame in paths), encoding='ascii')


def exposure_findings(shot, picks):
    command = [PYTHON, FILM / 'tools' / 'exposure_check.py']
    if shot in DAY:
        command.append('--day')
    # Pass basenames from the frame directory so whitespace in a checkout path cannot affect the report.
    result = subprocess.run([*command, *(p.name for p in picks)], cwd=picks[0].parent,
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    checks = {}
    current = None
    for line in result.stdout.splitlines():
        if line in {p.name for p in picks}:
            if line in checks:
                raise ValueError(f'duplicate exposure result for {line}')
            current = line
            checks[current] = []
        elif current and line.strip() and not line.strip().startswith('luma '):
            checks[current].append(line.strip())
    if len(checks) != len(picks) or any(not values for values in checks.values()):
        raise ValueError(f'exposure check did not report every sample (exit {result.returncode}): {result.stderr.strip()}')
    problems = {f'exposure:{name}': '; '.join(values) for name, values in checks.items() if values != ['PASS']}
    if result.returncode != (2 if problems else 0):
        raise ValueError(f'exposure check failed (exit {result.returncode}): {result.stderr.strip()}')
    return problems


def event_strips(shot, findings, frames, outdir):
    rows = []
    for finding in findings:
        match = re.search(r':f(\d+)', finding)
        if match:
            center = int(match[1])
            nearest = sorted(frames, key=lambda p: abs(int(p.stem) - center))[:5]
            rows.append((finding, sorted(nearest)))
        if len(rows) == 10:
            break
    if not rows:
        return []
    listing = outdir / 'events.txt'
    concat_file(listing, [picks[min(i, len(picks) - 1)] for _, picks in rows for i in range(5)])
    image = outdir.parent / f'{shot}_events.jpg'
    ffmpeg(['-v', 'error', '-y', '-f', 'concat', '-i', listing.name, '-vf',
            f'scale=480:-2,tile=5x{len(rows)}', '-frames:v', '1', image], outdir)
    captions = image.with_suffix('.jpg.txt')
    captions.write_text('\n'.join(f'row {i}: {finding}' for i, (finding, _) in enumerate(rows, 1)),
                        encoding='utf-8')
    return [image, captions]


def preview(script, shot, options):
    record = start_record(shot, options)
    scene = run_probe(script, shot, options)
    record['scene'] = scene
    outdir = FILM / 'tests' / 'gate' / shot
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob('*.jpg'):
        old.unlink()
    sheet = outdir.parent / f'{shot}_sheet.jpg'
    for old in (sheet, outdir.parent / f'{shot}_events.jpg', outdir.parent / f'{shot}_events.jpg.txt'):
        old.unlink(missing_ok=True)
    log = REVIEW / f'{shot}_preview.log'
    rc = run_blender(script, shot, ['--anim', '--jpg', '--pct', '30', '--samples', '8', '--step', '2',
                                    '--outdir', str(outdir), *options], log)
    warnings = scan(log)
    if rc or warnings:
        raise ValueError(f'{shot} preview failed (exit {rc}, warnings {warnings[:3]}). See {log}')
    frames = verify_frames(outdir, frame_names(scene, '.jpg', step=2))
    listing = outdir / 'list.txt'
    concat_file(listing, frames)
    rows = math.ceil(len(frames) / 6)
    ffmpeg(['-v', 'error', '-y', '-f', 'concat', '-i', listing.name, '-vf',
            f'scale=320:-2,tile=6x{rows}', '-frames:v', '1', sheet], outdir)
    picks = [frames[i * (len(frames) - 1) // 5] for i in range(6)] if len(frames) > 6 else frames
    findings = exposure_findings(shot, picks)
    stats = ffmpeg(['-v', 'info', '-f', 'concat', '-i', listing.name, '-vf',
                    'signalstats,metadata=print:key=lavfi.signalstats.YAVG', '-f', 'null', '-'], outdir)
    luma = [float(value) for value in re.findall(r'lavfi\.signalstats\.YAVG=([0-9.]+)', stats)]
    if len(luma) != len(frames):
        raise ValueError(f'black-frame scan measured {len(luma)} of {len(frames)} preview frames')
    findings.update({f'near-black:{frame.name}': 'near-black frame' for frame, y in zip(frames, luma) if y < 14})
    findings.update({finding: 'scene probe finding' for finding in scene['findings']})
    events = event_strips(shot, scene['findings'], frames, outdir)
    artifacts = {}
    for path in [*frames, sheet, *events]:
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f'missing review artifact {path}')
        artifacts[path.relative_to(FILM).as_posix()] = file_digest(path)
    require_current(record)
    record['preview'] = {'artifacts': artifacts, 'findings': findings}
    save(shot, record)
    print(f'[gate] {shot}: {len(frames)} preview frames, {len(picks)} exposure samples, {len(findings)} findings')
    print(f'  contact sheet: {sheet}')
    for event in events:
        print(f'  event strip: {event}')
    for finding, description in findings.items():
        print(f'  {finding} — {description}')


def evidence_id(record):
    keys = ('source', 'tools', 'options', 'scene', 'preview', 'accepted')
    return digest(json.dumps([record.get(key) for key in keys], sort_keys=True).encode())


def require_preview(shot, record):
    require_current(record)
    if 'preview' not in record or 'scene' not in record:
        raise ValueError(f'{shot} has no completed preview; run preview first')
    scene = record['scene']
    validate_probe(scene, shot)
    artifacts = record['preview']['artifacts']
    expected = {f'tests/gate/{shot}/{name}' for name in frame_names(scene, '.jpg', step=2)}
    expected.add(f'tests/gate/{shot}_sheet.jpg')
    if not expected <= artifacts.keys():
        raise ValueError(f'{shot} preview is missing review artifacts')
    for name, checksum in artifacts.items():
        path = FILM / name
        if not path.resolve().is_relative_to(FILM.resolve()) or not path.is_file() or file_digest(path) != checksum:
            raise ValueError(f'{shot} preview artifact changed or is missing: {name}; run preview again')


def reasons(entries, findings):
    accepted = {}
    for entry in entries:
        key, separator, reason = entry.partition(': ')
        if not separator or key not in findings or not reason.strip() or key in accepted:
            raise ValueError(f'expected an exact, unique finding ID and reason: {entry!r}')
        accepted[key] = reason.strip()
    return accepted


def open_findings(record):
    return [*record.get('open', []),
            *(finding for finding in record['preview']['findings'] if finding not in record.get('accepted', {}))]


def review(args):
    shot = args.shot
    record = load(shot)
    if args.open is None and args.approve is None and not args.accepted:
        raise ValueError('review requires --open, --accepted or --approve')
    if args.reviewer is not None and args.approve is None:
        raise ValueError('--reviewer requires --approve')
    if args.open is not None:
        record['open'] = [line.strip() for line in args.open.split(';') if line.strip()]
        record.pop('approval', None)
    if args.accepted or args.approve is not None:
        require_preview(shot, record)
    if args.accepted:
        record.setdefault('accepted', {}).update(reasons(args.accepted, record['preview']['findings']))
        record.pop('approval', None)
    if args.approve is not None:
        if not args.approve.strip() or not (args.reviewer or '').strip():
            raise ValueError('approval requires a reviewer name and a note describing what they checked')
        outstanding = open_findings(record)
        if outstanding:
            raise ValueError(f'{shot} still has open findings: {outstanding}')
        record['approval'] = {'reviewer': args.reviewer.strip(), 'note': args.approve.strip(),
                              'evidence': evidence_id(record)}
    save(shot, record)
    print(f"[gate] {shot}: {'approved' if 'approval' in record else 'review pending'}")


def require_approval(shot, record):
    require_preview(shot, record)
    approval = record.get('approval', {})
    if approval.get('evidence') != evidence_id(record) or not approval.get('reviewer') or not approval.get('note'):
        raise ValueError('no director approval for this preview')
    outstanding = open_findings(record)
    if outstanding:
        raise ValueError(f'open findings: {outstanding}')


def publish(stage, output):
    """Swap the verified staging folder in for the shot's frames as one step. If the old folder cannot be moved
    (a file in use), nothing changes; if the new one cannot be moved in, the old one is put back."""
    previous = None
    if output.exists():
        previous = output.with_name(f'.{output.name}-previous-{os.getpid()}')
        output.rename(previous)
    try:
        stage.rename(output)
    except OSError:
        if previous is not None:
            previous.rename(output)
        raise
    if previous is not None:
        shutil.rmtree(previous, ignore_errors=True)


def final(script, shot, options, samples, pct):
    record = load(shot)
    require_approval(shot, record)
    if options != record['options']:
        raise ValueError(f'{shot} final must use the scene options from its reviewed preview')
    quality = []
    if samples is not None:
        quality += ['--samples', str(samples)]
    if pct is not None:
        quality += ['--pct', str(pct)]
    output = FILM / 'renders' / shot
    output.parent.mkdir(parents=True, exist_ok=True)
    record['final'] = {'status': 'in_progress'}
    save(shot, record)
    log = REVIEW / f'{shot}_final.log'
    try:
        with TemporaryDirectory(prefix=f'.{shot}-', dir=output.parent, ignore_cleanup_errors=True) as folder:
            stage = Path(folder)
            rc = run_blender(script, shot, ['--anim', '--outdir', folder, *quality, *options], log)
            warnings = scan(log)
            if rc or warnings:
                raise ValueError(f'final render failed (exit {rc}, warnings {warnings[:3]}). See {log}')
            frames = verify_frames(stage, frame_names(record['scene'], '.png'))
            require_approval(shot, record)
            publish(stage, output)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        record.pop('approval', None)
        record['final'] = {'status': 'failed', 'error': str(error)}
        save(shot, record)
        raise
    record['final'] = {'status': 'complete', 'frames': len(frames), 'quality': quality}
    save(shot, record)
    print(f'[gate] {shot}: rendered and verified {len(frames)} final frames in {output}')


def race_times():
    """Read the race times from the shot definitions."""
    times = {}
    for name in ('duel.py', 'finale.py'):
        source = (HERE / name).read_text(encoding='utf-8')
        for shot, first, last in re.findall(r"""'(\w\w)': \(([\d.]+), ([\d.]+), [\d.]+, ['"]""", source):
            times[shot] = float(first), float(last)
    return times


def location(shot):
    return 'garage' if shot in GARAGE else 'canyon'


def closing(frames):
    gaps = [frame['gap'] for frame in frames if frame['gap'] is not None]
    return len(gaps) >= 4 and gaps[0] - gaps[-1] > 1.0 and gaps[-1] < 15.0


def continuity(clips):
    seen = {'canyon': {'Car'}, 'garage': set()}
    problems = []
    previous = None
    times = race_times()
    for clip in clips:
        if clip is None or clip[0] in TITLES:
            previous = None
            continue
        shot, actors, mount = clip
        place = location(shot)
        prev, prior, prior_mount = previous or (None, {}, None)
        transition = '9L' in (prev, shot)
        for actor, frames in actors.items():
            first = frames[0]
            carried = transition and actor in prior
            if first['visible'] and actor not in seen[place] and not first['edge'] and not carried:
                problems.append(f'cut:{shot}:{actor}:appears-without-entrance')
            if any(frame['visible'] for frame in frames):
                seen[place].add(actor)
            if actor in prior:
                forward = not (prev in times and shot in times and times[shot][0] < times[prev][1] - 0.05)
                a = set(filter(None, prior[actor][-1]['surfaces']))
                b = set(filter(None, first['surfaces']))
                if location(prev) == place and forward and a and b and not a & b:
                    problems.append(f'cut:{prev}>{shot}:{actor}:surface-{"/".join(sorted(a))}->{"/".join(sorted(b))}')
                tail, head = prior[actor][-12:], frames[:12]
                if closing(tail) and closing(head):
                    last_gap = next(f['gap'] for f in reversed(tail) if f['gap'] is not None)
                    first_gap = next(f['gap'] for f in head if f['gap'] is not None)
                    if first_gap > last_gap + 2.0:
                        problems.append(f'cut:{prev}>{shot}:{actor}:approach-repeated')
        if prev:
            if mount and mount == prior_mount:
                problems.append(f'cut:{prev}>{shot}:same-camera-mount:{mount}')
            if location(prev) != place and not transition:
                problems.append(f'cut:{prev}>{shot}:place-changes-on-a-plain-cut')
        previous = clip
    return list(dict.fromkeys(problems))


def cuts(edl_path, exceptions):
    edl_path = Path(edl_path)
    edl_bytes = edl_path.read_bytes()
    edl = json.loads(edl_bytes)
    upstream = {shot['id'] for shot in read_json(FILM / 'shotlist.json')['shots']}
    clips, blockers = [], []
    scenes = {}
    skipped = 0
    source, tools = source_id(), tool_id()
    for clip in edl['clips']:
        shot = clip.get('shot') or Path(clip.get('src', clip.get('dir', ''))).parent.name
        if shot in upstream:
            skipped += 1
            clips.append(None)
            continue
        if shot not in SCRIPTS:
            blockers.append(f'unknown shot {shot!r}')
            continue
        try:
            if shot not in scenes:
                record = load(shot)
                if (record.get('version') != VERSION or record.get('source') != source
                        or record.get('tools') != tools or 'scene' not in record):
                    raise ValueError('missing or stale scene probe; run preview or probe')
                scene = record['scene']
                validate_probe(scene, shot)
                scenes[shot] = scene
            scene = scenes[shot]
            first, last = scene['frames']
            start, stop = clip.get('in', first), clip.get('out', last)
            if type(start) is not int or type(stop) is not int or not first <= start <= stop <= last:
                raise ValueError(f'clip range {start}–{stop} is outside the probed frames {first}–{last}')
            actors = {actor: facts['cut_frames'][start - first:stop - first + 1]
                      for actor, facts in scene['manifest'].items()}
            clips.append((shot, actors, scene['cam_mount']))
        except (OSError, ValueError) as error:
            blockers.append(f'{shot}: {error}')
    if not scenes and not blockers:
        blockers.append('no extension clips to check')
    if source_id() != source or tool_id() != tools or edl_path.read_bytes() != edl_bytes:
        blockers.append('sources, tools or edit changed during the cut check; run it again')
    findings = continuity(clips) if not blockers else []
    accepted = reasons(exceptions, findings) if not blockers else {}
    outstanding = [finding for finding in findings if finding not in accepted]
    write_json(REVIEW / '_cuts.json', {'edl': str(edl_path), 'edl_hash': digest(edl_bytes), 'source': source, 'blockers': blockers,
                                     'findings': findings, 'accepted': accepted, 'open': outstanding,
                                     'extension_clips': sum(clip is not None for clip in clips), 'upstream_clips': skipped})
    if blockers:
        print('[gate] cut check incomplete:')
        for reason in dict.fromkeys(blockers):
            print(f'  BLOCKED {reason}')
        return 1
    print(f'[gate] {sum(clip is not None for clip in clips)} extension clips checked, '
          f'{skipped} upstream clips excluded, {len(outstanding)} open findings')
    for finding in findings:
        print(f'  {"ACCEPTED" if finding in accepted else "OPEN"} {finding}')
    return int(bool(outstanding))


def status():
    for shot in sorted(SCRIPTS):
        if not (REVIEW / f'{shot}.json').is_file():
            continue
        record = load(shot)
        try:
            require_approval(shot, record)
        except (OSError, ValueError) as error:
            print(f'{shot}: BLOCKED — {error}')
        else:
            print(f"{shot}: READY — {record['approval']['reviewer']}: {record['approval']['note']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('preview', 'probe', 'final'):
        render = commands.add_parser(command)
        render.add_argument('script')
        render.add_argument('shot', choices=sorted(SCRIPTS))
        render.add_argument('--fog', choices=('0', '1'))
        if command == 'final':
            render.add_argument('--samples', type=int)
            render.add_argument('--pct', type=int)
    reviewing = commands.add_parser('review')
    reviewing.add_argument('shot', choices=sorted(SCRIPTS))
    reviewing.add_argument('--open')
    reviewing.add_argument('--approve')
    reviewing.add_argument('--reviewer')
    reviewing.add_argument('--accepted', action='append', default=[])
    cut = commands.add_parser('cuts')
    cut.add_argument('edl')
    cut.add_argument('--accepted', action='append', default=[])
    commands.add_parser('status')
    args = parser.parse_args()
    try:
        if args.command == 'cuts':
            return cuts(args.edl, args.accepted)
        if args.command == 'status':
            status()
            return 0
        with shot_lock(args.shot):
            if args.command == 'review':
                review(args)
            else:
                script = require_script(args.script, args.shot)
                options = scene_options(args.shot, args.fog)
                if args.command == 'preview':
                    preview(script, args.shot, options)
                elif args.command == 'probe':
                    probe(script, args.shot, options)
                else:
                    if args.samples is not None and args.samples < 1:
                        raise ValueError('--samples must be positive')
                    if args.pct is not None and not 1 <= args.pct <= 100:
                        raise ValueError('--pct must be between 1 and 100')
                    final(script, args.shot, options, args.samples, args.pct)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'[gate] {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
