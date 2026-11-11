# How the extension was made

ESCAPEMENT's own README and notes explain its toolkit, its multi-agent method and its render/edit pipeline. This
document only covers what the extension added on top, and what we learned doing it. Read his first.

The extension was made by one Claude Code session directed by a human with short notes ("the blue car looks boxy",
"the ground comes twice"). Every note below that changed the method is quoted as a defect class, not a one-off fix.

---

## 1. One race, many cameras

The duel and the crash are not separate animations. There is one race timeline (`duel.py`): the hero's speed, the
gap between the cars, each car's lane and drift are functions of race time `T`. Each shot is a camera window onto
that race: `(T0, T1, timescale)`. A slow-motion shot is the same race with a smaller timescale.

- Interpolate keys with Catmull-Rom / cubic Hermite splines, not smoothstep: smoothstep stops at every key, which
  reads as the car hesitating ("the hero pauses, then drives on").
- Derive heading from the lane change (`lane_yaw`): the nose points where the car is going.
- When shots replay or run in parallel (a second angle of the same moment), they share the timeline, so continuity
  is free.
- A shot can have its own clock: the roof-cam fall (`9D`) runs in real time, then eases into 0.2x for the breach.
  Everything is keyed through `Tf(f)`, so a non-linear clock is one function.

## 2. A second car from scratch (`rival.py`)

The first rival looked toy-like next to his hero. What fixed it, from studying `lib/car.py`:

- Body from cross-section stations (y, width, height, ...), skinned and subdivided, then cut: panel gaps, door shut
  lines, headlamp slots and vents are cut into the skin. Never stick separate parts on top: they read as stickers.
- Split the skin into real panels (hood, doors, boot, nose, tail) with `recalc=False` normals, so the exploded view
  has real parts; delete the inner hull where it pokes through the nose.
- Details are ~30 small objects (mirrors, splitter, diffuser, roundels, numbers, handles), each attached to the
  panel it lives on, so doors carry their own roundels when the car comes apart.
- An engine, radiator, driveline, fuel cell, tub and seats exist only for the exploded view; they are never seen
  otherwise, and they are what makes the exploded view convincing.
- Helper lights are light-linked to the car only, with a low specular factor: otherwise they show up as hot
  rectangles in the paint ("a rectangle that shouldn't be there").

## 3. Physical truth, measured (`debris.py`, `finale.py`)

Things that looked fine in stills and were wrong, found by measuring the scene (section 5):

- **Ride height.** His toolkit places a car's root at the road's base height, but the road ribbon has a crown
  (+6 cm at the centre) and noise: the tyres sat 5-7 cm inside the asphalt. `debris.ride_z` computes the exact
  height of the built surface under each wheel (crowned road, gravel shoulder formula, terrain) and keys the root on it.
- **Tilt.** Rolling or pitching the root tilts the wheels with it and buries one side. `settle()` lowers or raises
  the root so the lowest *supported* tyre touches; wheels hanging over a drop carry nothing.
- **The rendered mesh wins.** A formula for the surface is not the mesh that renders: at a cliff lip the coarse
  terrain grid cuts the corner by up to 25 cm and the car hovered over the lip in a close-up. After the world is
  built, `ground_pass()` casts rays onto the built road, shoulder and terrain under each wheel, tilts the rigid car
  to its supported wheels (front/rear always, left/right when both sides touch) and re-keys height, pitch and roll.
- **A barrier that breaks.** A piece breaks when any of its points enters a car's body outline (plus margin), not
  when the car's centre nears the piece's middle: a 4 m rail can be hit at its end by a corner. It starts moving
  a beat before the body arrives and is thrown faster than the car. Every released piece's ballistic flight is
  checked against both cars' future paths; if they would meet, it is thrown harder, higher and further out.
- **Violence on the road.** Kicked stones (1.5-14 cm, tumbling, one bounce, settle), static gravel and rubber crumbs
  denser where the fights happen, and rubber marks that appear exactly as the tyre lays them (each vertex stores the
  race time it was laid; the material shows only what is older than "now"). All scale with an intensity curve: slide
  angle, lane-change rate, contact, wheelspin.

## 4. The breach: the ground is the boundary (`breach.py`)

The rival dives at the valley floor; as its nose touches, the ground shatters and it falls into a garage. This is
his 2G studio-disintegration debris system (`act2lib._gn_debris_group`: ragged accelerating wavefront, five convex
shard shapes, burst + suction + gravity, tumbling), aimed at the ground instead of a room. To make that possible the
patch adds three optional parameters to his function, defaults unchanged:

- `clamp_ground=False`: shards may fall through their rest level (his floor tiles stop at it).
- `cull_z`: shards are culled far below the hole, not at world zero.
- `tscale`: the shards' flight plays at the shot's slow-motion speed (his time is real seconds per frame).

Around it:

- The real ground dissolves exactly behind the wavefront (a distance mask in the floor material, keyed per frame),
  so the hole is a real hole.
- His `keep` zone: tiles directly under the car drop away instead of bursting into the lens.
- Pre-glow: in the last ~12 frames, glowing cracks spread from the impact point (a Voronoi edge mask, emissive,
  inside a growing radius), so the eye knows where it will break.
- A warm light under the hole, light-linked to the shards only: the break glows from inside.
- His act-2 studio is built under the floor, its ceiling fittings over the hole removed, its lights linked to the
  studio only (otherwise they light the canyon shards white).
- The next shot (`9L`) is the other side of the same hole: a floor camera in the garage looking up through a ragged
  ceiling hole at a dusk sky, the same debris system raining down, the car bursting through, flaring, landing.
- The valley floor got detail, because from the roof cam it read as one murky colour: dried-mud cracks, multi-scale
  earth colour and relief near the impact, and ~7,300 of his rocks, pebbles, scrub and grass instances.

## 5. The quality gate (`final_gate.py`, `probe.py`)

Rule: no full-quality render while any check is open. Each shot goes `preview` → `review` → `final`:

1. **Scene probe** (`probe.py`, no rendering). The shot script builds its scene and, instead of rendering, the probe
   reads it frame by frame and writes findings: body intersections (with depth, and whether the other piece was
   still standing), floating or sunk wheels, every touchdown and the surface touched, what an airborne car is over,
   one-frame jolts, stop-starts, cars appearing mid-frame, all tagged off-screen when the car is out of frame.
   Back-tested: it reports every defect the director found by eye in earlier versions.
2. **Preview**. Render every second frame across the full shot at 30% resolution and 8 samples. A completed
   preview requires the expected frames, a contact sheet, exposure results for up to six sampled frames, a
   black-frame measurement for every preview frame, and clean probe and render logs.
3. **Event strips**. The first ten probe events with frame numbers get larger strips. Inspect the preview frames
   for any remaining findings.
4. **Review**. A named reviewer looks at the preview and describes what they checked. Unresolved findings
   block approval. Deliberate exceptions identify the exact finding and give a reason. The approval is bound
   to the preview artifacts, source files, tool setup and scene options. The gate records the reviewer's
   declaration. A separate reviewer provides independence.
5. **Final**. Render the same shot with the reviewed scene options. A failed render or incomplete frame sequence
   returns an error and clears the approval.

And before any final: **a preview reel goes to the director.** The previews of the changed section are stitched
into a rough cut with the real sound. Notes cost minutes there and hours after the finals.

### Cut grammar (`final_gate.py cuts`, on the assembled edit)

- A car first seen in a location must enter from the frame edge or arrive through the transition shot.
- No cut between two shots from the same mounted camera: it reads as one shot repeated.
- One beat happens once: if the next clip starts further from the ground than the last one ended, the ground comes
  twice. Intercutting one continuous fall is fine; restarting the approach is not.
- A story location changes through a transition shot. Opening and closing titles sit outside the story.
- Surfaces are compared across a cut only when the action continues forward in time. The probe names
  the actual mesh face hit by the wheel ray and the check uses the clip's trimmed frame boundaries.
- Missing, stale or incomplete scene data blocks the cut check. The check covers extension clips and reports
  how many upstream clips were excluded.

## 6. Blender 5.2 traps we hit

- Camera eulers flip by ±180° between keys and motion blur draws a full spin: build each rotation with
  `to_euler('XYZ', previous)`.
- `scene.ray_cast` hits objects hidden from the render: skip `hide_render` objects, or switch them off with
  `hide_viewport` for the probe. A fog box flush with the floor makes rays slip past the floor.
- Objects placed with `.location` have a stale `matrix_world` until `view_layer.update()`.
- Rays down through a car's own dense tyre tread can run out of steps: measure the ground on the static scenery
  alone.
- `Material.use_nodes` now logs a deprecation warning: the gate counts it as a warning, so don't set it.
- Instanced geometry (scatter, geometry-nodes debris) has no polygons on the object itself: a BVH of the object is
  empty.

## 7. Numbers

- Extension: ~19 shots, ~40 s of new footage; full-quality EEVEE at 1080p, 48 samples, 2-10 s per frame on a
  mid-range desktop GPU.
- Gate previews: 25-60 s per shot. The scene probe: 1-3 min per shot.
