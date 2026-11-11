"""RIVAL v2 — an original front-engine long-hood GT racer, built entirely from Python (Ai.chemyst with Claude).

    import rival
    c = rival.build_rival(coll=None, name='Rival')

v2 applies what made ESCAPEMENT's hero car read as real (studied in lib/car.py; techniques, not geometry):
  1. a dense station table with crisp character lines (creased shoulder, sill, greenhouse base, a side cove)
  2. real panels: separate glass with an inset window frame, panel gaps, a matte inner hull behind every gap
  3. detail density: ~30 parts — headlamp bezels with LED blade + projector lenses, slatted grille, splitter with an
     accent lip, brake ducts, hood extractor vents, hood pins, side gills, skirts, side exhausts with heat tint,
     mirrors with glass, flush handles, race roundels with a number, race fuel filler, ducktail lip, twin round tail
     lamps in a bezel, finned diffuser, rear mesh, wiper, screws, visible suspension
  4. every material carries micro detail: flake + pinstriped livery, carbon weave, lathe-ringed machined faces,
     drilled discs, tyre sidewall lettering, heat-tinted titanium
  5. wheels as assemblies: grooved tyres (wider at the rear), 5x2 tapered spokes with machined faces, machined lip,
     3-eared knock-off spinner, drilled disc + bell, caliper
Interface matches ESCAPEMENT's car.py so canyon.drive() can drive it (root, sprung, wheels, wheel_radius, parts).
Units metres. Length 4.73, width 2.07, height 1.21, wheelbase 2.80, wheel radius 0.36.
"""
import bpy, bmesh, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import common as C

YF, YR = 1.40, -1.40
WR = 0.36
TRACK = {'F': 0.86, 'R': 0.87}
TYRE_HW = {'F': 0.132, 'R': 0.152}
NUMBER = '07'

# y, half-width, floor z, belt/shoulder z, top-centre z, top half-width
STATIONS = [
    (2.45, 0.34, 0.27, 0.33, 0.36, 0.21), (2.41, 0.57, 0.22, 0.39, 0.43, 0.33), (2.34, 0.73, 0.185, 0.46, 0.51, 0.41),
    (2.23, 0.85, 0.16, 0.55, 0.59, 0.47), (2.09, 0.92, 0.15, 0.635, 0.66, 0.50), (1.95, 0.965, 0.145, 0.71, 0.70, 0.51), (1.78, 0.995, 0.14, 0.79, 0.73, 0.50),
    (1.58, 1.005, 0.14, 0.83, 0.735, 0.48), (1.40, 1.01, 0.14, 0.845, 0.74, 0.47), (1.18, 0.995, 0.14, 0.82, 0.755, 0.46),
    (0.95, 0.975, 0.14, 0.79, 0.77, 0.45), (0.74, 0.965, 0.14, 0.765, 0.79, 0.44), (0.50, 0.96, 0.14, 0.755, 0.96, 0.42),
    (0.22, 0.955, 0.14, 0.76, 1.14, 0.45), (-0.10, 0.96, 0.14, 0.77, 1.21, 0.48), (-0.42, 0.975, 0.14, 0.79, 1.19, 0.48),
    (-0.74, 1.00, 0.14, 0.835, 1.09, 0.47), (-1.02, 1.025, 0.14, 0.875, 0.985, 0.47), (-1.30, 1.035, 0.145, 0.895, 0.935, 0.52),
    (-1.58, 1.03, 0.155, 0.895, 0.915, 0.58), (-1.86, 1.00, 0.17, 0.885, 0.905, 0.63), (-2.10, 0.95, 0.205, 0.875, 0.895, 0.67),
    (-2.28, 0.89, 0.26, 0.865, 0.88, 0.68), (-2.36, 0.84, 0.32, 0.86, 0.87, 0.66),
]
SIDE_WIN, SCREEN, BACKLIGHT = (-0.92, 0.70), (0.10, 0.72), (-1.05, -0.45)


def smooth(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def shade(o, angle=40.0):
    me = o.data
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(angle))   # Blender 5.2 name (the old name fails silently)


def mesh_from_bm(name, bm, coll, mats, smooth_=True, angle=40.0, parent=None, bevel=0.0, recalc=True):
    if recalc:                      # never on pieces cut from a shell: open pieces can flip inward
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    C.link(o, coll)
    for m in (mats if isinstance(mats, (list, tuple)) else [mats]):
        me.materials.append(m)
    if smooth_ and len(me.polygons):
        shade(o, angle)
    if bevel:
        C.bevel(o, bevel, 2, 35)
    if parent is not None:
        o.parent = parent
    return o


def loft(bm, secs, cap=True, closed=True):
    vs = [[bm.verts.new(p) for p in s] for s in secs]
    n = len(secs[0])
    for i in range(len(vs) - 1):
        for j in range(n if closed else n - 1):
            bm.faces.new((vs[i][j], vs[i][(j + 1) % n], vs[i + 1][(j + 1) % n], vs[i + 1][j]))
    if cap and closed:
        bm.faces.new(list(reversed(vs[0])))
        bm.faces.new(vs[-1])
    return vs


def tube(bm, pts, r, segs=10, flat=1.0, cap=True):
    if len(pts) < 2:
        return
    secs = []
    for i, p in enumerate(pts):
        p = Vector(p)
        d = (Vector(pts[min(i + 1, len(pts) - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
        up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
        u = d.cross(up).normalized(); v = d.cross(u).normalized()
        secs.append([p + (u * math.cos(2 * math.pi * k / segs) + v * math.sin(2 * math.pi * k / segs) * flat) * r
                     for k in range(segs)])
    loft(bm, secs, cap=cap)


def box(bm, center, size, rot=None):
    m = Matrix.Translation(Vector(center))
    if rot is not None:
        m = m @ rot.to_4x4()
    bmesh.ops.create_cube(bm, size=1.0, matrix=m @ Matrix.Diagonal((*size, 1.0)))


def revolve(bm, prof, segs, mat_idx=None):
    """prof [(x, r)] revolved about the X axis."""
    rings = []
    for k in range(segs):
        a = 2 * math.pi * k / segs
        rings.append([bm.verts.new((x, r * math.cos(a), r * math.sin(a))) for x, r in prof])
    for k in range(segs):
        A, B = rings[k], rings[(k + 1) % segs]
        for j in range(len(prof) - 1):
            f = bm.faces.new((A[j], A[j + 1], B[j + 1], B[j]))
            if mat_idx:
                f.material_index = mat_idx[j]


def frame_from_normal(p, n, up=Vector((0, 0, 1))):
    """4x4 with local Z = n (outward), local Y ~ up, at p."""
    n = Vector(n).normalized()
    x = up.cross(n)
    if x.length < 1e-4:
        x = Vector((1, 0, 0))
    x.normalize()
    y = n.cross(x)
    M = Matrix.Identity(4)
    for i in range(3):
        M[i][0], M[i][1], M[i][2], M[i][3] = x[i], y[i], n[i], p[i]
    return M

# ----------------------------------------------------------------------------- materials


def _xyz(b):
    tc = b.n('ShaderNodeTexCoord')
    sep = b.n('ShaderNodeSeparateXYZ')
    b.link(tc.outputs['Object'], sep.inputs[0])
    return tc, sep


def _polar(b, sep):
    r = b.math('SQRT', b.math('ADD', b.math('MULTIPLY', sep.outputs['Y'], sep.outputs['Y']),
                               b.math('MULTIPLY', sep.outputs['Z'], sep.outputs['Z'])))
    ang = b.n('ShaderNodeMath'); ang.operation = 'ARCTAN2'
    b.link(sep.outputs['Z'], ang.inputs[0]); b.link(sep.outputs['Y'], ang.inputs[1])
    return r, ang.outputs[0]


def mat_paint():
    """Cobalt metallic with fine flake; twin pearl stripes edged by thin gold pinstripes; crisp coat."""
    b = C.NB('rival_paint')
    tc, sep = _xyz(b)
    v = tc.outputs['Object']
    big = b.noise(v, 1.4, 4, 0.5)
    base = b.mix((0.006, 0.026, 0.16), (0.010, 0.040, 0.22), big.outputs['Fac'])
    ax = b.math('ABSOLUTE', sep.outputs['X'])
    topm = b.maprange(sep.outputs['Z'], 0.40, 0.46, 0.0, 1.0)
    stripe = b.math('MULTIPLY', b.math('MULTIPLY', b.maprange(ax, 0.062, 0.068, 0.0, 1.0), b.maprange(ax, 0.178, 0.172, 0.0, 1.0)), topm)
    pin = b.math('MAXIMUM', b.maprange(b.math('ABSOLUTE', b.math('SUBTRACT', ax, 0.0535)), 0.0036, 0.0022, 0.0, 1.0),
                 b.maprange(b.math('ABSOLUTE', b.math('SUBTRACT', ax, 0.1865)), 0.0036, 0.0022, 0.0, 1.0))
    pin = b.math('MULTIPLY', pin, topm)
    col = b.mix(base, (0.62, 0.62, 0.59), stripe)
    col = b.mix(col, (0.62, 0.40, 0.08), pin)
    fl = b.voronoi(v, 1600.0)
    b.set('Base Color', col)
    b.set('Metallic', b.maprange(stripe, 0, 1, 0.42, 0.10))
    b.set('Roughness', b.maprange(big.outputs['Fac'], 0.3, 0.7, 0.20, 0.27))
    b.set('Coat Weight', 1.0)
    b.set('Coat Roughness', 0.035)
    b.set('Normal', b.bump(fl.outputs['Distance'], 0.06, 0.0004))
    return b.mat


def mat_simple(name, color, rough, metal=0.0, coat=0.0, noise=0.0, scale=60.0):
    b = C.NB(name)
    b.set('Base Color', color).set('Roughness', rough).set('Metallic', metal)
    if coat:
        b.set('Coat Weight', coat).set('Coat Roughness', 0.05)
    if noise:
        n = b.noise(b.coord('Object', 1.0), scale, 4, 0.6)
        b.set('Roughness', b.maprange(n.outputs['Fac'], 0.3, 0.7, rough * (1 - noise), rough * (1 + noise)))
    return b.mat


def mat_carbon(name, gloss=True):
    """2x2 twill: diagonal checker of tows + fine weave ripple, anisotropic sheen."""
    b = C.NB(name)
    tc, sep = _xyz(b)
    mp = b.n('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (110, 110, 110)
    mp.inputs['Rotation'].default_value = (0, 0, math.radians(45))
    b.link(tc.outputs['Object'], mp.inputs['Vector'])
    ch = b.n('ShaderNodeTexChecker'); ch.inputs['Scale'].default_value = 1.0
    ch.inputs['Color1'].default_value = (0.020, 0.021, 0.024, 1); ch.inputs['Color2'].default_value = (0.007, 0.007, 0.008, 1)
    b.link(mp.outputs['Vector'], ch.inputs['Vector'])
    w = b.n('ShaderNodeTexWave'); w.inputs['Scale'].default_value = 220.0
    b.link(tc.outputs['Object'], w.inputs['Vector'])
    b.set('Base Color', ch.outputs['Color']).set('Metallic', 0.25)
    b.set('Roughness', b.maprange(ch.outputs['Fac'], 0, 1, 0.24, 0.40))
    if gloss:
        b.set('Coat Weight', 1.0).set('Coat Roughness', 0.04)
    b.set('Normal', b.bump(w.outputs['Fac'], 0.04, 0.0004))
    b.set('Anisotropic', 0.5)
    return b.mat


def mat_machined(name='rival_machined', base=(0.62, 0.62, 0.64)):
    """Lathe rings around the local X axis (wheel faces, spinners), anisotropic."""
    b = C.NB(name)
    tc, sep = _xyz(b)
    r, ang = _polar(b, sep)
    rings = b.math('SINE', b.math('MULTIPLY', r, 2600.0))
    b.set('Base Color', base).set('Metallic', 1.0)
    b.set('Roughness', b.maprange(rings, -1, 1, 0.10, 0.19))
    b.set('Normal', b.bump(rings, 0.03, 0.0003))
    b.set('Anisotropic', 0.7)
    return b.mat


def mat_disc():
    """Cast iron with two staggered rows of cross-drilled holes, lathe grooves and a blue-brown heat band."""
    b = C.NB('rival_disc')
    tc, sep = _xyz(b)
    r, ang = _polar(b, sep)
    cx = b.math('MULTIPLY', ang, 24.0 / (2 * math.pi))
    cy = b.math('MULTIPLY', b.math('SUBTRACT', r, 0.115), 1.0 / 0.026)
    cxy = b.n('ShaderNodeCombineXYZ')
    b.link(b.math('ADD', cx, b.math('MULTIPLY', b.math('FLOOR', cy), 0.5)), cxy.inputs[0]); b.link(cy, cxy.inputs[1])
    vor = b.n('ShaderNodeTexVoronoi'); vor.voronoi_dimensions = '2D'
    vor.inputs['Scale'].default_value = 1.0; vor.inputs['Randomness'].default_value = 0.0
    b.link(cxy.outputs[0], vor.inputs['Vector'])
    band = b.math('MULTIPLY', b.maprange(r, 0.115, 0.121, 0, 1), b.maprange(r, 0.172, 0.166, 0, 1))
    hole = b.math('MULTIPLY', b.maprange(vor.outputs['Distance'], 0.16, 0.13, 0, 1), band)
    grooves = b.math('SINE', b.math('MULTIPLY', r, 2300.0))
    col = b.mix((0.32, 0.32, 0.33), (0.16, 0.12, 0.12), b.maprange(r, 0.12, 0.19, 0, 1))
    col = b.mix(col, (0.12, 0.13, 0.22), b.math('MULTIPLY', b.maprange(r, 0.13, 0.15, 0, 1), b.maprange(r, 0.17, 0.15, 0, 1)))
    col = b.mix(col, (0.0, 0.0, 0.0), hole)
    b.set('Base Color', col).set('Metallic', b.maprange(hole, 0, 1, 1.0, 0.0))
    b.set('Roughness', b.maprange(grooves, -1, 1, 0.22, 0.40))
    b.set('Normal', b.bump(b.math('ADD', b.math('MULTIPLY', grooves, 0.2), b.math('MULTIPLY', hole, -1.0)), 0.3, 0.003))
    return b.mat


def mat_tyre():
    """Rubber: sidewall radial ribs + a raised lettering band (blocky polar voronoi), worn tread."""
    b = C.NB('rival_tyre')
    tc, sep = _xyz(b)
    r, ang = _polar(b, sep)
    ribs = b.math('SINE', b.math('MULTIPLY', r, 1300.0))
    cxy = b.n('ShaderNodeCombineXYZ')
    b.link(b.math('MULTIPLY', ang, 46.0), cxy.inputs[0]); b.link(b.math('MULTIPLY', r, 320.0), cxy.inputs[1])
    vor = b.n('ShaderNodeTexVoronoi'); vor.voronoi_dimensions = '2D'; vor.distance = 'CHEBYCHEV'
    vor.inputs['Scale'].default_value = 1.0
    b.link(cxy.outputs[0], vor.inputs['Vector'])
    band = b.math('MULTIPLY', b.maprange(r, 0.300, 0.304, 0, 1), b.maprange(r, 0.322, 0.318, 0, 1))
    letters = b.math('MULTIPLY', band, b.math('GREATER_THAN', vor.outputs['Distance'], 0.30))
    wear = b.noise(tc.outputs['Object'], 70, 3, 0.6)
    b.set('Base Color', b.mix((0.013, 0.013, 0.014), (0.055, 0.054, 0.052), letters))
    b.set('Roughness', b.maprange(wear.outputs['Fac'], 0.3, 0.7, 0.64, 0.86))
    b.set('Normal', b.bump(b.math('ADD', b.math('MULTIPLY', ribs, 0.12), letters), 0.25, 0.001))
    return b.mat


def mat_grille():
    b = C.NB('rival_grille')
    v = b.coord('Object', 1.0)
    vor = b.voronoi(v, 150.0, rand=0.0)
    holes = b.maprange(vor.outputs['Distance'], 0.30, 0.38, 1.0, 0.0)
    b.set('Base Color', b.mix((0.002, 0.002, 0.002), (0.045, 0.045, 0.05), holes))
    b.set('Metallic', b.maprange(holes, 0, 1, 0, 0.8)).set('Roughness', 0.35)
    b.set('Normal', b.bump(holes, 0.6, 0.002))
    return b.mat


def mat_titanium_heat():
    """Exhaust titanium: straw -> blue -> violet heat tint toward the outlet (object -Y), brushed."""
    b = C.NB('rival_ti_heat')
    tc, sep = _xyz(b)
    t = b.maprange(sep.outputs['Y'], -0.55, -0.95, 0.0, 1.0)
    ramp = b.ramp(t, [(0.0, (0.45, 0.42, 0.40)), (0.45, (0.55, 0.40, 0.18)), (0.7, (0.18, 0.22, 0.55)), (1.0, (0.30, 0.18, 0.40))])
    n = b.noise(tc.outputs['Object'], 400.0, 2, 0.5)
    b.set('Base Color', ramp.outputs['Color']).set('Metallic', 1.0)
    b.set('Roughness', b.maprange(n.outputs['Fac'], 0.3, 0.7, 0.18, 0.30)).set('Anisotropic', 0.6)
    return b.mat


def mat_light(name, color, strength, lens=(0.05, 0.05, 0.05), pitch=None):
    """Emitter behind a clear lens; Emission Strength is the animatable master; pitch -> LED dots along object X."""
    b = C.NB(name)
    b.set('Base Color', lens).set('Roughness', 0.06).set('Coat Weight', 1.0).set('Coat Roughness', 0.0)
    b.set('Emission Strength', strength)
    if pitch:
        tc, sep = _xyz(b)
        dots = b.maprange(b.math('SINE', b.math('MULTIPLY', sep.outputs['X'], pitch)), -0.3, 0.5, 0.35, 1.0)
        b.set('Emission Color', b.mix((0, 0, 0), color, dots))
    else:
        b.set('Emission Color', color)
    return b.mat


def materials():
    return {
        'paint': mat_paint(),
        'glass': mat_simple('rival_glass', (0.008, 0.010, 0.013), 0.03, coat=1.0),
        'well': mat_simple('rival_well', (0.006, 0.006, 0.007), 0.85),
        'bezel': mat_simple('rival_bezel', (0.004, 0.004, 0.0045), 0.55),
        'trim': mat_simple('rival_trim', (0.012, 0.012, 0.014), 0.42, coat=0.4),
        'rubber': mat_simple('rival_rubber', (0.010, 0.010, 0.011), 0.7),
        'carbon': mat_carbon('rival_carbon'),
        'carbon_matte': mat_carbon('rival_carbon_matte', gloss=False),
        'rim': mat_simple('rival_rim', (0.16, 0.165, 0.17), 0.30, metal=1.0, noise=0.25, scale=30.0),
        'machined': mat_machined(),
        'chrome': mat_simple('rival_chrome', (0.78, 0.78, 0.77), 0.08, metal=1.0),
        'steel': mat_simple('rival_steel', (0.45, 0.45, 0.47), 0.30, metal=1.0, noise=0.3, scale=20.0),
        'ti_heat': mat_titanium_heat(),
        'accent': mat_simple('rival_accent', (0.85, 0.52, 0.02), 0.30, coat=1.0),
        'caliper': mat_simple('rival_caliper', (0.85, 0.55, 0.02), 0.32, coat=0.8),
        'decal_white': mat_simple('rival_decal_white', (0.70, 0.70, 0.67), 0.30, coat=1.0),
        'decal_black': mat_simple('rival_decal_black', (0.010, 0.010, 0.012), 0.30, coat=1.0),
        'tyre': mat_tyre(),
        'disc': mat_disc(),
        'grille': mat_grille(),
        'mirror': mat_simple('rival_mirror', (0.85, 0.87, 0.9), 0.0, metal=1.0),
        'front_light': mat_light('rival_head', (1.0, 0.86, 0.68), 9.0, pitch=900.0),
        'projector': mat_light('rival_proj', (1.0, 0.90, 0.75), 2.5, lens=(0.3, 0.3, 0.32)),
        'drl': mat_light('rival_drl', (1.0, 0.45, 0.08), 2.5),
        'rear_light': mat_light('rival_tail', (1.0, 0.02, 0.01), 3.0, lens=(0.10, 0.005, 0.005)),
    }

# ----------------------------------------------------------------------------- body


def cove(y):          # side scallop between the wheels, deepest just behind the front wheel
    return 0.032 * smooth(0.95, 0.70, y) * smooth(-1.00, -0.70, y) * (1.0 + 0.4 * smooth(-0.6, 0.6, y))


def _profile(st):
    y, w, zb, zbelt, zt, wt = st
    zmid = (zb + zbelt) / 2 + 0.04
    c = cove(y)
    return [(0.0, zb), (w - 0.14, zb), (w - 0.03, zb + 0.07), (w - 0.012 - c, zb + 0.20), (w - c * 0.4, zmid),
            (w - 0.012, zbelt - 0.035), (w - 0.04, zbelt),
            (wt + (w - 0.04 - wt) * 0.35, zbelt + (zt - zbelt) * 0.55), (wt, zt - 0.015), (0.0, zt)]


def _cage():
    bm = bmesh.new()
    cl = bm.edges.layers.float.new('crease_edge')
    rings = []
    for st in STATIONS:
        p = _profile(st)
        right = [Vector((x, st[0], z)) for x, z in p]
        left = [Vector((-x, st[0], z)) for x, z in reversed(p[1:-1])]
        rings.append([bm.verts.new(v) for v in right + left])
    n = len(rings[0])                     # 18
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        yc = (STATIONS[i][0] + STATIONS[i + 1][0]) / 2
        for j in range(n):
            f = bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
            side = j in (7, 10) and SIDE_WIN[0] < yc < SIDE_WIN[1]
            screen = j in (8, 9) and (SCREEN[0] < yc < SCREEN[1] or BACKLIGHT[0] < yc < BACKLIGHT[1])
            f.material_index = 1 if (side or screen) else 0
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for i in range(len(rings) - 1):
        for j, c in {1: 1.0, 17: 1.0, 2: 0.5, 16: 0.5, 6: 1.0, 12: 1.0, 7: 0.7, 11: 0.7, 3: 0.4, 15: 0.4}.items():
            e = bm.edges.get((rings[i][j], rings[i + 1][j]))
            if e:
                e[cl] = c
    for ring, c in ((rings[0], 0.5), (rings[-1], 1.0)):
        for j in range(n):
            e = bm.edges.get((ring[j], ring[(j + 1) % n]))
            if e:
                e[cl] = c
    return bm


def lamp_z(ax):            # headlamp slot centre line (|x| from 0.38 to 0.83)
    return 0.466 - 0.05 * (ax - 0.38) / 0.45


def opening(c):
    """True where the nose skin is cut away: grille mouth, brake ducts, headlamp slots."""
    x, z = c.x, c.z
    if (x / 0.52) ** 2 + ((z - 0.285) / 0.095) ** 2 < 1.0:
        return True
    if ((abs(x) - 0.73) / 0.075) ** 2 + ((z - 0.255) / 0.042) ** 2 < 1.0:
        return True
    ax = abs(x)
    return 0.38 < ax < 0.83 and -0.042 < z - lamp_z(ax) < 0.022


def _cut_gaps(bm, cuts, gap=0.0035):
    for co, no, region in cuts:
        co, no = Vector(co), Vector(no).normalized()
        for off in (-gap, gap):
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=co + no * off, plane_no=no)
        kill = [f for f in bm.faces if abs((f.calc_center_median() - co).dot(no)) < gap
                and region(f.calc_center_median()) and f.material_index == 0]
        bmesh.ops.delete(bm, geom=kill, context='FACES')


def build_body(coll, M, sprung):
    bm = _cage()
    tmp = mesh_from_bm('rival_body_tmp', bm, coll, [M['paint'], M['glass'], M['well'], M['carbon_matte']])
    sub = tmp.modifiers.new('sub', 'SUBSURF'); sub.levels = sub.render_levels = 3
    cutters = []
    for y in (YF, YR):
        for sx in (-1, 1):
            o = C.prim('cylinder', f'rcut{y}{sx}', loc=(sx * 0.95, y, WR), rot=(0, math.pi / 2, 0), coll=coll,
                       r=WR + 0.035, depth=0.8, segments=96)
            C.set_mat(o, M['well'])
            cutters.append(o)
            bo = tmp.modifiers.new('arch', 'BOOLEAN')
            bo.operation, bo.solver, bo.object, bo.material_mode = 'DIFFERENCE', 'EXACT', o, 'TRANSFER'
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    for o in cutters + [tmp]:
        bpy.data.objects.remove(o, do_unlink=True)
    bm = bmesh.new(); bm.from_mesh(me); bpy.data.meshes.remove(me)
    for f in bm.faces:
        c = f.calc_center_median()
        if f.material_index == 0 and (c.z < 0.20 or (f.normal.z < -0.6 and c.z < 0.32)):
            f.material_index = 3
    bvh = BVHTree.FromBMesh(bm)
    side = lambda s: (lambda c: c.x * s > 0.80 and 0.24 < c.z < 0.86)
    top_front = lambda c: c.z > 0.60 and 0.80 < c.y < 2.22
    top_rear = lambda c: c.z > 0.70 and -2.25 < c.y < -1.62
    cuts = [((0, 0.80, 0), (0, 1, 0), lambda c: c.z > 0.64 and abs(c.x) < 0.61),
            ((0.60, 0, 0), (1, 0.05, 0), top_front), ((-0.60, 0, 0), (-1, 0.05, 0), top_front),
            ((0, 2.20, 0), (0, 1, 0.6), lambda c: c.z > 0.50 and abs(c.x) < 0.61),
            ((0, 0.76, 0), (0, 1, 0.12), side(1)), ((0, 0.76, 0), (0, 1, 0.12), side(-1)),
            ((0, -0.70, 0), (0, 1, -0.10), side(1)), ((0, -0.70, 0), (0, 1, -0.10), side(-1)),
            ((0, 0, 0.245), (0, 0, 1), lambda c: abs(c.x) > 0.85 and -0.70 < c.y < 0.76),
            ((0, -1.62, 0), (0, 1, 0), lambda c: c.z > 0.78 and abs(c.x) < 0.60),
            ((0.60, 0, 0), (1, 0, 0), top_rear), ((-0.60, 0, 0), (-1, 0, 0), top_rear),
            ((0, 0, 0.80), (0, 0, 1), lambda c: abs(c.x) > 0.80 and -0.70 < c.y < 0.76),          # door tops
            ((0, 2.05, 0), (0, 1, 0), lambda c: c.z < 0.62 and abs(c.x) > 0.0),                     # nose clip
            ((0, -1.95, 0), (0, 1, 0), lambda c: c.z < 0.78)]                                         # tail clip
    _cut_gaps(bm, cuts)
    # slice the nose exactly along the headlamp slot lines first, so the slots get clean straight edges
    for sx in (-1, 1):
        for dz in (-0.042, 0.022):            # z - lamp_z(sx*x) - dz = 0  ->  normal (0.111*sx, 0, 1)
            co = Vector((sx * 0.60, 2.2, lamp_z(0.60) + dz))
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-5, plane_co=co,
                                   plane_no=Vector((0.111 * sx, 0, 1)).normalized())
        for ax in (0.38, 0.83):
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-5,
                                   plane_co=Vector((sx * ax, 2.2, 0.45)), plane_no=Vector((1, 0, 0)))
    kill = [f for f in bm.faces if f.normal.y > 0.25 and f.calc_center_median().y > 1.8 and opening(f.calc_center_median())]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    hb = bm.copy(); hb.normal_update()
    for v in hb.verts:
        v.co -= v.normal * 0.012
    for f in hb.faces:
        f.material_index = 0
    # in the nose the openings bend the vertex normals and the hull pokes OUT through the skin (brown wedges);
    # the grille, lamp backings and duct meshes close the nose, so the hull stops before it
    bmesh.ops.delete(hb, geom=[f for f in hb.faces if f.calc_center_median().y > 1.85], context='FACES')
    hull = mesh_from_bm('rival_inner_hull', hb, coll, [M['well']], parent=sprung)
    gb = bm.copy()
    bmesh.ops.delete(gb, geom=[f for f in gb.faces if f.material_index != 1], context='FACES')
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index == 1], context='FACES')
    for f in gb.faces:
        f.material_index = 0
    ins = bmesh.ops.inset_region(gb, faces=gb.faces[:], thickness=0.018, depth=-0.002, use_even_offset=True)
    for f in ins['faces']:
        f.material_index = 1
    glass = mesh_from_bm('rival_glass', gb, coll, [M['glass'], M['rubber']], angle=60, parent=sprung)
    so = glass.modifiers.new('thick', 'SOLIDIFY'); so.thickness, so.offset, so.thickness_clamp = 0.005, -1.0, 1.0
    panels = {}
    bm.faces.ensure_lookup_table()
    groups = {}
    for f in bm.faces:
        groups.setdefault(panel_of(f.calc_center_median()), []).append(f.index)
    for name, idx in groups.items():
        pb = bm.copy()
        keep = set(idx)
        pb.faces.ensure_lookup_table()
        bmesh.ops.delete(pb, geom=[f for f in pb.faces if f.index not in keep], context='FACES')
        o = mesh_from_bm('rival_' + name, pb, coll, [M['paint'], M['glass'], M['well'], M['carbon_matte']], angle=50, parent=sprung,
                         recalc=False)
        if name != 'nose':          # the converging nose tip: a shell there pokes its matte inside through the paint
            so = o.modifiers.new('thick', 'SOLIDIFY')
            so.thickness, so.offset, so.use_even_offset, so.thickness_clamp = 0.006, -1.0, False, 1.0
            so.material_offset = so.material_offset_rim = 2
        panels[name] = o
    bm.free()
    return panels, hull, glass, bvh


def panel_of(c):
    """which body panel a face belongs to (the gap strips between them are already cut)."""
    if c.z > 0.60 and abs(c.x) < 0.60 and 0.80 < c.y < 2.20:
        return 'hood'
    if abs(c.x) < 0.60 and -2.25 < c.y < -1.62 and c.z > 0.78:
        return 'boot'
    if abs(c.x) > 0.80 and -0.70 < c.y < 0.76 and 0.245 < c.z < 0.80:
        return 'door_L' if c.x < 0 else 'door_R'
    if c.y > 2.05:
        return 'nose'
    if c.y < -1.95:
        return 'tail'
    return 'body'

# ----------------------------------------------------------------------------- details


def _hit(bvh, origin, direction, out=0.0):
    h = bvh.ray_cast(Vector(origin), Vector(direction).normalized())
    if h[0] is None:
        return None, None
    return h[0] + h[1] * out, h[1]


def nose(bvh, x, z, out=0.0):
    return _hit(bvh, (x, 4.0, z), (0, -1, 0), out)


def top(bvh, x, y, out=0.0):
    return _hit(bvh, (x, y, 3.0), (0, 0, -1), out)


def flank(bvh, sx, y, z, out=0.0):
    return _hit(bvh, (sx * 2.0, y, z), (-sx, 0, 0), out)


def tail(bvh, x, z, out=0.0):
    return _hit(bvh, (x, -4.0, z), (0, 1, 0), out)


def screws(bm, pts, r=0.0055, h=0.0035):
    for p, n in pts:
        M = frame_from_normal(Vector(p), Vector(n))
        ang = [2 * math.pi * k / 6 for k in range(6)]
        loft(bm, [[M @ Vector((r * math.cos(a), r * math.sin(a), 0)) for a in ang],
                  [M @ Vector((r * math.cos(a), r * math.sin(a), h)) for a in ang],
                  [M @ Vector((0.6 * r * math.cos(a), 0.6 * r * math.sin(a), h * 1.3)) for a in ang]])


def conform_disc(bm, bvh, centre, normal, radius, segs=48, lift=0.003, inner=0.0):
    """A flat disc/ring projected onto the body surface along -normal (decals that follow the curvature)."""
    M = frame_from_normal(Vector(centre), Vector(normal))
    n = Vector(normal).normalized()

    def proj(lx, ly):
        p = M @ Vector((lx, ly, 0.3))
        h = bvh.ray_cast(p, -n)
        return (h[0] + h[1] * lift) if h[0] is not None else M @ Vector((lx, ly, lift))
    ang = [2 * math.pi * k / segs for k in range(segs)]
    outer = [bm.verts.new(proj(radius * math.cos(a), radius * math.sin(a))) for a in ang]
    if inner > 0:
        inn = [bm.verts.new(proj(inner * math.cos(a), inner * math.sin(a))) for a in ang]
        for k in range(segs):
            bm.faces.new((inn[k], inn[(k + 1) % segs], outer[(k + 1) % segs], outer[k]))
    else:
        c = bm.verts.new(proj(0, 0))
        for k in range(segs):
            bm.faces.new((c, outer[k], outer[(k + 1) % segs]))


def text_mesh(name, body, size, coll):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.align_x, cu.align_y = 'CENTER', 'CENTER'
    cu.size = size
    cu.extrude = 0.0008
    cu.offset = 0.004            # heavier race-number weight
    o = bpy.data.objects.new(name, cu)
    C.link(o, coll)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(o, do_unlink=True)
    return me


def _disc_fan(bm, centre_v, pts):
    cv = bm.verts.new(centre_v)
    vs = [bm.verts.new(p) for p in pts]
    for i in range(len(vs)):
        bm.faces.new((cv, vs[i], vs[(i + 1) % len(vs)]))


def build_details(coll, M, sp, bvh):
    parts = {}
    # --- headlamps in real recessed slots: dark bezel ribbon behind, LED blade + three projectors inside, DRL tick
    bz, led, pr, ring, drl = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    for sx in (-1, 1):
        rows = [[], [], []]
        lp = []
        for i in range(16):
            ax = 0.37 + 0.47 * i / 15
            zc = lamp_z(ax)
            for r_, dz in enumerate((-0.050, -0.010, 0.030)):
                p, n = nose(bvh, sx * ax, zc + dz, 0.0)
                rows[r_].append(bz.verts.new((p - Vector((0, 0.028, 0))) if p is not None else Vector((sx * ax, 2.2, zc + dz))))
            q, _ = nose(bvh, sx * ax, zc + 0.006, 0.0)
            if q is not None and 1 <= i <= 14:
                lp.append(q - Vector((0, 0.014, 0)))
        for r_ in range(2):
            for i in range(15):
                bz.faces.new((rows[r_][i], rows[r_][i + 1], rows[r_ + 1][i + 1], rows[r_ + 1][i]))
        tube(led, lp, 0.0055, 8, flat=0.6)
        for u in (0.30, 0.52, 0.74):
            ax = 0.38 + 0.45 * u
            p, n = nose(bvh, sx * ax, lamp_z(ax) - 0.020, 0.0)
            if p is None:
                continue
            Mf = frame_from_normal(p - Vector((0, 0.016, 0)), Vector((0, 1, 0)))
            for rr, depth, target in ((0.015, 0.0, pr), (0.019, -0.002, ring)):
                _disc_fan(target, Mf @ Vector((0, 0, depth - 0.003)),
                          [Mf @ Vector((rr * math.cos(a), rr * math.sin(a), depth)) for a in [2 * math.pi * q / 20 for q in range(20)]])
        p, n = nose(bvh, sx * 0.83, 0.405, 0.004)
        if p is not None:
            box(drl, p, (0.07, 0.006, 0.008), Matrix.Rotation(sx * math.radians(-12), 3, 'Y'))
    mesh_from_bm('rival_head_bezel', bz, coll, M['bezel'], angle=60, parent=sp)
    mesh_from_bm('rival_head_led', led, coll, M['front_light'], angle=60, parent=sp)
    mesh_from_bm('rival_head_proj', pr, coll, M['projector'], parent=sp, angle=80)
    mesh_from_bm('rival_head_rings', ring, coll, M['chrome'], parent=sp, angle=80)
    mesh_from_bm('rival_drl', drl, coll, M['drl'], parent=sp)
    # --- grille: wide low mouth, hex mesh, five machined slats, chrome surround, small emblem
    mouth = []
    for i in range(32):
        a = 2 * math.pi * i / 32
        x, z = 0.52 * math.cos(a), 0.285 + 0.095 * math.sin(a) * (1.0 - 0.15 * math.cos(a) ** 2)
        p, _ = nose(bvh, x, z, -0.006)
        if p is not None:
            mouth.append(p)
    gm, sl, sr = bmesh.new(), bmesh.new(), bmesh.new()
    if len(mouth) > 8:
        _disc_fan(gm, sum(mouth, Vector()) / len(mouth) + Vector((0, -0.05, 0)), [p + Vector((0, -0.02, 0)) for p in mouth])
        tube(sr, mouth + [mouth[0]], 0.0085, 8)
    for k in range(5):
        z = 0.218 + k * 0.034
        half = 0.50 * math.sqrt(max(0.0, 1 - ((z - 0.285) / 0.10) ** 2))
        pts = [p for p in (nose(bvh, -half + 2 * half * i / 16, z, -0.012)[0] for i in range(17)) if p is not None]
        if len(pts) > 3:
            tube(sl, pts, 0.005, 6, flat=0.35)
    mesh_from_bm('rival_grille', gm, coll, M['grille'], angle=80, parent=sp)
    mesh_from_bm('rival_grille_slats', sl, coll, M['machined'], angle=60, parent=sp)
    mesh_from_bm('rival_grille_surround', sr, coll, M['chrome'], angle=60, parent=sp)
    em = bmesh.new()
    p, n = nose(bvh, 0.0, 0.43, 0.0)
    if p is not None:
        conform_disc(em, bvh, p, n, 0.032, 32, lift=0.003)
        conform_disc(em, bvh, p, n, 0.036, 32, lift=0.0035, inner=0.031)
    mesh_from_bm('rival_emblem', em, coll, M['chrome'], angle=80, parent=sp)
    # --- splitter (curved planform carbon blade) + yellow accent lip + tow hook + screws
    spl, lip, scr = bmesh.new(), bmesh.new(), bmesh.new()
    plan = []
    for i in range(23):
        x = -0.86 + 1.72 * i / 22
        plan.append((x, 2.40 - 0.40 * (abs(x) / 0.86) ** 2.2))
    topv = [Vector((x, y, 0.150)) for x, y in plan] + [Vector((x, 1.80, 0.150)) for x, y in reversed(plan)]
    loft(spl, [[v - Vector((0, 0, 0.016)) for v in topv], topv])
    mesh_from_bm('rival_splitter', spl, coll, M['carbon'], parent=sp, bevel=0.003, angle=30)
    tube(lip, [Vector((x, y + 0.006, 0.142)) for x, y in plan], 0.0075, 8)
    box(lip, (0.42, 2.34, 0.19), (0.03, 0.06, 0.02))
    mesh_from_bm('rival_splitter_lip', lip, coll, M['accent'], parent=sp, angle=60)
    screws(scr, [((x, y - 0.035, 0.151), (0, 0, 1)) for x, y in plan[1:-1]])
    # --- brake-cooling ducts at the nose corners (dark mesh in a carbon frame)
    duct, dfr = bmesh.new(), bmesh.new()
    for sx in (-1, 1):
        ring_ = [p for p in (nose(bvh, sx * 0.73 + 0.075 * math.cos(a), 0.255 + 0.042 * math.sin(a), -0.004)[0]
                             for a in [2 * math.pi * i / 20 for i in range(20)]) if p is not None]
        if len(ring_) > 8:
            _disc_fan(duct, sum(ring_, Vector()) / len(ring_) + Vector((0, -0.03, 0)), ring_)
            tube(dfr, ring_ + [ring_[0]], 0.006, 6)
    mesh_from_bm('rival_ducts', duct, coll, M['grille'], angle=80, parent=sp)
    mesh_from_bm('rival_duct_frames', dfr, coll, M['carbon'], angle=60, parent=sp)
    # --- hood: twin extractor vents (recessed plates + slats) and two chrome hood pins with cable loops
    plate, slats, pins = bmesh.new(), bmesh.new(), bmesh.new()
    for sx in (-1, 1):
        x0, x1, y0, y1 = sx * 0.16, sx * 0.44, 1.30, 1.62
        nu, nv = 8, 10
        grid = []
        for i in range(nu + 1):
            row = []
            for j in range(nv + 1):
                x = x0 + (x1 - x0) * i / nu; y = y0 + (y1 - y0) * j / nv
                p, _ = top(bvh, x, y, 0.0015)
                row.append(plate.verts.new(p if p is not None else (x, y, 0.74)))
            grid.append(row)
        for i in range(nu):
            for j in range(nv):
                plate.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
        for k in range(8):
            y = y0 + 0.025 + k * (y1 - y0 - 0.05) / 7
            p, _ = top(bvh, (x0 + x1) / 2, y, 0.007)
            if p is not None:
                box(slats, p, (abs(x1 - x0) - 0.02, 0.008, 0.015), Matrix.Rotation(math.radians(32), 3, 'X'))
        p, n = top(bvh, sx * 0.50, 2.02, 0.0)
        if p is not None:
            conform_disc(pins, bvh, p, n, 0.024, 24, lift=0.004)
            Mf = frame_from_normal(p, n)
            tube(pins, [Mf @ Vector((0.0, 0.0, 0.006)), Mf @ Vector((0.0, 0.012, 0.016)), Mf @ Vector((0.0, 0.03, 0.008)),
                        Mf @ Vector((0.0, 0.05, 0.004))], 0.0022, 6)
    mesh_from_bm('rival_hood_vents', plate, coll, M['grille'], parent=sp, angle=80)
    mesh_from_bm('rival_hood_slats', slats, coll, M['carbon'], parent=sp, bevel=0.0015, angle=30)
    mesh_from_bm('rival_hood_pins', pins, coll, M['chrome'], parent=sp, angle=60)
    # --- side gills behind the front wheels: recessed dark plate + 4 carbon blades + chrome surround
    gp, gb_, gs = bmesh.new(), bmesh.new(), bmesh.new()
    for sx in (-1, 1):
        y0, y1, z0, z1 = 0.70, 0.98, 0.38, 0.64
        grid = []
        for i in range(7):
            row = []
            for j in range(7):
                y = y0 + (y1 - y0) * i / 6; z = z0 + (z1 - z0) * j / 6
                p, _ = flank(bvh, sx, y, z, -0.004)
                row.append(gp.verts.new(p if p is not None else (sx * 0.95, y, z)))
            grid.append(row)
        for i in range(6):
            for j in range(6):
                gp.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
        for k in range(4):
            y = y0 + 0.04 + k * 0.065
            p, n = flank(bvh, sx, y, (z0 + z1) / 2, 0.006)
            if p is not None:
                box(gb_, p, (0.01, 0.022, z1 - z0 - 0.02), Matrix.Rotation(sx * math.radians(30), 3, 'Z'))
        edge = [flank(bvh, sx, y0 + (y1 - y0) * t, z0, 0.004)[0] for t in (0, 0.5, 1)] + \
               [flank(bvh, sx, y1, z0 + (z1 - z0) * t, 0.004)[0] for t in (0.5, 1)] + \
               [flank(bvh, sx, y1 - (y1 - y0) * t, z1, 0.004)[0] for t in (0.5, 1)] + \
               [flank(bvh, sx, y0, z1 - (z1 - z0) * t, 0.004)[0] for t in (0.5, 1)]
        tube(gs, [e for e in edge if e is not None], 0.004, 6)
    mesh_from_bm('rival_gill_plates', gp, coll, M['grille'], parent=sp, angle=80)
    mesh_from_bm('rival_gill_blades', gb_, coll, M['carbon'], parent=sp, bevel=0.0015, angle=30)
    mesh_from_bm('rival_gill_surround', gs, coll, M['chrome'], parent=sp, angle=60)
    # --- carbon side skirts with an outboard flick
    sk = bmesh.new()
    for sx in (-1, 1):
        secs = []
        for k in range(16):
            t = k / 15
            y = -0.96 + 1.90 * t
            p, _ = flank(bvh, sx, y, 0.17)
            x = p.x if p is not None else sx * 0.96
            fl = 0.035 + 0.018 * math.sin(math.pi * t)
            secs.append([Vector((x - sx * 0.04, y, 0.120)), Vector((x + sx * fl, y, 0.126)), Vector((x + sx * fl, y, 0.140)),
                         Vector((x - sx * 0.04, y, 0.145))])
        loft(sk, secs)
    mesh_from_bm('rival_skirts', sk, coll, M['carbon'], parent=sp, bevel=0.002, angle=30)
    # --- side exhausts: twin heat-tinted titanium pipes per side in a carbon heat shield, dark throats
    ex, th, hs = bmesh.new(), bmesh.new(), bmesh.new()
    for sx in (-1, 1):
        for dz in (0.0, 0.068):
            z = 0.215 + dz
            pts = [Vector((sx * 0.70, -0.30, z - 0.03)), Vector((sx * 0.86, -0.55, z)), Vector((sx * 0.975, -0.86, z))]
            tube(ex, pts, 0.031, 18, cap=False)
            end = pts[-1]
            ang = [2 * math.pi * q / 18 for q in range(18)]
            loft(ex, [[end + Vector((sx * x, r * math.cos(a), r * math.sin(a))) for a in ang]
                      for x, r in ((0.0, 0.031), (0.012, 0.034), (0.016, 0.028), (0.0, 0.026))], cap=False)
            _disc_fan(th, end + Vector((sx * 0.002, 0, 0)), [end + Vector((0, 0.026 * math.cos(a), 0.026 * math.sin(a))) for a in ang])
        p, n = flank(bvh, sx, -0.80, 0.30, 0.003)
        if p is not None:
            box(hs, p, (0.008, 0.30, 0.17))
    mesh_from_bm('rival_exhaust', ex, coll, M['ti_heat'], parent=sp, angle=60)
    mesh_from_bm('rival_exhaust_throats', th, coll, M['bezel'], parent=sp, angle=80)
    mesh_from_bm('rival_heat_shields', hs, coll, M['carbon_matte'], parent=sp, bevel=0.004, angle=30)
    # --- mirrors: paint pods on stalks with real mirror glass
    for sx in (-1, 1):
        mb_, gl = bmesh.new(), bmesh.new()
        base = Vector((sx * 0.92, 0.60, 0.80))
        secs = []
        for i in range(9):
            u = i / 8
            r = 0.012 + 0.052 * math.sin(math.pi * min(1.0, u * 1.1)) ** 0.6
            y = 0.10 - 0.20 * u
            secs.append([base + Vector((sx * (0.11 + r * 1.25 * math.cos(a)), y, 0.06 + r * 0.72 * math.sin(a)))
                         for a in [2 * math.pi * k / 14 for k in range(14)]])
        loft(mb_, secs)
        tube(mb_, [base + Vector((sx * 0.01, -0.03, -0.01)), base + Vector((sx * 0.08, -0.05, 0.05))], 0.011, 8)
        c_ = base + Vector((sx * 0.11, -0.098, 0.06))
        vv = [gl.verts.new(c_ + Vector((sx * dx, 0, dz))) for dx, dz in ((-0.058, -0.028), (0.058, -0.028), (0.058, 0.028), (-0.058, 0.028))]
        gl.faces.new(vv)
        mo = mesh_from_bm(f'rival_mirror_{sx}', mb_, coll, M['paint'], parent=sp, angle=60)
        mesh_from_bm(f'rival_mirror_glass_{sx}', gl, coll, M['mirror'], parent=mo, smooth_=False)
    # --- flush door handles, race roundels with the number, race fuel filler
    hd, rd_w, rd_b = bmesh.new(), bmesh.new(), bmesh.new()
    num = text_mesh('rival_number', NUMBER, 0.20, coll)
    num.materials.append(M['decal_black'])
    for sx in (-1, 1):
        p, n = flank(bvh, sx, 0.30, 0.735, 0.002)
        if p is not None:
            box(hd, p, (0.004, 0.12, 0.018))
        p, n = flank(bvh, sx, -0.10, 0.50, 0.0)
        if p is not None:
            conform_disc(rd_w, bvh, p, n, 0.18, 64, lift=0.0025)
            conform_disc(rd_b, bvh, p, n, 0.192, 64, lift=0.0026, inner=0.178)
            o = bpy.data.objects.new(f'rival_number_{sx}', num)
            C.link(o, coll)
            o.parent = sp
            o.matrix_basis = frame_from_normal(p + n * 0.007, n)   # local x reads front-to-back on each side
    mesh_from_bm('rival_handles', hd, coll, M['bezel'], parent=sp, smooth_=False)
    mesh_from_bm('rival_roundels', rd_w, coll, M['decal_white'], parent=sp, angle=80)
    mesh_from_bm('rival_roundel_rings', rd_b, coll, M['decal_black'], parent=sp, angle=80)
    fu, fs = bmesh.new(), bmesh.new()
    p, n = top(bvh, -0.78, -1.05, 0.0)
    if p is not None:
        conform_disc(fu, bvh, p, n, 0.055, 40, lift=0.004)
        conform_disc(fu, bvh, p, n, 0.062, 40, lift=0.0042, inner=0.056)
        Mf = frame_from_normal(p, n)
        screws(fs, [(Mf @ Vector((0.068 * math.cos(a), 0.068 * math.sin(a), 0.002)), n) for a in [2 * math.pi * k / 8 for k in range(8)]])
    mesh_from_bm('rival_filler', fu, coll, M['machined'], parent=sp, angle=80)
    # --- rear: carbon ducktail lip, twin round tail lamps per side in a black bezel, finned diffuser, rear mesh
    dl, tl, tb, df = bmesh.new(), bmesh.new(), bmesh.new(), bmesh.new()
    pts = [p for p in (top(bvh, -0.84 + 1.68 * i / 20, -2.30, 0.0)[0] for i in range(21)) if p is not None]
    if len(pts) > 3:
        loft(dl, [[p + Vector((0, dy, dz)) for dy, dz in ((0.04, -0.002), (-0.035, 0.0), (-0.04, 0.03), (0.0, 0.012))] for p in pts])
    mesh_from_bm('rival_ducktail', dl, coll, M['carbon'], parent=sp, bevel=0.002, angle=30)
    for sx in (-1, 1):
        for x in (0.70, 0.53):
            p, n = tail(bvh, sx * x, 0.72, 0.0)
            if p is None:
                continue
            conform_disc(tb, bvh, p, n, 0.072, 40, lift=0.003)
            conform_disc(tl, bvh, p, n, 0.058, 40, lift=0.006, inner=0.034)
            conform_disc(tl, bvh, p, n, 0.014, 20, lift=0.006)
    mesh_from_bm('rival_tail_bezels', tb, coll, M['bezel'], parent=sp, angle=80)
    mesh_from_bm('rival_tail_lamps', tl, coll, M['rear_light'], parent=sp, angle=80)
    box(df, (0, -2.12, 0.215), (1.30, 0.42, 0.012), Matrix.Rotation(math.radians(-18), 3, 'X'))
    for k in range(6):
        box(df, (-0.55 + k * 0.22, -2.13, 0.25), (0.008, 0.40, 0.07), Matrix.Rotation(math.radians(-18), 3, 'X'))
    mesh_from_bm('rival_diffuser', df, coll, M['carbon'], parent=sp, bevel=0.002, angle=30)
    rg = bmesh.new()
    rows = []
    for z in (0.40, 0.45, 0.50):
        row = []
        for k in range(25):
            x = -0.60 + 1.20 * k / 24
            p, _ = tail(bvh, x, z, -0.004)
            row.append(rg.verts.new(p if p is not None else Vector((x, -2.30, z))))
        rows.append(row)
    for i in range(2):
        for k in range(24):
            rg.faces.new((rows[i][k], rows[i][k + 1], rows[i + 1][k + 1], rows[i + 1][k]))
    mesh_from_bm('rival_rear_mesh', rg, coll, M['grille'], parent=sp, angle=80)
    # --- wiper at the base of the screen, screws
    wp = bmesh.new()
    tube(wp, [p for p in (top(bvh, -0.55 + 0.55 * i / 8, 0.70 - 0.02 * i / 8, 0.012)[0] for i in range(9)) if p is not None], 0.006, 6, flat=0.5)
    mesh_from_bm('rival_wiper', wp, coll, M['bezel'], parent=sp, angle=60)
    mesh_from_bm('rival_screws', scr, coll, M['steel'], parent=sp, angle=60)
    mesh_from_bm('rival_filler_screws', fs, coll, M['steel'], parent=sp, angle=60)
    # --- headlight spill: two soft warm spots on the road ahead
    spots = []
    for sx in (-1, 1):
        L = bpy.data.lights.new(f'rival_beam_{sx}', 'SPOT')
        L.energy, L.color = 40.0, (1.0, 0.86, 0.68)
        L.spot_size, L.spot_blend, L.shadow_soft_size, L.volume_factor = math.radians(55), 0.9, 0.05, 0.25
        o = bpy.data.objects.new(f'rival_beam_{sx}', L)
        C.link(o, coll)
        o.location = (sx * 0.62, 2.30, 0.46)
        o.rotation_euler = (math.radians(84), 0, 0)       # spot points -Z; +84 deg about X aims it forward, 6 deg down
        o.parent = sp
        spots.append(o)
    parts['head_spots'] = spots
    return parts

# ----------------------------------------------------------------------------- panels: details ride on their panel

ATTACH = {
    'nose': ('head_bezel', 'head_led', 'head_proj', 'head_rings', 'drl', 'grille', 'grille_slats', 'grille_surround',
             'emblem', 'ducts', 'duct_frames'),
    'hood': ('hood_vents', 'hood_slats', 'hood_pins'),
    'tail': ('tail_bezels', 'tail_lamps', 'rear_mesh', 'ducktail'),
    'body': ('gill_plates', 'gill_blades', 'gill_surround', 'filler', 'filler_screws', 'wiper'),
}
SIDED = ('roundels', 'roundel_rings', 'handles')      # one mesh holds both sides -> split, ride on each door


def split_by_side(o, coll):
    """split a mesh into its -x and +x halves (by face centre); returns {-1: obj, 1: obj}."""
    out = {}
    for sx in (-1, 1):
        bm = bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().x * sx < 0], context='FACES')
        me = bpy.data.meshes.new(f'{o.name}_{sx}')
        bm.to_mesh(me); bm.free()
        for m in o.data.materials:
            me.materials.append(m)
        n = bpy.data.objects.new(f'{o.name}_{sx}', me)
        C.link(n, coll)
        for p_ in me.polygons:
            p_.use_smooth = True
        out[sx] = n
    bpy.data.objects.remove(o, do_unlink=True)
    return out


def attach_details(coll, panels):
    for panel, names in ATTACH.items():
        for nm in names:
            o = bpy.data.objects.get('rival_' + nm)
            if o is not None and panel in panels:
                o.parent = panels[panel]
    for nm in SIDED:
        o = bpy.data.objects.get('rival_' + nm)
        if o is None:
            continue
        for sx, half in split_by_side(o, coll).items():
            half.parent = panels['door_L' if sx < 0 else 'door_R']
    for sx in (-1, 1):
        o = bpy.data.objects.get(f'rival_number_{sx}')
        if o is not None:                       # doors sit at the car origin: same local placement
            o.parent = panels['door_L' if sx < 0 else 'door_R']

# ----------------------------------------------------------------------------- mechanicals (seen in the exploded view)


def build_mechanicals(coll, M, sp):
    """front-mid V8 + intake + headers, radiator, driveshaft, diff, fuel cell, carbon tub, seats, wheel, roll hoop."""
    out = {}
    bm = bmesh.new()
    box(bm, (0, 1.05, 0.40), (0.50, 0.78, 0.30))
    box(bm, (0, 1.05, 0.22), (0.40, 0.66, 0.10))
    out['engine'] = mesh_from_bm('rival_engine', bm, coll, M['steel'], parent=sp, bevel=0.012, angle=30)
    bm = bmesh.new()
    for sx in (-1, 1):
        box(bm, (sx * 0.20, 1.05, 0.62), (0.20, 0.74, 0.12), Matrix.Rotation(sx * math.radians(30), 3, 'Y'))
    out['heads'] = mesh_from_bm('rival_heads', bm, coll, M['machined'], parent=out['engine'], bevel=0.008, angle=30)
    bm = bmesh.new()
    for sx in (-1, 1):
        for k in range(4):
            y = 0.80 + k * 0.17
            base = Vector((sx * 0.07, y, 0.66))
            secs = []
            for i in range(6):
                t = i / 5
                r = 0.026 + 0.016 * t ** 2.4
                c = base + Vector((0, 0, 0.13 * t))
                secs.append([c + Vector((r * math.cos(2 * math.pi * q / 14), r * math.sin(2 * math.pi * q / 14), 0)) for q in range(14)])
            loft(bm, secs, cap=False)
    out['trumpets'] = mesh_from_bm('rival_trumpets', bm, coll, M['ti_heat'], parent=out['engine'], angle=50)
    bm = bmesh.new()
    for sx in (-1, 1):
        for k in range(4):
            y = 0.80 + k * 0.17
            tube(bm, [(sx * 0.30, y, 0.50), (sx * 0.40, y - 0.04, 0.40), (sx * 0.52, y - 0.25, 0.30), (sx * 0.66, -0.20, 0.22)], 0.020, 8)
    out['headers'] = mesh_from_bm('rival_headers', bm, coll, M['ti_heat'], parent=out['engine'], angle=50)
    bm = bmesh.new()
    box(bm, (0, 1.88, 0.40), (1.10, 0.06, 0.34))
    for sx in (-1, 1):
        box(bm, (sx * 0.58, 1.88, 0.40), (0.06, 0.08, 0.36))
    out['radiator'] = mesh_from_bm('rival_radiator', bm, coll, [M['grille']], parent=sp, bevel=0.004, angle=30)
    bm = bmesh.new()
    tube(bm, [(0, 0.62, 0.26), (0, -1.25, 0.26)], 0.04, 12)
    box(bm, (0, -1.40, 0.32), (0.34, 0.30, 0.26))
    for sx in (-1, 1):
        tube(bm, [(sx * 0.17, -1.40, 0.34), (sx * 0.80, -1.40, WR)], 0.028, 10)
    out['driveline'] = mesh_from_bm('rival_driveline', bm, coll, M['steel'], parent=sp, angle=40)
    bm = bmesh.new()
    box(bm, (0, -1.85, 0.42), (0.95, 0.38, 0.26))
    out['fuel_cell'] = mesh_from_bm('rival_fuel_cell', bm, coll, M['carbon_matte'], parent=sp, bevel=0.03, angle=40)
    bm = bmesh.new()
    box(bm, (0, -0.15, 0.16), (1.55, 1.75, 0.04))
    for sx in (-1, 1):
        box(bm, (sx * 0.74, -0.15, 0.28), (0.10, 1.75, 0.24))
    box(bm, (0, 0.70, 0.40), (1.40, 0.04, 0.44))
    out['tub'] = mesh_from_bm('rival_tub', bm, coll, M['carbon'], parent=sp, bevel=0.01, angle=40)
    bm = bmesh.new()
    for sx in (-1, 1):
        secs = []
        for (y, z, w) in ((0.10, 0.22, 0.22), (-0.25, 0.24, 0.24), (-0.42, 0.40, 0.25), (-0.52, 0.75, 0.24), (-0.55, 0.95, 0.20)):
            secs.append([Vector((sx * 0.38 + w * math.cos(a), y, z + 0.06 * math.sin(a))) for a in [2 * math.pi * q / 12 for q in range(12)]])
        loft(bm, secs)
    out['seats'] = mesh_from_bm('rival_seats', bm, coll, M['carbon_matte'], parent=sp, angle=40)
    bm = bmesh.new()
    ring = [Vector((-0.38 + 0.17 * math.cos(a), 0.30, 0.78 + 0.17 * math.sin(a))) for a in [2 * math.pi * q / 24 for q in range(25)]]
    tube(bm, ring, 0.014, 8)
    for a in (math.pi / 2, math.pi * 7 / 6, -math.pi / 6):
        tube(bm, [(-0.38, 0.30, 0.78), (-0.38 + 0.16 * math.cos(a), 0.30, 0.78 + 0.16 * math.sin(a))], 0.010, 6)
    tube(bm, [(-0.38, 0.30, 0.78), (-0.38, 0.62, 0.62)], 0.018, 8)
    tube(bm, [(-0.78, -0.62, 0.30), (-0.70, -0.68, 1.02), (0.0, -0.70, 1.12), (0.70, -0.68, 1.02), (0.78, -0.62, 0.30)], 0.025, 10)
    out['cockpit'] = mesh_from_bm('rival_cockpit', bm, coll, M['bezel'], parent=sp, angle=50)
    return out

# ----------------------------------------------------------------------------- wheels


def wheel_meshes(coll, M, key):
    """Tyre + rim assembly for axle `key` ('F' or 'R') in local coords: axle = X, outer face at +X."""
    hw = TYRE_HW[key]
    bm = bmesh.new()
    prof = [(-hw + 0.012, 0.262), (-hw - 0.003, 0.276), (-hw - 0.005, 0.305), (-hw - 0.003, 0.330), (-hw + 0.006, 0.347),
            (-hw + 0.02, 0.356), (-hw + 0.042, WR)]
    for g in (-0.55 * hw, -0.18 * hw, 0.18 * hw, 0.55 * hw):
        prof += [(g - 0.011, WR), (g - 0.007, WR - 0.009), (g + 0.007, WR - 0.009), (g + 0.011, WR)]
    prof += [(hw - 0.042, WR), (hw - 0.02, 0.356), (hw - 0.006, 0.347), (hw + 0.003, 0.330), (hw + 0.005, 0.305),
             (hw + 0.003, 0.276), (hw - 0.012, 0.262)]
    revolve(bm, prof, 128)
    tyre = mesh_from_bm(f'rival_tyre_{key}', bm, coll, M['tyre'], angle=50)
    lip = hw - 0.006
    rp = [(-hw + 0.006, 0.236), (lip - 0.03, 0.236), (lip - 0.012, 0.240), (lip, 0.251), (lip + 0.004, 0.262),
          (lip - 0.002, 0.271), (lip - 0.016, 0.268), (lip - 0.03, 0.262), (-hw + 0.02, 0.262), (-hw + 0.01, 0.268),
          (-hw, 0.265), (-hw + 0.006, 0.236)]
    bm = bmesh.new()
    revolve(bm, rp, 128, mat_idx=[0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0])
    barrel = mesh_from_bm(f'rival_barrel_{key}', bm, coll, [M['rim'], M['machined']], angle=40)
    bm = bmesh.new()
    fx_hub, fx_rim = lip - 0.085, lip - 0.024
    for i in range(5):
        for k in (-1, 1):
            ph = 2 * math.pi * i / 5 + k * 0.11
            d = Vector((0, math.cos(ph), math.sin(ph))); t = Vector((0, -math.sin(ph), math.cos(ph)))
            secs = []
            for s in range(9):
                u = s / 8
                r = 0.062 + u * (0.240 - 0.062)
                w = 0.034 - 0.012 * u + 0.022 * max(0.0, u - 0.82) ** 2 / 0.032
                fx = fx_hub + (fx_rim - fx_hub) * (u ** 0.75)
                thk = 0.036 - 0.010 * u
                c = d * r + t * (-k * 0.004 * (1 - u))
                secs.append([Vector((fx - thk, 0, 0)) + c + t * (-w / 2), Vector((fx - 0.005, 0, 0)) + c + t * (-w / 2),
                             Vector((fx, 0, 0)) + c + t * (-w * 0.2), Vector((fx, 0, 0)) + c + t * (w * 0.2),
                             Vector((fx - 0.005, 0, 0)) + c + t * (w / 2), Vector((fx - thk, 0, 0)) + c + t * (w / 2)])
            loft(bm, secs)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        if f.normal.x > 0.85:
            f.material_index = 1
    spokes = mesh_from_bm(f'rival_spokes_{key}', bm, coll, [M['rim'], M['machined']], angle=30, bevel=0.0025)
    bm = bmesh.new()
    revolve(bm, [(fx_hub - 0.05, 0.0), (fx_hub - 0.05, 0.080), (fx_hub - 0.002, 0.080), (fx_hub + 0.004, 0.072), (fx_hub + 0.006, 0.0)], 48)
    oct_ = [(0.052 * math.cos(a), 0.052 * math.sin(a)) for a in [2 * math.pi * q / 8 + math.pi / 8 for q in range(8)]]
    x0, x1 = fx_hub + 0.004, fx_hub + 0.040
    loft(bm, [[Vector((x, yy * s, zz * s)) for yy, zz in oct_] for x, s in ((x0, 1.0), (x1 - 0.008, 1.0), (x1, 0.82))])
    for q in range(3):
        a = 2 * math.pi * q / 3 + math.pi / 2
        d = Vector((0, math.cos(a), math.sin(a))); t = Vector((0, -math.sin(a), math.cos(a)))
        secs = []
        for rr, wid, hgt in ((0.045, 0.026, 0.024), (0.085, 0.020, 0.018), (0.112, 0.012, 0.010)):
            c = d * rr + Vector((x0 + 0.012, 0, 0))
            secs.append([c + t * (-wid / 2), c + t * (wid / 2), c + t * (wid / 2) + Vector((hgt, 0, 0)), c + t * (-wid / 2) + Vector((hgt, 0, 0))])
        loft(bm, secs)
    spinner = mesh_from_bm(f'rival_spinner_{key}', bm, coll, M['machined'], angle=30, bevel=0.002)
    bm = bmesh.new()
    revolve(bm, [(-0.058, 0.112), (-0.058, 0.192), (-0.026, 0.192), (-0.026, 0.112), (-0.058, 0.112)], 96)
    disc = mesh_from_bm(f'rival_disc_{key}', bm, coll, M['disc'], angle=40)
    bm = bmesh.new()
    revolve(bm, [(-0.045, 0.0), (-0.045, 0.114), (-0.012, 0.114), (fx_hub - 0.05, 0.085), (fx_hub - 0.05, 0.0)], 48)
    bell = mesh_from_bm(f'rival_bell_{key}', bm, coll, M['steel'], angle=40)
    return {'tyre': tyre, 'barrel': barrel, 'spokes': spokes, 'spinner': spinner, 'disc': disc, 'bell': bell}


def caliper_mesh(coll, M):
    bm = bmesh.new()
    secs = []
    a0, a1 = math.radians(25), math.radians(95)
    for k in range(10):
        a = a0 + (a1 - a0) * k / 9
        d = Vector((0, math.cos(a), math.sin(a)))
        secs.append([Vector((x, 0, 0)) + d * r for x, r in ((-0.085, 0.165), (-0.085, 0.212), (-0.07, 0.222), (0.004, 0.222),
                                                             (0.012, 0.212), (0.012, 0.165))])
    loft(bm, secs)
    return mesh_from_bm('rival_caliper_proto', bm, coll, M['caliper'], angle=30, bevel=0.004)


def suspension(coll, M, hub_pos, sx, sp):
    """Double wishbones + coil-over, visible through the spokes."""
    hx, hy, hz = hub_pos
    bm = bmesh.new()
    for dz in (0.13, -0.12):
        p_out = (hx - sx * 0.12, hy, hz + dz)
        tube(bm, [p_out, (sx * 0.40, hy + 0.22, hz + dz + 0.02)], 0.015, 8)
        tube(bm, [p_out, (sx * 0.40, hy - 0.22, hz + dz + 0.02)], 0.015, 8)
    tube(bm, [(hx - sx * 0.11, hy, hz - 0.14), (hx - sx * 0.12, hy, hz + 0.15)], 0.028, 10)
    arms = mesh_from_bm('rival_arms', bm, coll, M['steel'], parent=sp)
    top_ = Vector((sx * 0.42, hy + 0.04, hz + 0.30)); bot = Vector((hx - sx * 0.14, hy, hz - 0.07))
    d = top_ - bot
    u = d.normalized().cross(Vector((0, 1, 0))).normalized(); v = d.normalized().cross(u)
    pts = [bot + d * (0.15 + 0.7 * k / 140) + (u * math.cos(2 * math.pi * 7 * k / 140) + v * math.sin(2 * math.pi * 7 * k / 140)) * 0.048
           for k in range(141)]
    bs = bmesh.new(); tube(bs, pts, 0.0075, 6)
    mesh_from_bm('rival_spring', bs, coll, M['accent'], parent=arms, angle=60)
    bd = bmesh.new(); tube(bd, [bot, bot + d * 0.6], 0.021, 12); tube(bd, [bot + d * 0.55, top_], 0.011, 10)
    mesh_from_bm('rival_damper', bd, coll, M['chrome'], parent=arms)
    return arms

# ----------------------------------------------------------------------------- assembly


def build_rival(coll=None, name='Rival'):
    coll = coll or C.collection(name)
    M = materials()
    root = C.empty(name + '_root', coll=coll)
    sprung = C.empty(name + '_sprung', coll=coll)
    sprung.parent = root
    panels, hull, glass, bvh = build_body(coll, M, sprung)
    body = panels['body']
    parts = {'sprung': sprung, 'body': body, 'inner_hull': hull, 'glass': glass, 'panels': panels}
    parts.update(build_details(coll, M, sprung, bvh))
    attach_details(coll, panels)
    parts['mech'] = build_mechanicals(coll, M, sprung)
    protos = {k: wheel_meshes(coll, M, k) for k in ('F', 'R')}
    cal = caliper_mesh(coll, M)
    wheels = []
    for key, y, sx in (('FL', YF, -1), ('FR', YF, 1), ('RL', YR, -1), ('RR', YR, 1)):
        ax = key[0]
        corner = C.empty(f'{name}_corner_{key}', loc=(sx * TRACK[ax], y, WR), coll=coll)
        corner.parent = root
        flip = C.empty(f'{name}_flip_{key}', coll=coll)       # +X spin under a 180-deg Z flip = forward roll
        flip.parent = corner
        flip.rotation_euler = (0, 0, math.pi)
        spin = C.empty(f'{name}_spin_{key}', coll=coll)
        spin.parent = flip
        rz = 0.0 if sx < 0 else math.pi                     # outer face outward on each side
        for k, proto in protos[ax].items():
            o = bpy.data.objects.new(f'{name}_{k}_{key}', proto.data)
            C.link(o, coll)
            o.parent = spin
            o.rotation_euler = (0, 0, rz)
            for m in proto.modifiers:
                mm = o.modifiers.new(m.name, m.type)
                for attr in ('width', 'segments', 'limit_method', 'angle_limit', 'harden_normals'):
                    if hasattr(m, attr):
                        setattr(mm, attr, getattr(m, attr))
        c = bpy.data.objects.new(f'{name}_caliper_{key}', cal.data)
        C.link(c, coll)
        c.parent = flip
        c.rotation_euler = (0, 0, rz)
        for m in cal.modifiers:
            mm = c.modifiers.new(m.name, m.type); mm.width, mm.segments = m.width, m.segments
        parts['susp_' + key] = suspension(coll, M, (sx * TRACK[ax], y, WR), sx, sprung)
        parts['corner_' + key] = corner
        wheels.append(spin)
    for d in list(protos['F'].values()) + list(protos['R'].values()) + [cal]:
        d.hide_render = d.hide_viewport = True
    return {'root': root, 'sprung': sprung, 'wheels': wheels, 'wheel_radius': WR, 'parts': parts, 'mats': M,
            'body': body, 'proxy': False}


def set_light(car, which, strength, frame):
    for n in car['mats'][which].node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED':
            n.inputs['Emission Strength'].default_value = strength
            n.inputs['Emission Strength'].keyframe_insert('default_value', frame=frame)
