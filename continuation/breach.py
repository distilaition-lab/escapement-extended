"""BREACH - the ground is the boundary (our work, built on ESCAPEMENT's 2G debris system, act2lib, MIT).

The instant the rival's nose meets the valley floor, the floor shatters from that point outward into irregular
chunks with mass (their r3 2G debris: ragged accelerating wavefront, 5 convex shard shapes, burst + suction +
gravity, tumbling), the real ground under the patch dissolves exactly behind the wavefront, and the garage is
waiting below: its lights glow up through the hole the car falls into.

  build_breach(P, f_imp, ...)   in the canyon shot (roof cam): the floor breaks around the car
  garage_below(P, heading, ...) their act-2 studio placed under the floor, ceiling opened
"""
import math, random
import bpy, bmesh
from mathutils import Vector as V, Matrix
from common import *
import act2lib as A

WAVE = dict(v=1.1, acc=0.16)          # wavefront (m/frame, m/frame^2): ~10 m open in 7 frames


def wave_radius(df):
    df = max(0.0, df)
    return WAVE['v'] * df + 0.5 * WAVE['acc'] * df * df


def tile_mat(name='BreachDirt'):
    """valley-floor dirt for the chunks: their mat_voxel recipe (rest-position texture, rough once broken)."""
    def base(n, rest=False):
        b = NB(n)
        co = A._rest_coord(b) if rest else b.coord('Object', 1.0)
        nz = b.noise(co, 0.9, 4, 0.6)
        b.set('Base Color', b.ramp(nz.outputs['Fac'], [(0.3, (0.10, 0.035, 0.02)), (0.7, (0.30, 0.115, 0.06))]).outputs[0])
        b.set('Roughness', 0.95)
        return b.mat
    return A.mat_voxel(name, base)


def dissolve_ground(objs, P, f_imp, R_max):
    """the real ground vanishes just behind the shatter wavefront (inside R_max of P), so the hole is a real hole."""
    done = set()
    for o in objs:
        for m in o.data.materials:
            if m is None or m.name in done or m.node_tree is None:
                continue
            done.add(m.name)
            nt = m.node_tree
            out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL']
            if not out or not out[0].inputs['Surface'].is_linked:
                continue
            out = out[0]
            src = out.inputs['Surface'].links[0].from_socket
            geo = nt.nodes.new('ShaderNodeNewGeometry')
            dist = nt.nodes.new('ShaderNodeVectorMath'); dist.operation = 'DISTANCE'
            dist.inputs[1].default_value = tuple(P)
            nt.links.new(geo.outputs['Position'], dist.inputs[0])
            rv = nt.nodes.new('ShaderNodeValue'); rv.name = 'BreachR'
            for f in range(1, 400):
                r = min(R_max, max(0.0, wave_radius(f - f_imp) - 1.5))
                rv.outputs[0].default_value = r if f >= f_imp else -1.0
                rv.outputs[0].keyframe_insert('default_value', frame=f)
            gt = nt.nodes.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'
            nt.links.new(dist.outputs['Value'], gt.inputs[0]); nt.links.new(rv.outputs[0], gt.inputs[1])
            # pre-glow (v6b): in the last ~12 frames glowing cracks spread from the impact point - the garage light
            # showing through the ground where it is about to break
            wn = nt.nodes.new('ShaderNodeTexNoise'); wn.inputs['Scale'].default_value = 0.7; wn.inputs['Detail'].default_value = 4
            nt.links.new(geo.outputs['Position'], wn.inputs['Vector'])
            wm = nt.nodes.new('ShaderNodeVectorMath'); wm.operation = 'MULTIPLY_ADD'      # warp: fissures, not a honeycomb
            nt.links.new(wn.outputs['Color'], wm.inputs[0]); wm.inputs[1].default_value = (0.9, 0.9, 0.9)
            nt.links.new(geo.outputs['Position'], wm.inputs[2])
            vo = nt.nodes.new('ShaderNodeTexVoronoi'); vo.feature = 'DISTANCE_TO_EDGE'; vo.inputs['Scale'].default_value = 0.9
            nt.links.new(wm.outputs['Vector'], vo.inputs['Vector'])
            ce = nt.nodes.new('ShaderNodeMapRange'); nt.links.new(vo.outputs['Distance'], ce.inputs['Value'])
            ce.inputs['From Min'].default_value = 0.0; ce.inputs['From Max'].default_value = 0.012
            ce.inputs['To Min'].default_value = 1.0; ce.inputs['To Max'].default_value = 0.0
            gr = nt.nodes.new('ShaderNodeValue'); gr.name = 'GlowR'
            for f, r in ((f_imp - 14, 0.0), (f_imp - 1, 7.0), (f_imp + 6, R_max)):
                gr.outputs[0].default_value = r; gr.outputs[0].keyframe_insert('default_value', frame=f)
            inr = nt.nodes.new('ShaderNodeMath'); inr.operation = 'LESS_THAN'
            nt.links.new(dist.outputs['Value'], inr.inputs[0]); nt.links.new(gr.outputs[0], inr.inputs[1])
            cm = nt.nodes.new('ShaderNodeMath'); cm.operation = 'MULTIPLY'
            nt.links.new(ce.outputs['Result'], cm.inputs[0]); nt.links.new(inr.outputs[0], cm.inputs[1])
            em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (1.0, 0.36, 0.08, 1)
            em.inputs['Strength'].default_value = 6.0
            emm = nt.nodes.new('ShaderNodeMixShader'); nt.links.new(cm.outputs[0], emm.inputs['Fac'])
            nt.links.new(src, emm.inputs[1]); nt.links.new(em.outputs[0], emm.inputs[2])
            tr = nt.nodes.new('ShaderNodeBsdfTransparent')
            mx = nt.nodes.new('ShaderNodeMixShader')
            nt.links.new(gt.outputs[0], mx.inputs['Fac'])
            nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(emm.outputs[0], mx.inputs[2])
            nt.links.new(mx.outputs[0], out.inputs['Surface'])
            m.surface_render_method = 'DITHERED'
            for fc in fcurves(nt):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'


def build_breach(P, f_imp, coll=None, R=13.0, cube=0.36, ground_names=('FarFloor', 'Terrain'), seed=5, tscale=1.0,
                 v=1.1, acc=0.16):
    """shatter the ground around P starting at frame f_imp (shot frames). tscale < 1 for a slow-motion shot: the
    wavefront (v, acc in m/frame) and the chunks' flight both play at that speed."""
    coll = coll or collection('Breach')
    WAVE.update(v=v, acc=acc)
    saved = dict(A.VOX)
    A.VOX.update(t0=float(f_imp), v=WAVE['v'], acc=WAVE['acc'], A=7.0, sink=(P.x, P.y, P.z - 14.0))
    mat = tile_mat()
    o = A.debris_surface('breach', coll, mat, (P.x, P.y, P.z - cube / 2), (2 * R, 2 * R), 'Z', cube, (P.x, P.y, P.z),
                         seed=seed, burst=6.5, up=1.2, turbk=2.0, big=0.25, cull_y=-1e9, cull_z=P.z - 40.0,
                         clamp_ground=False, tscale=tscale,       # a crater burst up/out, then pulled down the hole
                         keep=(P.x, 1.7, P.y, 1.7), keep_t=f_imp + 0.5)   # their 2G rule: tiles under the car drop away, never burst into it
    A.VOX.clear(); A.VOX.update(saved)
    # the glow of the garage bursting up through the crack: warm light from under the hole, on the chunks only
    glow = bpy.data.lights.new('BreachGlow', 'AREA'); glow.size = 3.0; glow.color = (1.0, 0.62, 0.32)
    go = bpy.data.objects.new('BreachGlow', glow); link(go, coll)
    go.location = (P.x, P.y, P.z - 2.0); go.rotation_euler = (math.pi, 0, 0)        # facing up
    for f, e in ((f_imp - 1, 0.0), (f_imp + 1, 9000.0), (f_imp + 10, 6000.0)):
        glow.energy = e; glow.keyframe_insert('energy', frame=f)
    rc = bpy.data.collections.new('BreachRecv'); bpy.context.scene.collection.children.link(rc)
    rc.objects.link(o)
    go.light_linking.receiver_collection = rc
    # ground light (v6b): the impact area sat in the car's own shadow at dusk - a soft sky fill from above on the
    # valley floor, its rocks and the tiles, building over the last second of the dive
    fill = bpy.data.lights.new('BreachFill', 'AREA'); fill.size = 30.0; fill.color = (1.0, 0.86, 0.72)
    fo = bpy.data.objects.new('BreachFill', fill); link(fo, coll)
    fo.location = (P.x, P.y, P.z + 30.0)
    for f, e in ((f_imp - 62, 0.0), (f_imp - 48, 26000.0), (f_imp + 8, 26000.0)):     # lit through the pitch-over too (60k washed it out)
        fill.energy = e; fill.keyframe_insert('energy', frame=f)
    fr = bpy.data.collections.new('BreachFillRecv'); bpy.context.scene.collection.children.link(fr)
    for g in bpy.data.objects:
        if g.type == 'MESH' and (g.name.startswith(('FarFloor', 'Valley_')) or g == o):
            fr.objects.link(g)
    fo.light_linking.receiver_collection = fr
    bm = bmesh.new(); bm.from_mesh(o.data)                    # a disc, not a square
    kill = [v for v in bm.verts if (V((v.co.x - P.x, v.co.y - P.y))).length > R]
    bmesh.ops.delete(bm, geom=kill, context='VERTS')
    bm.to_mesh(o.data); bm.free()
    grounds = [g for g in bpy.data.objects if g.type == 'MESH' and g.name.startswith(ground_names)]
    dissolve_ground(grounds, P, f_imp, R - 0.6)
    print(f'[breach] {len(o.data.vertices)} chunks around {tuple(round(c, 1) for c in P)} from frame {f_imp:.1f}', flush=True)
    return o


def garage_below(P, heading, coll=None, depth=6.6):
    """their act-2 studio under the breach (ceiling opened over the hole), aligned to the car's heading."""
    coll = coll or collection('GarageBelow')
    before = set(bpy.data.objects)
    S = A.build_studio(coll, voxel=False)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        if o.name.startswith(('ceiling', 'beam')) or 'beam' in o.name.lower():
            o.hide_render = True; o.hide_viewport = True
    rig = bpy.data.objects.new('GarageRig', None); link(rig, coll)
    rig.location = (P.x, P.y, P.z - depth)
    rig.rotation_euler = (0, 0, heading)
    for o in new:
        if o.parent is None:
            o.parent = rig
    bpy.context.view_layer.update()
    # nothing hangs over the hole (ceiling strips/panels flashed past the lens)
    hidden = 0
    for o in new:
        w = o.matrix_world.translation
        if w.z > P.z - depth + 3.0 and (V((w.x - P.x, w.y - P.y))).length < 9.0:
            o.hide_render = True; o.hide_viewport = True; hidden += 1
    # the studio lights light the studio only: the canyon chunks keep their dusk dirt colour (they read white-lit)
    recv = bpy.data.collections.new('GarageRecv')
    bpy.context.scene.collection.children.link(recv)
    recv.hide_render = False
    for o in new:
        if o.type != 'LIGHT':
            recv.objects.link(o)
    for o in new:
        if o.type == 'LIGHT':
            o.light_linking.receiver_collection = recv
    print(f'[breach] garage below: {hidden} fittings over the hole hidden', flush=True)
    print(f'[breach] garage below: {len(new)} objects, floor at z {P.z - depth:.1f}', flush=True)
    return S, rig


def add_clouds(cover=0.45, color=(1.0, 0.74, 0.58), shade=(0.42, 0.40, 0.46)):
    """dusk cumulus in the canyon sky (the roof cam sees the sky while the rival tumbles; it was a bare gradient).
    Projected onto a plane over the canyon (direction / z), sun-warm tops and cool bases, fading at the horizon."""
    w = bpy.context.scene.world
    nt = w.node_tree; N_, L_ = nt.nodes, nt.links
    bg = [n for n in N_ if n.type == 'BACKGROUND'][0]
    src = bg.inputs['Color'].links[0].from_socket if bg.inputs['Color'].is_linked else None
    tc = N_.new('ShaderNodeTexCoord')
    nrm = N_.new('ShaderNodeVectorMath'); nrm.operation = 'NORMALIZE'; L_.new(tc.outputs['Generated'], nrm.inputs[0])
    sep = N_.new('ShaderNodeSeparateXYZ'); L_.new(nrm.outputs['Vector'], sep.inputs[0])
    zc = N_.new('ShaderNodeMath'); zc.operation = 'MAXIMUM'; L_.new(sep.outputs['Z'], zc.inputs[0]); zc.inputs[1].default_value = 0.04
    px = N_.new('ShaderNodeMath'); px.operation = 'DIVIDE'; L_.new(sep.outputs['X'], px.inputs[0]); L_.new(zc.outputs[0], px.inputs[1])
    py = N_.new('ShaderNodeMath'); py.operation = 'DIVIDE'; L_.new(sep.outputs['Y'], py.inputs[0]); L_.new(zc.outputs[0], py.inputs[1])
    cmb = N_.new('ShaderNodeCombineXYZ'); L_.new(px.outputs[0], cmb.inputs[0]); L_.new(py.outputs[0], cmb.inputs[1])
    n1 = N_.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 0.9; n1.inputs['Detail'].default_value = 8.0
    n1.inputs['Roughness'].default_value = 0.62; L_.new(cmb.outputs[0], n1.inputs['Vector'])
    cov = N_.new('ShaderNodeMapRange'); L_.new(n1.outputs['Fac'], cov.inputs['Value'])
    cov.inputs['From Min'].default_value = 1.0 - cover; cov.inputs['From Max'].default_value = 1.0 - cover + 0.18
    hz = N_.new('ShaderNodeMapRange'); L_.new(sep.outputs['Z'], hz.inputs['Value'])
    hz.inputs['From Min'].default_value = 0.03; hz.inputs['From Max'].default_value = 0.22
    a = N_.new('ShaderNodeMath'); a.operation = 'MULTIPLY'; L_.new(cov.outputs['Result'], a.inputs[0]); L_.new(hz.outputs['Result'], a.inputs[1])
    tint = N_.new('ShaderNodeMix'); tint.data_type = 'RGBA'
    L_.new(n1.outputs['Fac'], tint.inputs['Factor'])
    tint.inputs[6].default_value = (*shade, 1); tint.inputs[7].default_value = (*color, 1)
    mx = N_.new('ShaderNodeMix'); mx.data_type = 'RGBA'
    L_.new(a.outputs[0], mx.inputs['Factor'])
    if src is not None:
        L_.new(src, mx.inputs[6])
    else:
        mx.inputs[6].default_value = bg.inputs['Color'].default_value
    L_.new(tint.outputs[2], mx.inputs[7])
    L_.new(mx.outputs[2], bg.inputs['Color'])
    print('[breach] clouds in the canyon sky', flush=True)


def valley_detail(P, R0=14.0, R1=140.0, seed=21):
    """the valley floor read as one murky colour from the roof cam: dried-mud cracks, multi-scale earth colour and
    relief near the breach, and their rocks, pebbles, scrub and grass scattered (clear of the breach itself)."""
    import canyon as C
    rng = random.Random(seed)
    fl = bpy.data.objects.get('FarFloor')
    if fl is not None and fl.data.materials:
        m = fl.data.materials[0]; nt = m.node_tree; N_, L_ = nt.nodes, nt.links
        bs = [n for n in N_ if n.type == 'BSDF_PRINCIPLED'][0]
        geo = N_.new('ShaderNodeNewGeometry')
        nA = N_.new('ShaderNodeTexNoise'); nA.inputs['Scale'].default_value = 0.35; nA.inputs['Detail'].default_value = 6
        nB = N_.new('ShaderNodeTexNoise'); nB.inputs['Scale'].default_value = 3.5; nB.inputs['Detail'].default_value = 4
        vo = N_.new('ShaderNodeTexVoronoi'); vo.feature = 'DISTANCE_TO_EDGE'; vo.inputs['Scale'].default_value = 2.2
        for t_ in (nA, nB, vo):
            L_.new(geo.outputs['Position'], t_.inputs['Vector'])
        crack = N_.new('ShaderNodeMapRange'); L_.new(vo.outputs['Distance'], crack.inputs['Value'])
        crack.inputs['From Min'].default_value = 0.0; crack.inputs['From Max'].default_value = 0.06
        crack.inputs['To Min'].default_value = 0.35; crack.inputs['To Max'].default_value = 1.0
        ramp = N_.new('ShaderNodeValToRGB'); L_.new(nA.outputs['Fac'], ramp.inputs['Fac'])
        el = ramp.color_ramp.elements
        el[0].position = 0.32; el[0].color = (0.13, 0.055, 0.03, 1)
        el[1].position = 0.70; el[1].color = (0.42, 0.24, 0.13, 1)
        e3 = el.new(0.52); e3.color = (0.26, 0.10, 0.05, 1)
        m1 = N_.new('ShaderNodeMix'); m1.data_type = 'RGBA'; m1.blend_type = 'MULTIPLY'; m1.inputs['Factor'].default_value = 1.0
        L_.new(ramp.outputs['Color'], m1.inputs[6]); L_.new(crack.outputs['Result'], m1.inputs[7])
        m2 = N_.new('ShaderNodeMix'); m2.data_type = 'RGBA'; m2.blend_type = 'OVERLAY'; m2.inputs['Factor'].default_value = 0.35
        L_.new(m1.outputs[2], m2.inputs[6]); L_.new(nB.outputs['Color'], m2.inputs[7])
        dist = N_.new('ShaderNodeVectorMath'); dist.operation = 'DISTANCE'; dist.inputs[1].default_value = tuple(P)
        L_.new(geo.outputs['Position'], dist.inputs[0])
        near = N_.new('ShaderNodeMapRange'); L_.new(dist.outputs['Value'], near.inputs['Value'])
        near.inputs['From Min'].default_value = R1 * 1.5; near.inputs['From Max'].default_value = R1 * 0.6
        old = bs.inputs['Base Color'].links[0].from_socket if bs.inputs['Base Color'].is_linked else None
        mf = N_.new('ShaderNodeMix'); mf.data_type = 'RGBA'; L_.new(near.outputs['Result'], mf.inputs['Factor'])
        if old is not None:
            L_.new(old, mf.inputs[6])
        L_.new(m2.outputs[2], mf.inputs[7]); L_.new(mf.outputs[2], bs.inputs['Base Color'])
        bmp = N_.new('ShaderNodeBump'); bmp.inputs['Strength'].default_value = 0.6; bmp.inputs['Distance'].default_value = 0.05
        hgt = N_.new('ShaderNodeMath'); hgt.operation = 'MULTIPLY'
        L_.new(crack.outputs['Result'], hgt.inputs[0]); L_.new(nB.outputs['Fac'], hgt.inputs[1])
        L_.new(hgt.outputs[0], bmp.inputs['Height']); L_.new(bmp.outputs['Normal'], bs.inputs['Normal'])
    srcs = {k: bpy.data.collections.get(k) for k in ('RockSrc', 'PebSrc', 'ScrubSrc', 'GrassSrc')}
    plan = (('RockSrc', 900, (0.12, 1.6), 0.5), ('PebSrc', 5000, (0.03, 0.14), 0.7), ('ScrubSrc', 500, (0.5, 1.3), 1.0),
            ('GrassSrc', 900, (0.4, 0.9), 1.0))
    made = 0
    for nm, n, (lo, hi), flat in plan:
        src = srcs.get(nm)
        if src is None:
            continue
        k_ = len(src.objects)
        pts, rots, scs, picks = [], [], [], []
        for _ in range(n):
            r = math.sqrt(rng.uniform(R0 * R0, R1 * R1)); a = rng.uniform(0, 2 * math.pi)
            x, y = P.x + r * math.cos(a), P.y + r * math.sin(a)
            sz = lo * (hi / lo) ** (rng.random() ** 2.2)
            pts.append((x, y, -54.0 + (0.0 if nm in ('ScrubSrc', 'GrassSrc') else -0.25 * sz)))
            rots.append((rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), rng.uniform(0, 6.3)))
            scs.append((sz, sz * rng.uniform(0.8, 1.2), sz * flat)); picks.append(rng.randrange(k_))
        C.scatter(f'Valley_{nm}', pts, rots, scs, picks, src)
        made += n
    print(f'[breach] valley detail: cracked earth + {made} rocks/pebbles/scrub/grass', flush=True)
