"""SHOT 7A "RIVAL" — our continuation after ESCAPEMENT 3E (see brief.md). Ai.chemyst with Claude.

  stills : rb.py ../continuation/shot_7a.py -- --stills 6,24,40,60,80,100,130 --pct 40 --samples 16 --tag _v1
  motion : rb.py ../continuation/shot_7a.py -- --anim --jpg --pct 30 --samples 8 --step 2 --outdir <ABSOLUTE dir>
  final  : rb.py ../continuation/shot_7a.py -- --anim            -> film/renders/7A/####.png

Reuses ESCAPEMENT's canyon (lib/canyon.py), hero car (lib/car.py) and helpers (MIT); the small camera/light
helpers below are re-implemented in the same spirit as act3_canyon.py. The rival car, the corner, the camera move,
the timing and the dust beats are ours.
"""
import sys, os, math, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, '..', 'film', 'lib'), HERE]
from common import *
import canyon as C
import rival as RV
from mathutils import Vector as V, Matrix, Quaternion

T0 = time.time()
N = 150                      # render frames; cut 1..144
FPS_ = 24.0
road = C.Road()
C.road_r = lambda rd, s: rd.at(s)[2]

# ------------------------------------------------------------------------------------------- timing (numbers first)
S_APEX, F_APEX = 625.0, 26                          # hero at the apex of the LEFT bend (k -0.022, R ~ 45 m)
hero_s = C.speed_curve(S_APEX, F_APEX, [(-20, 46.0), (12, 40.0), (32, 40.0), (56, 49.0)], f0=-60, f1=N + 20)
S_CAM_A = 643.0                                     # camera A: outside of the bend, after the apex
CAM_A = road.point(S_CAM_A, 5.2, 0.48)


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def vcam(f):
    """camera speed along the road, m/frame (negative = flying back toward the rival)."""
    if f < 38:
        return 0.0
    if f < 50:
        return -1.2 * smooth(38, 50, f)
    if f < 62:
        return -1.2 - 6.8 * smooth(50, 62, f)
    if f < 70:
        return -8.0
    if f < 90:
        return -8.0 + 10.0 * smooth(70, 90, f)
    return 2.0


_SC = {}


def s_free(f):
    """integrate vcam from the static position (0.05-frame steps, cached)."""
    k = round(f * 20)
    if k in _SC:
        return _SC[k]
    s, t = S_CAM_A, 0.0
    while t < f:
        s += vcam(t) * 0.05
        t += 0.05
    _SC[k] = s
    return s


def gap(f):                                          # camera distance ahead of the rival's nose
    return 10.0 - 7.2 * smooth(90, 144, f)


F_LOCK = 92
V_RIVAL = 47.0
S_R_LOCK = s_free(F_LOCK) - gap(F_LOCK) - 2.3       # rival root position at the lock frame (2.3 = root->nose)
rival_s = C.speed_curve(S_R_LOCK, F_LOCK, [(-20, V_RIVAL), (110, V_RIVAL), (140, V_RIVAL + 4.0)], f0=-60, f1=N + 20)


def s_cam(f):
    lock = rival_s(f) + 2.3 + gap(f)
    return s_free(f) + (lock - s_free(f)) * smooth(82, 98, f)


def cam_pos(f):
    if f <= 36:
        return CAM_A.copy()
    s = s_cam(f)
    d = 5.2 + (0.4 - 5.2) * smooth(36, 56, f)                       # in to the centre line for the flight
    d += (C.LANE + 0.95 - 0.4) * smooth(84, 100, f)                  # then to the rival's front three-quarter
    z = 0.48 + (2.4 - 0.48) * smooth(36, 52, f)                      # rise for the turn
    z += (1.25 - 2.4) * smooth(58, 84, f) + (0.72 - 1.25) * smooth(86, 102, f)
    return road.point(s, d, z)


def rival_nose(f):
    P, t, r, th, k = road.at(rival_s(f) + 2.0)
    return P + r * C.LANE + V((0, 0, 0.55))


def hero_body(f):
    P, t, r, th, k = road.at(hero_s(f))
    return P + r * (C.LANE + hero_lane(f)) + V((0, 0, 0.7))


def hero_slip(f):            # + = nose left (into the LEFT bend), tail out to the right / outside
    s = hero_s(f)
    return math.radians(13) * smooth(598, 612, s) * (1 - smooth(642, 665, s))


def hero_lane(f):
    s = hero_s(f)
    return 0.7 * smooth(605, 628, s) * (1 - smooth(650, 680, s))


def aim_dir(f):
    p = cam_pos(f)
    look_hero = (hero_body(f) - p).normalized()
    s = s_cam(f)
    look_back = (road.point(s - 40.0, -2.2, 0.6) - p).normalized()   # lean toward the cliff side
    look_rival = (rival_nose(f) + V((0, 0, 0.1)) - p).normalized()
    w1 = smooth(36, 48, f)
    w2 = smooth(80, 96, f)
    d = look_hero.lerp(look_back, w1).normalized()
    return d.lerp(look_rival, w2).normalized()

# ------------------------------------------------------------------------------------------- helpers (ours)


def yp(d):
    d = d.normalized()
    return math.atan2(d.y, d.x), math.asin(max(-1.0, min(1.0, d.z)))


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def key_camera(cam, f0, f1, omega=1.1, zeta=0.75, sub=8):
    """position keyed every frame; aim follows aim_dir through a critically-damped spring (operator lag)."""
    y, p = yp(aim_dir(f0))
    vy = vp = 0.0
    prev = None
    for f in range(f0, f1 + 1):
        if f > f0:
            for k in range(sub):
                ff = f - 1 + (k + 1) / sub
                ty, tp = yp(aim_dir(ff))
                vy += (omega * omega * wrap(ty - y) - 2 * zeta * omega * vy) / sub
                vp += (omega * omega * (tp - p) - 2 * zeta * omega * vp) / sub
                y += vy / sub; p += vp / sub
        d = V((math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)))
        e = d.to_track_quat('-Z', 'Y').to_euler('XYZ', prev) if prev else d.to_track_quat('-Z', 'Y').to_euler('XYZ')
        prev = e
        cam.rotation_euler = e
        cam.location = cam_pos(f)
        cam.keyframe_insert('rotation_euler', frame=f)
        cam.keyframe_insert('location', frame=f)
    set_interp(cam, 'BEZIER')


def hero_lights(car):
    C.car_lights(car, 4.0, 16.0, 1)
    m = car['mats'].get('rear_light')
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED' and not n.inputs['Emission Color'].links:
            n.inputs['Emission Color'].default_value = (1.0, 0.012, 0.004, 1)
    L = light('AREA', 'HeroRearGlow', (0, 0, 0), energy=60, color=(1.0, 0.03, 0.012), size=1.6, size_y=0.15)
    L.parent = car['root']; L.matrix_parent_inverse = Matrix.Identity(4)
    L.location = (0, -2.45, 0.85); L.rotation_euler = (math.radians(-90), 0, 0)


def dust(density, emit=0.03, **kw):
    kw.setdefault('contrast', 3.0); kw.setdefault('nscale', 2.4); kw.setdefault('soft', (0.32, 0.64))
    return C.mat_dust2('Dust', density=density, color=(0.62, 0.43, 0.28), aniso=0.7, emit=emit, f0=-160, f1=N + 20, **kw)

# ------------------------------------------------------------------------------------------- build


def build():
    reset()
    C._SCATTER_NG = None
    C._PUFF_ME.clear()
    sc = setup_render(1, N, samples=48, vol_tile='4', vol_samples=64, vol_end=90.0, vol_start=0.3,
                      look='AgX - Medium High Contrast', shutter=0.5, exposure=-0.3)
    ee = sc.eevee
    ee.volumetric_sample_distribution = 0.8
    ee.volumetric_light_clamp = 20.0
    ee.volumetric_ray_depth = 16
    ee.motion_blur_max = 128
    ee.motion_blur_steps = 5
    ee.shadow_pool_size = '1024'
    # sun: low (4.5 deg), behind the action as seen by the camera (which looks back down the road all shot),
    # 25 deg toward the open canyon side -> back-lit dust and cars, rim light, sun never centred in frame
    P, t, r, th, k = road.at(560.0)
    sd = (-t * math.cos(math.radians(25)) + r * math.sin(math.radians(25)))
    C.set_sun((sd.x, sd.y), 4.5)
    C.mat_sky_world(fog=0.0022, strength=1.15)
    C.sun_lamp(4.2)
    hints = [(CAM_A, (-t.x, -t.y), 60.0), (road.point(560, 0, 2), (-t.x, -t.y), 60.0)]
    env = C.build_environment(road, rival_s(1) - 70, hero_s(N) + 60, res=1.6)
    # hero (theirs) through the corner, drifting a little
    car = C.get_car()
    C.drive(car, road, hero_s, -2, N + 3, yaw_fn=hero_slip, lane_fn=hero_lane, roll_k=0.0036)
    hero_lights(car)
    # rival (ours)
    rv = RV.build_rival()
    C.drive(rv, road, rival_s, -2, N + 3, roll_k=0.0040, seed=7)
    import debris as DB                     # probe (gate v2): both cars sat 6 cm into the crowned road
    DB.settle_drive(car, road, (1.35, 1.35, 0.86)); DB.settle_drive(rv, road, (1.40, 1.40, 0.87))
    # car-photography lights, linked to the rival only: warm rim from the sun side behind it, cool sky softbox above
    rcoll = rv['root'].users_collection[0]
    for nm, loc, energy, col, size in (('RivalRim', (0.8, -4.2, 1.9), 260.0, (1.0, 0.62, 0.36), 5.0),
                                       ('RivalSky', (0.0, 0.6, 3.6), 100.0, (0.55, 0.74, 0.92), 6.0)):
        L = light('AREA', nm, (0, 0, 0), energy=energy, color=col, size=size)
        L.parent = rv['root']; L.matrix_parent_inverse = Matrix.Identity(4)
        L.location = loc
        L.rotation_euler = (V((0, 0.2, 0.5)) - V(loc)).to_track_quat('-Z', 'Y').to_euler()
        L.data.volume_factor = 0.0
        L.data.specular_factor = 0.12      # light the form, do not mirror as white sheets in the clearcoat
        L.visible_camera = False
        L.light_linking.receiver_collection = rcoll
    # dust: hero plume out of the corner (thin, back-lit), rival plume behind it
    C.dust_trail(road, hero_s, -10, N + 2, dust(0.2), every=1, life=70, grow=(2.2, 3.2, 1.3), rise=0.5, seed=71,
                 lateral=hero_lane, spread=(-0.5, 3.0))
    C.dust_trail(road, rival_s, -40, N + 2, dust(0.45), every=1, life=90, grow=(2.4, 3.4, 1.4), rise=0.5, seed=72,
                 spread=(-1.0, 2.5))
    # camera
    cam = camera('Cam7A', CAM_A, lens=24, fstop=2.8, focus=10.0, clip=(0.02, 4000))
    key_camera(cam, 1, N + 2)
    for f, ln in ((1, 40.0), (24, 40.0), (36, 22.0), (44, 22.0), (56, 16.0), (84, 16.0), (100, 30.0), (144, 35.0)):
        cam.data.lens = ln; cam.data.keyframe_insert('lens', frame=f)
    fd = cam.data.dof
    for f in range(1, N + 3):
        p = cam_pos(f)
        if f <= 44:
            dist = (hero_body(f) - p).length
        elif f <= 86:
            dist = 25.0
        else:
            dist = (rival_nose(f) - p).length
        fd.focus_distance = max(1.5, min(40.0, dist))
        fd.keyframe_insert('focus_distance', frame=f)
    for f, fs in ((1, 2.8), (44, 2.8), (56, 6.0), (84, 6.0), (98, 2.8)):
        fd.aperture_fstop = fs; fd.keyframe_insert('aperture_fstop', frame=f)
    for f, sh in ((1, 0.5), (48, 0.5), (58, 0.45), (84, 0.45), (96, 0.5)):
        sc.render.motion_blur_shutter = sh; sc.render.keyframe_insert('motion_blur_shutter', frame=f)
    # T3 continuity: open on the same featureless warm dust as 3E's last frames, clearing by f11
    cam.data.lens = 16.0          # size the dust sheets for the widest lens in the shot
    C.lens_dust(cam, [(1, 1.0), (3, 0.85), (7, 0.35), (11, 0.0), (N + 2, 0.0)], color=(0.95, 0.78, 0.60), strength=1.6,
                layers=2, seed=9, stream=(-2.0, 0.3), f_end=14, method='DITHERED')
    eng = C.mat_dust2('Reveal', density=0.5, color=(0.62, 0.43, 0.28), aniso=0.7, emit=0.02, f0=-60, f1=N + 20,
                      nscale=2.8, contrast=3.5, soft=(0.35, 0.62))
    P0, t0, r0, th0, k0 = road.at(S_CAM_A)
    for i, (ds_, dd, sz) in enumerate([(-6, -1.5, 5.0), (-12, 1.5, 6.0), (-4, 3.5, 4.0)]):
        o = C.puff(f'Reveal{i}', eng)
        o.location = road.point(S_CAM_A + ds_, 5.2 + dd, 1.4)
        for fk, sc_ in ((1, sz), (18, sz * 1.5)):
            o.scale = (sc_, sc_ * 1.2, sc_ * 0.6); o.keyframe_insert('scale', frame=fk)
        for fk, dv in ((1, 0.9), (8, 0.5), (18, 0.0)):
            o.color = (dv, 1.0, 0, 1); o.keyframe_insert('color', frame=fk)
    sc.camera = cam
    C.comp(bloom=0.4, threshold=0.9, size=0.7, dispersion=0.006, streaks=0.18, streak_thr=4.0)
    gap_f26 = hero_s(F_APEX) - rival_s(F_APEX)
    print(f'[7A] build {time.time() - T0:.1f}s  rival {gap_f26:.0f} m ({gap_f26 / V_RIVAL:.1f} s) behind the hero; '
          f'camera flies {S_CAM_A - min(s_free(f) for f in range(1, N)):.0f} m back, peak {abs(min(vcam(f) for f in range(N))) * FPS_:.0f} m/s',
          flush=True)
    return sc


build()
finish('7A')
