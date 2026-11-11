"""Prepare the final edit's audio from ESCAPEMENT's public manifest.

Run after make_final5.py: python continuation/prepare_audio.py film
Downloads sources, applies their recorded trim/fades/gain, and writes 48 kHz stereo 24-bit WAVs.
Music and effects retain the licences listed in the manifest.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import NamedTemporaryFile
import urllib.parse
import urllib.request


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise ValueError(result.stderr.strip() or f'{command[0]} exited with {result.returncode}')
    return result.stdout


def duration(path):
    return float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                      '-of', 'csv=p=0', str(path)]).strip())


def inside(film, name, folder):
    path = (film / name).resolve()
    if not path.is_relative_to((film / folder).resolve()):
        raise ValueError(f'manifest path is outside {folder}: {name}')
    return path


def download(url, path):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'assets.mixkit.co', 'cdn.freesound.org'}:
        raise ValueError(f'unexpected audio source: {url}')
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        partial = Path(handle.name)
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'escapement-audio-preparation/1.0'})
        with urllib.request.urlopen(request, timeout=60) as response, partial.open('wb') as output:
            shutil.copyfileobj(response, output)
        if not partial.stat().st_size:
            raise ValueError(f'empty download: {url}')
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def prepare(film, item, overwrite):
    raw = inside(film, item['raw_file'], 'audio/raw')
    output = inside(film, item['file'], 'audio')
    if output.suffix.lower() != '.wav' or output == raw:
        raise ValueError(f'expected a separate WAV destination: {item["file"]}')
    if output.exists() and not overwrite:
        if duration(output) <= 0:
            raise ValueError(f'invalid existing audio: {item["file"]}; rerun with --overwrite')
        return 'kept'
    if not raw.is_file():
        download(item['direct_url'], raw)
    processing = item['processing']
    if 'window_s' in processing:
        start, end = processing['window_s']
        cut = True
    else:
        start = processing['lead_trim_s']
        end = duration(raw) - processing['tail_trim_s']
        cut = False
    if 'max_cut_s' in processing and end - start > processing['max_cut_s']:
        end = start + processing['max_cut_s']
        cut = True
    if not 0 <= start < end:
        raise ValueError(f'invalid trim for {item["file"]}')
    filters = [f'atrim=start={start:.5f}:end={end:.5f}', 'asetpts=PTS-STARTPTS', 'afade=t=in:d=0.0015']
    if cut:
        filters.append(f'afade=t=out:st={max(0.0, end - start - 0.08):.5f}:d=0.08')
    filters.extend([f'volume={processing["gain_db"]}dB', 'aresample=48000', 'aformat=channel_layouts=stereo'])
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(suffix='.wav', dir=output.parent, delete=False) as handle:
        partial = Path(handle.name)
    try:
        run(['ffmpeg', '-v', 'error', '-y', '-i', str(raw), '-af', ','.join(filters),
             '-c:a', 'pcm_s24le', '-ar', '48000', '-ac', '2', str(partial)])
        if duration(partial) <= 0:
            raise ValueError(f'empty prepared audio: {item["file"]}')
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)
    return 'prepared'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('film', nargs='?', default='film')
    parser.add_argument('--overwrite', action='store_true', help='rebuild existing prepared WAVs')
    args = parser.parse_args()
    film = Path(args.film).resolve()
    try:
        for tool in ('ffmpeg', 'ffprobe'):
            if not shutil.which(tool):
                raise ValueError(f'{tool} must be on PATH')
        manifest = json.loads((film / 'audio/manifest.json').read_text(encoding='utf-8'))
        cues = json.loads((film / 'edit/cues_final5.json').read_text(encoding='utf-8'))
        used = {entry['file'] for key in ('music', 'cues') for entry in cues.get(key, [])}
        items = {entry['file']: entry for entry in manifest['items']}
        missing = sorted(used - items.keys())
        if missing:
            raise ValueError(f'no manifest entries for {missing}')
        for index, name in enumerate(sorted(used), 1):
            result = prepare(film, items[name], args.overwrite)
            print(f'[{index}/{len(used)}] {result} {name}', flush=True)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f'[audio] {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
