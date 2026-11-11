"""INTRO TITLE — shot 0T: ESCAPEMENT's own title shot (6A, Leon Lin, MIT: machined-brass word, turning gear world,
light sweep, fade to black) built by their code, plus two lines of ours under the steel rule in the same Bahnschrift:
the original author's name and "EXTENDED EDIT". Opens the extended edit.
END CARD - shot 0E: the same shot with the word "AI.CHEMYST" (their function, the body text swapped), "EXTENDED BY"
above it, and the credit "ESCAPEMENT - ORIGINAL BY LEON LIN" under the rule.

  rb.py ../continuation/title.py -- --shot 0T --stills 20,40,52 --pct 40 --samples 16 --tag _v1
"""
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, '..', 'film', 'lib'), os.path.join(HERE, '..', 'film', 'shots'), HERE]
from common import *
import act1_gears as A1
from mathutils import Vector as V

SHOT = str(arg('--shot', '0T'))
LINES = [('LEON LIN', 0.050, 1.55, 0.012, 'TitleBrass', -0.205),
         ('EXTENDED EDIT', 0.030, 1.9, 0.006, 'RuleSteel', -0.262)]
DROP = 0.10
if SHOT == '0E':
    LINES = [('EXTENDED BY', 0.034, 1.9, 0.006, 'RuleSteel', 0.165),
             ('ESCAPEMENT - ORIGINAL BY LEON LIN', 0.026, 1.7, 0.006, 'TitleBrass', -0.205)]
    DROP = 0.02


def text_line(body, size, spacing, extrude, mat, z):
    cu = bpy.data.curves.new('Line_' + body, 'FONT')
    cu.body = body
    cu.font = bpy.data.fonts.load(r'C:/Windows/Fonts/bahnschrift.ttf', check_existing=True)
    cu.size = size
    cu.space_character = spacing
    cu.extrude = extrude
    cu.offset = 0.0012
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    tcu = bpy.data.objects.new('LineCurve', cu)
    link(tcu)
    bpy.context.view_layer.update()
    me = bpy.data.meshes.new_from_object(tcu.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(tcu)
    o = bpy.data.objects.new('Line_' + body.replace(' ', '_'), me)
    link(o, bpy.data.objects['Title'].users_collection[0])
    o.rotation_euler = (math.radians(90), 0, 0)
    o.location = (0, 0, z)
    set_mat(o, bpy.data.materials[mat])
    m = o.modifiers.new('Bevel', 'BEVEL')
    m.width = 0.0015; m.segments = 2; m.limit_method = 'ANGLE'
    return o


if SHOT == '0E':                 # their own title function, only the word changed
    import inspect, textwrap
    src = textwrap.dedent(inspect.getsource(A1.shot_6A)).replace("cu.body = 'ESCAPEMENT'", "cu.body = 'AI.CHEMYST'")
    assert "'AI.CHEMYST'" in src
    ns = dict(A1.__dict__); exec(src, ns); ns['shot_6A']()
else:
    A1.shot_6A()
for body, size, spacing, ext, mat, z in LINES:
    text_line(body, size, spacing, ext, mat, z)
# frame the three-line block: the camera and its aim drop by half the extra height
cam = bpy.context.scene.camera
for fc in fcurves(cam):
    if fc.data_path == 'location' and fc.array_index == 2:
        for kp in fc.keyframe_points:
            kp.co[1] -= DROP; kp.handle_left[1] -= DROP; kp.handle_right[1] -= DROP
        fc.update()
for o in cam.constraints:
    tgt = getattr(o, 'target', None)
    if tgt is not None and tgt.type == 'EMPTY':
        for fc in fcurves(tgt):
            if fc.data_path == 'location' and fc.array_index == 2:
                for kp in fc.keyframe_points:
                    kp.co[1] -= DROP; kp.handle_left[1] -= DROP; kp.handle_right[1] -= DROP
        if not fcurves(tgt):
            tgt.location.z -= DROP
print(f'[title] {SHOT} built: their 6A + lines {[l[0] for l in LINES]}', flush=True)
finish(SHOT)
