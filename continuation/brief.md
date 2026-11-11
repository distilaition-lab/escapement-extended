# Continuation brief — shot 7A "RIVAL" (our own work, after ESCAPEMENT 3E)

Goal: test whether Claude can make NEW footage at ESCAPEMENT's quality bar without being handed the code for it.
Reused (continuity only): their canyon environment (`lib/canyon.py`), their hero car (`lib/car.py`), render runner,
grade and mixer. Ours: the rival car (`continuation/rival.py`, designed and modelled from scratch), the shot
(`continuation/shot_7a.py`: corner, camera move, timing, dust), the edit entry and the sound cues.

## The shot (one continuous move, 24 fps, 1920x1080, EEVEE, ~6 s)
| Frames | Beat | Numbers |
|---|---|---|
| 1–10 | Out of the dust | starts as 3E's last frame: featureless warm tan (≈205,196,187); lens dust clears by f10 |
| 1–36 | THE CORNER | hero takes the LEFT bend at s 625 (R ≈ 45 m) at 45 m/s, 10° drift slip, apex at f26; camera low (0.6 m) on the outside of the bend, 24 mm, pans with it; hero passes the lens ~4 m away |
| 36–50 | TURN | camera rises to 2.4 m and whips 180° to look back down the road the car came from |
| 50–86 | ULTRA-FAST PULL-BACK | camera flies backward along the road through the S-bend, peak ≈ 5.5 m/frame (≈ 130 m/s), lens 18 mm, motion blur streaks; drops to 1.2 m as it goes |
| 86–100 | MEET | camera brakes and reverses so it is flying ahead of the rival at the rival's speed; lens 18 → 32 mm |
| 100–144 | THE RIVAL | rival charging at 47 m/s, 4.4 s behind the hero, headlights on; camera 0.7 m high, 6 → 2.5 m ahead, front three-quarter; the rival closes on the lens at the end (cut) |

## The rival car (must read as a different car at a glance)
- Shape: front-engine long-hood grand tourer (hero = low mid-engine wedge). Length 4.7 m, width 2.0 m, height 1.22 m,
  wheelbase 2.8 m, wheel radius 0.36 m. Fenders rise above a sunken hood, cab set far back, fastback, ducktail.
- Colour: deep cobalt-blue metallic with twin pearl-white stripes (hero = black with teal accent and red light bar).
- Lights: slim warm-white LED headlight blades + amber DRL, round-ish quad projectors (hero has bars).
- Wheels: 10-spoke gunmetal, yellow calipers.

## Receipts (2026-11-09, v1 delivered)
- Rival car: written from scratch (`rival.py`, ~450 lines), 2 look-dev rounds (eyebrow headlights → LED slashes; splitter
  sticking out). Shot: 7 review rounds (stills v1–v7 + one motion test), fixes named by frame number.
- Final: 150 frames, 1080p, 48 samples, 5-step motion blur, 559.9 s (≈ 3.5 s/frame) on the RX 6650 XT, no errors.
  Finished with their `edit.py` (act-3 grade, grain, letterbox) + `mix.py` (their library, 12 new cues on the 120 BPM grid).
  Film: `film/out/escapement_rival.mp4` (22.7 s; our shot from 16.7 s), -12.5 LUFS, peak -1.5 dB.
- Exposure check (--day): 3 of 5 sampled frames PASS; 2 LOW CONTRAST (the hazy flight and the last frame).
- Mistakes caught in review: lens-dust sheets sized for the end lens; headlight spots aimed backward (glow under the car,
  "hovering"); spots 900 W blew out the road; mesa exclusion left a white "lake"; rim/sky lights mirrored white in the
  clearcoat (fixed with specular factor 0.12, light-linked to the rival only).
- Honest gaps vs their bar: the rival is simpler than their hero (fewer small parts, softer surfaces, deep arches); the
  "lake" still shows in the flight; the rival is 306 m (6.5 s) behind, not hot on the heels; two frames low contrast.

## Rival v2 — why their hero car reads as real, and what we applied (2026-11-09)
Studied `lib/car.py` (1,190 lines). The quality is four layers of craft, not one trick:
1. **Precise body definition:** 17 stations × 13 numbers (separate fender line, canopy width, side scoop) + creases on
   the character lines. v1 rival had 6 numbers per station → soft, blobby. v2: 23 stations, 10-point profile with a
   creased shoulder, sill and greenhouse base, and a side cove.
2. **Real panels:** nose / tail / doors / canopy are separate objects with real 7 mm gaps, solidified with matte rims,
   and a matte inner hull 14 mm under the skin so gaps never show light. v2: gaps + inner hull + separate glass with an
   inset rubber window frame; openings (grille mouth, brake ducts, headlamp slots) are cut INTO the skin, never stuck on.
3. **Detail density (~30 parts):** slats, vents, louvres, fin, skirts, buttresses, winged exhaust bay, segmented lights
   in black bezel channels, accent-coloured aero, 64 screws, visible suspension, engine. v2: ~35 parts — recessed
   headlamps (LED blade + 3 projectors + chrome rings), slatted grille + emblem, splitter + yellow lip + tow hook + 21
   screws, brake ducts, hood extractor vents + hood pins, side gills, skirts, side exhausts in heat shields, mirrors with
   glass, flush handles, race roundels "07" conformed to the door, race fuel filler + 8 screws, ducktail, twin round tail
   lamps in bezels, finned diffuser, rear mesh, wiper, wishbones + coil-overs.
4. **Micro-detail in every material:** carbon twill, lathe rings (anisotropic), drilled discs (polar voronoi), tyre
   sidewall lettering, flake + pinstripes. v2: all of those in our own parameters + heat-tinted titanium exhausts.
5. **Wheels are assemblies:** grooved tyres (wider rear), barrel + machined lip, tapered lofted spokes with machined
   faces, centre lock, drilled disc + bell, lofted caliper. v2: same structure, own design (5×2 spokes, 3-eared spinner).
Mistakes caught in look-dev: number text sank into the curved door (fix: orient to the surface normal, lift 7 mm);
grille/ducts/lamps were "stuck on" a closed skin (fix: cut openings, then bisect the slot lines for clean edges);
headlamp bezels as tubes read as black cigars (fix: recessed ribbon behind the slot); beam pools too bright (120 → 40 W).

## Look rules (theirs, kept)
Dusk: sun ≈ 4° behind the rival (back-lit dust, rim light), teal sky, rust rock. Nothing clips: practical emissions
2–8, shoulder on, exposure-check every still (`--day` for this exterior). Effects look real: dust volumetric and lit,
no glow particles. Budget ≤ 30 s/frame at full size.
