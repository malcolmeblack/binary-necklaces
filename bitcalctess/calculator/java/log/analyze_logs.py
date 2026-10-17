#!/usr/bin/env python3
"""Build an offline visual report from ParallelRunLog *.log files (Python 3.9+).

Place this file in ./log/ and run: python3 analyze_logs.py
The default output is analysis.html beside this script, regardless of cwd.
Optional: --directory PATH --output PATH --strict
No packages, network, Java changes, or web server are required. Input logs are
never modified. Appended runs remain separate; failed/incomplete runs are not
included in runtime medians. Invalid profiling is flagged, not drawn as zeros.
--strict writes the report then exits 2 if any run has validation warnings.
"""
import argparse
import csv
import html
import math
from pathlib import Path
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone

PHASES = [
    ('scan_and_overhead_worker_s', 'Scanning and overhead', 'scan_s'),
    ('cycle_entry_worker_s', 'Finding cycles', 'entry_s'),
    ('cycle_key_worker_s', 'Identifying chain pairs', 'key_s'),
    ('ownership_claim_worker_s', 'Claiming chains', 'claim_s'),
    ('tree_and_cycle_exploration_worker_s', 'Traversing cycles and trees', 'explore_s'),
]
COLORS = ['#64748b', '#2563eb', '#8b5cf6', '#d97706', '#0d9488']
KV = re.compile(r'(?<!\S)([A-Za-z_][\w]*)=(.*?)(?=\s+[A-Za-z_][\w]*=|$)')

def scalar(value):
    if value in ('n/a', 'null', ''):
        return None
    if value in ('true', 'false'):
        return value == 'true'
    try:
        if re.fullmatch(r'-?\d+', value):
            return int(value)
        number = float(value)
        return number if math.isfinite(number) else None
    except ValueError:
        return value

def pairs(line):
    return {key: scalar(value.strip()) for key, value in KV.findall(line.strip())}

def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def esc(value):
    return html.escape(str(value), quote=True)

def fmt(value, places=3):
    if not number(value):
        return 'Unavailable'
    return f'{value:,.{places}f}' if places else f'{value:,.0f}'

def secs(value):
    if not number(value): return 'Unavailable'
    if value == 0: return '0 s'
    if value < .001: return f'{value*1e6:,.1f} µs'
    if value < 1: return f'{value*1000:,.1f} ms'
    if value < 60: return f'{value:,.3f} s'
    return f'{value/60:,.2f} min'

def parse_file(path):
    text = path.read_text(encoding='utf-8', errors='replace')
    blocks = re.split(r'^=== RUN (.*?) ===\s*$', text, flags=re.M)
    runs = []
    if len(blocks) == 1:
        if not text.strip(): return []
        chunks = [('Unknown start', text)]
    else:
        chunks = list(zip(blocks[1::2], blocks[2::2]))
    for index, (stamp, body) in enumerate(chunks, 1):
        run = dict(source=path.name, index=index, timestamp=stamp, meta={}, totals={},
                   workers=[], cycles=[], slow=[], discoveries=[], progress=[], operations=[], warnings=[],
                   complete='=== END RUN ===' in body, raw=body)
        section = 'meta'
        header = None
        for line in body.splitlines():
            line = line.strip()
            if not line: continue
            if line.startswith('PROGRESS '):
                run['progress'].append(pairs(line[9:]) | {'workers': []}); section = 'progress'; continue
            if line.startswith('WORKERS '): section='workers'; continue
            if line == 'TOTALS': section='totals'; continue
            if line.startswith('BY_CYCLE_LENGTH '): section='cycles'; header=None; continue
            if line.startswith('TOP_10_CHAINS_'): section='slow'; header=None; continue
            if line == 'SLOWEST_DISCOVERY_ATTEMPTS': section='discoveries'; continue
            if line.startswith('canonical_phase='):
                run['operations'].append(pairs(line)); continue
            if line.startswith('DISCOVERY '):
                run['discoveries'].append(pairs(line[10:])); continue
            if line.startswith(('cycle_length,', 'cycle_key,')):
                header = next(csv.reader([line])); continue
            if section in ('cycles','slow') and re.match(r'^\d+,',line):
                values = next(csv.reader([line]))
                if header and len(values)==len(header):
                    run[section].append(dict(zip(header,map(scalar,values))))
                else: run['warnings'].append('A cycle/chain CSV row is malformed.')
                continue
            if line.startswith('worker='):
                worker = pairs(line)
                if section=='workers': run['workers'].append(worker)
                elif section=='progress' and run['progress']:
                    run['progress'][-1]['workers'].append(worker)
                continue
            fields = pairs(line)
            if fields:
                if set(fields) & {
                    'completed_chains', 'cycle_key_successor_evaluations',
                    'snapshot_publications', 'snapshot_publish_ns',
                    'sampled_peak_heap_bytes', 'partial_snapshot',
                }:
                    run['totals'].update(fields)
                    continue
                # Final summary can follow a progress block without a section marker.
                target = 'totals' if section=='totals' else 'meta'
                if section not in ('cycles','slow','discoveries'): run[target].update(fields)
        validate(run)
        runs.append(run)
    return runs

def validate(run):
    m,t,w=run['meta'],run['totals'],run['warnings']
    n=m.get('n')
    if not isinstance(n,int) or isinstance(n,bool) or not 1<=n<=30:
        w.append('Missing or unsupported n (expected an integer from 1 to 30).')
        n=None
    run['n']=n
    run['status']=str(m.get('status','INCOMPLETE'))
    wall=m.get('chainReps_wall_s')
    run['timing_valid']=(run['complete'] and run['status']=='SUCCESS' and number(wall) and wall>0 and n is not None)
    if not run['complete']: w.append('Run has no END RUN marker; it may still be running or was interrupted.')
    if run['status']!='SUCCESS': w.append('Run did not report SUCCESS; excluded from timing comparisons.')
    if not number(wall) or wall<=0: w.append('Missing or nonpositive chainReps wall time.')
    if n and m.get('powerset_size') != 2**n: w.append('Reported power-set size does not match 2^n.')
    if n:
        expected=sum(2**math.gcd(n,k) for k in range(n))//n
        run['expected_bitloops']=expected
        if run['status']=='SUCCESS':
            if t.get('scanned') != 2**n:
                w.append(f"Scanned candidates should be {2**n:,}; reported {t.get('scanned', 'missing')}. Worker instrumentation is incomplete or inconsistent.")
            if t.get('unique_covered_bitloops_both_orientations') != expected:
                w.append(f"Expected {expected:,} distinct rotation classes (bitloops); coverage reports {t.get('unique_covered_bitloops_both_orientations', 'missing')}.")
    def equal_sum(total,keys):
        vals=[t.get(k) for k in keys]
        if not number(t.get(total)) or not all(number(v) for v in vals) or t[total]!=sum(vals):
            w.append(f'Counter mismatch: {total} must equal ' + ' + '.join(keys)+'.')
    equal_sum('scanned',['covered_skips','noncanonical_skips','discovery_attempts'])
    equal_sum('discovery_attempts',['owned_chain_pairs','lost_claims'])
    if t.get('owned_chain_pairs')!=m.get('representatives'):
        w.append('Owned chain-pair count does not match the returned representative count.')
    worker_fields=['wall_s','scan_s','entry_s','key_s','claim_s','explore_s','scanned','claims','lost_claims']
    workers=run['workers']
    if len(workers)!=m.get('workers') or len({x.get('worker') for x in workers})!=len(workers):
        w.append('Final worker rows are missing, duplicated, or inconsistent with the worker count.')
    if not workers or not all(all(number(x.get(k)) and x[k]>=0 for k in worker_fields) for x in workers):
        w.append('Worker rows lack valid nonnegative measurements.')
    else:
        if not any(x['wall_s']>0 for x in workers): w.append('Every worker reports zero elapsed time. These are unpopulated measurements, not idle workers.')
        for field,total in [('scanned','scanned'),('claims','owned_chain_pairs'),('lost_claims','lost_claims')]:
            if sum(x[field] for x in workers)!=t.get(total): w.append(f'Worker {field} does not sum to {total}.')
        if any(abs(x['wall_s']-sum(x[p[2]] for p in PHASES))>0.000004 for x in workers):
            w.append('Worker phase times do not add up to worker elapsed time.')
    if workers:
        for total, _, field in PHASES:
            values=[x.get(field) for x in workers]
            if all(number(v) for v in values) and number(t.get(total)):
                if abs(sum(values)-t[total]) > (len(workers)+1)*0.0000005+0.000001:
                    w.append(f'Worker {field} does not sum to {total}.')
    phase_values=[t.get(p[0]) for p in PHASES]
    if not all(number(v) and v>=0 for v in phase_values) or not number(t.get('worker_wall_sum_s')):
        w.append('Phase totals are missing or invalid.')
    elif abs(sum(phase_values)-t['worker_wall_sum_s'])>0.000004:
        w.append('Phase totals do not add up to summed worker time.')
    cycles=run['cycles']
    needed=['cycle_length','owned','attempts','lost_claims','entry_s','key_s','explore_s','visited_nodes','max_tree_depth_edges']
    if not cycles or not all(all(number(c.get(k)) and c[k]>=0 for k in needed) and c['cycle_length']>0 for c in cycles):
        w.append('Cycle-length breakdown is absent or malformed.')
    else:
        for field,total in [('owned','owned_chain_pairs'),('attempts','discovery_attempts'),('lost_claims','lost_claims'),('visited_nodes','visited_nodes_one_orientation')]:
            if sum(c[field] for c in cycles)!=t.get(total): w.append(f'Cycle-table {field} does not sum to {total}.')
    raw_version=m.get('profiling_version',0) or 0
    version=int(raw_version) if number(raw_version) and raw_version>=0 else 0
    if raw_version and version not in (1,2):
        w.append(f'Unsupported profiling version: {raw_version}.')
    run['profiling_version']=version
    if version >= 2:
        if not number(m.get('setup_s')) or not number(m.get('jvm_uptime_start_ms')):
            w.append('Version 2 setup timing or JVM uptime is missing.')
        if not number(t.get('completed_chains')) or t.get('completed_chains') != m.get('representatives'):
            w.append('Completed traversal count does not match returned representatives.')
        if not number(t.get('cycle_key_successor_evaluations')):
            w.append('Corrected cycle-key successor count is missing.')
        elif cycles and sum(c['cycle_length']*c['attempts'] for c in cycles) != t['cycle_key_successor_evaluations']:
            w.append('Cycle-key successor count does not match cycle lengths and discovery attempts.')
        if not number(t.get('snapshot_publish_ns')) or not number(t.get('snapshot_publications')):
            w.append('Snapshot publication cost counters are missing.')
        by_phase={op.get('canonical_phase'):op for op in run['operations']}
        required_phases=['scan_and_overhead','cycle_entry','cycle_key','ownership_claim','tree_and_cycle_exploration']
        if set(by_phase) != set(required_phases) or len(run['operations']) != len(required_phases):
            w.append('Canonicalization operation counters are missing or duplicated.')
        else:
            for phase,op in by_phase.items():
                fields=['canonical_calls','rotation_steps','canonical_samples','canonical_sample_ns']
                if not all(number(op.get(k)) and op[k]>=0 for k in fields):
                    w.append(f'Canonicalization counters are invalid for {phase}.')
                    continue
                calls=op['canonical_calls']
                # Each worker samples independently; total samples differ by at most
                # workers - 1 from ceil(total calls / stride).
                min_samples=(calls+1023)//1024
                max_samples=min_samples+max(0,(m.get('workers') or 1)-1)
                if not min_samples <= op['canonical_samples'] <= max_samples:
                    w.append(f'Canonical timing sample count is inconsistent for {phase}.')
                if op['rotation_steps'] > calls*max(0,n-1):
                    w.append(f'Canonical rotation count is out of range for {phase}.')
            if by_phase.get('cycle_entry',{}).get('canonical_calls') != t.get('cycle_entry_successor_evaluations'):
                w.append('Floyd successor count does not match cycle-entry canonical calls.')
            if by_phase.get('cycle_key',{}).get('canonical_calls') != 2*t.get('cycle_key_successor_evaluations',-1):
                w.append('Cycle-key canonical calls do not match successor evaluations.')
        worker_v2=['start_offset_s','finish_offset_s','completed_chains']
        if all(all(number(x.get(k)) and x[k]>=0 for k in worker_v2) for x in workers):
            if sum(x['completed_chains'] for x in workers) != m.get('representatives'):
                w.append('Worker completed-traversal counts do not match representatives.')
            for x in workers:
                if x['finish_offset_s'] < x['start_offset_s'] or abs((x['finish_offset_s']-x['start_offset_s'])-x['wall_s']) > 0.000004:
                    w.append(f'Worker {x.get("worker")} start/finish offsets do not match elapsed time.')
        else:
            w.append('Version 2 worker offsets or completed-traversal counts are missing.')
        if not run['discoveries'] and t.get('discovery_attempts',0):
            w.append('Slow discovery-attempt samples are missing.')
        for d in run['discoveries']:
            if not all(number(d.get(k)) for k in ['rank','candidate','chain_key','cycle_length','entry_successors','entry_s','key_s']) or not isinstance(d.get('won'),bool):
                w.append('A slow discovery-attempt record is malformed.')
                break
        progress_fields=['elapsed_s','scanned','attempts','claimed','visited_nodes','heap_used_bytes',
                         'completed_chains','covered_bitloops','active_workers','scan_fraction','interval_s',
                         'scan_rate_per_s','node_rate_per_s','sampled_peak_heap_bytes','gc_time_ms_delta']
        for snapshot in run['progress']:
            if not all(k in snapshot for k in progress_fields):
                w.append('A progress snapshot is missing version 2 fields.')
                break
            if len(snapshot.get('workers',[])) != m.get('workers'):
                w.append('A progress snapshot has an incomplete worker list.')
                break
    # Fail closed: only consistent completed profiles drive operation-level charts.
    run['profile_valid']=run['timing_valid'] and not w
    run['config']=' | '.join(f'{k}={m.get(k,"unknown")}' for k in
            ['workers','available_processors','java','vm','os','arch','heap_max_bytes'])
    run['config']+=' | profiling_version='+str(version)
    run['max_cycle']=max((c['cycle_length'] for c in cycles),default=None) if run['profile_valid'] else None
    run['divisors']=[i for i in range(1,n+1) if n%i==0] if n else []
    run['prime']=n is not None and len(run['divisors'])==2

def table(headers,rows):
    return '<div class="tablewrap"><table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def empty(message):
    return '<div class="empty">'+esc(message)+'</div>'

def bars(rows,unit='worker seconds'):
    """rows: (label, value, color). SVG is offline and has native hover titles."""
    if not rows: return empty('No valid measurements are available for this chart.')
    maxval=max(v for _,v,_ in rows) or 1
    height=48+len(rows)*34
    out=[f'<svg role="img" aria-label="{esc(unit)}" viewBox="0 0 880 {height}" style="min-width:640px"><text x="280" y="18" class="axis">{esc(unit)} · bars start at zero</text>']
    for i,(label,value,color) in enumerate(rows):
        y=36+i*34
        out += [f'<text x="265" y="{y+17}" text-anchor="end">{esc(label)}</text>',
                f'<rect x="280" y="{y}" width="{500*value/maxval:.2f}" height="24" rx="4" fill="{color}"><title>{esc(label)}: {value:,.6f} {esc(unit)}</title></rect>',
                f'<text x="{290+500*value/maxval:.2f}" y="{y+17}">{value:,.3f}</text>']
    return '<div class="chart">'+''.join(out)+'</svg></div>'

def scatter(points,xlabel,ylabel,log_y=False,integer_x=False):
    """All supplied points are preserved; hover labels identify each observation."""
    if not points: return empty('No valid measurements are available for this comparison.')
    points=[p for p in points if p[1]>0] if log_y else points
    if not points: return empty('No positive measurements are available.')
    xs=[p[0] for p in points]; ys=[math.log10(p[1]) if log_y else p[1] for p in points]
    x0,x1=min(xs),max(xs)
    if x0==x1: x0-=1; x1+=1
    else: pad=(x1-x0)*.06; x0-=pad; x1+=pad
    if log_y:
        y0,y1=math.floor(min(ys)),math.ceil(max(ys))
        if y0==y1: y0-=1; y1+=1
    else: y0=0; y1=max(ys)*1.12 or 1
    def xp(x): return 85+(x-x0)/(x1-x0)*720
    def yp(y): return 286-(y-y0)/(y1-y0)*235
    out=['<svg role="img" aria-label="'+esc(ylabel+' versus '+xlabel)+'" viewBox="0 0 880 355">']
    for i in range(5):
        val=y0+(y1-y0)*i/4; y=yp(val)
        label=f'{10**val:.3g}' if log_y else f'{val:.3g}'
        out.append(f'<path d="M85 {y}H805" stroke="#e2e8f0"/><text x="76" y="{y+4}" text-anchor="end" class="axis">{label}</text>')
    if integer_x: ticks=list(range(math.ceil(x0),math.floor(x1)+1))
    else: ticks=[x0+(x1-x0)*i/4 for i in range(5)]
    for val in ticks:
        out.append(f'<text x="{xp(val)}" y="310" text-anchor="middle" class="axis">{val:g}</text>')
    for (x,y,label,color),transformed in zip(points,ys):
        out.append(f'<circle cx="{xp(x)}" cy="{yp(transformed)}" r="6" fill="{color}" stroke="white" stroke-width="1.5" opacity=".85"><title>{esc(label)}; x={x:g}; y={y:.6g}</title></circle>')
    out.extend([f'<text x="445" y="342" text-anchor="middle">{esc(xlabel)}</text>',f'<text x="85" y="25">{esc(ylabel)}'+(' · logarithmic scale' if log_y else '')+'</text>','</svg>'])
    return '<div class="chart">'+''.join(out)+'</div>'

def run_detail(run,i):
    m,t=run['meta'],run['totals']
    content=[f'<article class="run" id="run-{i}">',f'<h2>n = {esc(run["n"])} · {esc(run["timestamp"])}</h2>',
             '<p class="muted">'+esc(f'{run["source"]} · run {run["index"]} · {run["status"]}')+'</p>']
    if run['warnings']:
        content.append('<div class="warning"><b>Validation warnings</b><ul>'+''.join('<li>'+esc(x)+'</li>' for x in run['warnings'])+'</ul></div>')
    content.append('<h3>Measured scope and structure</h3>')
    content.append(table(['Metric','Value'],[
        ['Component discovery wall time',secs(m.get('chainReps_wall_s'))],
        ['Setup time (bitmap and workers)',secs(m.get('setup_s'))],
        ['Parallel phase wall time',secs(m.get('parallel_wall_s'))],
        ['Output assembly',secs(m.get('assembly_s'))],
        ['Log scope','ParallelCalculator.chainReps'],
        ['Full program runtime','Not recorded'],
        ['Power-set size',fmt(m.get('powerset_size'),0)],
        ['Divisors of n',esc(', '.join(map(str,run['divisors'])))],
        ['Prime n','Yes' if run['prime'] else 'No'],
        ['Largest power of 2 dividing n',str(run['n'] & -run['n']) if run['n'] else 'Unavailable'],
        ['Representatives (components/reflected pairs)',fmt(m.get('representatives'),0)],
        ['Profiling version',fmt(m.get('profiling_version'),0)],
        ['JVM uptime at start',fmt(m.get('jvm_uptime_start_ms')/60000,2)+' min' if number(m.get('jvm_uptime_start_ms')) else 'Unavailable'],
        ['Sampled peak heap',fmt(t.get('sampled_peak_heap_bytes')/1048576,1)+' MiB' if number(t.get('sampled_peak_heap_bytes')) else 'Unavailable'],
        ['Coverage bitmap',fmt(m.get('coverage_bitmap_bytes'),0)+' bytes'],
        ['JVM garbage collection',fmt(m.get('gc_time_ms_delta'),0)+' ms (whole JVM)'],
    ]))
    content.append('<h3>Where worker time went</h3>')
    if run['profile_valid']:
        content.append(bars([(label,t[key],COLORS[j]) for j,(key,label,_) in enumerate(PHASES)]))
        content.append('<h3>Worker workload</h3>')
        content.append(bars([(f'Worker {x["worker"]}',x['wall_s'],'#2563eb') for x in run['workers']], 'elapsed seconds'))
        content.append(table(['Worker','Elapsed','CPU','Scanned','Components owned','Lost claims'],[
            [esc(x.get('worker')),secs(x.get('wall_s')),secs(x.get('cpu_s')),fmt(x.get('scanned'),0),fmt(x.get('claims'),0),fmt(x.get('lost_claims'),0)] for x in run['workers']]))
        if run['profiling_version'] >= 2:
            content.append('<h3>Canonicalization work by phase</h3>')
            content.append(table(['Phase','Canonical calls','Rotation steps','Steps / call','Sampled calls','Mean sampled time / call'],[
                [esc(q['canonical_phase']),fmt(q['canonical_calls'],0),fmt(q['rotation_steps'],0),
                 f'{q["rotation_steps"]/q["canonical_calls"]:.2f}' if q['canonical_calls'] else '0.00',
                 fmt(q['canonical_samples'],0),secs(q['canonical_sample_ns']/q['canonical_samples']/1e9) if q['canonical_samples'] else 'Unavailable']
                for q in run['operations']]))
            op_by_phase={q['canonical_phase']:q for q in run['operations']}
            content.append(bars([(name,op_by_phase[name]['rotation_steps'],COLORS[i]) for i,name in enumerate(
                ['scan_and_overhead','cycle_entry','cycle_key','ownership_claim','tree_and_cycle_exploration'])], 'canonical rotation steps'))
            content.append('<h3>Slowest discovery attempts</h3>')
            content.append(table(['Rank','Candidate','Component key','Cycle length','Claim won','Floyd successor steps','Cycle entry time','Key time'],[
                [fmt(q.get('rank'),0),fmt(q.get('candidate'),0),fmt(q.get('chain_key'),0),fmt(q.get('cycle_length'),0),
                 'Yes' if q.get('won') else 'No',fmt(q.get('entry_successors'),0),secs(q.get('entry_s')),secs(q.get('key_s'))]
                for q in run['discoveries']]))
        content.append('<h3>Cost by cycle length</h3>')
        content.append(bars([(f'Cycle length {c["cycle_length"]}',c['entry_s']+c['key_s']+c['explore_s'],'#8b5cf6') for c in run['cycles']]))
        content.append(table(['Cycle length','Component pairs','Discovery attempts','Find cycle','Identify pair','Explore','Nodes visited','Tree depth'],[
            [fmt(c.get('cycle_length'),0),fmt(c.get('owned'),0),fmt(c.get('attempts'),0),secs(c.get('entry_s')),secs(c.get('key_s')),secs(c.get('explore_s')),fmt(c.get('visited_nodes'),0),fmt(c.get('max_tree_depth_edges'),0)] for c in run['cycles']]))
        content.append('<h3>Slowest individual traversals</h3>')
        content.append(table(['Representative','Cycle length','Nodes visited','Depth','Discovery','Exploration'],[
            [fmt(c.get('representative'),0),fmt(c.get('cycle_length'),0),fmt(c.get('visited_nodes'),0),fmt(c.get('max_tree_depth_edges'),0),secs(c.get('discovery_s')),secs(c.get('explore_s'))] for c in run['slow']]))
    else: content.append(empty('Detailed charts withheld: profiling counters failed validation.'))
    if run['progress']:
        content.append('<h3>Progress snapshots</h3>')
        points=[(p['elapsed_s'],p['scanned'],f"elapsed={p['elapsed_s']} s",'#0d9488') for p in run['progress'] if number(p.get('elapsed_s')) and number(p.get('scanned'))]
        content.append(scatter(points,'Elapsed seconds','Candidates scanned'))
        points=[(p['elapsed_s'],p['heap_used_bytes']/1048576,f"elapsed={p['elapsed_s']} s",'#8b5cf6') for p in run['progress'] if number(p.get('elapsed_s')) and number(p.get('heap_used_bytes'))]
        content.append(scatter(points,'Elapsed seconds','Used heap (MiB)'))
        points=[(p['elapsed_s'],p['active_workers'],f"elapsed={p['elapsed_s']} s",'#d97706') for p in run['progress'] if number(p.get('elapsed_s')) and number(p.get('active_workers'))]
        content.append(scatter(points,'Elapsed seconds','Active workers'))
        last=run['progress'][-1]
        content.append('<h3>Latest worker checkpoints</h3>')
        content.append(table(['Worker','State','Snapshot age','Current candidate','Component key','Cycle length','Tree nodes','Completed components','Floyd successor steps','Key successor steps','CPU time'],[
            [esc(q.get('worker')),esc(q.get('state')),secs(q.get('snapshot_age_s')),
             fmt(q.get('candidate'),0) if number(q.get('candidate')) and q['candidate']>=0 else '—',
             fmt(q.get('chain_key'),0) if number(q.get('chain_key')) and q['chain_key']>=0 else '—',
             fmt(q.get('cycle_length'),0),fmt(q.get('chain_nodes'),0),fmt(q.get('completed_chains'),0),
             fmt(q.get('entry_successors'),0),fmt(q.get('key_successors'),0),secs(q.get('cpu_s'))]
            for q in last.get('workers',[])]))
        content.append(table(['Elapsed','Scan fraction','Candidates scanned','Scan rate / s','Nodes visited','Node rate / s','Completed components','Active workers','Used heap','Sampled peak heap','GC time'],[
            [secs(q.get('elapsed_s')),f'{100*q["scan_fraction"]:.3f}%' if number(q.get('scan_fraction')) else 'Unavailable',
             fmt(q.get('scanned'),0),fmt(q.get('scan_rate_per_s'),0),fmt(q.get('visited_nodes'),0),fmt(q.get('node_rate_per_s'),0),
             fmt(q.get('completed_chains'),0),fmt(q.get('active_workers'),0),fmt(q.get('heap_used_bytes')/1048576,1)+' MiB' if number(q.get('heap_used_bytes')) else 'Unavailable',
             fmt(q.get('sampled_peak_heap_bytes')/1048576,1)+' MiB' if number(q.get('sampled_peak_heap_bytes')) else 'Unavailable',
             fmt(q.get('gc_time_ms_delta'),0)+' ms' if number(q.get('gc_time_ms_delta')) else 'Unavailable']
            for q in run['progress']]))
    content.append('<details><summary>Inspect the original log section</summary><pre>'+esc(run['raw'])+'</pre></details></article>')
    return ''.join(content)

def report(runs,files):
    good=[r for r in runs if r['timing_valid']]
    configs=sorted({r['config'] for r in runs})
    config_id={c:i for i,c in enumerate(configs)}
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
           '<title>Binary necklace log analysis</title><style>'+CSS+'</style><main>',
           '<header><div class="eyebrow">BINARY NECKLACE CALCULATOR</div><h1>Log analysis</h1></header>',
           '<div class="cards">'+''.join(f'<div><strong>{value}</strong><span>{label}</span></div>' for value,label in [(len(files),'log files'),(len(runs),'recorded runs'),(len(good),'usable wall timings'),(sum(r['profile_valid'] for r in runs),'validated detailed profiles')])+'</div>',
           '<section><h2>Run summary</h2>'+table(['Runs','Usable wall timings','Validated detailed profiles','Files'],[[len(runs),len(good),sum(r['profile_valid'] for r in runs),len(files)]])+'</section>']
    parts.append('<section><h2>Aggregate by n</h2><label>Environment <select id="config">'+''.join(f'<option value="{i}">{esc(c)}</option>' for c,i in config_id.items())+'</select></label>')
    for config in configs:
        cid=config_id[config]; selected=[r for r in good if r['config']==config]
        parts.append(f'<div class="configuration" data-config="{cid}"><h3>Wall time by n</h3>')
        points=[(r['n'],r['meta']['chainReps_wall_s'],f'n={r["n"]}; {r["timestamp"]}; {r["source"]} run {r["index"]}', '#d97706' if r['prime'] else '#2563eb') for r in selected]
        parts.append(scatter(points,'n','Component discovery seconds',log_y=True,integer_x=True))
        groups=defaultdict(list)
        for r in selected: groups[r['n']].append(r)
        rows=[]
        for n, group in sorted(groups.items()):
            times=[r['meta']['chainReps_wall_s'] for r in group]
            median=statistics.median(times)
            rows.append([n,len(times),secs(median),secs(min(times)),secs(max(times)),f'{median/(2**n)*1e6:.4f} µs','Yes' if group[0]['prime'] else 'No',len(group[0]['divisors']),sum(r['profile_valid'] for r in group)])
        parts.append(table(['n','Runs','Median','Fastest','Slowest','Median / 2ⁿ','Prime','Divisors','Valid profiles'],rows))
        parts.append('<h3>Maximum cycle length vs wall time</h3>')
        points=[(r['max_cycle'],r['meta']['chainReps_wall_s'],f'n={r["n"]}; {r["timestamp"]}', '#d97706' if r['prime'] else '#2563eb') for r in selected if r['profile_valid']]
        parts.append(scatter(points,'Maximum cycle length (necklaces)','Component discovery seconds',log_y=True))
        parts.append('</div>')
    parts.append('</section><section><h2>Inspect a run</h2><label>Run <select id="runpick">')
    for i,r in enumerate(runs):
        quality='detailed profile available' if r['profile_valid'] else 'profiling incomplete'
        label = f"n={r['n']} · {r['timestamp']} · {r['source']} #{r['index']} · {quality}"
        parts.append(f'<option value="run-{i}">{esc(label)}</option>')
    parts.append('</select></label>')
    parts.extend(run_detail(r,i) for i,r in enumerate(runs))
    parts.extend(['</section>',
    '<footer>Generated '+esc(datetime.now(timezone.utc).isoformat(timespec='seconds'))+'</footer></main>',
    '<script>function selectGroup(){document.querySelectorAll(".configuration").forEach(e=>e.hidden=e.dataset.config!==document.getElementById("config").value)}function selectRun(){document.querySelectorAll(".run").forEach(e=>e.hidden=e.id!==document.getElementById("runpick").value)}document.getElementById("config").addEventListener("change",selectGroup);document.getElementById("runpick").addEventListener("change",selectRun);selectGroup();selectRun();</script></html>'])
    return ''.join(parts)

CSS='''
:root{color-scheme:light;--ink:#17263c;--muted:#546477}*{box-sizing:border-box}body{margin:0;background:#f2f5f9;color:var(--ink);font:15px/1.6 system-ui,-apple-system,sans-serif}main{max-width:1160px;margin:auto;padding:42px 24px}header{margin-bottom:28px}h1{font-size:38px;line-height:1.15;letter-spacing:-1px;margin:12px 0}h2{font-size:24px;margin:0 0 14px}h3{margin-top:30px}.eyebrow{letter-spacing:2px;font-size:12px;font-weight:700;color:#2563eb}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0}.cards>div,section{background:white;border:1px solid #dce4ee;border-radius:12px;padding:22px}.cards strong{display:block;font-size:32px}.cards span,.muted,footer{color:var(--muted)}section{margin:24px 0}.notice,.warning,.empty{border-radius:8px;padding:18px;margin:18px 0}.notice{background:#e8f0fe;border-left:4px solid #2563eb}.warning{background:#fff6df;border-left:4px solid #c48513}.empty{background:#f1f5f9;color:#546477;min-height:90px;display:flex;align-items:center}.tablewrap,.chart{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;border-bottom:1px solid #e2e8f0;padding:10px 12px;vertical-align:top}th{background:#f5f7fa;color:#4a5b70;white-space:nowrap}td{font-variant-numeric:tabular-nums}select{display:block;width:100%;padding:11px;border:1px solid #b9c6d6;border-radius:6px;background:white;color:#17263c;margin:8px 0 20px}svg{width:100%;display:block}svg text{font:13px system-ui;fill:#34455c}svg .axis{fill:#627286;font-size:12px}.prime{color:#d97706}.composite{color:#2563eb}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef2f7;padding:18px;font-size:12px}details{margin-top:24px}summary{cursor:pointer;color:#2563eb}li{margin:8px 0}footer{font-size:12px}[hidden]{display:none!important}@media(max-width:650px){main{padding:22px 12px}.cards{grid-template-columns:repeat(2,1fr)}h1{font-size:30px}section{padding:14px}}@media print{body{background:white}select{display:none}[hidden]{display:block!important}section{break-inside:avoid}.chart{overflow:visible}}
'''

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent,help='Folder containing *.log files (default: beside this script)')
    parser.add_argument('--output',type=Path,help='HTML destination (default: DIRECTORY/analysis.html)')
    parser.add_argument('--strict',action='store_true',help='Write report, then exit 2 if any run has validation warnings')
    args=parser.parse_args(argv)
    files=sorted(args.directory.glob('*.log'))
    if not files: parser.error(f'No *.log files found in {args.directory.resolve()}')
    runs=[]
    try:
        for path in files: runs.extend(parse_file(path))
        if not runs: parser.error('Log files contain no run data.')
        runs.sort(key=lambda r:(r['n'] if r['n'] is not None else -1,r['timestamp'],r['source'],r['index']))
        output=args.output or args.directory/'analysis.html'
        output.parent.mkdir(parents=True,exist_ok=True)
        if output.suffix.lower()=='.log' or output.resolve() in {p.resolve() for p in files}:
            parser.error('Output must not overwrite an input log or use the .log extension.')
        output.write_text(report(runs,files),encoding='utf-8')
    except OSError as exc: parser.error(str(exc))
    for r in runs:
        state='detailed profile valid' if r['profile_valid'] else 'profiling incomplete/invalid'
        print(f'{r["source"]} run {r["index"]}: n={r["n"]}; chainReps={secs(r["meta"].get("chainReps_wall_s"))}; {state}')
        for warning in r['warnings']: print('  ! '+warning)
    print(f'Report: {output.resolve()}')
    return 2 if args.strict and any(r['warnings'] for r in runs) else 0

if __name__=='__main__':
    sys.exit(main())
