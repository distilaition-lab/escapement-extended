"""THE FALL — shots 9A-9D (our work): the barrier crash, the hero on the edge + donut, the rival's flip and plunge.

  stills : rb.py ../continuation/finale.py -- --shot 9B --stills 1,24,48 --pct 40 --samples 16 --tag _v1
  final  : rb.py ../continuation/finale.py -- --shot 9B --anim

Continues the race timeline of duel.py (same road, same cars, same T). After T 19.9 both cars leave the road model:
  rival: slides wide, breaks the barrier at T_B, goes over the edge at T_EDGE, then a ballistic fall with a tumbling roll
  hero : follows through the gap, stops with its right wheels hanging over the drop (rocking), then a smoky donut back
         onto the road and a halt.
"""
import sys, os, math, random, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, '..', 'film', 'lib'), HERE]
from common import *
import canyon as C
import duel as D
import numpy as np
from mathutils import Vector as V, Matrix, Euler

T_START = time.time()
road = D.road
smooth_ = D.smooth_
keyed = D.keyed
G = 9.81
WR = 0.35          # hero wheel radius (car.py)
WRR = 0.36         # rival

# ----------------------------------------------------------------------------------- crash timeline (numbers first)
T_B = 20.00        # rival's right flank meets the barrier
T_EDGE = 20.18     # rival's centre crosses the cliff edge -> ballistic
T_HH = 20.45       # hero hits what is left of the barrier
T_OVER = 20.95     # hero's right wheels are over the drop, body rolled toward the void (no stop: it keeps sliding)
T_PIVOT = 21.25    # full lock + wheelspin: it starts dragging itself back on
T_HALT = 23.60     # hero at rest after the donut

lane_r2 = keyed([(19.70, D.lane_rival(19.70)), (20.00, 3.75), (T_EDGE, D.CLIFF_D)])
slip_r2 = keyed([(19.80, D.drift_rival(19.80)), (20.10, 0.80), (T_EDGE, 0.95)])


def spline(keys):
    """Catmull-Rom through (T, value) keys: smooth AND moving through every key (no stop at keys, unlike smoothstep)."""
    ks = sorted(keys)
    Ts = [k[0] for k in ks]
    Vs = [k[1] for k in ks]

    def f(T):
        if T <= Ts[0]:
            return Vs[0]
        if T >= Ts[-1]:
            return Vs[-1]
        i = max(0, min(len(Ts) - 2, int(np.searchsorted(Ts, T)) - 1))
        t0, t1 = Ts[i], Ts[i + 1]
        p0, p1 = Vs[i], Vs[i + 1]
        m0 = (Vs[i + 1] - Vs[i - 1]) / (Ts[i + 1] - Ts[i - 1]) if i > 0 else (p1 - p0) / (t1 - t0)
        m1 = (Vs[i + 2] - Vs[i]) / (Ts[i + 2] - Ts[i]) if i + 2 < len(Ts) else (p1 - p0) / (t1 - t0)
        h = t1 - t0
        u = (T - t0) / h
        h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
        return h00 * p0 + h10 * h * m0 + h01 * p1 + h11 * h * m1
    return f


T0H = 19.90
v_h2 = spline([(T0H, 34.0), (20.20, 30.0), (T_HH, 24.0), (20.75, 15.0), (T_OVER, 9.0), (T_PIVOT, 7.0), (22.0, 6.0),
               (22.8, 3.5), (23.3, 1.0), (T_HALT, 0.0)])
lane_h2 = spline([(T0H, D.lane_hero(T0H)), (20.20, 1.2), (T_HH, 4.2), (20.75, 6.9), (T_OVER, 7.45), (21.15, 7.40),
                  (21.45, 6.9), (21.8, 5.6), (22.3, 3.8), (22.9, 2.2), (T_HALT, 1.4)])
yaw_h2 = spline([(T0H, D.drift_hero(T0H)), (20.20, 0.70), (T_HH, 0.92), (20.75, 0.48), (T_OVER, 0.06), (21.15, 0.18),
                 (21.45, 0.75), (21.8, 1.75), (22.3, 3.40), (22.9, 5.30), (23.3, 6.40), (T_HALT, 6.75)])
roll_h2 = spline([(T0H, 0.0), (20.60, 0.02), (20.85, 0.11), (T_OVER, 0.17), (21.15, 0.18), (21.35, 0.12), (21.6, 0.03),
                  (21.8, 0.0), (T_HALT, 0.0)])
steer_h2 = spline([(T0H, -0.20), (20.6, -0.35), (T_OVER, -0.10), (21.15, 0.45), (T_PIVOT, 0.60), (23.0, 0.60), (T_HALT, 0.35)])

_TT = np.arange(19.0, T_HALT + 1.5, 0.002)
_vh = np.array([D.v_hero(t) if t < T0H else max(0.0, v_h2(t)) for t in _TT])
_SH = np.concatenate([[0.0], np.cumsum((_vh[1:] + _vh[:-1]) * 0.5 * 0.002)])
_SH += D.s_hero(19.0) - _SH[0]


def s_h2(T):
    return float(np.interp(T, _TT, _SH))


S_OVER = s_h2(T_OVER)
S_STOP = S_OVER


def pose_from_road(s, lane, slip, axles=(1.35, 1.35, 0.86)):
    """root position ON the built surface (crowned road / gravel shoulder; over the edge it rests on the supported
    wheels) + yaw. The probe found the old flat placement 5-15 cm into the road and the shoulder."""
    import debris as DB
    P, t, r, th, k = road.at(s)
    p = P + r * lane
    yaw = -th + slip
    fwd = V((-math.sin(yaw), math.cos(yaw), 0)); right = V((math.cos(yaw), math.sin(yaw), 0))
    return V((p.x, p.y, DB.ride_z(road, p, fwd, right, *axles))), yaw


HERO_W = [(-0.86, 1.35, 0.0), (0.86, 1.35, 0.0), (-0.86, -1.35, 0.0), (0.86, -1.35, 0.0)]
RIVAL_W = [(-0.87, 1.40, 0.0), (0.87, 1.40, 0.0), (-0.87, -1.40, 0.0), (0.87, -1.40, 0.0)]


def settle(p, yaw, roll, pitch, wheels):
    """after the body is tilted (roll/pitch on the root tilts the wheels too), drop/raise the root so the lowest
    SUPPORTED tyre sits exactly on the surface: none sinks in (probe: 7-15 cm), wheels over the drop are ignored."""
    import debris as DB
    M = Euler((pitch, roll, yaw), 'XYZ').to_matrix()
    need = []
    for w in wheels:
        off = M @ V(w)
        g = DB.ground_z(road, p.x + off.x, p.y + off.y)
        need.append((g, g - off.z))
    top = max(g for g, _ in need)
    return V((p.x, p.y, max(n for g, n in need if g > top - 0.3)))


def ground_pass(car, pose_fn, Tf, f0, f1, wheels, T_max=None):
    """after the environment exists: re-key the root height against the BUILT surface meshes (road, shoulders,
    terrain), so the supported tyres touch what is rendered. The formula surface (debris.ground_z) misses the coarse
    terrain grid at the cliff lip by up to ~0.25 m (gate probe + 9W event strip: the hero hovered over the lip)."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in bpy.data.objects:
        if o.type == 'MESH' and (o.name in ('Road', 'ShoulderL', 'ShoulderR') or o.name.startswith('Terrain')):
            me = o.evaluated_get(dg).to_mesh()
            b = len(verts)
            verts += [o.matrix_world @ v.co for v in me.vertices]
            polys += [[b + i for i in p_.vertices] for p_ in me.polygons]
            o.evaluated_get(dg).to_mesh_clear()
    tree = BVHTree.FromPolygons(verts, polys)
    zc = [fc for fc in fcurves(car['root']) if fc.data_path == 'location' and fc.array_index == 2][0]
    kps = {int(round(kp.co[0])): kp for kp in zc.keyframe_points}
    rc = {i: {int(round(kp.co[0])): kp for kp in fc.keyframe_points}
          for fc in fcurves(car['root']) if fc.data_path == 'rotation_euler' for i in (fc.array_index,) if i in (0, 1)}
    n = 0
    for f in range(f0, f1 + 1):
        T = Tf(f)
        if T_max is not None and T > T_max or f not in kps:
            continue
        p, yaw, roll, pitch = pose_fn(T)
        # tilt the rigid car to the ground under its SUPPORTED tyres (front/rear always, left/right when both sides
        # are supported; over the drop the scripted roll stays), then set the height so they touch
        for _ in range(3):
            M = Euler((pitch, roll, yaw), 'XYZ').to_matrix()
            gs = []
            for w in wheels:
                off = M @ V(w)
                hit = tree.ray_cast(V((p.x + off.x, p.y + off.y, p.z + 6.0)), V((0, 0, -1)), 40.0)
                gs.append((hit[0].z if hit[0] is not None else None, off, w))
            known = [g for g, _, _ in gs if g is not None]
            if not known:
                break
            top = max(known)
            sup = [(g, off, w) for g, off, w in gs if g is not None and g > top - 0.3]
            fr = [g for g, _, w in sup if w[1] > 0]; rr = [g for g, _, w in sup if w[1] < 0]
            lf = [g for g, _, w in sup if w[0] < 0]; rt = [g for g, _, w in sup if w[0] > 0]
            if fr and rr:
                pitch = math.atan2(sum(fr) / len(fr) - sum(rr) / len(rr), abs(wheels[0][1]) + abs(wheels[2][1]))
            if lf and rt:
                roll = math.atan2(sum(lf) / len(lf) - sum(rt) / len(rt), 2 * abs(wheels[0][0]))
        if not known:
            continue
        M = Euler((pitch, roll, yaw), 'XYZ').to_matrix()
        z = max(g - (M @ V(w)).z for g, off, w in sup)
        kp = kps[f]
        kp.co[1] = z; kp.handle_left[1] = z; kp.handle_right[1] = z
        for i, v_ in ((0, pitch), (1, roll)):
            k_ = rc.get(i, {}).get(f)
            if k_ is not None:
                k_.co[1] = v_; k_.handle_left[1] = v_; k_.handle_right[1] = v_
        n += 1
    zc.update()
    for fc in fcurves(car['root']):
        fc.update()
    print(f"[finale] ground pass {car['root'].name}: {n} frames on the built surface", flush=True)


def hero_pose(T):
    """(location, yaw, roll, pitch) of the hero root; roll + = right side down (toward the drop)."""
    if T < T0H:
        p, f, r = D.hero_at(T)
        return p, -road.at(D.s_hero(T))[3] + D.drift_hero(T) + D.lane_yaw(D.lane_hero, D.s_hero, T), 0.0, 0.0
    p, yaw = pose_from_road(s_h2(T), lane_h2(T), yaw_h2(T))
    roll = roll_h2(T)
    chatter = 0.012 * math.sin(T * 63.0) * smooth_(20.8, T_OVER, T) * (1 - smooth_(21.4, 21.7, T))  # the sill grinding the rock
    pitch = -0.025 * smooth_(20.8, T_OVER, T) * (1 - smooth_(21.3, 21.6, T))
    return settle(p, yaw, roll + chatter, pitch, HERO_W), yaw, roll + chatter, pitch


def rival_pose(T):
    if T < 19.7:
        p, f, r = D.rival_at(T)
        return p, -road.at(D.s_rival(T))[3] + D.drift_rival(T) + D.lane_yaw(D.lane_rival, D.s_rival, T), 0.0, 0.0
    if T <= T_EDGE:
        p, yaw = pose_from_road(D.s_rival(T), lane_r2(T), slip_r2(T), (1.40, 1.40, 0.87))
        roll = -0.10 * smooth_(T_B, T_B + 0.08, T)              # the barrier hit rocks it up on its right side
        return settle(p, yaw, roll, 0.0, RIVAL_W), yaw, roll, 0.0
    p0, yaw0, _, _ = rival_pose(T_EDGE)
    P, t, r, th, k = road.at(D.s_rival(T_EDGE))
    v0 = t * 26.0 + r * 17.0 + V((0, 0, 1.8))       # v6: lands on the flat valley floor (the breach), not the cliff toe
    tau = T - T_EDGE
    p = p0 + v0 * tau + V((0, 0, -0.5 * G * tau * tau))
    # heads for the ground: nose pitches down to ~70 deg, a slow roll toward the void, a little yaw
    # v6b tumble (user: the roof cam first sees sky and clouds, then the ground): nose up off the edge, then it
    # pitches over and dives nose-first at the valley floor
    pitch = 0.9 * smooth_(0.0, 0.5, tau) - 2.12 * smooth_(1.0, 2.6, tau)
    return p, yaw0 + 0.25 * tau, 0.10 + 0.10 * tau, pitch


_IMPACT = []


def impact():
    """(T, point) where the rival's nose meets the valley floor (z -54): the breach."""
    if not _IMPACT:
        T = T_EDGE
        while T < 26.0 and wheel_world(rival_pose, T, (0, 2.45, 0.3)).z > -54.0:
            T += 0.002
        P = wheel_world(rival_pose, T, (0, 2.45, 0.3)); P.z = -54.0
        _IMPACT.extend([T, P])
    return _IMPACT[0], _IMPACT[1]


def rival_vel(T, dt=0.01):
    return (rival_pose(T + dt)[0] - rival_pose(T - dt)[0]) / (2 * dt)


def hero_vel(T, dt=0.01):
    return (hero_pose(T + dt)[0] - hero_pose(T - dt)[0]) / (2 * dt)


def key_car(car, pose_fn, Tf, f0, f1, R, spin_fn=None, steer_fn=None):
    """Key root location + XYZ rotation (pitch, roll, yaw); wheels roll by distance (+ per-wheel extra spin);
    front hubs steer (steer_fn: radians, + = left)."""
    root = car['root']
    root.rotation_mode = 'XYZ'
    sp = car.get('sprung')
    parts = car.get('parts', {})
    hubs = [parts.get('corner_FL'), parts.get('corner_FR')]
    base = {h.name: h.rotation_euler[2] for h in hubs if h is not None}
    dist = 0.0
    prev = None
    for f in range(f0, f1 + 1):
        T = Tf(f)
        p, yaw, roll, pitch = pose_fn(T)
        root.location = p
        root.rotation_euler = (pitch, roll, yaw)
        root.keyframe_insert('location', frame=f)
        root.keyframe_insert('rotation_euler', frame=f)
        if prev is not None:
            dist += (p - prev).length
        prev = p
        extra = spin_fn(T) if spin_fn else (0.0, 0.0, 0.0, 0.0)
        for i, w in enumerate(car['wheels']):
            w.rotation_mode = 'XYZ'
            w.rotation_euler[0] = dist / R + extra[i]
            w.keyframe_insert('rotation_euler', index=0, frame=f)
        if steer_fn:
            for h in hubs:
                if h is not None:
                    h.rotation_euler[2] = base[h.name] + steer_fn(T)
                    h.keyframe_insert('rotation_euler', index=2, frame=f)
        if sp is not None:
            sp.location = (0, 0, 0.004 * math.sin(f * 2.1))
            sp.keyframe_insert('location', frame=f)
    set_interp(root, 'LINEAR')
    for w in car['wheels']:
        set_interp(w, 'LINEAR')


def _integ(rate, T, T0=20.6, dt=0.01):
    a, t = 0.0, T0
    while t < T:
        a += rate(t) * dt
        t += dt
    return a


def hero_spin(T):
    """extra wheel radians [FL, FR, RL, RR]: the right wheels spin free over the drop, the rears burn through the donut."""
    air = lambda t: 70.0 * smooth_(20.85, T_OVER, t) * (1 - smooth_(21.45, 21.75, t))
    burn = lambda t: 95.0 * smooth_(21.0, T_PIVOT, t) * (1 - smooth_(22.9, T_HALT, t))
    fr = _integ(air, T)
    rl = _integ(burn, T)
    rr = _integ(lambda t: max(air(t), burn(t)), T)
    return (0.0, fr, rl, rr)

# ----------------------------------------------------------------------------------- the barrier, in breakable pieces


RELEASE = {}
WRECK_SPAN = [0.0, 0.0]


def build_barrier(s0, s1, breaks, coll=None, s_rb=0.0):
    """breaks: [(s_from, s_to, T_release, car_vel_fn)]; pieces inside a break zone fly off at T_release."""
    coll = coll or collection('Barrier')
    steel = mat_metal('Galv', base=(0.48, 0.49, 0.50), rough=(0.25, 0.55), scale=4.0, bump=0.04)
    refl = mat_emission('BarrierRefl', (1.0, 0.28, 0.03), 2.5)
    d = 4.7
    prof = [(0.0, 0.50), (0.05, 0.53), (0.05, 0.58), (0.0, 0.61), (0.0, 0.64), (0.05, 0.67), (0.05, 0.72), (0.0, 0.75)]
    pieces = []

    def rail(sa, sb, name):
        bm = bmesh.new()
        secs = []
        s = sa
        while s <= sb + 1e-6:
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
        return from_bmesh(name, bm, coll, smooth=False)

    def post(s, name):
        P, t, r, th, k = road.at(s)
        base = P + r * (d + 0.14)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(V((0, 0, 0.35))) @ Matrix.Diagonal((0.08, 0.12, 0.95, 1)))
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(V((-0.10, 0, 0.84))) @ Matrix.Diagonal((0.012, 0.06, 0.04, 1)))
        o = from_bmesh(name, bm, coll, smooth=False)
        o.data.materials.append(steel); o.data.materials.append(refl)
        o.data.polygons.foreach_set('material_index', [0] * 6 + [1] * 6)
        o.location = base
        o.rotation_euler = (0, 0, -th)
        return o
    s = s0
    i = 0
    while s < s1:
        sb = min(s + 4.0, s1)
        o = rail(s, sb, f'rail{i}')
        set_mat(o, steel)
        pieces.append(('rail', (s + sb) / 2, o))
        p = post(s, f'post{i}')
        pieces.append(('post', s, p))
        s = sb
        i += 1
    # Every piece breaks the moment a car body reaches it (flung along that car), and the whole run around the
    # crash tears loose in a chain from the first impact, so nothing intact is left for a car to pass through.
    rng = random.Random(9)
    bpy.context.view_layer.update()            # posts were placed by .location: refresh their world matrices
    Ts = [19.8 + 0.02 * i for i in range(int((T_HALT - 19.8) / 0.02) + 1)]
    cars = []
    for pose_fn, vel_fn in ((hero_pose, hero_vel), (rival_pose, rival_vel)):
        cars.append([(T, pose_fn(T)[0], pose_fn(T)[1], vel_fn) for T in Ts])
    s_far = max(s_h2(T) for T in Ts if lane_h2(T) > 3.0) if any(lane_h2(T) > 3.0 for T in Ts) else s_rb
    s_lo_w, s_hi_w = min(s_rb, s_h2(T_HH)) - 25.0, max(s_far, s_rb) + 30.0
    WRECK_SPAN[:] = [s_lo_w, s_hi_w]
    s_rb_ = s_rb

    def in_car(q, pos, yaw):
        cy, sy = math.cos(yaw), math.sin(yaw)
        dx, dy = q.x - pos.x, q.y - pos.y
        lx, ly = cy * dx + sy * dy, -sy * dx + cy * dy
        return abs(lx) < 1.25 and abs(ly) < 2.65 and pos.z - 0.1 < q.z < pos.z + 1.3

    def flight_conflict(pts, Trel, v, skip=0.0):
        """first race time a released piece, flying ballistically, is inside a car body (None if never)"""
        for track in cars:
            for T, pos, yaw, vel_fn in track:
                if T < Trel + skip or pos.z < -1.5:
                    continue
                tau = T - Trel
                dz = -0.5 * G * tau * tau
                for q in pts[::2]:
                    if in_car(V((q.x + v.x * tau, q.y + v.y * tau, q.z + v.z * tau + dz)), pos, yaw):
                        return T, vel_fn
        return None
    for kind, sm, o in pieces:
        if kind == 'rail':
            c = sum((V(vv.co) for vv in o.data.vertices), V()) / len(o.data.vertices)
        else:
            c = o.location.copy()
        # v5: a piece breaks when ANY of its points enters a car's body outline (+ margin), not when the car's centre
        # nears the piece's middle (a 4 m rail could be hit at its end by a corner while still standing: probe finding)
        pts = [o.matrix_world @ V(vv.co) for vv in o.data.vertices][::3]
        hit = None
        for track in cars:
            for T, pos, yaw, vel_fn in track:
                if pos.z < -1.5 or (V((pos.x - c.x, pos.y - c.y))).length > 6.5:
                    continue
                cy, sy = math.cos(yaw), math.sin(yaw)
                inside = False
                for q in pts:
                    dx, dy = q.x - pos.x, q.y - pos.y
                    lx, ly = cy * dx + sy * dy, -sy * dx + cy * dy
                    if abs(lx) < 1.25 and abs(ly) < 2.65 and q.z < pos.z + 1.3:
                        inside = True
                        break
                if inside:
                    if hit is None or T < hit[0]:
                        hit = (T, vel_fn)
                    break
        P, t, r, th, k = road.at(sm)
        if hit is not None:
            Trel = hit[0] - 0.04                      # moving a beat before the body arrives
            v = hit[1](hit[0]) * rng.uniform(1.05, 1.3) + r * rng.uniform(5, 11) + V((0, 0, rng.uniform(2.5, 6.0)))   # faster than the car: it cannot be run through
            for k_ in range(4):      # probe: a struck rail flew low and slow into the hero's spinning donut -> higher, further out
                if flight_conflict(pts, Trel, v, skip=0.12) is None:
                    break
                v = v + r * 4.0 + V((0, 0, 2.0))
            w = V((rng.uniform(-8, 8), rng.uniform(-8, 8), rng.uniform(-5, 5)))
        elif s_lo_w <= sm <= s_hi_w:                  # torn loose by the rail tension: falls out over the edge
            Trel = T_B + abs(sm - s_rb_) / 60.0 + rng.uniform(0.0, 0.06)
            v = r * rng.uniform(2.0, 5.0) + t * rng.uniform(-3.0, 3.0) + V((0, 0, rng.uniform(1.0, 3.0)))
            w = V((rng.uniform(-4, 4), rng.uniform(-4, 4), rng.uniform(-2, 2)))
            # v5 (probe: the hero hung over the edge THROUGH torn rails still falling there): throw it clear of every
            # car's path, harder each try; if it still meets a car, the car strikes it (released fast at that moment)
            for k_ in range(4):
                cf = flight_conflict(pts, Trel, v)
                if cf is None:
                    break
                v = r * (6.0 + 3.0 * k_) + t * v.dot(t) + V((0, 0, 2.5 + k_))
            else:
                if cf is not None:
                    Trel = cf[0] - 0.04
                    v = cf[1](cf[0]) * rng.uniform(1.05, 1.3) + r * rng.uniform(5, 11) + V((0, 0, rng.uniform(2.5, 6.0)))
                    w = V((rng.uniform(-8, 8), rng.uniform(-8, 8), rng.uniform(-5, 5)))
        else:
            continue
        RELEASE[o.name] = (Trel, v, w)
        if kind == 'rail':
            # rails are built in world space: pivot them about their centre so they tumble properly
            o.data.transform(Matrix.Translation(-c))
            o.location = c
    return pieces


def key_barrier(pieces, Tf, N):
    for kind, sm, o in pieces:
        rel = RELEASE.get(o.name)
        if rel is None:
            continue
        Trel, v, w = rel
        p0, r0 = o.location.copy(), o.rotation_euler.copy()
        v, w = V(v), V(w)
        for f in range(1, N + 3):
            tau = max(0.0, Tf(f) - Trel)
            o.location = p0 + v * tau + V((0, 0, -0.5 * G * tau * tau))
            o.rotation_euler = (r0.x + w.x * tau, r0.y + w.y * tau, r0.z + w.z * tau)
            o.keyframe_insert('location', frame=f); o.keyframe_insert('rotation_euler', frame=f)
        set_interp(o, 'LINEAR')

# ----------------------------------------------------------------------------------- sparks, dust, smoke on arbitrary paths


def spark_burst_at(Tf, N, T_a, T_b, origin_fn, vel_fn, per_frame=10, seed=11, coll=None):
    import act2lib as A2
    _, me = A2.spark_mat()
    rng = random.Random(seed)
    coll = coll or collection('Sparks')
    ts = (Tf(2) - Tf(1)) * 24.0
    dt = ts / 24.0
    for f in range(1, N + 1):
        T = Tf(f)
        if not (T_a <= T <= T_b):
            continue
        for i in range(per_frame):
            o = bpy.data.objects.new(f'bspk{seed}_{f}_{i}', me)
            link(o, coll)
            o.visible_shadow = False
            p = origin_fn(T) + V((rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(0.0, 0.5)))
            v = vel_fn(T) * rng.uniform(0.5, 0.9) + V((rng.gauss(0, 4), rng.gauss(0, 4), abs(rng.gauss(0, 3)) + 1))
            lf = rng.randint(4, 11)
            o.scale = (0, 0, 0); o.keyframe_insert('scale', frame=f - 1)
            th = rng.uniform(0.6, 1.3) * 0.0034
            for k in range(lf + 1):
                if k:
                    v.z -= G * dt; p = p + v * dt
                o.location = p; o.keyframe_insert('location', frame=f + k)
                o.rotation_euler = v.normalized().to_track_quat('X', 'Z').to_euler()
                o.keyframe_insert('rotation_euler', frame=f + k)
                u = k / lf
                o.color = (1.0, 0.92 - 0.45 * u, 0.62 - 0.6 * min(1.0, u * 1.6), 1.0) if u < 0.6 else (0.95 - 0.35 * u, 0.45 - 0.33 * u, 0.03, 1.0)
                o.keyframe_insert('color', frame=f + k)
                o.scale = (max(0.008, v.length * 0.35 * dt), th * (1 - u ** 3), th * (1 - u ** 3))
                o.keyframe_insert('scale', frame=f + k)
            o.scale = (0, 0, 0); o.keyframe_insert('scale', frame=f + lf + 1)
            set_interp(o, 'LINEAR')


def puffs(name, mat, Tf, N, T_a, T_b, pos_fn, every=2, life=70, grow=(2.4, 3.0, 1.6), rise=0.8, drift=(0, 0, 0), seed=3, dens=1.0):
    """volume puffs born at pos_fn(T) between T_a and T_b; each grows, rises, drifts and fades."""
    rng = random.Random(seed)
    out = []
    for f in range(1, N + 1, every):
        T = Tf(f)
        if not (T_a <= T <= T_b):
            continue
        o = C.puff(f'{name}{f:03d}', mat)
        base = pos_fn(T) + V((rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), 0.2))
        gx, gy, gz = [g * rng.uniform(0.75, 1.3) for g in grow]
        o.rotation_euler = (0, 0, rng.uniform(0, 6.28))
        for fk, u in ((f - 1, 0.0), (f, 0.03), (f + 3, 0.22), (f + 8, 0.45), (f + 18, 0.68), (f + life * 0.5, 0.88), (f + life, 1.0)):
            g = 1 - (1 - u) ** 2
            o.location = base + V(drift) * (fk - f) / 24.0 + V((0, 0, (gz + rise) * g * 0.7))
            o.scale = (0.3 + gx * g, 0.3 + gy * g, 0.25 + gz * g)
            o.keyframe_insert('location', frame=fk); o.keyframe_insert('scale', frame=fk)
        for fk, dv in ((f - 1, 0.0), (f, 0.0), (f + 2, dens), (f + life * 0.4, 0.7 * dens), (f + life, 0.2 * dens), (f + life * 1.5, 0.0)):
            o.color = (dv, 1.0, 0, 1); o.keyframe_insert('color', frame=fk)
        out.append(o)
    return out


def wheel_world(pose_fn, T, local):
    p, yaw, roll, pitch = pose_fn(T)
    M = Matrix.Translation(p) @ Euler((pitch, roll, yaw), 'XYZ').to_matrix().to_4x4()
    return M @ V(local)

# ----------------------------------------------------------------------------------- shots
SHOTS = {
    '9A': (19.80, 20.80, 0.5, 'the barrier breaks (half speed)'),
    '9B': (20.55, 21.95, 0.6, 'close-up side: wheels spinning over the drop, sparks, then it drags itself back on'),
    '9C': (20.05, 21.75, 0.75, 'the rival goes over and dives for the valley floor'),
    '9D': (21.00, 23.76, 1.0, "roof cam: the rival's dive at the ground - the ground shatters as the nose hits (breach)"),
    '9G': (21.30, 23.80, 1.0, 'the donut back onto the road, smoke and streaks, to a halt (wide)'),
    '9V': (20.30, 23.50, 1.0, 'valley-floor cam looking straight up the cliff: the rival tumbles down at the lens'),
    '9W': (20.98, 21.78, 0.5, 'close-up: the road-side rear tyre spinning in the edge dirt, then it bites'),
}


def tyre_marks(coll=None):
    """black rubber streaks laid by the hero's rear tyres from the slide to the halt (only where the tyre is on the road)."""
    coll = coll or collection('TyreMarks')
    b = NB('rubber_marks')
    b.set('Base Color', (0.008, 0.008, 0.009)).set('Roughness', 0.55)
    n = b.noise(b.coord('Object', 1.0), 6.0, 3, 0.6)
    b.set('Alpha', b.maprange(n.outputs['Fac'], 0.3, 0.7, 0.45, 0.85))
    mat = b.mat
    mat.surface_render_method = 'DITHERED'
    for side, x in (('L', -0.86), ('R', 0.86)):
        bm = bmesh.new()
        prev = None
        T = 20.15
        while T < T_HALT:
            c = wheel_world(hero_pose, T, (x, -1.35, 0.0))
            d = D.road.sd(c.x, c.y)[1]
            if d < D.CLIFF_D - 0.1:
                p = V((c.x, c.y, 0.075))           # above the road crown (0.06 at the centre line)
                if prev is not None and (p - prev[0]).length > 0.05:
                    dirv = (p - prev[0]).normalized()
                    side_v = dirv.cross(V((0, 0, 1))) * 0.13
                    a, b_ = prev[1]
                    c_, d_ = bm.verts.new(p + side_v), bm.verts.new(p - side_v)
                    if a is not None:
                        bm.faces.new((a, b_, d_, c_))
                    prev = (p, (c_, d_))
                elif prev is None:
                    prev = (p, (None, None))
            else:
                prev = None
            T += 0.01
        o = from_bmesh(f'TyreMark{side}', bm, coll, smooth=False)
        set_mat(o, mat)
        o.visible_shadow = False


def impact_shake(cam, Tf, N, events):
    """real camera shake at impacts: events [(T, amp_m, rot_rad)] -> a hard jolt that rings out over ~10 frames."""
    ts = (Tf(2) - Tf(1)) * 24.0
    for T, amp, rot in events:
        f = 1 + (T - Tf(1)) / ts * 24.0
        if -10 < f < N + 2:
            shake(cam, amp=amp, rot_amp=rot, scale=1.6, seed=int(T * 100) % 97, start=int(f) - 1, end=int(f) + 10)


def dirt_spray(Tf, N, T_a, T_b, origin_fn, back_fn, per_frame=12, seed=51, coll=None):
    """dirt + gravel flung back off a spinning tyre on the shoulder (ballistic chips, motion-blurred)."""
    coll = coll or collection('Dirt')
    rng = random.Random(seed)
    m = mat_principled('DirtChip', (0.11, 0.06, 0.035), 0.95)
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    for v in bm.verts:
        v.co = V((v.co.x * rng.uniform(0.6, 1.3), v.co.y * rng.uniform(0.6, 1.3), v.co.z * rng.uniform(0.5, 1.0)))
    me = bpy.data.meshes.new('chip'); bm.to_mesh(me); bm.free(); me.materials.append(m)
    ts = (Tf(2) - Tf(1)) * 24.0
    dt = ts / 24.0
    for f in range(1, N + 1):
        T = Tf(f)
        if not (T_a <= T <= T_b):
            continue
        for i in range(per_frame):
            o = bpy.data.objects.new(f'chip{f}_{i}', me)
            link(o, coll)
            p = origin_fn(T) + V((rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), 0.03))
            v = back_fn(T) * rng.uniform(4.0, 11.0) + V((rng.gauss(0, 1.5), rng.gauss(0, 1.5), rng.uniform(1.0, 4.5)))
            sz = rng.uniform(0.006, 0.022)
            wv = V((rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(-20, 20)))
            lf = rng.randint(6, 14)
            o.scale = (0, 0, 0); o.keyframe_insert('scale', frame=f - 1)
            for k in range(lf + 1):
                tau = k * dt
                q = p + v * tau + V((0, 0, -4.9 * tau * tau))
                q.z = max(q.z, 0.01)
                o.location = q; o.keyframe_insert('location', frame=f + k)
                o.rotation_euler = (wv.x * tau, wv.y * tau, wv.z * tau); o.keyframe_insert('rotation_euler', frame=f + k)
                o.scale = (sz, sz, sz); o.keyframe_insert('scale', frame=f + k)
            o.scale = (0, 0, 0); o.keyframe_insert('scale', frame=f + lf + 1)
            set_interp(o, 'LINEAR')


def build(shot):
    T0, T1, ts, desc = SHOTS[shot]
    N = int(round((T1 - T0) / ts * 24)) + 1
    Tf = lambda f: T0 + (f - 1) / 24.0 * ts
    if shot == '9D':          # v6: real time, then easing into 0.2x slow motion for the breach (like their 2G)
        TL, T = [], T0
        while T <= T1 + 1e-6:
            TL.append(T)
            T += (1.0 if T < 23.40 else max(0.2, 1.0 - (T - 23.40) / 0.06 * 0.8)) / 24.0
        N = len(TL)

        def Tf(f, TL=TL):
            if f <= 1:
                return TL[0] + (f - 1) * (TL[1] - TL[0])
            if f >= len(TL):
                return TL[-1] + (f - len(TL)) * (TL[-1] - TL[-2])
            i = int(f) - 1
            return TL[i] + (f - 1 - i) * (TL[i + 1] - TL[i])
    reset()
    C._SCATTER_NG = None
    C._PUFF_ME.clear()
    sc = setup_render(1, N, samples=48, vol_tile='4', vol_samples=64, vol_end=170.0, vol_start=0.2,
                      look='AgX - Medium High Contrast', shutter=0.65 if ts == 1.0 else 0.45,
                      exposure={'9A': -0.95, '9C': -0.9, '9G': -0.45}.get(shot, -0.3))
    ee = sc.eevee
    ee.volumetric_sample_distribution = 0.8; ee.volumetric_light_clamp = 20.0; ee.volumetric_ray_depth = 16
    ee.motion_blur_max = 128; ee.motion_blur_steps = 4; ee.shadow_pool_size = '2048'
    hero = C.get_car()
    import rival as RV
    rv = RV.build_rival()
    D.hero_lights(hero); D.rival_lights(rv)
    g = bpy.data.objects.get('HeroRearGlow')
    if g is not None:
        g.data.energy = 14.0
    key_car(hero, hero_pose, Tf, -2, N + 3, WR, spin_fn=hero_spin, steer_fn=steer_h2)
    key_car(rv, rival_pose, Tf, -2, N + 3, WRR)
    s_rb, s_hb = D.s_rival(T_B), s_h2(T_HH)
    pieces = build_barrier(D.S_WIDE - 120, D.S_WIDE + 120, None, s_rb=s_rb)
    print(f'[finale] barrier: {len(RELEASE)} of {len(pieces)} pieces wrecked', flush=True)
    key_barrier(pieces, Tf, N)
    # ---- violence: kicked chunks, bits on the road, rubber laid in time (debris.py)
    import debris as DB

    def it_r(T):
        if T < 19.6:
            return D.violence(D.s_rival, D.lane_rival, D.drift_rival, T)
        return 1.3 if T <= T_EDGE + 0.02 else 0.0

    def it_h(T):
        if T < 19.6:
            return D.violence(D.s_hero, D.lane_hero, D.drift_hero, T, True)
        return 1.1 if T < 21.0 else 1.2 * (1 - smooth_(22.6, T_HALT - 0.2, T))

    def it_edge(T):           # the road-side tyres chewing the broken edge, then the drop-side ones in the dirt
        return 1.2 * smooth_(20.7, 20.85, T) * (1 - smooth_(21.5, 21.8, T))
    emit, tracks = [], []
    for x in (-0.86, 0.86):
        hp = lambda T, x=x: wheel_world(hero_pose, T, (x, -1.35, 0.0))
        rp = lambda T, x=x: wheel_world(rival_pose, T, (x * 0.87 / 0.86, -1.40, 0.0))
        emit += [(hp, hero_vel, None, it_h), (rp, rival_vel, None, it_r)]
        tracks += [(hp, it_h), (rp, it_r)]
    emit.append((lambda T: wheel_world(hero_pose, T, (-0.86, 1.45, 0.0)), hero_vel, None,
                 lambda T: 0.7 * smooth_(21.1, 21.25, T) * (1 - smooth_(22.4, 22.9, T))))      # front tyre on full lock
    emit.append((lambda T: wheel_world(hero_pose, T, (0.95, 0.0, 0.0)), hero_vel, None, it_edge))    # the sill on the rock edge
    mp = 4 if ts == 1.0 else 3
    DB.kick_chunks('Kick', Tf, N, emit, road, seed=91, max_per=mp, base=0.1, cap=1700)
    # the barrier footings + the rock lip break up: heavier chunks at the two impacts
    imp = [(lambda T: wheel_world(rival_pose, T_B, (1.4, 0.5, 0.0)), rival_vel, None,
            lambda T: 1.5 * (1 - smooth_(T_B, T_B + 0.2, T)) * (T >= T_B - 0.01)),
           (lambda T: wheel_world(hero_pose, T_HH, (1.0, 1.9, 0.0)), hero_vel, None,
            lambda T: 1.2 * (1 - smooth_(T_HH, T_HH + 0.18, T)) * (T >= T_HH - 0.01))]
    DB.kick_chunks('ImpactChunks', Tf, N, imp, road, seed=92, max_per=10 if ts < 1 else 7, base=0.0, cap=500, big=1.5)
    DB.tyre_marks('Rubber', road, Tf, N, tracks, max(14.0, Tf(1) - 6.0), min(T_HALT, Tf(N) + 0.05))
    DB.road_debris('RoadBits', road, min(D.s_rival(T0), s_h2(T0)) - 40, S_OVER + 90, per_m=6.0, seed=83,
                   hot=((s_rb, 35.0, 4.0), (S_OVER, 30.0, 3.0)))
    ev = 2 if ts == 1.0 else 3
    # sparks: rival flank on the rail, hero nose on the stumps, hero's right sill grinding the rock edge
    spark_burst_at(Tf, N, T_B - 0.02, T_B + 0.18, lambda T: wheel_world(rival_pose, T, (1.0, 0.4, 0.45)), rival_vel,
                   per_frame=16 if ts < 1 else 12, seed=21)
    spark_burst_at(Tf, N, T_HH - 0.02, T_HH + 0.16, lambda T: wheel_world(hero_pose, T, (0.7, 2.1, 0.30)), hero_vel,
                   per_frame=12, seed=22)
    spark_burst_at(Tf, N, 20.80, 21.45, lambda T: wheel_world(hero_pose, T, (0.92, 0.2 + 0.9 * math.sin(T * 9.0), 0.12)),
                   lambda T: hero_vel(T) + V((0, 0, -2.0)), per_frame=7 if ts < 1 else 5, seed=23)
    # dust + smoke: impact dust, rubber smoke white-grey and thick, dust spilling over the edge
    if shot == '9C':      # this camera stands at the breach: every cloud born there would fill the lens
        globals()['puffs'] = lambda *a, **k: []
    dmat = D.dust('Dust', 0.55, N=N)
    smat = D.dust('Smoke', 0.75, color=(0.66, 0.65, 0.63), emit=0.06, N=N, contrast=2.0, soft=(0.25, 0.58))
    wmat = D.dust('SmokeW', 0.40, color=(0.80, 0.80, 0.78), emit=0.08, N=N, contrast=2.8, soft=(0.30, 0.62))
    life = int(80 / max(ts, 0.3))
    if shot != '9C':
        puffs('ImpactDust', dmat, Tf, N, T_B, T_B + 0.25, lambda T: wheel_world(rival_pose, T_B, (1.6, 0.0, 0.0)), every=2,
              life=life, grow=(1.8, 2.2, 1.3), seed=31, dens=0.5)
    puffs('RivalSmoke', smat, Tf, N, 19.6, T_EDGE + (0.0 if shot == '9C' else 0.4), lambda T: wheel_world(rival_pose, T, (0.0, -1.4, 0.0)), every=ev,
          life=life, seed=36)
    puffs('SlideSmokeL', smat, Tf, N, 19.6, T_OVER, lambda T: wheel_world(hero_pose, T, (-0.9, -1.35, 0.0)), every=ev, life=life, seed=33)
    puffs('EdgeDust', dmat, Tf, N, 20.75, 21.6, lambda T: wheel_world(hero_pose, T, (1.2, 0.0, -0.4)), every=2, life=life,
          grow=(2.2, 2.8, 1.6), rise=-0.6, drift=(0, 0, -3.0), seed=34, dens=0.8)
    for nm, mat_, x, sd in (('BurnL', wmat, -0.86, 37), ('BurnR', smat, 0.86, 38), ('BurnC', wmat, 0.0, 39)):
        puffs(nm, mat_, Tf, N, 21.0, T_HALT - 0.3, lambda T, x=x: wheel_world(hero_pose, T, (x, -1.35, 0.0)), every=ev,
              life=int(120 / max(ts, 0.3)), grow=(2.2, 2.6, 1.8), rise=1.6, seed=sd, dens=0.75)
    # --------------------------------------------------------------------------- cameras
    if shot == '9A':
        cp = road.point(s_rb + 26.0, -2.6, 1.3)
        cam = camera('Cam9A', cp, lens=28, fstop=4.0, focus=20.0, clip=(0.05, 4000))
        D.key_cam(cam, N, lambda f: cp, lambda f: rival_pose(Tf(f))[0] * 0.6 + hero_pose(Tf(f))[0] * 0.4 + V((0, 0, 0.6)), omega=0.9)
        view = (rival_pose(T_B)[0] - cp)
    elif shot == '9B':        # close-up side, hovering just past the edge at sill height: the wheels spin in the void
        P, t, r, th, k = road.at(S_OVER)
        cp0 = None
        for back, out_, up_ in ((-3.0, 11.6, 0.35), (3.0, 11.6, 0.6), (6.0, 11.0, 0.8), (-8.0, 11.0, 1.2), (9.0, 10.5, 1.5)):
            c_ = P + r * out_ + t * back + V((0, 0, up_))
            clear = min((rival_pose(Tf(f))[0] - (c_ + t * (0.6 * (Tf(f) - T0)))).length for f in range(1, N + 1))
            if clear > 3.5:
                cp0 = c_
                print(f'[finale] 9B camera clearance from the falling rival: {clear:.1f} m', flush=True)
                break
        assert cp0 is not None, '9B: no camera position clears the falling rival'
        tgt = lambda f: hero_pose(Tf(f))[0] + V((0, 0, 0.35))
        pos = lambda f: cp0 + t * (0.6 * (Tf(f) - T0)) + V((0, 0, 0.05 * math.sin(f * 0.21)))
        cam = camera('Cam9B', cp0, lens=30, fstop=2.8, focus=4.0, clip=(0.05, 4000))
        D.key_cam(cam, N, pos, tgt, omega=1.1, zeta=0.8)
        fd = cam.data.dof
        for f in range(1, N + 3, 2):
            fd.focus_distance = max(1.5, (tgt(f) - pos(f)).length); fd.keyframe_insert('focus_distance', frame=f)
        view = (hero_pose(T_OVER)[0] - cp0)
    elif shot == '9C':
        P, t, r, th, k = road.at(s_rb + 2.0)
        cp = P + r * 6.6 + t * -6.0 + V((0, 0, 1.9))
        cam = camera('Cam9C', cp, lens=24, fstop=5.6, focus=20.0, clip=(0.05, 4000))
        D.key_cam(cam, N, lambda f: cp, lambda f: rival_pose(Tf(f))[0] + V((0, 0, 0.5)), omega=1.3, zeta=0.85)
        fd = cam.data.dof
        for f in range(1, N + 3, 2):
            fd.focus_distance = max(2.0, (rival_pose(Tf(f))[0] - cp).length); fd.keyframe_insert('focus_distance', frame=f)
        view = (rival_pose(T1)[0] - cp)
    elif shot == '9D':
        cam = D.mount_cam('Cam9D', rv['sprung'], (0.0, -0.05, 1.32), (74, 0, 0), 16, fstop=11.0, focus=8.0)
        P, t, r, th, k = road.at(D.s_rival(T_EDGE))
        view = t + r * 0.5
    elif shot == '9W':        # low beside the road-side rear tyre on the gravel shoulder: it spins in the dirt, then bites
        RL = (-0.86, -1.35, 0.0)
        p0, yaw0, _, _ = hero_pose(T0)
        side = V((-math.cos(yaw0), -math.sin(yaw0), 0))          # the car's left (-x) in world
        fwd = V((-math.sin(yaw0), math.cos(yaw0), 0))
        w0 = wheel_world(hero_pose, T0, RL)
        cp = w0 + side * 1.05 - fwd * 1.25 + V((0, 0, 0.62))      # behind-left, looking down at the contact patch
        tgt = lambda f: wheel_world(hero_pose, Tf(f), RL) + V((0, 0, 0.12))
        cam = camera('Cam9W', cp, lens=35, fstop=2.8, focus=1.4, clip=(0.02, 4000))
        D.key_cam(cam, N, lambda f: cp, tgt, omega=0.35, zeta=0.9)
        fd = cam.data.dof
        for f in range(1, N + 3, 2):
            fd.focus_distance = max(0.8, (tgt(f) - cp).length); fd.keyframe_insert('focus_distance', frame=f)
        dirt_spray(Tf, N, T0, T1, lambda T: wheel_world(hero_pose, T, (-0.86, -1.70, 0.0)),
                   lambda T: (wheel_world(hero_pose, T, (0, -1.0, 0)) - wheel_world(hero_pose, T, (0, 0, 0))).normalized(),
                   per_frame=10, seed=52)
        view = (w0 - cp)
    elif shot == '9V':        # v6b: on the valley floor beyond the impact, looking up the cliff at the falling rival
        T_imp, P = impact()
        vv = rival_vel(T_imp); u = V((vv.x, vv.y, 0)).normalized()
        cp = P + u * 10.0 + V((0, 0, 0.35))
        cam = camera('Cam9V', cp, lens=20, fstop=5.6, focus=30.0, clip=(0.05, 4000))
        tgt = lambda f: rival_pose(Tf(f))[0] + V((0, 0, 0.4))
        D.key_cam(cam, N, lambda f: cp, tgt, omega=1.4, zeta=0.85)
        fd = cam.data.dof
        for f in range(1, N + 3, 2):
            fd.focus_distance = max(3.0, (tgt(f) - cp).length); fd.keyframe_insert('focus_distance', frame=f)
        view = (rival_pose(T0)[0] - cp)
    elif shot == '9G':        # wide from the road ahead: the donut back on, smoke rolling over the broken edge
        cp = road.point(S_OVER + 18.0, -2.2, 2.0)
        cam = camera('Cam9G', cp, lens=35, fstop=5.6, focus=28.0, clip=(0.05, 4000))
        D.key_cam(cam, N, lambda f: cp, lambda f: hero_pose(Tf(f))[0] + V((0, 0, 0.6)), omega=0.7)
        view = (hero_pose(T_PIVOT)[0] - cp)
    if shot in ('9A', '9B', '9C', '9G', '9W'):
        impact_shake(cam, Tf, N, [(T_B, 0.07, 0.020), (T_HH, 0.05, 0.015), (20.85, 0.06, 0.018),
                                  (T_PIVOT, 0.04, 0.012), (21.5, 0.02, 0.006)])
    sc.camera = cam
    h = V((view.x, view.y, 0)).normalized()
    a = math.radians(28)
    C.set_sun((h.x * math.cos(a) - h.y * math.sin(a), h.x * math.sin(a) + h.y * math.cos(a)), 4.5)
    C.mat_sky_world(fog=0.0022, strength=1.15)
    C.sun_lamp(4.2)
    s_lo = min(D.s_rival(T0), s_h2(T0)) - 70
    s_hi = max(D.s_rival(min(T1, T_EDGE)), S_OVER) + 120
    C.build_environment(road, s_lo, s_hi, res=1.6, right=260.0)
    import breach as BR_                                # v6b: readable valley floor + clouds, in every crash shot
    BR_.valley_detail(impact()[1])
    BR_.add_clouds()
    posts = bpy.data.objects.get('Posts')          # the roadside marker posts in the wrecked stretch go too
    if posts is not None:
        me = posts.data
        sc_a = me.attributes['scale']
        n_gone = 0
        for i, v in enumerate(me.vertices):
            if WRECK_SPAN[0] <= road.sd(v.co.x, v.co.y)[0] <= WRECK_SPAN[1]:
                sc_a.data[i].vector = (0.0, 0.0, 0.0); n_gone += 1
        me.update()
        print(f'[finale] marker posts removed in the wreck: {n_gone // 2}', flush=True)
    if shot == '9D':          # v6: the ground is the boundary: it shatters from the nose, the garage glows below
        import breach as BR
        T_imp, P = impact()
        f_imp = next(f for f in range(1, N + 1) if Tf(f) >= T_imp)
        f_imp -= (Tf(f_imp) - T_imp) / (Tf(f_imp) - Tf(f_imp - 1))
        vv = rival_vel(T_imp)
        BR.build_breach(P, f_imp, tscale=0.2, v=0.45, acc=0.03)
        BR.garage_below(P, math.atan2(-vv.x, vv.y))
        print(f'[finale] 9D breach at T {T_imp:.3f} (frame {f_imp:.1f})', flush=True)
    ground_pass(hero, hero_pose, Tf, -2, N + 3, HERO_W)
    ground_pass(rv, rival_pose, Tf, -2, N + 3, RIVAL_W, T_max=T_EDGE)
    C.comp(bloom=0.4, threshold=0.9, size=0.7, dispersion=0.006, streaks=0.18, streak_thr=4.0)
    print(f'[finale] {shot} {desc}: T {T0}-{T1} x{ts}, {N} frames, built in {time.time() - T_START:.1f}s', flush=True)
    return sc


if __name__ == '__main__':
    build(str(arg('--shot', '9A')))
    finish(str(arg('--shot', '9A')))
