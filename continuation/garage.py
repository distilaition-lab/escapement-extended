"""THE GARAGE — shots 9E-9F (our work), back in ESCAPEMENT's act-2 studio.

  9E: the last frame of the plunge (9D) shatters into 3D glass shards (the screen breaks, like 2G), revealing the rival
      floating apart in an exploded parts view in the dark studio; the parts slam home in five groups with sparks.
  9F: both cars side by side facing the camera, fog, headlights + brake lights; the camera pans from the side round
      to the front while the engines rev (body wobble).
  stills : rb.py ../continuation/garage.py -- --shot 9E --stills 1,20,60,120 --pct 40 --samples 16 --tag _v1
  final  : rb.py ../continuation/garage.py -- --shot 9E --anim
"""
import sys, os, math, random, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, '..', 'film', 'lib'), HERE]
from common import *
import act2lib as A
import car as CAR
import rival as RV
from mathutils import Vector as V, Matrix, Euler

T_START = time.time()
SHOT = str(arg('--shot', '9E'))
N = {'9E': 140, '9F': 192, '9L': 84}[SHOT]

reset()
sc = setup_render(1, N, samples=48, vol_tile='8', vol_samples=48, vol_end=120.0, shutter=0.5,
                  look='AgX - Medium High Contrast')
sc.eevee.shadow_pool_size = '2048'   # 9E: dozens of exploded parts overflowed 1024 (gate caught it in the final log)
sc.eevee.motion_blur_steps = 2
compositor(bloom=0.45, threshold=1.2, bloom_size=0.7, dispersion=0.004)
world_color((0.0015, 0.0018, 0.0022), 1.0)
coll = collection('garage')
S = A.build_studio(coll, voxel=False)
A.probes(coll)
fx = collection('fx')
# low-lying fog over the wet floor (thin, noisy, never a milky veil)
fog = mat_volume('GroundFog', density=0.018, color=(0.75, 0.80, 0.85), anisotropy=0.4, noise_scale=2.5)
if arg('--fog', '1') == '1':
    volume_box('GroundFog', (0, 0, 0.35), (26, 30, 0.7), fog, coll)


def car_recv(root, name):
    cr = bpy.data.collections.new(name)

    def walk(o):
        yield o
        for ch in o.children:
            yield from walk(ch)
    for o in walk(root):
        if o.type == 'MESH':
            cr.objects.link(o)
    return cr


def rim_lights(root, recv, rig):
    """car-only rims (their r3 lesson: light-linked so the wet floor does not mirror them as cards)."""
    for nm, loc, e, col, size in rig:
        L = light('AREA', nm, loc, energy=e, color=col, size=size)
        L.rotation_euler = (V((root.location.x, root.location.y, 0.6)) - V(loc)).to_track_quat('-Z', 'Y').to_euler()
        L.visible_camera = False
        L.data.volume_factor = 0.0
        L.light_linking.receiver_collection = recv

# ----------------------------------------------------------------------------------- 9E


def shard_wall(cam, image_path, d=1.0, n=72, seed=4):
    """The previous shot's last frame on a pane of Voronoi glass shards filling the lens at distance d."""
    w = cam.data.sensor_width / cam.data.lens * d
    h = w * 9 / 16
    rng = random.Random(seed)
    pts = []
    while len(pts) < n:              # denser near the impact point (centre, a little low)
        x, y = rng.uniform(-w / 2, w / 2), rng.uniform(-h / 2, h / 2)
        if rng.random() < math.exp(-((x / (0.45 * w)) ** 2 + ((y + 0.05 * h) / (0.45 * h)) ** 2)) + 0.25:
            pts.append(V((x, y)))
    rect = [V((-w / 2, -h / 2)), V((w / 2, -h / 2)), V((w / 2, h / 2)), V((-w / 2, h / 2))]

    def clip(poly, a, b):
        m, nrm = (a + b) / 2, (b - a)
        out = []
        for i in range(len(poly)):
            p, q = poly[i], poly[(i + 1) % len(poly)]
            dp, dq = (p - m).dot(nrm), (q - m).dot(nrm)
            if dp <= 0:
                out.append(p)
            if dp * dq < 0:
                out.append(p + (q - p) * (dp / (dp - dq)))
        return out
    img = None
    if image_path and os.path.exists(image_path):
        img = bpy.data.images.load(image_path)
    b = NB('shard_glass')
    b.set('Base Color', (0.0, 0.0, 0.0)).set('Roughness', 0.04).set('Coat Weight', 1.0).set('Coat Roughness', 0.0)
    if img is not None:
        t = b.n('ShaderNodeTexImage'); t.image = img; t.extension = 'EXTEND'
        uv = b.n('ShaderNodeUVMap')
        b.link(uv.outputs[0], t.inputs['Vector'])
        b.set('Emission Color', t.outputs['Color'])
    else:
        b.set('Emission Color', (0.45, 0.30, 0.20))
    b.set('Emission Strength', 1.0)
    mat = b.mat
    shards = []
    for i, si in enumerate(pts):
        cell = rect
        for j, sj in enumerate(pts):
            if i != j and cell:
                cell = clip(cell, si, sj)
        if len(cell) < 3:
            continue
        c = sum(cell, V((0, 0))) / len(cell)
        me = bpy.data.meshes.new(f'shard{i}')
        me.from_pydata([(p.x - c.x, p.y - c.y, 0.0) for p in cell], [], [list(range(len(cell)))])
        uvl = me.uv_layers.new(name='UVMap')
        for li, loop in enumerate(me.loops):
            p = cell[loop.vertex_index]
            uvl.data[li].uv = (p.x / w + 0.5, p.y / h + 0.5)
        o = bpy.data.objects.new(f'shard{i}', me)
        link(o, fx)
        o.data.materials.append(mat)
        so = o.modifiers.new('thick', 'SOLIDIFY'); so.thickness = 0.004
        o.parent = cam; o.matrix_parent_inverse = Matrix.Identity(4)
        o.location = (c.x, c.y, -d)
        shards.append((o, c))
    imp = V((0.0, -0.05 * h))
    for o, c in shards:
        r = (c - imp)
        f_rel = 3 + int(r.length / (w * 0.5) * 9) + rng.randint(0, 2)
        dirv = r.normalized() if r.length > 1e-4 else V((0, 1))
        v = V((dirv.x * rng.uniform(0.5, 1.3), dirv.y * rng.uniform(0.5, 1.3), rng.uniform(0.6, 1.6)))   # out + toward the lens
        wv = V((rng.uniform(-6, 6), rng.uniform(-6, 6), rng.uniform(-3, 3)))
        p0 = o.location.copy()
        for f in (1, f_rel):
            o.location = p0; o.rotation_euler = (0, 0, 0)
            o.keyframe_insert('location', frame=f); o.keyframe_insert('rotation_euler', frame=f)
        for f in range(f_rel + 1, 40):
            tau = (f - f_rel) / 24.0
            o.location = p0 + v * tau + V((0, -1.2 * tau * tau, 0))
            o.rotation_euler = (wv.x * tau, wv.y * tau, wv.z * tau)
            o.keyframe_insert('location', frame=f); o.keyframe_insert('rotation_euler', frame=f)
        set_interp(o, 'LINEAR')
    # a white-hot crack flash at the impact point
    A.flash(fx, cam.matrix_world @ V((0, 0, -0.9)), 3, energy=60.0, color=(1.0, 0.85, 0.7))
    return shards


def exploded(rv, slams, f_hold0=1):
    """Rival parts float apart (slow drift + tumble), then slam home group by group with sparks."""
    sp = rv['sprung']
    rng = random.Random(12)
    items = []
    for o in list(sp.children):
        if o.type not in ('MESH',) or o.name.startswith('rival_inner_hull'):
            continue
        bb = [V(c) for c in o.bound_box]
        c = (sum(bb, V()) / 8) if o.type == 'MESH' else V()
        nm = o.name
        if nm.startswith('rival_body'):
            g, off = 1, V((0, 0, 1.7))
        elif nm.startswith('rival_glass'):
            g, off = 2, V((0, 0.25, 2.7))
        elif nm.startswith(('rival_arms',)):
            g, off = 0, V((c.x * 0.9, 0.0, -0.10))
        else:
            off = V((c.x * 1.35, c.y * 0.45, 0.8 + max(0.0, c.z) * 1.4))
            if c.y > 1.7:
                off.y += 1.3
            if c.y < -1.8:
                off.y -= 1.3
            small = any(k in nm for k in ('screws', 'emblem', 'pins', 'filler', 'number', 'handles', 'wiper', 'roundel'))
            g = 4 if small else (2 if c.y > 1.5 else 3)
        rot = V((rng.uniform(-14, 14), rng.uniform(-14, 14), rng.uniform(-10, 10)))
        items.append((o, g, off, rot))
    for key in ('FL', 'FR', 'RL', 'RR'):
        o = rv['parts']['corner_' + key]
        sx = -1 if key[1] == 'L' else 1
        items.append((o, 0, V((sx * 1.7, 0.25 if key[0] == 'F' else -0.25, 0.25)), V((0, 0, sx * 12))))
    hull = rv['parts'].get('inner_hull')
    for o, g, off, rot in items:
        hl, hr = o.location.copy(), o.rotation_euler.copy()
        s = slams[g]
        d = off.normalized() if off.length > 1e-6 else V((0, 0, 1))

        def put(f, frac, extra_rot=1.0, jit=0.0):
            o.location = hl + off * frac + V((math.sin(f * 0.05 + off.x), math.cos(f * 0.04 + off.y), math.sin(f * 0.03)) ) * jit
            o.rotation_euler = Euler([hr[i] + math.radians(rot[i]) * frac * extra_rot for i in range(3)])
            o.keyframe_insert('location', frame=f); o.keyframe_insert('rotation_euler', frame=f)
        put(f_hold0, 0.92)
        put(s - 8, 1.0, 1.0, 0.02)                        # slow outward drift while the camera orbits
        for f, a in ((s, -0.022), (s + 1, 0.007), (s + 3, 0.0)):   # expo slam: overshoot, rebound, settle
            o.location = hl + d * a
            o.rotation_euler = hr
            o.keyframe_insert('location', frame=f); o.keyframe_insert('rotation_euler', frame=f)
        for fc in fcurves(o):
            for kp in fc.keyframe_points:
                if abs(kp.co[0] - (s - 8)) < 0.5:
                    kp.interpolation = 'EXPO'; kp.easing = 'EASE_IN'
    if hull is not None:                             # the gap-blocker hull only exists once the body is home
        for f, s_ in ((1, 0.0), (slams[1] - 1, 0.0), (slams[1], 1.0)):
            hull.scale = (s_, s_, s_); hull.keyframe_insert('scale', frame=f)
        set_interp(hull, 'CONSTANT', path='scale')
    pts = [[(0.86, 1.4, 0.36), (-0.86, -1.4, 0.36), (0.86, -1.4, 0.36)], [(0.9, 0.0, 0.5), (-0.9, 0.3, 0.5), (0, 2.1, 0.4)],
           [(0.5, 0.6, 0.85), (-0.5, 0.6, 0.85), (0, 2.3, 0.3)], [(0.95, -0.8, 0.3), (-0.95, -0.8, 0.3), (0, -2.3, 0.7)],
           [(0.0, 1.2, 0.75), (0.95, -0.1, 0.5)]]
    for gi, s in enumerate(slams):
        for j, p in enumerate(pts[gi]):
            A.spark_burst(fx, rv['root'].matrix_world @ V(p), s, n=9, seed=gi * 10 + j, speed=(3.0, 9.0), up=0.5, life=(3, 8))
        A.flash(fx, rv['root'].matrix_world @ V(pts[gi][0]) + V((0, 0, 0.1)), s, energy=300)


def studio_surge(slams):
    """strips brown out and surge on every slam (their 2B language)."""
    for L in S['strip_lights']:
        e0 = L.data.energy
        for s in slams:
            for f, k in ((s - 2, 1.0), (s, 0.35), (s + 2, 1.25), (s + 6, 1.0)):
                L.data.energy = e0 * k; L.data.keyframe_insert('energy', frame=f)


def orbit_pos(center, R, phi_deg, h):
    p = math.radians(phi_deg)
    return V((center[0] + R * math.cos(p), center[1] + R * math.sin(p), h))


def smooth_(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


E0 = 18                              # the rival idles (just landed), then blows apart
SLAMS = [92, 102, 112, 122, 132]     # reassembly: chassis, mechanicals, panels, glass+aero, small parts
EXPLODE = {   # object name: (group, offset in car space, rotation degrees) - layered like their 2B (chassis low ... glass high)
    'rival_tub': (0, (0, 0, 0.18), (0, 0, 0)), 'rival_driveline': (0, (0, -0.15, 0.45), (0, 0, 0)),
    'rival_engine': (1, (0, 0.25, 1.35), (-8, 0, 5)), 'rival_radiator': (1, (0, 1.75, 1.05), (-12, 0, 0)),
    'rival_fuel_cell': (1, (0, -1.10, 1.05), (10, 0, 0)), 'rival_seats': (1, (0, -0.25, 1.25), (0, 0, 0)),
    'rival_cockpit': (1, (0, -0.30, 1.85), (0, 0, -8)), 'rival_exhaust': (1, (0, -0.30, 0.55), (0, 0, 0)),
    'rival_exhaust_throats': (1, (0, -0.30, 0.55), (0, 0, 0)), 'rival_heat_shields': (1, (0, -0.30, 0.80), (0, 0, 0)),
    'rival_body': (2, (0, 0, 2.55), (0, 2, 0)), 'rival_nose': (2, (0, 2.2, 1.9), (-14, 0, 0)),
    'rival_tail': (2, (0, -2.3, 2.1), (12, 0, 0)), 'rival_hood': (2, (0, 1.1, 3.15), (-16, 0, 0)),
    'rival_boot': (2, (0, -1.5, 3.25), (14, 0, 0)), 'rival_door_L': (2, (-2.1, 0.25, 1.75), (0, -28, 0)),
    'rival_door_R': (2, (2.1, 0.25, 1.75), (0, 28, 0)),
    'rival_glass': (3, (0, 0.25, 3.85), (8, 0, 0)), 'rival_splitter': (3, (0, 2.3, -0.02), (0, 0, 0)),
    'rival_splitter_lip': (3, (0, 2.55, 0.0), (0, 0, 0)), 'rival_diffuser': (3, (0, -2.2, 0.25), (-12, 0, 0)),
    'rival_skirts': (3, (0, 0, 0.08), (0, 0, 0)), 'rival_mirror_-1': (3, (-1.35, 0.35, 2.4), (0, 0, -20)),
    'rival_mirror_1': (3, (1.35, 0.35, 2.4), (0, 0, 20)), 'rival_screws': (4, (0, 2.45, 0.35), (0, 0, 0)),
}


def exploded2(rv):
    """Explode at E0 (expo-out burst, then a slow drift into the layout and a hold), then slam home group by group."""
    sp = rv['sprung']
    rng = random.Random(12)
    items = []
    for o in list(sp.children):
        if o.type != 'MESH' or o.name.startswith('rival_inner_hull'):
            continue
        if o.name in EXPLODE:
            g, off, rot = EXPLODE[o.name]
        elif o.name.startswith('rival_arms'):
            bb = [V(c) for c in o.bound_box]
            c = sum(bb, V()) / 8
            g, off, rot = 0, (math.copysign(0.75, c.x), 0.0, 0.35), (0, 0, 0)
        else:                                     # anything else: outward + up by where it sits, small-parts group
            bb = [V(c) for c in o.bound_box]
            c = sum(bb, V()) / 8
            g, off, rot = 4, (c.x * 1.3, c.y * 0.5, 0.9 + max(0.0, c.z) * 1.3), (rng.uniform(-12, 12), rng.uniform(-12, 12), 0)
        items.append((o, g, V(off), V(rot)))
    for key in ('FL', 'FR', 'RL', 'RR'):
        o = rv['parts']['corner_' + key]
        sx = -1 if key[1] == 'L' else 1
        items.append((o, 0, V((sx * 1.95, 0.35 if key[0] == 'F' else -0.35, 0.15)), V((0, 0, sx * 14))))
    for o, g, off, rot in items:
        hl, hr = o.location.copy(), o.rotation_euler.copy()
        s = SLAMS[g]
        d = off.normalized() if off.length > 1e-6 else V((0, 0, 1))
        drift = V((rng.uniform(-4, 4), rng.uniform(-4, 4), rng.uniform(-4, 4)))

        def put(f, frac, rfrac=None, dr=0.0):
            rfrac = frac if rfrac is None else rfrac
            o.location = hl + off * frac
            o.rotation_euler = Euler([hr[i] + math.radians(rot[i] * rfrac + drift[i] * dr) for i in range(3)])
            o.keyframe_insert('location', frame=f); o.keyframe_insert('rotation_euler', frame=f)
        st = E0 + g % 2                              # outer groups a frame later: a ripple, not a pop
        put(1, 0.0); put(st, 0.0)
        put(st + 3, 0.55, 0.4)
        put(st + 10, 0.86, 0.8, 0.3)
        put(s - 10, 1.0, 1.0, 1.0)                    # slow drift into the layout + hold while the camera orbits
        for f, a in ((s, -0.022), (s + 1, 0.007), (s + 3, 0.0)):
            o.location = hl + d * a
            o.rotation_euler = hr
            o.keyframe_insert('location', frame=f); o.keyframe_insert('rotation_euler', frame=f)
        for fc in fcurves(o):
            for kp in fc.keyframe_points:
                if abs(kp.co[0] - (st + 3)) < 0.5 or abs(kp.co[0] - (st + 10)) < 0.5:
                    kp.interpolation = 'EXPO'; kp.easing = 'EASE_OUT'
                elif abs(kp.co[0] - (s - 10)) < 0.5:
                    kp.interpolation = 'EXPO'; kp.easing = 'EASE_IN'
                elif kp.co[0] >= s:
                    kp.interpolation = 'BEZIER'
    hull = rv['parts'].get('inner_hull')
    if hull is not None:
        for f, s_ in ((1, 1.0), (E0 - 1, 1.0), (E0, 0.0), (SLAMS[2] - 1, 0.0), (SLAMS[2], 1.0)):
            hull.scale = (s_, s_, s_); hull.keyframe_insert('scale', frame=f)
        set_interp(hull, 'CONSTANT', path='scale')
    burst = [(0.9, 1.4, 0.4), (-0.9, 1.4, 0.4), (0.9, -1.4, 0.4), (-0.9, -1.4, 0.4), (0, 2.3, 0.3), (0, -2.3, 0.6),
             (1.0, 0.0, 0.6), (-1.0, 0.0, 0.6), (0, 1.0, 0.8), (0, -0.6, 1.0)]
    for j, p in enumerate(burst):
        A.spark_burst(fx, rv['root'].matrix_world @ V(p), E0, n=10, seed=200 + j, speed=(4.0, 12.0), up=0.6, life=(4, 10))
    A.flash(fx, rv['root'].matrix_world @ V((0, 0, 0.8)), E0, energy=900)
    pts = [[(0.86, 1.4, 0.36), (-0.86, -1.4, 0.36), (0.86, -1.4, 0.36)], [(0.0, 1.0, 0.6), (0.0, -1.6, 0.5), (0.4, -0.2, 0.5)],
           [(0.9, 0.0, 0.5), (-0.9, 0.3, 0.5), (0, 2.1, 0.4), (0, -2.1, 0.7)], [(0.5, 0.6, 0.95), (-0.5, 0.6, 0.95), (0, 2.35, 0.15)],
           [(0.0, 1.2, 0.75), (0.95, -0.1, 0.5)]]
    for gi, s in enumerate(SLAMS):
        for j, p in enumerate(pts[gi]):
            A.spark_burst(fx, rv['root'].matrix_world @ V(p), s, n=8, seed=gi * 10 + j, speed=(3.0, 9.0), up=0.5, life=(3, 8))
        A.flash(fx, rv['root'].matrix_world @ V(pts[gi][0]) + V((0, 0, 0.1)), s, energy=300)
    # idle tremble before the blast (the engine is still running after the landing)
    fc_key(sp, 'location', 2, [(1, 0.0), (E0 - 6, 0.0), (E0 - 3, -0.012), (E0 - 1, 0.004), (E0, 0.0)])
    shake(sp, amp=0.0012, rot_amp=0.001, scale=1.3, seed=7, start=1, end=E0)


if SHOT == '9E':
    rv = RV.build_rival(coll, 'Rival')
    RV.set_light(rv, 'front_light', 7.0, 1); RV.set_light(rv, 'rear_light', 3.0, 1)
    recv = car_recv(rv['root'], 'rival_recv')
    rim_lights(rv['root'], recv, [('rimA', (-4.0, -3.0, 2.6), 380, (0.55, 0.85, 1.0), 4.0),
                                  ('rimB', (4.5, -2.0, 3.0), 300, (1.0, 0.62, 0.36), 4.0),
                                  ('top', (0.0, 0.5, 5.0), 160, (0.8, 0.85, 0.9), 6.0)])
    exploded2(rv)
    studio_surge([E0] + SLAMS)
    cam = camera('Cam9E', (6, 4, 1), lens=28, fstop=4.0, focus=7.6, clip=(0.02, 400))

    def cam_at(f):
        u = (f - 1) / (N - 1)
        up = smooth_(E0 - 2, E0 + 30, f) * (1 - smooth_(SLAMS[1], SLAMS[-1] + 4, f))
        phi = 58 - 48 * smooth_(1, SLAMS[0], f) + 55 * smooth_(SLAMS[0], N, f)
        R = 7.0 + 3.0 * up
        h = 1.0 + 2.4 * up
        tgt = V((0, 0.1, 0.55 + 1.35 * up))
        return orbit_pos((0, 0), R, phi, h), tgt
    for f in range(1, N + 3):
        p, tgt = cam_at(f)
        cam.location = p
        cam.rotation_euler = (tgt - p).to_track_quat('-Z', 'Y').to_euler('XYZ', cam.rotation_euler)   # continuous
        cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
        cam.data.dof.focus_distance = (tgt - p).length; cam.data.dof.keyframe_insert('focus_distance', frame=f)
    set_interp(cam, 'BEZIER')
    shake(cam, amp=0.03, rot_amp=0.006, scale=2.0, seed=5, start=E0 - 1, end=E0 + 8)     # the blast hits the camera
    shake(cam, amp=0.002, rot_amp=0.0006, scale=7, seed=6)
    sc.camera = cam

elif SHOT == '9L':
    # v6 THE LANDING (user: "the ground becomes the boundary ... gives way to the garage which the car then drives
    # into"): a floor camera looks up at the ragged hole the canyon ground left in the garage ceiling, dusk light and
    # their 2G chunks pouring through; the rival comes down nose-first (slow motion out of 9D), flares, lands hard and
    # drives forward to the centre where 9E finds it idling.
    import breach as BR
    import bmesh as _bm
    HX, HY, HR = 0.0, -5.0, 3.6                       # the hole in the ceiling, over the landing spot
    bpy.context.view_layer.update()
    for o in list(bpy.data.objects):                  # their flat ceiling + anything hanging over the hole goes
        w = o.matrix_world.translation
        if o.name.startswith('ceiling') or (w.z > A.SH - 1.6 and (V((w.x - HX, w.y - HY))).length < HR + 1.6):
            o.hide_render = True; o.hide_viewport = True
    rng_ = random.Random(3)

    def jag(a):
        return HR + 0.55 * math.sin(a * 5 + 1.3) + 0.35 * math.sin(a * 11 + 0.4)
    bm = _bm.new()                                     # the new ceiling: a grid with a ragged round hole
    W_, L_ = 2 * A.SX, A.SY1 - A.SY0
    _bm.ops.create_grid(bm, x_segments=104, y_segments=192, size=0.5)
    for v in bm.verts:
        v.co.x *= W_; v.co.y = v.co.y * L_ + (A.SY0 + A.SY1) / 2; v.co.z = A.SH
    kill = []
    for f_ in bm.faces:
        c_ = f_.calc_center_median()
        if (V((c_.x - HX, c_.y - HY))).length < jag(math.atan2(c_.y - HY, c_.x - HX)):
            kill.append(f_)
    _bm.ops.delete(bm, geom=kill, context='FACES')
    for f_ in bm.faces:
        f_.normal_flip()
    ceil = bpy.data.objects.new('ceilingHole', bpy.data.meshes.new('ceilingHole')); bm.to_mesh(ceil.data); bm.free()
    link(ceil, coll); set_mat(ceil, S['mats']['ceil'])
    # the canyon above: a dirt rim around the hole (underside of the broken valley floor) + dusk light pouring in
    bm = _bm.new()
    segs = 72
    for i in range(segs):
        a0, a1 = 2 * math.pi * i / segs, 2 * math.pi * (i + 1) / segs
        q = [V((HX + r_ * math.cos(a), HY + r_ * math.sin(a), A.SH + 0.02 + 0.25 * rng_.random()))
             for a, r_ in ((a0, jag(a0) - 0.05), (a1, jag(a1) - 0.05), (a1, jag(a1) + 1.4), (a0, jag(a0) + 1.4))]
        bm.faces.new([bm.verts.new(c) for c in q])
    rim = bpy.data.objects.new('holeRim', bpy.data.meshes.new('holeRim')); bm.to_mesh(rim.data); bm.free()
    link(rim, coll)
    rm = bpy.data.materials.new('RimDirt')
    rm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.16, 0.06, 0.035, 1)
    rm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.95
    set_mat(rim, rm)
    sky = bpy.data.objects.new('canyonSky', bpy.data.meshes.new('canyonSky'))
    bm = _bm.new(); _bm.ops.create_grid(bm, x_segments=1, y_segments=1, size=8.0)
    for f_ in bm.faces:
        f_.normal_flip()
    bm.to_mesh(sky.data); bm.free()
    link(sky, coll); sky.location = (HX, HY, A.SH + 14.0); sky.scale = (6.0, 6.0, 1.0)     # its edge never shows through the hole
    b_ = NB('CanyonDusk')                               # the dusk sky seen through the hole: warm low, deep blue high
    gco = b_.coord('Generated', 1.0)
    sep_ = b_.n('ShaderNodeSeparateXYZ'); b_.link(gco, sep_.inputs[0])
    nz_ = b_.noise(b_.coord('Object', 1.0), 0.6, 4, 0.5)
    mixf = b_.math('ADD', sep_.outputs[1], b_.math('MULTIPLY', nz_.outputs['Fac'], 0.25))
    ramp_ = b_.ramp(mixf, [(0.15, (1.0, 0.55, 0.28)), (0.55, (0.95, 0.42, 0.30)), (1.0, (0.20, 0.25, 0.42))])
    em = b_.n('ShaderNodeEmission'); b_.link(ramp_.outputs[0], em.inputs['Color']); em.inputs['Strength'].default_value = 3.2
    out_ = [n for n in b_.mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    b_.link(em.outputs[0], out_.inputs['Surface'])
    set_mat(sky, b_.mat)
    shaft = light('SPOT', 'DuskShaft', (HX + 0.8, HY - 0.6, A.SH + 6.0), energy=0, color=(1.0, 0.62, 0.36), spot=38,
                  blend=0.6, coll=coll, target=(HX, HY + 1.0, 0.0))
    for f, e in ((1, 26000.0), (40, 18000.0), (N, 14000.0)):
        shaft.data.energy = e; shaft.data.keyframe_insert('energy', frame=f)
    # the broken ground still falling through: their 2G chunks, slow motion, settling on the floor
    saved = dict(A.VOX)
    A.VOX.update(t0=-6.0, v=0.5, acc=0.03, A=1.5, sink=(HX, HY, -3.0))       # raining through the hole as the shot opens
    deb = A.debris_surface('holeChunks', coll, BR.tile_mat('HoleDirt'), (HX, HY, A.SH + 0.15), (2 * HR + 1.0, 2 * HR + 1.0),
                           'Z', 0.30, (HX, HY, A.SH), seed=9, burst=2.0, up=-2.0, turbk=1.6, big=0.25, cull_y=-1e9,
                           tscale=0.9)
    A.VOX.clear(); A.VOX.update(saved)
    bm = _bm.new(); bm.from_mesh(deb.data)
    _bm.ops.delete(bm, geom=[v for v in bm.verts if (V((v.co.x - HX, v.co.y - HY))).length > HR + 0.4], context='VERTS')
    bm.to_mesh(deb.data); bm.free()
    # the rival: nose-down through the hole (continuing 9D's slow motion), flare, hard landing, drive to the centre
    rv = RV.build_rival(coll, 'Rival')
    RV.set_light(rv, 'front_light', 7.0, 1); RV.set_light(rv, 'rear_light', 3.0, 1)
    recv = car_recv(rv['root'], 'rival_recv')
    rim_lights(rv['root'], recv, [('rimA', (-4.0, -3.0, 2.6), 380, (0.55, 0.85, 1.0), 4.0),
                                  ('rimB', (4.5, -2.0, 3.0), 300, (1.0, 0.62, 0.36), 4.0),
                                  ('top', (0.0, 0.5, 5.0), 160, (0.8, 0.85, 0.9), 6.0)])
    root, sp = rv['root'], rv['sprung']
    root.rotation_mode = 'XYZ'
    FL = 24                                            # touchdown frame

    def car_at(f):
        if f <= FL:
            u = (f - 1) / (FL - 1)
            return (V((0.0, HY - 0.6 * (1 - u), 11.5 * (1 - u) ** 1.5)), -1.2 * (1 - smooth_(3, FL - 3, f)),
                    0.44 * (1 - smooth_(2, FL - 4, f)))
        u = smooth_(FL + 2, FL + 40, f)
        return V((0.0, HY * (1 - u) ** 2, 0.0)), 0.0, 0.0
    dist, prev = 0.0, None
    for f in range(1, N + 3):
        pz, pitch, roll = car_at(f)
        root.location = pz; root.rotation_euler = (pitch, roll, 0.0)
        root.keyframe_insert('location', frame=f); root.keyframe_insert('rotation_euler', frame=f)
        if prev is not None and f > FL:
            dist += (pz - prev).length
        prev = pz
        for w in rv['wheels']:
            w.rotation_mode = 'XYZ'
            w.rotation_euler[0] = dist / RV.WR - (0.0 if f > FL else (FL - f) * 0.9)     # spinning in the air
            w.keyframe_insert('rotation_euler', index=0, frame=f)
    set_interp(root, 'LINEAR')
    for w in rv['wheels']:
        set_interp(w, 'LINEAR')
    fc_key(sp, 'location', 2, [(1, 0.0), (FL, 0.0), (FL + 2, -0.07), (FL + 5, 0.025), (FL + 9, -0.01), (FL + 14, 0.0)])
    fc_key(sp, 'rotation_euler', 0, [(1, 0.0), (FL, 0.0), (FL + 2, math.radians(-1.5)), (FL + 6, math.radians(0.8)),
                                     (FL + 11, 0.0), (FL + 38, 0.0), (FL + 42, math.radians(-1.2)), (FL + 48, 0.0)])
    for j, p in enumerate(((-0.87, 1.4, 0.05), (0.87, 1.4, 0.05), (-0.87, -1.4, 0.05), (0.87, -1.4, 0.05), (0, 2.3, 0.08))):
        A.spark_burst(fx, V((p[0], HY + p[1], p[2])), FL, n=12, seed=300 + j, speed=(4.0, 11.0), up=0.5, life=(4, 10))
    A.flash(fx, V((0, HY, 0.4)), FL, energy=1500)
    studio_surge([FL])
    # floor camera: low ahead of the landing, looking up at the hole, following the car down and in
    cp = V((2.5, -1.4, 0.18))                          # on the floor beside the landing spot, looking up at the hole
    cam = camera('Cam9L', cp, lens=20, fstop=4.0, focus=6.0, clip=(0.02, 400))

    def aim(f):
        pz, _, _ = car_at(f)
        return pz + V((0, 0, 0.6))
    import duel as D_
    D_.key_cam(cam, N, lambda f: cp, aim, omega=1.6, zeta=0.85)
    for f in range(1, N + 3, 2):
        cam.data.dof.focus_distance = (aim(f) - cp).length; cam.data.dof.keyframe_insert('focus_distance', frame=f)
    shake(cam, amp=0.03, rot_amp=0.008, scale=2.0, seed=8, start=FL - 1, end=FL + 9)       # the landing hits the floor
    shake(cam, amp=0.002, rot_amp=0.0006, scale=7, seed=6)
    sc.camera = cam

elif SHOT == '9F':
    hero = CAR.build_car(coll, 'Car')
    rv = RV.build_rival(coll, 'Rival')
    rv['root'].location = (1.45, 0.3, 0.0)
    # v3: the hero is not just there: it rolls in from out of shot (frame-left, behind), brakes, and stops beside the
    # rival at F_STOP with a nose dip; brake lights while it stops
    F_STOP, Y0 = 49, -14.0
    hr = hero['root']; hr.rotation_mode = 'XYZ'
    dist, prev = 0.0, None
    for f in range(1, N + 3):
        u = min(1.0, (f - 1) / (F_STOP - 1))
        y = Y0 * (1 - u) ** 2
        dip = (-0.022 * smooth_(F_STOP - 16, F_STOP - 2, f) * (1 - smooth_(F_STOP - 2, F_STOP + 4, f))
               + 0.008 * smooth_(F_STOP + 1, F_STOP + 5, f) * (1 - smooth_(F_STOP + 5, F_STOP + 14, f)))
        hr.location = (-1.45, y, 0.0); hr.rotation_euler = (dip, 0.0, 0.0)
        hr.keyframe_insert('location', frame=f); hr.keyframe_insert('rotation_euler', frame=f)
        if prev is not None:
            dist += abs(y - prev)
        prev = y
        for w in hero['wheels']:
            w.rotation_mode = 'XYZ'; w.rotation_euler[0] = dist / CAR.WR
            w.keyframe_insert('rotation_euler', index=0, frame=f)
    set_interp(hr, 'LINEAR')
    for w in hero['wheels']:
        set_interp(w, 'LINEAR')
    for f, s in ((1, 9), (30, 9), (32, 16), (F_STOP + 6, 16), (F_STOP + 9, 9), (58, 9), (60, 15), (66, 10), (82, 10), (84, 15), (92, 10)):
        CAR.set_light(hero, 'rear', s, f, spill=s * 1.6)
    CAR.set_light(hero, 'front', 6.0, 1, spill=3.0)
    RV.set_light(rv, 'front_light', 8.0, 1)
    for f, s in ((1, 3.0), (28, 3.0), (30, 6.0), (36, 3.5), (82, 3.5), (84, 6.0), (92, 3.5)):
        RV.set_light(rv, 'rear_light', s, f)
    for root, name, rig in ((hero['root'], 'hero_recv', [('hRim', (-5.0, -3.0, 2.6), 320, (0.55, 0.85, 1.0), 4.0),
                                                         ('hTop', (-1.45, 0.5, 4.6), 140, (0.8, 0.85, 0.9), 6.0)]),
                            (rv['root'], 'rival_recv', [('rRim', (5.0, -3.0, 2.6), 300, (1.0, 0.62, 0.36), 4.0),
                                                        ('rTop', (1.45, 0.8, 4.6), 120, (0.8, 0.85, 0.9), 6.0)])):
        rim_lights(root, car_recv(root, name), rig)
    # revs: body squat + rock on each blip (rival f30 while the hero rolls in, hero f60 once stopped, both f84)
    for sp, blips, seed in ((hero['sprung'], (60, 84), 1), (rv['sprung'], (30, 84), 2)):
        kx, ky, kz = [(1, 0.0)], [(1, 0.0)], [(1, 0.0)]
        for b in blips:
            kx += [(b - 1, 0.0), (b + 3, math.radians(-1.1)), (b + 7, math.radians(0.5)), (b + 11, math.radians(-0.25)), (b + 16, 0.0)]
            ky += [(b - 1, 0.0), (b + 2, math.radians(0.8)), (b + 5, math.radians(-0.5)), (b + 9, math.radians(0.2)), (b + 14, 0.0)]
            kz += [(b - 1, 0.0), (b + 3, -0.022), (b + 8, 0.006), (b + 13, -0.002), (b + 18, 0.0)]
        fc_key(sp, 'rotation_euler', 0, kx); fc_key(sp, 'rotation_euler', 1, ky); fc_key(sp, 'location', 2, kz)
        shake(sp, amp=0.0012, rot_amp=0.0010, scale=1.3, seed=seed)
    ctr = V((0, 0.15, 0.55))
    # v3: start on the HERO's side (it rolls in across the foreground instead of hiding behind the rival), swing to the front
    cam = camera('Cam9F', orbit_pos(ctr, 7.6, 172, 0.75), lens=24, fstop=2.8, focus=7.0, clip=(0.02, 400))
    N0 = 120                                           # v6: the swing to the front (as v5), then it lingers
    for f in range(1, N + 3):
        u = min(1.0, (f - 1) / (N0 - 1))
        e = u * u * (3 - 2 * u)
        h_ = smooth_(N0, N, f)                         # the held moment: a slow drift on round + a gentle push in
        p = orbit_pos(ctr, 7.6 - 0.4 * e - 0.7 * h_, 172 - 82 * e - 16 * h_, 0.75 - 0.30 * e + 0.12 * h_)
        cam.location = p
        cam.rotation_euler = (ctr - p).to_track_quat('-Z', 'Y').to_euler('XYZ', cam.rotation_euler)   # continuous: no +-180 flip
        cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
        cam.data.dof.focus_distance = (ctr - p).length; cam.data.dof.keyframe_insert('focus_distance', frame=f)
    set_interp(cam, 'BEZIER')
    shake(cam, amp=0.003, rot_amp=0.0008, scale=6, seed=4)
    sc.camera = cam


def smooth_(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


print(f'[garage] {SHOT} built in {time.time() - T_START:.1f}s', flush=True)
finish(SHOT)
