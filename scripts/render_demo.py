"""Render real lab recordings without subtitles, labels or text overlays."""
from datetime import datetime
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TEMP = ROOT / '.runtime/demo_segments_new'
TEMP.mkdir(parents=True, exist_ok=True)
timeline = json.loads((ROOT / 'evidence/video_timeline.json').read_text())
monitor = json.loads((ROOT / 'evidence/navigation_goals.json').read_text())
if not monitor['summary']['monitor_criteria_met']:
    raise SystemExit('Require three verified successful goals before rendering.')
goals = [g for g in monitor['goals'] if g['terminal_status'] == 'SUCCEEDED'
         and not g['initial_terminal_history']][:3]
started = datetime.fromisoformat(monitor['started_at_utc']).timestamp()
record_start = timeline['nav_record_start_epoch']
clips = []
edit_log = []

def encode(name, inputs, filters=None, duration=None):
    output = TEMP / (name + '.mp4')
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
               '-filter_threads', '1', *inputs, '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
               '-map', '0:v:0', '-map', '1:a:0']
    if duration is not None:command += ['-t', str(duration)]
    vf = list(filters or []) + ['scale=1280:720:flags=lanczos', 'setsar=1', 'fps=20']
    command += ['-vf', ','.join(vf), '-c:v', 'libx264', '-profile:v', 'baseline',
                '-level:v', '3.1', '-threads', '2', '-preset', 'veryfast', '-crf', '20',
                '-pix_fmt', 'yuv420p', '-g', '40', '-c:a', 'aac', '-b:a', '96k',
                '-shortest', '-movflags', '+faststart', str(output)]
    sources = {str(Path(v).resolve()): [Path(v).stat().st_size, Path(v).stat().st_mtime_ns] for v in inputs if Path(v).is_file()}
    recipe = json.dumps({'inputs': inputs, 'filters': filters, 'duration': duration, 'sources': sources}, sort_keys=True)
    stamp = output.with_suffix('.recipe.json')
    if output.is_file() and stamp.is_file() and stamp.read_text() == recipe:
        print('Using verified completed segment:', name, flush=True)
        clips.append(output)
        return
    print('Rendering:', name, flush=True)
    subprocess.run(command, check=True)
    stamp.write_text(recipe)
    clips.append(output)

encode('01_gazebo', ['-i', str(ROOT / 'evidence/gazebo_new_raw.mp4')],
       ['setpts=PTS-STARTPTS'], 10)
# Keep every operator-selected movement and its surrounding map update, trimming pauses.
events=[json.loads(line) for line in (ROOT / 'evidence/teleop_commands.jsonl').read_text().splitlines()]
active={}; windows=[]; mapping_start=timeline['mapping_record_start_epoch']
for event in events:
    if event.get('event')=='operator_command':active[event['id']]=event
    elif event.get('event')=='command_finished' and event.get('id') in active:
        beginning=active.pop(event['id'])
        lo=max(0,datetime.fromisoformat(beginning['timestamp_utc']).timestamp()-mapping_start-2)
        hi=datetime.fromisoformat(event['timestamp_utc']).timestamp()-mapping_start+3
        windows.append([lo,hi])
if not windows:raise SystemExit('No recorded teleoperation intervals')
merged=[]
for lo,hi in sorted(windows):
    if merged and lo<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],hi)
    else:merged.append([lo,hi])
selection="select='"+'+'.join(f'between(t,{lo:.3f},{hi:.3f})' for lo,hi in merged)+"'"
encode('02_mapping', ['-i', str(ROOT / 'evidence/mapping_new_raw.mp4')],
       [selection,'setpts=N/(15*TB*4)'])
encode('03_map', ['-loop', '1', '-i', str(ROOT / 'evidence/map_complete_rviz.png')], duration=6)
nav = ROOT / 'evidence/navigation_new_raw.mp4'
loc_start = max(0, timeline['localization_start_epoch'] - record_start)
pose_start = max(0, timeline['proper_initial_pose_epoch'] - record_start - 2)
encode('05_initial_pose', ['-ss', str(pose_start), '-i', str(nav)], ['setpts=PTS-STARTPTS'], 14)
encode('04_localization', ['-ss', str(loc_start), '-i', str(nav)], ['setpts=PTS-STARTPTS'], 12)
for number, goal in enumerate(goals, 1):
    # Preserve the unsuccessful autonomous approach before relocalization and retry.
    if number == 3 and timeline.get('retry_initial_pose_epoch'):
        failed = [g for g in monitor['goals'] if g['terminal_status'] == 'ABORTED'
                  and not g['initial_terminal_history']
                  and g['first_seen_elapsed_wall_seconds'] < goal['first_seen_elapsed_wall_seconds']
                  and g['first_seen_elapsed_wall_seconds'] > goals[1]['completed_elapsed_wall_seconds']]
        for index, attempt in enumerate(failed):
            active = started + attempt['first_seen_elapsed_wall_seconds']
            completed = started + attempt['completed_elapsed_wall_seconds']
            clicks = [c['epoch'] for c in timeline['goal_clicks'] if -1 <= active-c['epoch'] <= 10]
            if not clicks: raise SystemExit('Missing RViz click for unsuccessful approach')
            begin = min(max(clicks), active)-2
            duration_failed = completed-begin+5
            encode(f'07a_approach{index}', ['-ss', str(max(0, begin-record_start)), '-i', str(nav)],
                   ['setpts=PTS-STARTPTS'], duration_failed)
            edit_log.append({'goal_id': attempt['goal_id'], 'terminal_status': 'ABORTED',
                             'source_start_seconds': max(0, begin-record_start),
                             'clip_duration_seconds': duration_failed, 'speed': 1,
                             'complete_active_interval_preserved': True})
        encode('07b_relocalization', ['-ss', str(max(0, timeline['retry_initial_pose_epoch']-record_start-2)),
                                     '-i', str(nav)], ['setpts=PTS-STARTPTS'], 12)
    active_epoch = started + goal['first_seen_elapsed_wall_seconds']
    completed_epoch = started + goal['completed_elapsed_wall_seconds']
    click_candidates=[c['epoch'] for c in timeline['goal_clicks'] if -1 <= active_epoch-c['epoch'] <= 10]
    if not click_candidates:raise SystemExit('No recorded RViz click for ' + goal['goal_id'])
    begin_epoch = min(max(click_candidates), active_epoch) - 2
    source_start = max(0, begin_epoch - record_start)
    duration = completed_epoch - begin_epoch + 5
    encode(f'0{number+5}_goal{number}', ['-ss', str(source_start), '-i', str(nav)],
           ['setpts=PTS-STARTPTS'], duration)
    edit_log.append({'goal_id': goal['goal_id'], 'source_start_seconds': source_start,
                     'clip_duration_seconds': duration, 'speed': 1,
                     'complete_active_interval_preserved': True})
listing = TEMP / 'concat.txt'
listing.write_text(''.join("file '" + str(path) + "'\n" for path in clips))
output = ROOT / 'submission/demo_tb4_23020732.mp4'
output.parent.mkdir(exist_ok=True)
subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-f', 'concat',
                '-safe', '0', '-i', str(listing), '-c', 'copy', '-movflags', '+faststart',
                str(output)], check=True)
mapping_end = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(ROOT / 'evidence/mapping_new_raw.mp4')], text=True).strip())
(ROOT / 'evidence/video_edit.json').write_text(json.dumps({
    'output': str(output.relative_to(ROOT)), 'mapping_speed': 4,
    'mapping_source_intervals': [[lo, min(hi, mapping_end)] for lo, hi in merged if lo < mapping_end],'mapping_pauses_trimmed':True,
    'text_overlays': False, 'subtitles': False, 'navigation_clips': edit_log,
    'statement': 'Real new recordings and actual map; recorded teleoperation at 4x with pauses trimmed, complete successful goal intervals at 1x; no added text.'
}, indent=2) + '\n')
print('Demo complete:', output, flush=True)
