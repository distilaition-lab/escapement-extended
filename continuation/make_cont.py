"""Build the continuation edit: their car section (2A..3E) + our shot 7A, with their act-3 grade and a cue sheet.

  python continuation/make_cont.py film     -> film/edit/edl_cont.json, film/edit/cues_cont.json

Their timeline frames 156..556 become 0..400; 7A local frame f sits at 399 + f. Sounds are their downloaded
library (Mixkit / Freesound CC0); every new cue lands on their 120 BPM grid (12 frames per beat, phase from the
music segment that starts at new frame 230).
"""
import json, os, sys

FILM = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else 'film')
E = json.load(open(os.path.join(FILM, 'edit', 'edl.json')))
Q = json.load(open(os.path.join(FILM, 'edit', 'cues.json')))
A, B = E['starts']['2A'], E['starts']['4B']           # 156, 556
clips = [c for c in E['clips'] if c['shot'][0] in '23']
for c in clips:
    if c['shot'] == '3E':
        c.pop('tr_out', None)
F7 = 144
clips.append({'shot': '7A', 'in': 1, 'out': F7, 'grade': 'act3', 'fx': [
    {'type': 'shake', 'from': 32, 'to': 40, 'px': 10},                     # hero blasts past the lens
    {'type': 'whip', 'from': 42, 'to': 50, 'env': 'tri', 'px': 70},        # the 180-degree turn
    {'type': 'zoom', 'from': 50, 'to': 86, 'env': 'tri', 'amount': 0.07},  # ultra-fast pull-back
    {'type': 'shake', 'from': 88, 'to': 96, 'env': 'down', 'px': 8},       # braking into position
]})
edl = dict(E)
edl['clips'] = clips
T0 = B - A                                              # 400 = 7A local frame 1
edl['total'] = T0 + F7
edl['starts'] = {}
t = 0
for c in clips:
    edl['starts'][c['shot']] = t
    t += c['out'] - c['in'] + 1
json.dump(edl, open(os.path.join(FILM, 'edit', 'edl_cont.json'), 'w'), indent=1)

L7 = lambda f: T0 + f - 1                               # 7A local frame -> timeline frame
beat = lambda fr: 230 + 12 * round((fr - 230) / 12)     # snap to their 120 BPM grid
cues = [dict(c, frame=c['frame'] - A) for c in Q['cues'] if A <= c['frame'] < B]
music = []
for m in Q['music']:
    if m['end_frame'] <= A or m['start_frame'] >= B:
        continue
    s0 = max(m['start_frame'], A)
    m2 = dict(m, start_frame=s0 - A, end_frame=min(m['end_frame'], B) - A,
              offset_s=m['offset_s'] + (s0 - m['start_frame']) / 24.0)
    music.append(m2)
music[-1]['end_frame'] = T0 + F7                        # the drums keep running through 7A
music[-1]['fade_out_s'] = 0.9
new = [
    # out of the dust: desert wind, the hero's engine arriving
    dict(file='audio/sfx/wind__desert_gust.wav', frame=L7(1), gain_db=-15, fade_in_s=0.25, fade_out_s=1.2, dur_s=3.0),
    dict(file='audio/sfx/car__tire_squeal_long.wav', frame=L7(14), gain_db=-15, fade_in_s=0.2, fade_out_s=0.5, dur_s=1.4, pan=-0.2),
    dict(file='audio/sfx/car__passby_v8_supercar.wav', frame=beat(L7(36)), gain_db=-3, align='peak', pan=0.3),
    dict(file='audio/sfx/car__gravel_skid.wav', frame=L7(30), gain_db=-12, pan=0.2),
    # the turn and the pull-back
    dict(file='audio/sfx/whoosh__fast_transition.wav', frame=beat(L7(47)), gain_db=-5, align='peak'),
    dict(file='audio/sfx/whoosh__speeding.wav', frame=L7(50), gain_db=-5, fade_in_s=0.1, fade_out_s=0.25, dur_s=1.7),
    dict(file='audio/sfx/wind__high_altitude.wav', frame=L7(52), gain_db=-13, fade_in_s=0.3, fade_out_s=0.4, dur_s=1.6),
    # the meet: a hit on the beat as the camera locks in front of the rival
    dict(file='audio/sfx/hit__trailer_whoosh_impact.wav', frame=beat(L7(93)), gain_db=-6, align='peak'),
    dict(file='audio/sfx/boom__sub_knock.wav', frame=beat(L7(93)), gain_db=-8, align='peak'),
    # the rival: a front-engine V8 on the throttle, closing on the lens
    dict(file='audio/sfx/car__v8_acceleration.wav', frame=L7(92), gain_db=-4, fade_in_s=0.15, pan=-0.1),
    dict(file='audio/sfx/car__v8_revs_amg.wav', frame=L7(112), gain_db=-6, fade_in_s=0.2, fade_out_s=0.5, dur_s=1.4),
    dict(file='audio/sfx/car__highrpm_outside.wav', frame=beat(L7(140)), gain_db=-5, align='peak', fade_out_s=0.3),
]
cq = dict(Q, length_frames=T0 + F7, music=music, cues=cues + new)
json.dump(cq, open(os.path.join(FILM, 'edit', 'cues_cont.json'), 'w'), indent=1)
print('timeline', T0 + F7, 'frames', round((T0 + F7) / 24, 2), 's;', len(cues), 'of their cues kept,', len(new), 'new;',
      'music', [(m['start_frame'], m['end_frame']) for m in music])
