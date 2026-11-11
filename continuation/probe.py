"""SCENE PROBE — physical-plausibility facts for one shot, read from the 3D scene (no rendering).

Why: the picture checks (exposure, black frames, log warnings) and a contact-sheet glance missed every material defect
the user found: a car passing through the barrier, a car touching down on a surface it should never reach, a car
appearing from nowhere, a vertical blip, a stop-start. Those are facts about geometry and motion, so they are measured
from the scene and written down as findings. The gate refuses a final until each finding is fixed or accepted with a
written reason, so nothing physical goes through on intention alone.

Run by the gate:  rb.py <script> -- --shot X --probe <out.json>   (common.finish calls probe.run instead of rendering)

Findings (each has an id the reviewer must accept or fix):
  intersect   a car body overlaps another solid (barrier piece, the other car, terrain, floor) over frames a-b
  floating    a wheel contact point is > FLOAT_M above whatever is under it (while the car is meant to be driving)
  sunk        a wheel contact point is > SINK_M below the surface under it
  touchdown   a car goes from airborne to touching a surface: names the surface (is it the one the story wants?)
  surface     the surface under a car changes kind (road -> terrain -> floor ...)
  pop         a one-frame vertical jolt of a car root (second difference > POP_M) that is not free fall
  stopstart   a car's speed drops below STOP_MS and rises again inside the shot
  popin       a car becomes visible inside the frame without crossing a frame edge (appears from nowhere)
Manifest (for the cut check): per car, visible at first/last frame, screen position, surface under it.
"""
import json, math
import bpy
from mathutils import Vector as V
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view

FLOAT_M, SINK_M, POP_M, STOP_MS = 0.07, 0.03, 0.03, 0.8
INTERSECT_TOL = 0.02     # deeper than this through a surface is a visible clip
# car roots by object name -> wheel contact points in root space (x, y, z=0 at the tyre bottom)
ACTORS = {
    'Car': [(-0.86, 1.35, 0.0), (0.86, 1.35, 0.0), (-0.86, -1.35, 0.0), (0.86, -1.35, 0.0)],
    'Rival_root': [(-0.87, 1.40, 0.0), (0.87, 1.40, 0.0), (-0.87, -1.40, 0.0), (0.87, -1.40, 0.0)],
}
LABEL = {'hero': 'Car', 'rival': 'Rival_root'}
SKIP_PARTS = ('wheel', 'tyre', 'tire', 'rim', 'brake', 'caliper', 'disc', 'hub', 'spoke', 'flip', 'corner', 'susp',
              'light', 'lamp', 'glow', 'beam', 'spill')
SKIP_OTHERS = ('kick', 'impact', 'chunk', 'chip', 'spk', 'grit', 'dust', 'smoke', 'puff', 'burn', 'slide', 'rubber',
               'tyremark', 'roadbits', 'deb', 'mote', 'spark', 'haze', 'fog', 'shard', 'grind', 'flash')


def _descendants(o):
    out = []
    for c in o.children:
        out.append(c); out += _descendants(c)
    return out


def _is_volume(o):
    for m in (o.data.materials if o.type == 'MESH' else []):
        if m and m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == 'OUTPUT_MATERIAL' and n.inputs['Volume'].is_linked and not n.inputs['Surface'].is_linked:
                    return True
    return False


def _animated(o):
    p = o
    while p is not None:
        if p.animation_data and p.animation_data.action:
            return True
        p = p.parent
    return False


def _bvh(objs, dg, owners=None):
    verts, polys = [], []
    for o in objs:
        oe = o.evaluated_get(dg)
        try:
            me = oe.to_mesh()
        except Exception:
            continue
        if me is None:
            continue
        mw = oe.matrix_world
        base = len(verts)
        verts += [mw @ v.co for v in me.vertices]
        polys += [[base + i for i in p.vertices] for p in me.polygons]
        if owners is not None:
            owners.extend([o.name] * len(me.polygons))
        oe.to_mesh_clear()
    _bvh.verts = verts
    return BVHTree.FromPolygons(verts, polys) if polys else None


GROUNDS = ('road', 'terrain', 'shoulder', 'floor', 'ground', 'desert', 'cliff')


def _depth(verts, tree, other_name, cap=4000):
    """how deep the body goes into the other thing.
    ground-like surfaces: the largest height of surface above a body vertex (ray straight up, face facing up);
    anything else: largest distance of a body vertex behind the nearest face, ignoring > 0.3 m (open thin meshes)."""
    step = max(1, len(verts) // cap)
    d = 0.0
    ground = any(k in other_name.lower() for k in GROUNDS)
    for v in verts[::step]:
        if ground:
            loc, nrm, idx, dist = tree.ray_cast(v, V((0, 0, 1)), 1.0)
            if loc is not None and nrm.z > 0.3:
                d = max(d, dist)
        else:
            loc, nrm, idx, dist = tree.find_nearest(v, 0.3)
            if loc is not None and (v - loc).dot(nrm) < 0:
                d = max(d, dist)
    return d


def _world_bbox(objs):
    lo, hi = V((1e9, 1e9, 1e9)), V((-1e9, -1e9, -1e9))
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ V(c)
            lo = V((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
            hi = V((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
    return lo, hi


def _kind(name):
    n = name.lower()
    for k, lab in (('road', 'road'), ('barr', 'barrier'), ('rail', 'barrier'), ('post', 'barrier'), ('floor', 'floor'),
                   ('vox', 'floor'), ('tile', 'floor'), ('ground', 'terrain'), ('terrain', 'terrain'), ('desert', 'terrain'),
                   ('cliff', 'terrain'), ('butte', 'terrain'), ('rock', 'terrain'), ('wall', 'wall')):
        if k in n:
            return lab
    return 'other:' + name


def _runs(frames):
    """[1,2,3,7,8] -> [(1,3),(7,8)] (frames sampled at a step are joined when within 2 steps)."""
    out = []
    for f in sorted(frames):
        if out and f - out[-1][1] <= 4:
            out[-1][1] = f
        else:
            out.append([f, f])
    return [tuple(r) for r in out]


def run(shot, out_path, step=2):
    sc = bpy.context.scene
    cam = sc.camera
    f0, f1 = sc.frame_start, sc.frame_end
    actors = {}
    for name, wheels in ACTORS.items():
        root = bpy.data.objects.get(name)
        if root is None:
            continue
        desc = _descendants(root)
        body = [o for o in desc if o.type == 'MESH' and not o.hide_render and not any(k in o.name.lower() for k in SKIP_PARTS)
                and not _is_volume(o)]
        actors[name] = dict(root=root, wheels=wheels, body=body, members=set(o.name for o in desc) | {name})
    members_all = set().union(*[a['members'] for a in actors.values()]) if actors else set()
    # the probe never needs fog, dust, sparks, chunks or hidden helpers: switch them off for ray casts entirely
    # (a fog box flush with the floor made every downward ray slip past the floor)
    for o in sc.objects:
        if o.name in members_all or o.type != 'MESH':
            continue
        if o.hide_render or any(k in o.name.lower() for k in SKIP_OTHERS) or _is_volume(o):
            o.hide_viewport = True
    solids_static, solids_dyn = [], []
    for o in sc.objects:
        if o.type != 'MESH' or o.hide_render or o.name in members_all:
            continue
        nl = o.name.lower()
        if any(k in nl for k in SKIP_OTHERS) or _is_volume(o):
            continue
        if not o.data.polygons:
            continue
        if max(o.dimensions) < 0.3:
            continue
        (solids_dyn if _animated(o) else solids_static).append(o)
    dg = bpy.context.evaluated_depsgraph_get()
    sc.frame_set(f0)
    dg = bpy.context.evaluated_depsgraph_get()
    static_bvh = {o.name: (_bvh([o], dg), _world_bbox([o])) for o in solids_static}
    # the ground under the wheels, measured on the static scenery alone: rays through the car's own wheel parts ran out
    # of steps (dense tyre tread) and left wheels unmeasured -> false 'floating'
    ground_owners = []
    ground_tree = _bvh(solids_static, dg, ground_owners)
    rest = {o.name: o.matrix_world.translation.copy() for o in solids_dyn}     # where each moving solid starts
    hits = {}          # (kind, actor, other) -> frames
    track = {n: [] for n in actors}
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for n, a in actors.items():
            M = a['root'].matrix_world
            pos = M.translation.copy()
            # visibility on screen (8 bbox corners of the body)
            lo, hi = _world_bbox(a['body'] or [a['root']])
            corners = [V((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
            proj = [world_to_camera_view(sc, cam, c) for c in corners] if cam else []
            inside = [p for p in proj if 0 <= p.x <= 1 and 0 <= p.y <= 1 and p.z > 0]
            touches_edge = len(inside) < len(proj)
            sx = sum(p.x for p in inside) / len(inside) if inside else None
            # surface under each wheel
            gaps, kinds = [], []
            for w in a['wheels']:
                c = M @ V(w)
                start = c + V((0, 0, 0.15))
                d = V((0, 0, -1))
                hit_kind, gap = None, None
                if ground_tree is not None:
                    loc_, nrm_, idx_, dist_ = ground_tree.ray_cast(c + V((0, 0, 0.5)), d, 60.0)
                    if loc_ is not None:
                        # The BVH hit identifies the actual face, even when object bounds overlap.
                        hit_kind, gap = _kind(ground_owners[idx_]), c.z - loc_.z
                for _ in range(0 if gap is not None and gap < 1.5 else 60):
                    ok, loc, nrm, idx, ob, mx = sc.ray_cast(dg, start, d, distance=60.0)
                    if not ok:
                        break
                    if ob.name in a['members'] or ob.hide_render or any(k in ob.name.lower() for k in SKIP_OTHERS) \
                            or _is_volume(ob) or max(ob.dimensions) < 0.3:
                        start = loc + d * 1e-5
                        continue
                    hit_kind, gap = _kind(ob.name), c.z - loc.z
                    break
                gaps.append(gap); kinds.append(hit_kind)
            track[n].append(dict(f=f, pos=pos, vis=bool(inside), edge=touches_edge, sx=sx, gaps=gaps, kinds=kinds))
            if (f - f0) % step:
                continue
            # body intersections
            if not a['body']:
                continue
            blo, bhi = _world_bbox(a['body'])
            blo -= V((0.05, 0.05, 0.05)); bhi += V((0.05, 0.05, 0.05))
            bb = None
            cands = []
            for nm, (t, (slo, shi)) in static_bvh.items():
                if t is not None and slo.x <= bhi.x and shi.x >= blo.x and slo.y <= bhi.y and shi.y >= blo.y and slo.z <= bhi.z and shi.z >= blo.z:
                    cands.append((nm, t))
            for o in solids_dyn:
                slo, shi = _world_bbox([o])
                if slo.x <= bhi.x and shi.x >= blo.x and slo.y <= bhi.y and shi.y >= blo.y and slo.z <= bhi.z and shi.z >= blo.z:
                    cands.append((o.name, None))
            for m2, a2 in actors.items():
                if m2 != n and a2['body']:
                    slo, shi = _world_bbox(a2['body'])
                    if slo.x <= bhi.x and shi.x >= blo.x and slo.y <= bhi.y and shi.y >= blo.y:
                        cands.append((m2, 'actor'))
            if not cands:
                continue
            bb = _bvh(a['body'], dg)
            if bb is None:
                continue
            body_verts = _bvh.verts
            for nm, t in cands:
                if t == 'actor':
                    t = _bvh(actors[nm]['body'], dg)
                elif t is None:
                    t = _bvh([bpy.data.objects[nm]], dg)
                if t is not None and bb.overlap(t):
                    dep = _depth(body_verts, t, nm)
                    o_ = bpy.data.objects.get(nm)
                    standing = o_ is not None and nm in rest and (o_.matrix_world.translation - rest[nm]).length < 0.02
                    hits.setdefault(('intersect', n, nm + (' (still standing)' if standing else '')), []).append((f, dep))
    findings = []
    visf = {n: {s_['f'] for s_ in tr if s_['vis']} for n, tr in track.items()}

    def seen(n, a_, b_):
        return any(a_ <= f <= b_ for f in visf.get(n, ()))
    for (k, n, nm), fd_ in sorted(hits.items()):
        dmap = dict(fd_)
        for a_, b_ in _runs(list(dmap)):
            dep = max(v for f, v in dmap.items() if a_ <= f <= b_)
            sev = 'MAJOR' if (dep >= INTERSECT_TOL or 'still standing' in nm) else 'minor'
            if not seen(n, a_, b_):
                sev = 'offscreen'
            findings.append(f'intersect:{n}~{nm}:f{a_}-{b_}:{dep * 100:.0f}cm:{sev}')
    manifest = {}
    for n, tr in track.items():
        fl, sk, pops, td, surf, over = [], [], [], [], [], []
        prev_on, prev_kind, air = None, None, 0
        for i, s in enumerate(tr):
            g = [x for x in s['gaps'] if x is not None]
            ks = [k for k in s['kinds'] if k]
            on = bool(g) and min(g) < FLOAT_M
            if g and min(g) > FLOAT_M and min(g) < 1.5:
                fl.append(s['f'])
            if g and min(g) < -SINK_M:
                sk.append(s['f'])
            kind = max(set(ks), key=ks.count) if ks else 'none'
            if on and air >= 3:
                td.append(f"touchdown:{n}:f{s['f']}:on-{kind}")
            air = 0 if on else air + 1
            if on:
                surf.append((s['f'], kind))
            elif ks:
                over.append((s['f'], kind))
            prev_on = on
            if 0 < i < len(tr) - 1:
                z0, z1, z2 = tr[i - 1]['pos'].z, s['pos'].z, tr[i + 1]['pos'].z
                dd = z0 - 2 * z1 + z2
                if abs(dd) > POP_M and not (dd < 0 and abs(dd + 9.8 * (1 / 24) ** 2) < 0.02):
                    pops.append(s['f'])
        # surface changes under a grounded car, ignoring flicker: a new kind must hold for 3+ grounded frames
        stable, run_k, run_n, run_f = None, None, 0, None
        changes = []
        for f_, k_ in surf:
            if k_ == run_k:
                run_n += 1
            else:
                run_k, run_n, run_f = k_, 1, f_
            if run_n == 3 and run_k != stable:
                if stable is not None:
                    changes.append(f'surface:{n}:f{run_f}:{stable}->{run_k}')
                stable = run_k
        surf = changes
        sp = [(tr[i + 1]['pos'] - tr[i]['pos']).length * 24.0 for i in range(len(tr) - 1)]
        moving = [x > STOP_MS for x in sp]
        for i in range(1, len(moving) - 1):
            if not moving[i] and any(moving[:i]) and any(moving[i + 1:]):
                findings.append(f'stopstart:{n}:f{tr[i]["f"]}')
                break
        gmin = {s_['f']: min([x for x in s_['gaps'] if x is not None], default=0.0) for s_ in tr}
        for a_, b_ in _runs(fl):
            findings.append(f'floating:{n}:f{a_}-{b_}:{max(gmin[f] for f in fl if a_ <= f <= b_) * 100:.0f}cm')
        for a_, b_ in _runs(sk):
            findings.append(f'sunk:{n}:f{a_}-{b_}:{-min(gmin[f] for f in sk if a_ <= f <= b_) * 100:.0f}cm')
        for a_, b_ in _runs(pops):
            findings.append(f'pop:{n}:f{a_}-{b_}')
        findings += td + surf
        for kind_ in sorted(set(k for _, k in over)):     # what an airborne car is falling/flying toward
            for a_, b_ in _runs([f for f, k in over if k == kind_]):
                findings.append(f'over:{n}:f{a_}-{b_}:{kind_}')
        for i in range(1, len(tr)):
            if tr[i]['vis'] and not tr[i - 1]['vis'] and not tr[i]['edge']:
                findings.append(f'popin:{n}:f{tr[i]["f"]}')
        first, last = tr[0], tr[-1]
        # cut-grammar facts (gate v3): is the car closing on the ground at the shot's start / end?
        gmins = [min([x for x in s_['gaps'] if x is not None], default=None) for s_ in tr]

        def closing(seq):
            seq = [g for g in seq if g is not None]
            return len(seq) >= 4 and seq[0] - seq[-1] > 1.0 and seq[-1] < 15.0

        manifest[n] = dict(visible_first=first['vis'], edge_first=first['edge'], sx_first=first['sx'],
                           visible_last=last['vis'], sx_last=last['sx'],
                           surface_first=[k for k in first['kinds']], surface_last=[k for k in last['kinds']],
                           gap_first=gmins[0], gap_last=gmins[-1],
                           closing_start=closing(gmins[:12]), closing_end=closing(gmins[-12:]),
                           gaps_head=gmins[:12], gaps_tail=gmins[-12:], gaps=gmins,
                           cut_frames=[dict(visible=s['vis'], edge=s['edge'], surfaces=s['kinds'], gap=gap)
                                       for s, gap in zip(tr, gmins)])
    # which car (if any) carries the camera: two consecutive shots from the same mount read as one shot repeated
    mount = None
    p_ = cam.parent if cam else None
    while p_ is not None:
        for n_, a_ in actors.items():
            if p_.name in a_['members']:
                mount = n_
        p_ = p_.parent
    out = dict(shot=shot, frames=[f0, f1], findings=findings, manifest=manifest, cam_mount=mount,
               actors=list(actors), solids=len(solids_static) + len(solids_dyn))
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1)
    print(f'[probe] {shot}: {len(findings)} findings -> {out_path}', flush=True)
    for x in findings:
        print('   ', x, flush=True)
