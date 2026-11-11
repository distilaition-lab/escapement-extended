"""Final edit (v6): intro 0T + their car section + 7A + THE DUEL + THE CRASH + THE FALL (roof cam / valley-floor cam
intercut) + THE BREACH into the garage (9L) + exploded view (9E) + both cars (9F) + end card 0E.
  python continuation/make_final5.py film   -> film/edit/edl_final5.json + film/edit/cues_final5.json
"""
import json, os, sys

FILM = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else 'film')
E = json.load(open(os.path.join(FILM, 'edit', 'edl_duel.json')))
Q = json.load(open(os.path.join(FILM, 'edit', 'cues_duel.json')))
for c in E['clips']:
    if c['shot'] == '8H':
        c['fx'] = []
    if c['shot'] in ('8A', '8D'):                       # speed: a drone/bumper buzz on the two calmest framings
        c['fx'] = c.get('fx', []) + [{'type': 'shake', 'from': 0, 'to': c['out'] - c['in'], 'env': 'flat', 'px': 4}]
FIN = [
    ('9A', 1, 49, 'act3', [{'type': 'shake', 'from': 8, 'to': 24, 'env': 'down', 'px': 30},
                           {'type': 'zoom', 'from': 8, 'to': 14, 'env': 'down', 'amount': 0.05}], None),
    ('9C', 1, 55, 'act3', [{'type': 'shake', 'from': 0, 'to': 10, 'env': 'down', 'px': 8}], None),
    ('9B', 1, 57, 'act3', [{'type': 'shake', 'from': 0, 'to': 56, 'env': 'flat', 'px': 7},
                           {'type': 'shake', 'from': 8, 'to': 26, 'env': 'down', 'px': 22},
                           {'type': 'shake', 'from': 28, 'to': 40, 'env': 'down', 'px': 16}], None),
    ('9W', 1, 39, 'act3', [{'type': 'shake', 'from': 0, 'to': 38, 'env': 'flat', 'px': 9},
                           {'type': 'shake', 'from': 12, 'to': 24, 'env': 'down', 'px': 20}], None),
    ('9G', 1, 61, 'act3', [{'type': 'shake', 'from': 0, 'to': 60, 'env': 'flat', 'px': 6},
                           {'type': 'shake', 'from': 0, 'to': 10, 'env': 'down', 'px': 14}], None),
    # v6b intercut (user): roof cam sky -> valley-floor cam -> roof cam ground -> valley-floor cam -> roof cam plunge + break
    ('9D', 1, 15, 'act3', [{'type': 'shake', 'from': 0, 'to': 14, 'env': 'flat', 'px': 7}], None),
    ('9V', 31, 49, 'act3', [{'type': 'shake', 'from': 0, 'to': 18, 'env': 'flat', 'px': 3},
                            {'type': 'exposure', 'from': 0, 'to': 18, 'env': 'flat', 'stops': -0.4}], None),   # gate: up into a bright sky
    ('9D', 33, 48, 'act3', [{'type': 'shake', 'from': 0, 'to': 15, 'env': 'flat', 'px': 7}], None),
    ('9V', 65, 75, 'act3', [{'type': 'shake', 'from': 0, 'to': 10, 'env': 'up', 'px': 6},
                            {'type': 'exposure', 'from': 0, 'to': 10, 'env': 'flat', 'stops': -0.4}], None),
    ('9D', 64, 94, 'act3', [{'type': 'shake', 'from': 0, 'to': 16, 'env': 'flat', 'px': 6},
                            {'type': 'shake', 'from': 16, 'to': 30, 'env': 'down', 'px': 22}], None),
    ('9L', 1, 84, 'act2', [{'type': 'shake', 'from': 22, 'to': 32, 'env': 'down', 'px': 16}], None),     # v6: the landing
    ('9E', 1, 140, 'act2', [{'type': 'exposure', 'from': 17, 'to': 22, 'env': 'down', 'stops': 0.5}], None),
    ('9F', 1, 192, 'act2', [{'type': 'black', 'from': 168, 'to': 191, 'env': 'up', 'amount': 1.0}], None),   # v6: it lingers, then fades
    ('0E', 7, 66, 'act6', [{'type': 'zoom', 'from': 0, 'to': 4, 'env': 'down', 'amount': 0.05}], None),     # end card: EXTENDED BY AI.CHEMYST
]
starts = {}
first = {}                 # a shot cut into several clips: where its first clip starts
clip_in = {}               # ... and the render frame its LAST clip starts at
t = E['total']
for shot, a, b, grade, fx, remap in FIN:
    c = {'shot': shot, 'in': a, 'out': b, 'grade': grade, 'fx': fx}
    if remap:
        c['remap'] = remap                            # 9P plays backwards: the canyon assembles into the garage
    E['clips'].append(c)
    starts[shot] = t
    first.setdefault(shot, t)
    clip_in[shot] = a
    E['starts'][shot] = t
    t += b - a + 1
E['total'] = t
json.dump(E, open(os.path.join(FILM, 'edit', 'edl_final5.json'), 'w'), indent=1)

S = lambda shot, local: starts[shot] + local - 1
SR = lambda shot, render_f: starts[shot] + render_f - clip_in[shot]     # by render frame, in the shot's last clip
FS = lambda shot: first[shot]
E0, SLAMS = 18, (92, 102, 112, 122, 132)
new = [
    # 9A barrier (half speed)
    dict(file='audio/sfx/metal__slam_explosion_impact.wav', frame=S('9A', 10), gain_db=-3, align='peak', rate=0.75),
    dict(file='audio/sfx/metal__slam_heavy_reverb.wav', frame=S('9A', 12), gain_db=-7, rate=0.8),
    dict(file='audio/sfx/spark__welder_burst.wav', frame=S('9A', 10), gain_db=-9, rate=0.7),
    dict(file='audio/sfx/car__tire_squeal_long.wav', frame=S('9A', 1), gain_db=-12, rate=0.6, dur_s=2.0, fade_out_s=0.5),
    # 9C the rival goes over
    dict(file='audio/sfx/car__highrpm_outside.wav', frame=S('9C', 1), gain_db=-6, fade_out_s=1.2, dur_s=2.2, rate=0.9),
    dict(file='audio/sfx/wind__dark_storm_gust.wav', frame=S('9C', 8), gain_db=-8),
    dict(file='audio/sfx/whoosh__deep_impact.wav', frame=S('9C', 4), gain_db=-8),
    # 9B the hero at the edge (0.6x): squeal, the sill grinding the rock, the engine screaming, the burnout
    dict(file='audio/sfx/car__tire_squeal_long.wav', frame=S('9B', 1), gain_db=-7, rate=0.8, dur_s=2.4, fade_out_s=0.4),
    dict(file='audio/sfx/spark__welding_short.wav', frame=S('9B', 10), gain_db=-6, rate=0.7),
    dict(file='audio/sfx/spark__welder_burst.wav', frame=S('9B', 18), gain_db=-8, rate=0.7),
    dict(file='audio/sfx/metal__slam_door_heavy.wav', frame=S('9B', 12), gain_db=-8, align='peak', rate=0.8),
    dict(file='audio/sfx/car__supercar_rev.wav', frame=S('9B', 26), gain_db=-4, dur_s=1.4, fade_out_s=0.3),
    dict(file='audio/sfx/wind__high_altitude.wav', frame=S('9B', 1), gain_db=-14, dur_s=2.3, fade_out_s=0.4),
    # 9W the tyre in the dirt (half speed): pitched-down scream, gravel, the engine wound out
    dict(file='audio/sfx/car__tire_squeal_long.wav', frame=S('9W', 1), gain_db=-5, rate=0.6, dur_s=1.7, fade_out_s=0.3),
    dict(file='audio/sfx/car__gravel_skid.wav', frame=S('9W', 6), gain_db=-4, rate=0.6),
    dict(file='audio/sfx/car__v8_revs_amg.wav', frame=S('9W', 1), gain_db=-6, rate=0.7, dur_s=1.6, fade_out_s=0.3),
    dict(file='audio/sfx/boom__sub_knock.wav', frame=S('9W', 18), gain_db=-8, align='peak'),
    # 9G the donut to a halt
    dict(file='audio/sfx/car__tire_squeal_long.wav', frame=S('9G', 1), gain_db=-6, fade_out_s=0.6, dur_s=2.4),
    dict(file='audio/sfx/car__dyno_revs_turbo.wav', frame=S('9G', 1), gain_db=-8, fade_out_s=0.6, dur_s=2.0),
    dict(file='audio/sfx/car__gravel_skid.wav', frame=S('9G', 52), gain_db=-8),
    # 9D the dive at the ground
    dict(file='audio/sfx/wind__mountain_top.wav', frame=FS('9D'), gain_db=-5, fade_in_s=0.15, dur_s=3.9, fade_out_s=0.3),
    dict(file='audio/sfx/whoosh__tunnel_reverb_long.wav', frame=FS('9D'), gain_db=-9, dur_s=3.9, fade_out_s=0.2),
    # 9P the portal (reversed): the disintegration sucked backwards into the garage, a heavy landing
    # v6 the breach: the ground cracks open at the nose (9D 80), the world shatters, the car falls into the garage
    dict(file='audio/sfx/riser__reverse_impact.wav', frame=SR('9D', 80), gain_db=-5, align='end'),
    dict(file='audio/sfx/hit__trailer_epic_impact.wav', frame=SR('9D', 81), gain_db=-3, align='peak', reverb=0.2),
    dict(file='audio/sfx/glitch__disintegration.wav', frame=SR('9D', 81), gain_db=-5),
    dict(file='audio/sfx/wind__dark_storm_gust.wav', frame=first['9V'], gain_db=-9),          # valley-floor cam: the fall overhead
    dict(file='audio/sfx/whoosh__deep_impact.wav', frame=S('9V', 1), gain_db=-7),
    dict(file='audio/sfx/whoosh__long_sweeping_air.wav', frame=S('9L', 1), gain_db=-8),
    dict(file='audio/sfx/boom__sub_knock.wav', frame=S('9L', 24), gain_db=-3, align='peak'),
    dict(file='audio/sfx/metal__slam_door_heavy.wav', frame=S('9L', 24), gain_db=-5, align='peak'),
    dict(file='audio/sfx/spark__welder_burst.wav', frame=S('9L', 24), gain_db=-10),
    dict(file='audio/sfx/car__tire_squeal_long.wav', frame=S('9L', 27), gain_db=-11, dur_s=1.2, fade_out_s=0.4),
    dict(file='audio/sfx/car__v8_rev.wav', frame=S('9L', 30), gain_db=-8, dur_s=1.4, fade_out_s=0.5),
    # 9E idle -> blast -> hold -> five slams
    dict(file='audio/sfx/car__engine_start.wav', frame=S('9E', 1), gain_db=-12),
    dict(file='audio/sfx/hit__trailer_epic_impact.wav', frame=S('9E', E0), gain_db=-3, align='peak'),
    dict(file='audio/sfx/metal__slam_explosion_impact.wav', frame=S('9E', E0), gain_db=-6, align='peak'),
    dict(file='audio/sfx/glitch__laser_disintegrate.wav', frame=S('9E', E0 + 1), gain_db=-11),
    dict(file='audio/sfx/choir__magic_shine.wav', frame=S('9E', E0 + 12), gain_db=-16, fade_out_s=1.0),
] + [dict(file='audio/sfx/metal__slam_door_heavy.wav', frame=S('9E', s), gain_db=-6 - i, align='peak') for i, s in enumerate(SLAMS)] + \
    [dict(file='audio/sfx/mech__gear_lock_metallic.wav', frame=S('9E', s + 1), gain_db=-10) for s in SLAMS[::2]] + \
    [dict(file='audio/sfx/elec__fluorescent_switch_flicker.wav', frame=S('9E', SLAMS[0] - 2), gain_db=-15, dur_s=2.2, fade_out_s=0.3)] + [
    # 9F the garage: hero blip f30, rival answers f48, both f78; braam to close
    dict(file='audio/sfx/car__highrpm_outside.wav', frame=S('9F', 1), gain_db=-9, dur_s=2.0, fade_out_s=0.6, pan=0.5),
    dict(file='audio/sfx/car__v8_revs_amg.wav', frame=S('9F', 28), gain_db=-5, dur_s=1.2, fade_out_s=0.4, pan=-0.3),
    dict(file='audio/sfx/car__tire_squeal_long.wav', frame=S('9F', 36), gain_db=-15, dur_s=0.6, fade_out_s=0.3, pan=0.3),
    dict(file='audio/sfx/car__dyno_revs_turbo.wav', frame=S('9F', 58), gain_db=-6, dur_s=1.2, fade_out_s=0.4, pan=0.3),
    dict(file='audio/sfx/car__supercar_rev.wav', frame=S('9F', 82), gain_db=-6, dur_s=1.4, fade_out_s=0.6, pan=0.3),
    dict(file='audio/sfx/car__v8_rev.wav', frame=S('9F', 82), gain_db=-6, dur_s=1.4, fade_out_s=0.6, pan=-0.3),
    dict(file='audio/sfx/boom__braam.wav', frame=S('9F', 98), gain_db=-7, fade_out_s=1.0),
    # end card (same design as the intro / their title): riser into the sweep, impact, whoosh, the clock tick
    dict(file='audio/sfx/riser__synth.wav', frame=S('0E', 10), gain_db=-14, align='end'),
    dict(file='audio/sfx/hit__trailer_epic_impact.wav', frame=S('0E', 10), gain_db=-5, align='peak', reverb=0.2),
    dict(file='audio/sfx/whoosh__tunnel_reverb_long.wav', frame=S('0E', 10), gain_db=-10, align='peak'),
    dict(file='audio/sfx/clock__tick_closemic_96k.wav', frame=S('0E', 50), gain_db=-8, reverb=0.5),
]
m = Q['music'][-1]
m['end_frame'] = E['total']
m['fade_out_s'] = 2.6
h8 = E['starts']['8H']
m['duck'] = [[h8 - 2, 0.0], [h8 + 4, -9.0], [S('9C', 1) - 2, -9.0], [S('9C', 4), -2.0], [FS('9D'), -4.0],
             [SR('9D', 80), -8.0], [S('9L', 30), 0.0], [S('9F', 1), -3.0], [E['total'], -3.0]]
cq = dict(Q, length_frames=E['total'], cues=Q['cues'] + new)
json.dump(cq, open(os.path.join(FILM, 'edit', 'cues_final5.json'), 'w'), indent=1)
print('timeline', E['total'], 'frames', round(E['total'] / 24, 2), 's;', starts)

# ---- v5 intro: ESCAPEMENT's own title shot (Leon Lin, MIT) + "LEON LIN" / "EXTENDED EDIT" (continuation/title.py) in
# front of everything; every later clip, cue and music segment moves back by its length. Their own title sound design.
T_IN, T_OUT = 7, 66                  # render frames: gears, rack to the word, the sweep (16-40), fade to black (56-66)
L = T_OUT - T_IN + 1
E = json.load(open(os.path.join(FILM, 'edit', 'edl_final5.json')))
cq = json.load(open(os.path.join(FILM, 'edit', 'cues_final5.json')))
E['clips'].insert(0, {'shot': '0T', 'in': T_IN, 'out': T_OUT, 'grade': 'act6',
                      'fx': [{'type': 'zoom', 'from': 0, 'to': 4, 'env': 'down', 'amount': 0.05}]})
E['starts'] = {k: v + L for k, v in E['starts'].items()}
E['starts']['0T'] = 0
E['total'] += L
for c in cq['cues']:
    c['frame'] += L
for m_ in cq['music']:
    m_['start_frame'] += L; m_['end_frame'] += L
    if 'duck' in m_:
        m_['duck'] = [[f + L, g] for f, g in m_['duck']]
hit = 16 - T_IN                       # the sweep lands on the word
cq['cues'] = [dict(file='audio/sfx/riser__synth.wav', frame=hit, gain_db=-14, align='end'),
              dict(file='audio/sfx/hit__trailer_epic_impact.wav', frame=hit, gain_db=-4, align='peak', reverb=0.2),
              dict(file='audio/sfx/whoosh__tunnel_reverb_long.wav', frame=hit, gain_db=-9, align='peak'),
              dict(file='audio/sfx/clock__tick_closemic_96k.wav', frame=56 - T_IN, gain_db=-8, reverb=0.5)] + cq['cues']
cq['length_frames'] = E['total']
json.dump(E, open(os.path.join(FILM, 'edit', 'edl_final5.json'), 'w'), indent=1)
json.dump(cq, open(os.path.join(FILM, 'edit', 'cues_final5.json'), 'w'), indent=1)
print('v5 with intro:', E['total'], 'frames', round(E['total'] / 24, 2), 's')
