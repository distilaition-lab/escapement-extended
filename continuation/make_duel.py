"""Append THE DUEL (8A-8H) to the continuation edit: film/edit/edl_duel.json + film/edit/cues_duel.json.

  python continuation/make_duel.py film
Sounds are their downloaded library; hits land on their 120 BPM grid where they mark a beat.
"""
import json, os, sys

FILM = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else 'film')
E = json.load(open(os.path.join(FILM, 'edit', 'edl_cont.json')))
Q = json.load(open(os.path.join(FILM, 'edit', 'cues_cont.json')))
# (shot, in, out, fx)
DUEL = [
    ('8A', 1, 48, [{'type': 'whip', 'from': 0, 'to': 3, 'env': 'down', 'px': 120}]),
    ('8B', 1, 48, []),
    ('8C', 1, 38, [{'type': 'shake', 'from': 20, 'to': 30, 'env': 'tri', 'px': 5}]),
    ('8D', 1, 53, []),
    ('8E', 1, 67, [{'type': 'shake', 'from': 0, 'to': 66, 'env': 'flat', 'px': 3}]),
    ('8F', 1, 38, [{'type': 'shake', 'from': 14, 'to': 24, 'env': 'down', 'px': 14},
                   {'type': 'zoom', 'from': 14, 'to': 20, 'env': 'down', 'amount': 0.05}]),
    ('8G', 1, 30, [{'type': 'shake', 'from': 0, 'to': 29, 'env': 'flat', 'px': 7},
                   {'type': 'exposure', 'from': 0, 'to': 4, 'env': 'down', 'stops': 0.4}]),
    ('8H', 1, 117, [{'type': 'black', 'from': 104, 'to': 116, 'env': 'up', 'amount': 1.0}]),
]
start = E['total']
starts = {}
t = start
for shot, a, b, fx in DUEL:
    E['clips'].append({'shot': shot, 'in': a, 'out': b, 'grade': 'act3', 'fx': fx})
    starts[shot] = t
    E['starts'][shot] = t
    t += b - a + 1
E['total'] = t
json.dump(E, open(os.path.join(FILM, 'edit', 'edl_duel.json'), 'w'), indent=1)

beat = lambda fr: 230 + 12 * round((fr - 230) / 12)
S = lambda shot, local: starts[shot] + local - 1
new = [
    # 8A bumper cam: the rival's engine screaming, road rush
    dict(file='audio/sfx/car__supercar_rev.wav', frame=S('8A', 1), gain_db=-6, fade_in_s=0.05, fade_out_s=0.3, dur_s=2.1),
    dict(file='audio/sfx/whoosh__speeding.wav', frame=S('8A', 1), gain_db=-9, dur_s=2.0, fade_out_s=0.3),
    # 8B telephoto: distant engines, wind
    dict(file='audio/sfx/wind__desert_gust.wav', frame=S('8B', 1), gain_db=-14, fade_in_s=0.2, fade_out_s=0.4, dur_s=2.0),
    dict(file='audio/sfx/car__highrpm_outside.wav', frame=S('8B', 6), gain_db=-12, fade_out_s=0.4, dur_s=1.6),
    # 8C mirror cam: the rival right behind, pulling out
    dict(file='audio/sfx/car__v8_revs_amg.wav', frame=S('8C', 1), gain_db=-4, fade_in_s=0.05, fade_out_s=0.3, dur_s=1.6, pan=-0.4),
    dict(file='audio/sfx/whoosh__fast_air.wav', frame=S('8C', 18), gain_db=-8, pan=-0.5),
    # 8D bird's-eye: the block (squeal) and the dive (acceleration)
    dict(file='audio/sfx/car__tire_squeal_long.wav', frame=S('8D', 12), gain_db=-12, fade_out_s=0.25, dur_s=0.9),
    dict(file='audio/sfx/car__v8_acceleration.wav', frame=S('8D', 28), gain_db=-6, fade_out_s=0.3),
    # 8E side by side: two engines flat out
    dict(file='audio/sfx/car__dyno_revs_turbo.wav', frame=S('8E', 1), gain_db=-7, fade_in_s=0.1, fade_out_s=0.4, dur_s=2.8, pan=0.3),
    dict(file='audio/sfx/car__v8_rev.wav', frame=S('8E', 1), gain_db=-7, fade_in_s=0.1, fade_out_s=0.4, dur_s=2.8, pan=-0.3),
    # 8F blind corner: drift squeal, door slam on contact, grinding
    dict(file='audio/sfx/car__tire_squeal_long.wav', frame=S('8F', 1), gain_db=-8, fade_out_s=0.3, dur_s=1.6),
    dict(file='audio/sfx/metal__slam_door_smash.wav', frame=S('8F', 16), gain_db=-4, align='peak'),
    dict(file='audio/sfx/spark__welder_burst.wav', frame=S('8F', 16), gain_db=-9, fade_out_s=0.2),
    dict(file='audio/sfx/car__gravel_skid.wav', frame=S('8F', 26), gain_db=-8),
    # 8G door cam (half speed): heavy hit, grinding sparks pitched down
    dict(file='audio/sfx/metal__slam_factory_hard_hit.wav', frame=S('8G', 1), gain_db=-5, align='start', rate=0.8),
    dict(file='audio/sfx/spark__welding_short.wav', frame=S('8G', 2), gain_db=-7, rate=0.6, fade_out_s=0.2),
    dict(file='audio/sfx/boom__sub_knock.wav', frame=S('8G', 1), gain_db=-8),
    # 8H slow motion: braam into the drift, pitched-down squeal and air, the swell
    dict(file='audio/sfx/boom__braam.wav', frame=S('8H', 1), gain_db=-8, fade_out_s=1.5, dur_s=4.0),
    dict(file='audio/sfx/car__tire_squeal_long.wav', frame=S('8H', 1), gain_db=-11, rate=0.5, fade_in_s=0.3, fade_out_s=1.0, dur_s=4.6),
    dict(file='audio/sfx/whoosh__deep_air.wav', frame=S('8H', 6), gain_db=-9, rate=0.6, fade_out_s=0.6),
    dict(file='audio/sfx/choir__huge_echo_swell.wav', frame=S('8H', 10), gain_db=-15, fade_in_s=0.8, fade_out_s=1.2, dur_s=4.2),
]
music = Q['music']
music[-1]['end_frame'] = E['total']
music[-1]['fade_out_s'] = 1.2
# duck the drums under the slow-motion so the braam and the squeal carry it
music[-1]['duck'] = [[S('8H', 1) - 2, 0.0], [S('8H', 6), -9.0], [E['total'], -9.0]]
cq = dict(Q, length_frames=E['total'], music=music, cues=Q['cues'] + new)
json.dump(cq, open(os.path.join(FILM, 'edit', 'cues_duel.json'), 'w'), indent=1)
print('timeline', E['total'], 'frames', round(E['total'] / 24, 2), 's; duel starts at', start, starts)
