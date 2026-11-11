"""DEBRIS — shared violence effects for the duel + finale (our work).

  kick_chunks : big ballistic stones / dirt clods / grit thrown off the tyres. How many per frame follows an
                intensity curve (slides, sudden lane changes, contact, wheelspin), so calm running kicks a little
                and the violent moments kick a lot. Chunks carry part of the car's velocity, fly out toward the
                outside of a slide, tumble, bounce once on the road/ground and settle.
  road_debris : static gravel, stones, rubber crumbs (+ paint / carbon flakes at hot spots) lying on the road;
                denser where the fights happen.
  tyre_marks  : rubber ribbons under the rear tyres wherever intensity is high; every vertex stores the race
                time it was laid ('tl') and the material only shows ribbon laid before 'now' (keyed per frame),
                so a mark appears exactly as the tyre paints it, never ahead of the car.

Everything takes race-time functions (T -> world Vector), so it works for any shot window / timescale.
"""
import math, random
import bpy, bmesh
from mathutils import Vector as V
from common import *
import canyon as C

FPSf = 24.0


def surface_z(road, x, y):
    """height of whatever is under (x, y): crowned road, or their terrain off it."""
    s, d = road.sd(x, y)
    if abs(d) < 3.9:
        P = road.point(s, d, 0.0)
        return P.z + 0.06 * (1 - (abs(d) / 3.9) ** 2) - (0.02 if abs(d) > 3.7 else 0.0)
    try:
        return C.ground_h(s, d, x, y)
    except Exception:
        return 0.0


_MESHES = {}


def _chunk_meshes():
    """4 rock shapes x 3 materials (dark grit, tan stone, dusty clod) as mesh datablocks shared by every chunk."""
    if _MESHES:
        return _MESHES
    mats = [mat_principled('ChunkGrit', (0.09, 0.05, 0.03), 0.95),
            mat_principled('ChunkStone', (0.30, 0.17, 0.10), 0.9),
            mat_principled('ChunkClod', (0.45, 0.31, 0.20), 1.0)]
    for i in range(4):
        src = C.rock_mesh(f'ChunkSrc{i}', 1.0, seed=300 + i, flat=0.55 + 0.1 * i, sub=1, sharp=1.0)
        for j, m in enumerate(mats):
            me = src.data.copy(); me.name = f'chunk{i}_{j}'
            me.materials.clear(); me.materials.append(m)
            _MESHES[(i, j)] = me
        bpy.data.objects.remove(src)
    return _MESHES


def kick_chunks(name, Tf, N, emitters, road, seed=1, max_per=6, base=0.12, cap=1600, coll=None, big=1.0):
    """emitters: [(pos_fn, vel_fn, out_fn, inten_fn)], each a function of race time T.
    pos = tyre contact point, vel = car velocity, out = unit vector the slide throws toward (or None),
    inten in 0..~1.5. Per frame each emitter throws round(inten * max_per (+ base)) chunks."""
    coll = coll or collection(name)
    rng = random.Random(seed)
    meshes = _chunk_meshes()
    ts = (Tf(2) - Tf(1)) * FPSf
    dt = ts / FPSf
    made = 0
    for f in range(1, N + 1):
        T = Tf(f)
        for e, (pos_fn, vel_fn, out_fn, inten_fn) in enumerate(emitters):
            it = inten_fn(T)
            lam = it * max_per + base
            n = int(lam) + (1 if rng.random() < lam - int(lam) else 0)
            if n <= 0:
                continue
            p0 = pos_fn(T)
            cv = vel_fn(T)
            out = out_fn(T) if out_fn is not None else None
            back = -V((cv.x, cv.y, 0)).normalized() if cv.length > 0.5 else V((0, 0, 0))
            for _ in range(n):
                if made >= cap:
                    break
                u = rng.random()
                sz = (rng.uniform(0.015, 0.03) if u < 0.45 else rng.uniform(0.03, 0.07) if u < 0.78
                      else rng.uniform(0.07, 0.14)) * big
                kind = 0 if sz < 0.03 else rng.choice((1, 1, 2))
                me = meshes[(rng.randrange(4), kind)]
                o = bpy.data.objects.new(f'{name}{f:03d}_{e}_{made}', me)
                link(o, coll)
                if sz < 0.03:
                    o.visible_shadow = False
                p = p0 + V((rng.gauss(0, 0.12), rng.gauss(0, 0.12), 0.04 + sz))
                v = (cv * rng.uniform(0.15, 0.55) + back * rng.uniform(1.0, 4.0) * (0.5 + it)
                     + V((rng.gauss(0, 1.2), rng.gauss(0, 1.2), rng.uniform(1.2, 3.0) + 2.5 * it * rng.random())))
                if out is not None:
                    v += out * rng.uniform(1.5, 6.5) * min(1.2, it)
                w = V((rng.uniform(-25, 25), rng.uniform(-25, 25), rng.uniform(-15, 15)))
                life = int(rng.uniform(0.55, 1.3) / dt)
                life = max(6, min(life, 70))
                o.scale = (0, 0, 0); o.keyframe_insert('scale', frame=f - 1)
                rot = V((rng.uniform(0, 6.3), rng.uniform(0, 6.3), rng.uniform(0, 6.3)))
                bounced = False
                for k in range(life + 1):
                    if k:
                        v.z -= 9.8 * dt
                        p = p + v * dt
                        floor = surface_z(road, p.x, p.y) + sz * 0.5 if (k % 2 == 0 or p.z < 1.0) else -1e9
                        if p.z < floor:
                            p.z = floor
                            if not bounced:
                                v = V((v.x * 0.55, v.y * 0.55, -v.z * 0.32)); w *= 0.5; bounced = True
                            else:
                                v = V((v.x * 0.6, v.y * 0.6, 0.0)); w *= 0.6
                        rot = rot + w * dt
                    o.location = p; o.keyframe_insert('location', frame=f + k)
                    o.rotation_euler = rot; o.keyframe_insert('rotation_euler', frame=f + k)
                    s_ = sz * (1.0 if k < life - 2 else 0.6)
                    o.scale = (s_, s_ * rng.uniform(0.7, 1.0), s_ * 0.8); o.keyframe_insert('scale', frame=f + k)
                o.scale = (0, 0, 0); o.keyframe_insert('scale', frame=f + life + 1)
                set_interp(o, 'LINEAR')
                made += 1
    print(f'[debris] {name}: {made} kicked chunks', flush=True)
    return made


def road_debris(name, road, s_a, s_b, per_m=6.0, hot=(), seed=7, coll=None, flake_cols=()):
    """static bits lying on the road between s_a and s_b. hot: [(s, half_len_m, multiplier)] raise density there.
    flake_cols: paint colours for broken body flakes that only appear at hot spots."""
    rng = random.Random(seed)
    srcs = []
    gm = mat_principled('DebGrit', (0.07, 0.045, 0.03), 0.95)
    sm = mat_principled('DebStone', (0.33, 0.20, 0.12), 0.9)
    rm = mat_principled('DebRubber', (0.012, 0.012, 0.013), 0.7)
    for i in range(3):
        o = C.rock_mesh(f'DebSrc{i}', 1.0, seed=400 + i, flat=0.45, sub=1, sharp=1.0); set_mat(o, gm if i < 2 else sm); srcs.append(o)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 1.0; v.co.y *= 0.7; v.co.z *= 0.6
    crumb = from_bmesh('DebCrumb', bm, None, smooth=False); set_mat(crumb, rm); srcs.append(crumb)
    flakes = []
    for j, col in enumerate(flake_cols):
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.z *= 0.06; v.co.x *= rng.uniform(0.8, 1.4)
        fo = from_bmesh(f'DebFlake{j}', bm, None, smooth=False)
        set_mat(fo, mat_principled(f'DebFlakeMat{j}', col, 0.35)); srcs.append(fo); flakes.append(len(srcs) - 1)
    src = C.src_collection(name + 'Src', srcs)
    pts, rots, scs, picks = [], [], [], []
    s = s_a
    while s < s_b:
        mult = 1.0
        hot_here = False
        for hs, hl, hm in hot:
            if abs(s - hs) < hl:
                mult += hm * (1 - abs(s - hs) / hl); hot_here = True
        n = int(per_m * mult * 0.5) + (1 if rng.random() < (per_m * mult * 0.5) % 1 else 0)
        for _ in range(n):
            r_ = rng.random()   # wheel lines + the edges collect most of it
            d = (rng.choice((-1, 1)) * rng.gauss(1.75, 0.5) if r_ < 0.45 else
                 rng.choice((-1, 1)) * rng.uniform(3.0, 3.7) if r_ < 0.8 else rng.uniform(-3.6, 3.6))
            d = max(-3.65, min(3.65, d))
            ss = s + rng.uniform(0, 0.5)
            P = road.point(ss, d, 0.0)
            u = rng.random()
            if hot_here and flakes and u < 0.12:
                pk = rng.choice(flakes); sz = rng.uniform(0.03, 0.09)
                sc_ = (sz, sz * rng.uniform(0.5, 1.0), sz)
            elif u < 0.2:
                pk = 3; sz = rng.uniform(0.008, 0.02); sc_ = (sz, sz, sz)
            elif u < 0.93:
                pk = rng.randrange(2); sz = rng.uniform(0.006, 0.022); sc_ = (sz, sz, sz)
            else:
                pk = 2; sz = rng.uniform(0.03, 0.08); sc_ = (sz, sz, sz)
            z = P.z + 0.06 * (1 - (abs(d) / 3.9) ** 2) + 0.004
            pts.append((P.x, P.y, z)); scs.append(sc_); picks.append(pk)
            rots.append((rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(0, 6.3)))
        s += 0.5
    o = C.scatter(name, pts, rots, scs, picks, src, coll)
    print(f'[debris] {name}: {len(pts)} bits on the road', flush=True)
    return o


_RUBBER = {}


def rubber_mat(Tf, N, name='RubberLaid'):
    """dithered black rubber; shows only ribbon whose laid time 'tl' <= the frame's race time."""
    key = (name, round(Tf(1), 4), N)
    if key in _RUBBER:
        return _RUBBER[key]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.surface_render_method = 'DITHERED'
    nt = m.node_tree; N_, L = nt.nodes, nt.links
    bsdf = N_['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.008, 0.008, 0.009, 1)
    bsdf.inputs['Roughness'].default_value = 0.55
    at = N_.new('ShaderNodeAttribute'); at.attribute_type = 'GEOMETRY'; at.attribute_name = 'tl'
    ai = N_.new('ShaderNodeAttribute'); ai.attribute_type = 'GEOMETRY'; ai.attribute_name = 'ti'
    now = N_.new('ShaderNodeValue'); now.name = 'Tnow'
    for f in range(0, N + 3):
        now.outputs[0].default_value = Tf(f); now.outputs[0].keyframe_insert('default_value', frame=f)
    if nt.animation_data and nt.animation_data.action:
        for fc in fcurves(nt):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    cmp_ = N_.new('ShaderNodeMath'); cmp_.operation = 'LESS_THAN'
    L.new(at.outputs['Fac'], cmp_.inputs[0]); L.new(now.outputs[0], cmp_.inputs[1])
    tc = N_.new('ShaderNodeTexCoord')
    nz = N_.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 6.0
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    mr = N_.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 0.3; mr.inputs['From Max'].default_value = 0.7
    mr.inputs['To Min'].default_value = 0.5; mr.inputs['To Max'].default_value = 0.95
    L.new(nz.outputs['Fac'], mr.inputs['Value'])
    m1 = N_.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'
    L.new(mr.outputs[0], m1.inputs[0]); L.new(ai.outputs['Fac'], m1.inputs[1])
    m2 = N_.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'
    L.new(m1.outputs[0], m2.inputs[0]); L.new(cmp_.outputs[0], m2.inputs[1])
    L.new(m2.outputs[0], bsdf.inputs['Alpha'])
    _RUBBER[key] = m
    return m


def fcurves_of(idblock):
    ad = idblock.animation_data
    if ad is None or ad.action is None:
        return []
    act = ad.action
    if hasattr(act, 'fcurves') and len(getattr(act, 'fcurves', [])):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, 'layers', []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


def tyre_marks(name, road, Tf, N, tracks, T_a, T_b, thr=0.2, width=0.27, dT=0.01, coll=None, min_d_off=3.75):
    """tracks: [(pos_fn, inten_fn)] tyre contact points over race time. Ribbon laid where inten > thr and the tyre is on
    the road; its opacity follows the intensity. Revealed in time by rubber_mat."""
    coll = coll or collection('TyreMarks')
    mat = rubber_mat(Tf, N)
    nseg = 0
    for ti_, (pos_fn, inten_fn) in enumerate(tracks):
        bm = bmesh.new()
        tl_l = bm.verts.layers.float.new('tl')
        ti_l = bm.verts.layers.float.new('ti')
        prev = None
        T = T_a
        while T <= T_b:
            it = inten_fn(T)
            c = pos_fn(T)
            s, d = road.sd(c.x, c.y)
            if it > thr and abs(d) < min_d_off:
                z = road.point(s, d, 0.0).z + 0.06 * (1 - (abs(d) / 3.9) ** 2) + 0.016
                p = V((c.x, c.y, z))
                alpha = min(1.0, 0.55 + (it - thr) * 1.5)
                if prev is None:
                    prev = (p, None, None)
                elif (p - prev[0]).length > 0.06:
                    dirv = (p - prev[0]); dirv.z = 0
                    if dirv.length > 1e-4:
                        dirv.normalize()
                        sv = dirv.cross(V((0, 0, 1))) * (width / 2)
                        a = bm.verts.new(p + sv); b = bm.verts.new(p - sv)
                        for vv in (a, b):
                            vv[tl_l] = T; vv[ti_l] = alpha
                        if prev[1] is not None:
                            bm.faces.new((prev[1], prev[2], b, a)); nseg += 1
                        prev = (p, a, b)
            else:
                prev = None
            T += dT
        if len(bm.verts):
            o = from_bmesh(f'{name}{ti_}', bm, coll, smooth=False)
            set_mat(o, mat)
            o.visible_shadow = False
        else:
            bm.free()
    print(f'[debris] {name}: {nseg} rubber segments', flush=True)


# ----------------------------------------------------------------------------------- ride height on the real surface
# (the gate's scene probe found every car 5-7 cm INTO the road: the toolkit placed roots at the road's base height and
#  ignored its crown; on the gravel shoulder a guessed -0.14 m drop sank the hero 9-15 cm)

def ground_z(road, x, y):
    """the exact height of the built surface at (x, y): road ribbon (crown + noise), gravel shoulder, else terrain."""
    s, d = road.sd(x, y)
    P = road.point(s, d, 0.0)
    ad = abs(d)
    if ad <= 3.9:
        crown = 0.06 * (1 - (ad / 3.9) ** 2) - (0.02 if ad > 3.7 else 0.0)
        return P.z + crown + 0.01 * C.nz(x * 0.3, y * 0.3)
    if ad <= 7.4:
        e = abs(ad - 3.75)
        return -0.02 - 0.05 * min(e, 1.0) - 0.08 * C.smooth(2.5, 3.6, e) + 0.03 * C.nz(x * 0.7, y * 0.7, 3)
    try:
        return C.ground_h(s, d, x, y)
    except Exception:
        return P.z


def ride_z(road, pos, fwd, right, axle_f, axle_r, track):
    """root height so the tyres sit on the surface: mean of the supported wheels (a wheel more than 0.3 m below the
    highest one is hanging over a drop and carries nothing)."""
    hs = [ground_z(road, *(pos + fwd * ax + right * sx * track).xy) for ax in (axle_f, -axle_r) for sx in (-1, 1)]
    top = max(hs)
    sup = [h for h in hs if h > top - 0.3]
    return sum(sup) / len(sup)


def settle_drive(car, road, axles):
    """after the toolkit's C.drive: re-key the root height so the tyres sit on the crowned road (probe: 6-7 cm in).
    Reads each keyed frame's own position + yaw (root rotation z = -road heading + slip)."""
    root = car['root']
    fx = {fc.array_index: fc for fc in fcurves(root) if fc.data_path == 'location'}
    fr = {fc.array_index: fc for fc in fcurves(root) if fc.data_path == 'rotation_euler'}
    n = 0
    for kp in fx[2].keyframe_points:
        f = kp.co[0]
        x, y = fx[0].evaluate(f), fx[1].evaluate(f)
        yaw = fr[2].evaluate(f) if 2 in fr else 0.0
        fwd = V((-math.sin(yaw), math.cos(yaw), 0)); right = V((math.cos(yaw), math.sin(yaw), 0))
        z = ride_z(road, V((x, y, 0)), fwd, right, *axles)
        kp.co[1] = z; kp.handle_left[1] = z; kp.handle_right[1] = z
        n += 1
    fx[2].update()
    print(f'[debris] settle_drive {root.name}: {n} keys on the crowned road', flush=True)
