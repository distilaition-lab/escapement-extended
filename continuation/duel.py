"""THE DUEL — shots 8A-8H (our work). One continuous race on a timeline; each shot is a camera window onto it.

  stills : rb.py ../continuation/duel.py -- --shot 8C --stills 1,20,38 --pct 40 --samples 16 --tag _v1
  final  : rb.py ../continuation/duel.py -- --shot 8C --anim            -> film/renders/8C/####.png

Race time T (seconds). Hero = ESCAPEMENT's car (lib/car.py), rival = ours (continuation/rival.py). Their canyon
toolkit builds the environment on OUR road (custom curvature: S-bend, blind left under the cliff, wide left
sweeper with a barrier and a sheer drop). Sparks reuse their hot-metal spark material; the emitter is ours.
"""
import sys, os, math, time, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, '..', 'film', 'lib'), HERE]
from common import *
import canyon as C
import act2lib as A2
import rival as RV
import debris as DB
import numpy as np
from mathutils import Vector as V, Matrix, Quaternion

T_START = time.time()
FPSf = 24.0
LANE0 = 0.0

# ----------------------------------------------------------------------------------- the race (numbers first)


def keyed(keys):
    """smoothstep-eased piecewise function of T from [(T, value), ...]."""
    ks = sorted(keys)

    def f(T):
        if T <= ks[0][0]:
            return ks[0][1]
        for (ta, va), (tb, vb) in zip(ks, ks[1:]):
            if T <= tb:
                u = (T - ta) / (tb - ta)
                return va + (vb - va) * u * u * (3 - 2 * u)
        return ks[-1][1]
    return f


v_hero = keyed([(-3, 50), (12.8, 50), (14.6, 36), (15.4, 37), (16.6, 46), (17.6, 40), (18.3, 34), (20.6, 34), (23, 44)])
_gap_late = keyed([(8.4, 6.5), (9.8, 6.0), (10.4, 3.5), (11.2, 0.0), (14.0, 0.3),
             (15.0, -0.2), (15.6, 0.8), (17.0, 0.4), (18.5, -0.3), (20.0, 0.2), (23, 0.0)])


def gap(T):
    """metres the rival trails the hero: one smooth catch-up to T 8.4, then the battle keys."""
    if T < 8.4:
        u = max(0.0, T) / 8.4
        return 6.5 + 103.5 * (1 - u * u * (3 - 2 * u))
    return _gap_late(T)


lane_hero = keyed([(0, 1.85), (8.3, 1.85), (8.9, -0.6), (9.4, -0.9), (9.9, 0.0), (10.3, -0.4), (11.2, -1.55), (14.2, -1.6),
                   (14.8, -1.38), (15.05, -1.12), (15.5, -1.48), (17.0, -1.6), (18.0, -1.7), (19.5, -1.5), (21, -1.6)])
lane_rival = keyed([(0, 1.85), (3.0, 1.85), (4.2, -0.35), (6.6, -0.2), (7.0, 1.2), (7.8, -0.9), (8.6, -1.3), (9.2, -1.1), (9.8, 1.2), (10.3, 1.75), (11.4, 1.65),
                    (14.2, 1.6), (14.8, 1.32), (15.05, 1.22), (15.35, 1.75), (15.8, 1.5), (17.0, 1.6), (18.0, 1.85),
                    (19.5, 1.95), (21, 1.7)])
drift_hero = keyed([(14.0, 0.0), (14.5, 0.33), (15.3, 0.30), (15.9, 0.0), (17.7, 0.0), (18.3, 0.46), (19.8, 0.44), (20.6, 0.0)])
drift_rival = keyed([(14.0, 0.0), (14.5, 0.28), (14.98, 0.26), (15.15, 0.44), (15.4, 0.10), (15.9, 0.0), (17.8, 0.0),
                     (18.4, 0.42), (19.8, 0.46), (20.7, 0.0)])
CONTACT = (14.92, 15.32)            # doors grind: sparks
SPIN = (15.25, 16.4)                # hero rear wheelspin out of the blind corner

_TT = np.arange(-4.0, 26.0, 0.005)
_vh = np.array([v_hero(t) for t in _TT])
_SH = np.concatenate([[0.0], np.cumsum((_vh[1:] + _vh[:-1]) * 0.5 * 0.005)])
_SH += 100.0 - float(np.interp(0.0, _TT, _SH))


def s_hero(T):
    return float(np.interp(T, _TT, _SH))


def s_rival(T):
    return s_hero(T) - gap(T)


S_BLIND = s_hero(15.0)              # apex of the blind left-hander
S_WIDE = s_hero(19.0)               # middle of the wide left sweeper
DUEL_BUMPS = [(250, 60, 0.004), (720, 50, 0.006),        # long straight 330-660 for the telephoto
              (S_BLIND, 22, -0.026),            # blind LEFT under the cliff (cliff on the inside)
              (S_WIDE, 55, -0.011)]             # wide LEFT sweeper, drop on the outside (right)
road = C.Road(s0=-300.0, s1=1700.0, bumps=DUEL_BUMPS)
C.road_r = lambda rd, s: rd.at(s)[2]


def lane_yaw(lane_fn, s_fn, T):
    """heading change from a lane change (nose points where the car is going); + = nose left."""
    dl = lane_fn(T + 0.05) - lane_fn(T - 0.05)
    ds = s_fn(T + 0.05) - s_fn(T - 0.05)
    return -math.atan2(dl, max(ds, 0.5))


# --- the barrier + drop at the wide corner (patched into their terrain function)
_ground_orig = C.ground_h
CLIFF_D = 7.6


def ground_patched(s, d, x, y, H=None):
    g = _ground_orig(s, d, x, y, H)
    w = smooth_(S_WIDE - 140, S_WIDE - 90, s) * (1 - smooth_(S_WIDE + 90, S_WIDE + 140, s))
    if d > CLIFF_D and w > 0:
        drop = -0.16 - 62.0 * smooth_(0.0, 3.0, d - CLIFF_D) - 0.12 * (d - CLIFF_D)
        return g * (1 - w) + min(g, drop) * w
    return g


def smooth_(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


C.ground_h = ground_patched

# ----------------------------------------------------------------------------------- shots
#  id: (T0, T1, timescale, description)
SHOTS = {
    '8A': (1.0, 3.0, 1.0, 'bumper cam on the rival'),
    '8B': (4.5, 6.5, 1.0, 'head-on telephoto down the straight'),
    '8C': (7.0, 8.6, 1.0, 'wing-mirror cam on the hero'),
    '8D': (8.4, 10.6, 1.0, "bird's-eye: the block and the dive"),
    '8E': (11.0, 13.8, 1.0, 'aerial pursuit: side by side'),
    '8F': (14.3, 15.9, 1.0, 'static low pass-by at the blind corner'),
    '8G': (14.85, 15.45, 0.5, 'rival door cam: the scrape'),
    '8H': (18.0, 19.6, 0.33, 'slow-motion tandem drift over the drop'),
}


def frames_of(shot):
    T0, T1, ts, _ = SHOTS[shot]
    return int(round((T1 - T0) / ts * FPSf)) + 1


def T_of(shot):
    T0, T1, ts, _ = SHOTS[shot]
    return lambda f: T0 + (f - 1) / FPSf * ts

# ----------------------------------------------------------------------------------- build helpers


def hero_lights(car):
    C.car_lights(car, 4.0, 16.0, 1)
    m = car['mats'].get('rear_light')
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED' and not n.inputs['Emission Color'].links:
            n.inputs['Emission Color'].default_value = (1.0, 0.012, 0.004, 1)
    L = light('AREA', 'HeroRearGlow', (0, 0, 0), energy=60, color=(1.0, 0.03, 0.012), size=1.6, size_y=0.15)
    L.parent = car['root']; L.matrix_parent_inverse = Matrix.Identity(4)
    L.location = (0, -2.45, 0.85); L.rotation_euler = (math.radians(-90), 0, 0)


def rival_lights(rv):
    rcoll = rv['root'].users_collection[0]
    for nm, loc, energy, col, size in (('RivalRim', (0.8, -4.2, 1.9), 260.0, (1.0, 0.62, 0.36), 5.0),
                                       ('RivalSky', (0.0, 0.6, 3.6), 100.0, (0.55, 0.74, 0.92), 6.0)):
        L = light('AREA', nm, (0, 0, 0), energy=energy, color=col, size=size)
        L.parent = rv['root']; L.matrix_parent_inverse = Matrix.Identity(4)
        L.location = loc
        L.rotation_euler = (V((0, 0.2, 0.5)) - V(loc)).to_track_quat('-Z', 'Y').to_euler()
        L.data.volume_factor = 0.0
        L.data.specular_factor = 0.12
        L.visible_camera = False
        L.light_linking.receiver_collection = rcoll


def drive_pair(Tf, N):
    hero = C.get_car()
    rv = RV.build_rival()
    for car, s_of, lane_of, drift_of, seed in ((hero, s_hero, lane_hero, drift_hero, 3), (rv, s_rival, lane_rival, drift_rival, 7)):
        C.drive(car, road, lambda f, s_of=s_of: s_of(Tf(f)), -2, N + 3, lane=0.0,
                lane_fn=lambda f, lane_of=lane_of: lane_of(Tf(f)),
                yaw_fn=lambda f, s_of=s_of, lane_of=lane_of, drift_of=drift_of: drift_of(Tf(f)) + lane_yaw(lane_of, s_of, Tf(f)),
                roll_k=0.0036, pitch_k=0.0018, seed=seed)
    # ride height: the toolkit keyed the roots at the road's base height (tyres 5-7 cm into the crowned asphalt)
    for car, s_of, lane_of, drift_of in ((hero, s_hero, lane_hero, drift_hero), (rv, s_rival, lane_rival, drift_rival)):
        for fc in fcurves(car['root']):
            if fc.data_path == 'location' and fc.array_index == 2:
                for kp in fc.keyframe_points:
                    z = car_frame(s_of, lane_of, drift_of, Tf(kp.co[0]))[0].z
                    kp.co[1] = z; kp.handle_left[1] = z; kp.handle_right[1] = z
                fc.update()
    # wheelspin: hero rear wheels turn faster than the road out of the blind corner
    for w in hero['wheels'][2:]:
        for fc in fcurves(w):
            if fc.data_path == 'rotation_euler' and fc.array_index == 0:
                acc, prev_s = 0.0, None
                for kp in sorted(fc.keyframe_points, key=lambda k_: k_.co[0]):
                    T = Tf(kp.co[0])
                    s_now = s_hero(T)
                    extra = 0.9 * smooth_(SPIN[0], SPIN[0] + 0.15, T) * (1 - smooth_(SPIN[1] - 0.3, SPIN[1], T))
                    if prev_s is not None:
                        acc += extra * (s_now - prev_s) / 0.35          # wheel turns 1.9x faster than the road
                    prev_s = s_now
                    kp.co[1] += acc
                fc.update()
    hero_lights(car=hero)
    rival_lights(rv)
    return hero, rv


def car_frame(s_of, lane_of, drift_of, T):
    """world position + forward/right of a car at race time T (body yaw included)."""
    P, t, r, th, k = road.at(s_of(T))
    pos = P + r * lane_of(T)
    yaw = drift_of(T) + lane_yaw(lane_of, s_of, T)
    c, s = math.cos(yaw), math.sin(yaw)
    fwd = t * c - r * s           # + yaw = nose left = rotate toward -r
    right = r * c + t * s
    af, ar, tr = (1.35, 1.35, 0.86) if s_of is s_hero else (1.40, 1.40, 0.87)
    pos = V((pos.x, pos.y, DB.ride_z(road, pos, fwd, right, af, ar, tr)))     # tyres ON the crowned road (probe: 7 cm in)
    return pos, fwd, right


def hero_at(T):
    return car_frame(s_hero, lane_hero, drift_hero, T)


def rival_at(T):
    return car_frame(s_rival, lane_rival, drift_rival, T)


def world_vel(fn, T, dt=0.02):
    return (fn(T + dt)[0] - fn(T - dt)[0]) / (2 * dt)


def dust(name, density, color=(0.62, 0.43, 0.28), emit=0.03, N=200, **kw):
    kw.setdefault('contrast', 3.0); kw.setdefault('nscale', 2.4); kw.setdefault('soft', (0.32, 0.64))
    return C.mat_dust2(name, density=density, color=color, aniso=0.7, emit=emit, f0=-160, f1=N + 20, **kw)


def trails(Tf, N, ts, every=2):
    """road dust behind both cars always; grey tyre smoke when a car is sliding."""
    life = int(90 / max(ts, 0.3))
    d_mat = dust('Dust', 0.65, N=N)
    s_mat = dust('Smoke', 0.55, color=(0.55, 0.53, 0.50), emit=0.05, N=N, contrast=2.4, soft=(0.28, 0.60))
    for s_of, lane_of, drift_of, seed in ((s_hero, lane_hero, drift_hero, 41), (s_rival, lane_rival, drift_rival, 42)):
        sf = lambda f, s_of=s_of: s_of(Tf(f))
        lat = lambda f, lane_of=lane_of, drift_of=drift_of: lane_of(Tf(f)) + 1.35 * math.sin(drift_of(Tf(f)))
        C.dust_trail(road, sf, -30, N + 2, d_mat, every=every, life=life, lane=0.0, lateral=lat, grow=(2.8, 4.2, 1.6),
                     rise=0.6, seed=seed, spread=(-1.8, 2.4), dens=1.0)
        C.grit_spray(road, sf, 1, N + 2, every=2 if ts == 1.0 else 3, lane=0.0, n_per=40, life=int(12 / max(ts, 0.3)),
                     lateral=lat, size=(0.006, 0.018), seed=seed + 20, back=(3.0, 8.0), up=(1.0, 2.6))
        slide = lambda s, f, drift_of=drift_of: abs(drift_of(Tf(f))) < 0.12 and not (SPIN[0] < Tf(f) < SPIN[1] and seed == 41)
        C.dust_trail(road, sf, -20, N + 2, s_mat, every=every, life=life, lane=0.0, lateral=lat, grow=(2.6, 3.6, 1.8),
                     rise=0.9, seed=seed + 10, skip=slide, spread=(-1.0, 1.5), dens=1.0)


def violence(s_of, lane_of, drift_of, T, hero=False):
    """0..1.5: how hard a car is working its tyres at race time T (slide, sudden lane change, contact, wheelspin)."""
    rate = abs(lane_of(T + 0.05) - lane_of(T - 0.05)) / 0.1
    it = 1.8 * abs(drift_of(T)) + 0.16 * rate
    it += 1.0 * smooth_(CONTACT[0] - 0.45, CONTACT[0], T) * (1 - smooth_(CONTACT[1], CONTACT[1] + 0.35, T))
    if hero:
        it += 0.6 * smooth_(SPIN[0], SPIN[0] + 0.15, T) * (1 - smooth_(SPIN[1] - 0.3, SPIN[1], T))
    return min(1.5, it)


CARS = (('hero', s_hero, lane_hero, drift_hero, 1.35, 0.86), ('rival', s_rival, lane_rival, drift_rival, 1.40, 0.87))


def rear_wheel(s_of, lane_of, drift_of, T, back, x):
    pos, fwd, right = car_frame(s_of, lane_of, drift_of, T)
    return pos - fwd * back + right * x


def violence_fx(Tf, N, ts):
    """big chunks kicked off the rear tyres, bits lying on the road, rubber marks laid in time."""
    emit, tracks = [], []
    for nm, s_of, lane_of, drift_of, back, tx in CARS:
        it = lambda T, s_of=s_of, lane_of=lane_of, drift_of=drift_of, h=(nm == 'hero'): violence(s_of, lane_of, drift_of, T, h)
        vel = lambda T, s_of=s_of, lane_of=lane_of, drift_of=drift_of: world_vel(lambda t: car_frame(s_of, lane_of, drift_of, t), T)

        def out(T, s_of=s_of, lane_of=lane_of, drift_of=drift_of):
            d = drift_of(T)
            if abs(d) < 0.08:
                return None
            return car_frame(s_of, lane_of, drift_of, T)[2] * (1 if d > 0 else -1)
        for x in (-tx, tx):
            pf = lambda T, s_of=s_of, lane_of=lane_of, drift_of=drift_of, back=back, x=x: rear_wheel(s_of, lane_of, drift_of, T, back, x)
            emit.append((pf, vel, out, it))
            tracks.append((pf, it))
    DB.kick_chunks('Kick', Tf, N, emit, road, seed=71, max_per=4 if ts == 1.0 else 3, base=0.15, cap=1500)
    DB.tyre_marks('Rubber', road, Tf, N, tracks, max(0.0, Tf(1) - 8.0), Tf(N) + 0.05)


def road_grit(Tf, N, every_m=10.0, seed=61):
    """sparse airborne grit + dust specks hanging over the road: static in the world, so every moving camera
    streaks them past the lens (the strongest cue of speed in the tracking and aerial shots)."""
    s0 = min(s_rival(Tf(1)), s_hero(Tf(1))) - 20
    s1 = max(s_rival(Tf(N)), s_hero(Tf(N))) + 40
    s, i = s0, 0
    while s < s1:
        c = road.point(s, 0.0, 0.0)
        C.motes((c.x, c.y, 0.0), radius=8.0, n=55, size=(0.003, 0.009), strength=0.6, zmax=3.2, seed=seed + i,
                f0=1, f1=N + 2, name=f'RoadGrit{i}')
        s += every_m
        i += 1


def sparks(Tf, N, ts, coll=None, per_frame=9, seed=5):
    """door-to-door grinding: sparks born at the contact patch, carrying the cars' velocity, thrown back and out."""
    _, me = A2.spark_mat()
    rng = random.Random(seed)
    coll = coll or collection('Sparks')
    dt = ts / FPSf
    out = []
    for f in range(1, N + 1):
        T = Tf(f)
        if not (CONTACT[0] <= T <= CONTACT[1]):
            continue
        ph, fh, rh = hero_at(T)
        pr, fr, rr = rival_at(T)
        mid = (ph + pr) / 2
        vbase = (world_vel(hero_at, T) + world_vel(rival_at, T)) / 2
        side = (pr - ph).normalized()
        for i in range(per_frame):
            o = bpy.data.objects.new(f'spk{f}_{i}', me)
            link(o, coll)
            o.visible_shadow = False
            p = mid + fh * rng.uniform(-1.4, 0.9) + V((0, 0, rng.uniform(0.35, 0.62)))
            v = vbase * rng.uniform(0.75, 0.95) - fh * rng.uniform(2, 9) + side * rng.uniform(-3, 3) + V((0, 0, rng.uniform(0, 3)))
            lf = rng.randint(4, 10)
            o.scale = (0, 0, 0); o.keyframe_insert('scale', frame=f - 1)
            th = rng.uniform(0.6, 1.3) * 0.0032
            for k in range(lf + 1):
                if k:
                    v.z -= 9.8 * dt
                    p = p + v * dt
                    if p.z < 0.02:
                        p.z = 0.02; v.z = -v.z * 0.3
                o.location = p
                o.keyframe_insert('location', frame=f + k)
                rel = v - vbase * 0.0
                o.rotation_euler = rel.normalized().to_track_quat('X', 'Z').to_euler()
                o.keyframe_insert('rotation_euler', frame=f + k)
                u = k / lf
                o.color = (1.0, 0.92 - 0.45 * u, 0.62 - 0.6 * min(1.0, u * 1.6), 1.0) if u < 0.6 else (0.95 - 0.35 * u, 0.45 - 0.33 * u, 0.03, 1.0)
                o.keyframe_insert('color', frame=f + k)
                ln = max(0.008, v.length * 0.5 * dt * 0.7)
                o.scale = (ln, th * (1 - u ** 3), th * (1 - u ** 3))
                o.keyframe_insert('scale', frame=f + k)
            o.scale = (0, 0, 0); o.keyframe_insert('scale', frame=f + lf + 1)
            set_interp(o, 'LINEAR')
            out.append(o)
        if f % 2 == 0:      # contact flash on the doors
            L = light('POINT', f'grind{f}', mid + V((0, 0, 0.5)), energy=0.0, color=(1.0, 0.55, 0.2))
            for fk, e in ((f - 1, 0.0), (f, 40.0), (f + 2, 0.0)):
                L.data.energy = e; L.data.keyframe_insert('energy', frame=fk)
    return out


def guardrail(s0, s1, d=4.7, coll=None):
    """galvanised W-beam guardrail on steel posts along the outside of the wide corner."""
    coll = coll or collection('Barrier')
    steel = mat_metal('Galv', base=(0.48, 0.49, 0.50), rough=(0.25, 0.55), scale=4.0, bump=0.04)
    refl = mat_emission('BarrierRefl', (1.0, 0.28, 0.03), 2.5)
    bm = bmesh.new(); bp = bmesh.new(); br = bmesh.new()
    prof = [(0.0, 0.50), (0.05, 0.53), (0.05, 0.58), (0.0, 0.61), (0.0, 0.64), (0.05, 0.67), (0.05, 0.72), (0.0, 0.75)]
    secs = []
    s = s0
    while s <= s1:
        P, t, r, th, k = road.at(s)
        base = P + r * d
        secs.append([base + r * (x + 0.06) + V((0, 0, z)) for x, z in prof] +
                    [base + r * (x + 0.075) + V((0, 0, z)) for x, z in reversed(prof)])
        s += 0.5
    vs = [[bm.verts.new(p) for p in sec] for sec in secs]
    n = len(vs[0])
    for i in range(len(vs) - 1):
        for j in range(n):
            bm.faces.new((vs[i][j], vs[i][(j + 1) % n], vs[i + 1][(j + 1) % n], vs[i + 1][j]))
    rail = bpy.data.meshes.new('rail'); bm.to_mesh(rail); bm.free()
    o = bpy.data.objects.new('GuardRail', rail); link(o, coll); set_mat(o, steel)
    s = s0
    while s <= s1:
        P, t, r, th, k = road.at(s)
        base = P + r * (d + 0.14)
        Mr = Matrix.Translation(base + V((0, 0, 0.35))) @ Matrix.Rotation(-th, 4, 'Z')
        bmesh.ops.create_cube(bp, size=1.0, matrix=Mr @ Matrix.Diagonal((0.08, 0.12, 0.95, 1)))
        Mq = Matrix.Translation(base - r * 0.10 + V((0, 0, 0.84))) @ Matrix.Rotation(-th, 4, 'Z')
        bmesh.ops.create_cube(br, size=1.0, matrix=Mq @ Matrix.Diagonal((0.012, 0.06, 0.04, 1)))
        s += 2.0
    po = bpy.data.meshes.new('posts'); bp.to_mesh(po); bp.free()
    o2 = bpy.data.objects.new('GuardPosts', po); link(o2, coll); set_mat(o2, steel)
    rr = bpy.data.meshes.new('refl'); br.to_mesh(rr); br.free()
    o3 = bpy.data.objects.new('GuardRefl', rr); link(o3, coll); set_mat(o3, refl)
    for ob in (o, o2):
        bev = ob.modifiers.new('bev', 'BEVEL'); bev.width = 0.004; bev.segments = 1
    return o


def key_cam(cam, N, pos_fn, aim_fn, omega=1.0, zeta=0.8, sub=6, roll_fn=None):
    """world-space camera: position per frame, aim through a damped spring (operator lag)."""
    def yp(d):
        d = d.normalized(); return math.atan2(d.y, d.x), math.asin(max(-1, min(1, d.z)))
    y, p = yp(aim_fn(1) - pos_fn(1)); vy = vp = 0.0; prev = None
    for f in range(1, N + 3):
        if f > 1:
            for k in range(sub):
                ff = f - 1 + (k + 1) / sub
                ty, tp = yp(aim_fn(ff) - pos_fn(ff))
                dy = (ty - y + math.pi) % (2 * math.pi) - math.pi
                vy += (omega * omega * dy - 2 * zeta * omega * vy) / sub
                vp += (omega * omega * (tp - p) - 2 * zeta * omega * vp) / sub
                y += vy / sub; p += vp / sub
        d = V((math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)))
        q = d.to_track_quat('-Z', 'Y')
        if roll_fn:
            q = Quaternion(d, roll_fn(f)) @ q
        e = q.to_euler('XYZ', prev) if prev else q.to_euler('XYZ')
        prev = e
        cam.location = pos_fn(f); cam.rotation_euler = e
        cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
    set_interp(cam, 'BEZIER')


def mount_cam(name, parent, loc, rot_deg, lens, fstop=4.0, focus=3.0):
    cam = camera(name, (0, 0, 0), lens=lens, fstop=fstop, focus=focus, clip=(0.02, 4000))
    cam.parent = parent; cam.matrix_parent_inverse = Matrix.Identity(4)
    cam.location = loc
    cam.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    return cam

# ----------------------------------------------------------------------------------- the shots


def build(shot):
    T0, T1, ts, desc = SHOTS[shot]
    N = frames_of(shot)
    Tf = T_of(shot)
    reset()
    C._SCATTER_NG = None
    C._PUFF_ME.clear()
    sc = setup_render(1, N, samples=48, vol_tile='4', vol_samples=64, vol_end=170.0 if shot in ('8H', '8B') else 90.0, vol_start=0.2,
                      look='AgX - Medium High Contrast', shutter=0.7 if ts == 1.0 else 0.4,
                      exposure={'8B': -0.6, '8D': -0.1}.get(shot, -0.3))
    ee = sc.eevee
    ee.volumetric_sample_distribution = 0.8; ee.volumetric_light_clamp = 20.0; ee.volumetric_ray_depth = 16
    ee.motion_blur_max = 128; ee.motion_blur_steps = 4; ee.shadow_pool_size = '1024'
    Tm = (T0 + T1) / 2
    ph, fh, rh = hero_at(Tm)
    pr, fr, rr = rival_at(Tm)
    mid = lambda f: (hero_at(Tf(f))[0] + rival_at(Tf(f))[0]) / 2 + V((0, 0, 0.6))
    hero, rv = drive_pair(Tf, N)
    s_lo = min(s_rival(Tf(1)), s_hero(Tf(1))) - 70
    s_hi = max(s_rival(Tf(N)), s_hero(Tf(N))) + 90
    cam_view = None
    # --------------------------------------------------------------------------- cameras
    if shot == '8A':          # bumper cam: on the rival's nose, splitter height
        cam = mount_cam('Cam8A', rv['sprung'], (0.30, 2.44, 0.22), (90, 0, 0), 18, fstop=8.0, focus=20.0)
        cam_view = fr
        s_hi += 120
    elif shot == '8B':        # head-on telephoto from far down the straight
        s_cam = s_hero(T1) + 170
        cp = road.point(s_cam, -0.3, 1.5)
        cam = camera('Cam8B', cp, lens=300, fstop=4.0, focus=250.0, clip=(0.5, 6000))
        key_cam(cam, N, lambda f: cp, lambda f: (hero_at(Tf(f))[0] * 0.55 + rival_at(Tf(f))[0] * 0.45) + V((0, 0, 0.7)),
                omega=0.6, zeta=0.9)
        fd = cam.data.dof
        for f in range(1, N + 3, 2):
            fd.focus_distance = (hero_at(Tf(f))[0] - cp).length; fd.keyframe_insert('focus_distance', frame=f)
        cam_view = (ph - cp).normalized()
        s_hi = s_cam + 60
    elif shot == '8C':        # wing-mirror cam on the hero (left side), looking back along the flank
        cam = mount_cam('Cam8C', hero['sprung'], (-1.16, 0.36, 0.97), (86, 0, 185), 22, fstop=5.6, focus=6.0)
        cam_view = -fh
    elif shot == '8D':        # bird's-eye, locked above the pair, road running up the frame
        def pos(f):
            return mid(f) + V((0, 0, 30.0))

        def roll(f):
            return 0.0
        cam = camera('Cam8D', pos(1), lens=35, fstop=11.0, focus=30.0, clip=(0.5, 4000))
        for f in range(1, N + 3):
            P, t, r, th, k = road.at((s_hero(Tf(f)) + s_rival(Tf(f))) / 2 + 3)
            cam.location = pos(f) + t * 3.0
            cam.rotation_euler = (0.0, 0.0, -th)                      # looking straight down, frame-up = road tangent
            cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
        set_interp(cam, 'BEZIER')
        cam_view = V((0, 0, -1)); cam_view_h = fh
    elif shot == '8E':        # aerial pursuit: drone ahead-right of the pair, flying backward at their speed
        def pos(f):
            T = Tf(f)
            sm = (s_hero(T) + s_rival(T)) / 2
            ahead = 13.0 - 6.0 * (f - 1) / N
            return road.point(sm + ahead, 7.8 - 1.5 * (f - 1) / N, 3.8 - 1.2 * (f - 1) / N)
        cam = camera('Cam8E', pos(1), lens=28, fstop=4.0, focus=12.0, clip=(0.05, 4000))
        key_cam(cam, N, pos, mid, omega=1.2)
        fd = cam.data.dof
        for f in range(1, N + 3, 2):
            fd.focus_distance = (mid(f) - pos(f)).length; fd.keyframe_insert('focus_distance', frame=f)
        cam_view = (mid(N // 2) - pos(N // 2)).normalized()
    elif shot == '8F':        # static curb cam at the blind corner exit, outside edge
        cp = road.point(S_BLIND + 8.0, 5.6, 0.32)
        cam = camera('Cam8F', cp, lens=22, fstop=4.0, focus=15.0, clip=(0.02, 4000))
        key_cam(cam, N, lambda f: cp, mid, omega=0.9, zeta=0.75)
        fd = cam.data.dof
        for f in range(1, N + 3, 2):
            fd.focus_distance = max(2.0, (mid(f) - cp).length); fd.keyframe_insert('focus_distance', frame=f)
        cam_view = (ph - cp).normalized()
    elif shot == '8G':        # door cam on the rival's left flank, looking back along the grinding doors
        cam = mount_cam('Cam8G', rv['sprung'], (-1.00, 1.15, 0.66), (86, 0, 188), 20, fstop=4.0, focus=1.6)   # inboard: the hero's door never swallows the lens
        cam_view = -fr
    elif shot == '8H':        # slow-mo: drone hovering over the drop beyond the barrier, tracking the tandem drift
        def pos(f):
            T = Tf(f)
            sm = (s_hero(T) + s_rival(T)) / 2
            return road.point(sm + 15.0 - 8.0 * (f - 1) / N, 15.0, 3.4)    # over the void, ahead: front three-quarter on the drift
        cam = camera('Cam8H', pos(1), lens=26, fstop=4.0, focus=12.0, clip=(0.05, 4000))
        key_cam(cam, N, pos, lambda f: mid(f) - V((0, 0, 1.2)), omega=0.8)   # barrier + cars, the face dropping away below
        fd = cam.data.dof
        for f in range(1, N + 3, 2):
            fd.focus_distance = (mid(f) - pos(f)).length; fd.keyframe_insert('focus_distance', frame=f)
        cam_view = (mid(N // 2) - pos(N // 2)).normalized()
        guardrail(S_WIDE - 120, S_WIDE + 120)
    sc.camera = cam
    # --------------------------------------------------------------------------- light: back-light every shot
    h = V((cam_view.x, cam_view.y, 0))
    if h.length < 0.1:
        h = V((fh.x, fh.y, 0))
    h.normalize()
    # per-shot sun: back-light by default; the bird's-eye wants a higher sun (long shadows, contrast from above),
    # the side-by-side a sun swung round to the side (the flanks catch it instead of a murky back-lit dust wall)
    off_deg, elev = {'8D': (-70, 18.0), '8E': (70, 7.0)}.get(shot, (28, 4.5))   # 8D: canyon side, or the cliff shades the road
    a = math.radians(off_deg)
    C.set_sun((h.x * math.cos(a) - h.y * math.sin(a), h.x * math.sin(a) + h.y * math.cos(a)), elev)
    C.mat_sky_world(fog=0.0008 if shot == '8B' else 0.0022, strength=1.15)   # telephoto: 170 m of haze washed it out
    C.sun_lamp(4.2)
    C.build_environment(road, s_lo, s_hi, res=1.6)
    trails(Tf, N, ts, every=1 if ts == 1.0 else 2)
    road_grit(Tf, N)
    violence_fx(Tf, N, ts)
    DB.road_debris('RoadBits', road, s_lo + 30, s_hi - 20, per_m=6.0, seed=81,
                   hot=((S_BLIND, 45.0, 3.0), (s_hero(9.0), 30.0, 2.0), (S_WIDE, 70.0, 2.0)))
    if Tf(1) <= CONTACT[1] and Tf(N) >= CONTACT[0]:
        sparks(Tf, N, ts)
    if shot in ('8F', '8G') and not any(o.name == 'GuardRail' for o in bpy.data.objects):
        pass
    C.comp(bloom=0.4, threshold=0.9, size=0.7, dispersion=0.006, streaks=0.18, streak_thr=4.0)
    print(f'[duel] {shot} {desc}: T {T0}-{T1} x{ts}, {N} frames, s {s_lo:.0f}-{s_hi:.0f}, built in {time.time() - T_START:.1f}s',
          flush=True)
    return sc


if __name__ == '__main__':          # importable by finale.py (race timeline + helpers)
    build(str(arg('--shot', '8A')))
    finish(str(arg('--shot', '8A')))
