# ESCAPEMENT — Extended Edit

**This is an extension of [ESCAPEMENT](https://github.com/Leonxlnx/escapement) by Leon Lin ([@Leonxlnx](https://github.com/Leonxlnx)).**
His film, his toolkit and his method are the foundation of everything here: the canyon, the hero car, the studio,
the voxel and debris systems, the render runner, the grade and the mixer are his work, used under his MIT licence.
Start with his repo and his README. This repo only adds what is new, and never repeats what his already explains.

Extended by **Ai.chemyst**, with Claude Code.

## Watch or download

[Download the personal showcase (1080p MP4, 147 MB)](https://github.com/distilaition-lab/escapement-extended-clean/releases/download/v6/ESCAPEMENT_EXTENDED_SHOWCASE.mp4)
or open the [v6 release](https://github.com/distilaition-lab/escapement-extended-clean/releases/tag/v6).
GitHub's "Source code" ZIP contains the code; the MP4 is a separate release download.

The viewing edit is about **86 seconds**. Ai.chemyst added **"Wall of Sound"**, made with Suno on its free plan,
then lightly edited the soundtrack, slowed the crash and added heartbeat/boom effects from InShot's library.
The remaining picture comes from the rendered project. See [the viewing-edit notes and music prompt](docs/VIEWING_EDIT.md).

**Music and reuse:** this is a personal, non-monetised showcase. The Suno soundtrack and InShot library effects
are excluded from the MIT code licence; their own terms apply. This repo grants no commercial music rights.
Rebuilding the code below produces the original approximately 78-second edit and its manifest-based sound mix;
it does not recreate the later Suno soundtrack or manual InShot changes.

---

## What the extension adds

ESCAPEMENT's car section ends as the hero disappears into the canyon dust. The extension continues the story,
again with no 3D assets: every object, material, light and camera move is Python.

| Section | Shots | What happens |
|---|---|---|
| Intro | `0T` | His own brass title shot, with two lines added: the original author and "EXTENDED EDIT" |
| The rival | `7A` | The hero corners; the camera whips round and flies ~190 m back down the road to meet a new car, built from scratch |
| The duel | `8A`–`8H` | Bumper cam, 300 mm telephoto, wing mirror, bird's-eye, aerial pursuit, curb cam, door cam, slow-motion tandem drift over a cliff |
| The crash | `9A` `9C` `9B` `9W` `9G` | The barrier breaks, the rival goes over, the hero hangs over the edge, tyre close-up in the dirt, donut back onto the road |
| The fall | `9D` `9V` | Intercut: roof cam (sky, then ground) and a valley-floor cam looking up the cliff as the rival tumbles |
| The breach | `9D` → `9L` | The valley floor shatters at the rival's nose (his 2G debris system, aimed at the ground), and it falls into a garage |
| The garage | `9L` `9E` `9F` | Floor cam: it bursts through the ceiling, lands, drives in; exploded parts view; the hero drives in and both cars rev |
| End card | `0E` | His title shot again, the word swapped: "EXTENDED BY AI.CHEMYST" |

## Files

```
continuation/
  rival.py         the rival: an original front-engine GT, body stations, cut panels, ~30 details, V8/tub/seats for the exploded view
  shot_7a.py       7A: corner, whip, fly-back, meet
  duel.py          8A-8H: one race timeline, each shot a camera window onto it
  finale.py        9A-9D, 9V, 9W, 9G: barrier, edge, donut, the fall
  garage.py        9L, 9E, 9F: the landing, exploded view, both cars
  title.py         0T intro and 0E end card (his 6A title shot, extended)
  debris.py        kicked stones, road debris, rubber marks laid in time, exact ride height on the crowned road
  breach.py        the ground-shatter transition, the garage below, valley-floor detail, sky clouds
  probe.py         scene probe: physical findings read from the 3D scene before any preview
  final_gate.py    the quality gate: preview -> review -> final, plus the cut-continuity check
  make_cont.py     edit: his car section + 7A
  make_duel.py     edit: + the duel
  make_final5.py   edit: + the crash, the fall, the garage, intro and end card; cue sheet for the mixer
  prepare_audio.py download and prepare the final cue sheet's sounds from the upstream manifest
  brief.md         the 7A brief and receipts
patches/
  escapement.patch the only changes to his files: debris options, a scene-probe hook and audio input checks
docs/
  METHOD.md        how it was made, and what we learned building it
```

## Running it

This is an extension and needs the original ESCAPEMENT repository as well. Both repositories are public and can
be cloned without signing in to GitHub. An agent following these instructions needs a local terminal, permission
to write in its chosen project folder, and internet access to GitHub and the manifest's Mixkit/Freesound sources.
It also needs Git, Blender, FFmpeg and ffprobe installed on that machine.

The tested setup is Windows with Git, Blender 5.2, and both `ffmpeg` and `ffprobe` on PATH.
Run these commands in PowerShell from a folder where you want to install the project:

```powershell
git clone https://github.com/distilaition-lab/escapement-extended-clean.git escapement-extended
Set-Location escapement-extended
git clone --branch v1.0 https://github.com/Leonxlnx/escapement.git film
git -C film apply --check ../patches/escapement.patch
git -C film apply ../patches/escapement.patch

$env:BLENDER = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$py = Join-Path (Split-Path $env:BLENDER) '5.2/python/bin/python.exe'
& $py --version
ffmpeg -version
ffprobe -version
```

Change `BLENDER` if your installation is elsewhere. The tested upstream commit is
[`02cf7a4`](https://github.com/Leonxlnx/escapement/commit/02cf7a489e10975f6e18ab3af68d103758220b36).
The resulting layout has `continuation/`, `patches/` and the upstream checkout `film/` in the same directory.
Run the remaining commands from that directory.

### Render and review

Render the original shots used by the extension with upstream's render queue. Its `--dry` option lists the ranges
and missing frames before any rendering.

```powershell
& $py film/tools/render_queue.py 2A 2B 2C 2D 2E 2F 2G 3A 3B 3C 3D 3E 3F 3G 3H
```

Use the following script for each extension shot.

| Script | Shot IDs |
|---|---|
| `title.py` | `0T`, `0E` |
| `shot_7a.py` | `7A` |
| `duel.py` | `8A` through `8H` |
| `finale.py` | `9A`, `9B`, `9C`, `9D`, `9V`, `9W`, `9G` |
| `garage.py` | `9L`, `9E`, `9F` |

For example, build the `8A` preview:

```powershell
& $py continuation/final_gate.py preview continuation/duel.py 8A
```

Open `film/tests/gate/8A_sheet.jpg` and the preview frames in `film/tests/gate/8A/`. Where the probe
reports events, inspect the event strips and the corresponding frames. The person reviewing the shot
records their own name and what they checked before the final:

```powershell
& $py continuation/final_gate.py review 8A --reviewer "Reviewer name" --approve "Describe what you checked"
& $py continuation/final_gate.py final continuation/duel.py 8A
```

Use `review 8A --open "Describe the issue"` to record a visual issue. After checking the fix in a fresh preview,
use `--open ""` to clear the issue. A deliberate exception needs its exact printed finding ID and a reason, for
example `--accepted "exposure:0001.jpg: Intentional overexposure at the flash"`. Repeat `--accepted` for multiple
findings. Missing or failed checks must be rerun. A new preview invalidates the old approval and exceptions.
The gate verifies the evidence and records the reviewer's declaration. The production team supplies an independent
reviewer when it requires independent sign-off.

The gated preview covers the whole shot. The final accepts `--samples` and `--pct` for render quality.
If you use `--fog 0` on a garage shot, use it for both preview and final. Use upstream's runner for scratch renders.
Existing review records from older versions of the gate require a fresh preview.

### Assemble the edit

```powershell
& $py continuation/make_cont.py film
& $py continuation/make_duel.py film
& $py continuation/make_final5.py film
& $py continuation/final_gate.py cuts film/edit/edl_final5.json
```

The cut check needs a current scene probe for every extension clip, including the title cards. A preview runs
the probe automatically. To check cuts before rendering any previews, run `probe` with the same script, shot ID
and scene options as `preview`. Running `probe` on its own replaces that shot's preview record. The cut check
reports the upstream clips it excluded. Resolve open findings or record a deliberate exception by repeating
`--accepted "exact finding ID: reason"` on the cut command.

Prepare the 56 required sounds from the upstream manifest. This downloads each source from its listed
`direct_url`, applies its recorded trim, fade and gain, and writes 48 kHz stereo, 24-bit PCM WAVs at the paths
the mixer expects. Existing WAVs are kept. Add `--overwrite` to rebuild them.

```powershell
& $py continuation/prepare_audio.py film
```

The sounds retain the licences listed in `film/audio/manifest.json`. The mixer names any required files
that are missing. This step prepares ESCAPEMENT's original mix. The Suno soundtrack and manual InShot changes
in the viewing edit are separate, as described above.

```powershell
& $py film/tools/mix.py film/edit/cues_final5.json --out film/out/mix_final5.wav
& $py film/tools/edit.py film/edit/edl_final5.json --audio film/out/mix_final5.wav --out film/out/escapement_extended.mp4
```

The final film is written to `film/out/escapement_extended.mp4`. Check the assembled video's sound, black frames
and visible continuity before delivery.

## Credits

- **ESCAPEMENT** — film, toolkit and method by **Leon Lin** ([github.com/Leonxlnx/escapement](https://github.com/Leonxlnx/escapement)), MIT.
- **Extension** — Ai.chemyst, with Claude Code (Claude Opus 5.5) and Blender 5.2.
- Reconstructed music and sound effects: from ESCAPEMENT's `audio/manifest.json` (Mixkit / Freesound CC0), under their own licences.
  Source audio is downloaded separately.
- Viewing-edit music: **"Wall of Sound"**, made with Suno by [djkix93](https://suno.com/@djkix93), prompted by Ai.chemyst, on the free plan.
- Viewing-edit post-production: Ai.chemyst in InShot; soundtrack edits, crash slow motion and InShot-library heartbeat/boom effects.
  See [viewing-edit notes](docs/VIEWING_EDIT.md) for scope and separate audio terms.

## License

MIT, see [LICENSE](LICENSE). The files in `patches/` modify ESCAPEMENT's MIT-licensed code; his copyright notice
applies to those parts (see [NOTICE](NOTICE)). The viewing video's music and third-party library sounds are not
covered by MIT; see [viewing-edit notes](docs/VIEWING_EDIT.md).
