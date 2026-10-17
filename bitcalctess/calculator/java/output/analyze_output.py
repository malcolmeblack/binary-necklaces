#!/usr/bin/env python3
"""Offline graph explorer for Powerset p<n>.csv outputs. Python 3.9+, stdlib only.
Place in output/ and run python3 analyze_output.py. Opens no network connections.
Options: --directory DIR --output FILE --strict. Inputs are never modified.
Graph topology is reconstructed from cycle length and branching sequence.
Legacy input column names are preserved. Reflected component pairs have coverage weight 2.
Full graphs are drawn up to 600 nodes; larger graphs use a cycle schematic.
Trees over 200 nodes are grouped by depth. Component tables are paginated.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

FIELDS = ['bitstrings', 'bitloops', 'factors', 'sym-chains', 'asym-chains', 'graphs']
GRAPH = ['name', 'sym-chains', 'asym-chains', 'bitloops', 'cycle-order', 'tree-depth', 'signature']
CHAIN = ['sample', 'bitstrings', 'bitloops', 'factors', 'cycle-order', 'tree-depth', 'signature']


def levels(signature):
    if not re.fullmatch(r'2[12]*0', signature):
        raise ValueError('Unsupported branching sequence: ' + signature)
    result = [1, 1]
    for digit in signature[1:-1]:
        result.append(result[-1] * int(digit))
    return result


def parse_file(path):
    rows = list(csv.reader(path.read_text(encoding='utf-8-sig').splitlines()))
    rows = [[cell.strip() for cell in row] for row in rows if any(c.strip() for c in row)]
    if not rows:
        raise ValueError('Empty file')
    match = re.fullmatch(r'P\((\d+)\)', rows[0][0])
    if not match:
        raise ValueError('Missing P(n) header')
    n = int(match[1])
    if n < 1 or rows[1] != FIELDS:
        raise ValueError('Invalid n or summary header')
    def record(header, row):
        if len(header) != len(row):
            raise ValueError('Column count mismatch')
        out = dict(zip(header, row))
        for key in header:
            if key not in ('sample', 'signature', 'name'):
                out[key] = int(out[key])
                if out[key] < 0:
                    raise ValueError('Negative ' + key)
        return out
    data = dict(n=n, source=path.name, summary=record(FIELDS, rows[2]), graphs=[], chains=[], warnings=[])
    sections = {'Graphs': GRAPH, 'Symmetric chains': CHAIN, 'Asymmetric chains': CHAIN}
    section = None
    seen = set()
    i = 3
    while i < len(rows):
        row = rows[i]
        if len(row) == 1 and row[0] in sections:
            section = row[0]
            seen.add(section)
            i += 1
            if i >= len(rows) or rows[i] != sections[section]:
                raise ValueError('Invalid header: ' + section)
        elif section:
            item = record(sections[section], row)
            item['levels'] = levels(item['signature'])
            if item['cycle-order'] < 1:
                raise ValueError('Cycle length must be positive')
            if section == 'Graphs':
                data['graphs'].append(item)
            else:
                if not re.fullmatch('[01]{' + str(n) + '}', item['sample']):
                    raise ValueError('Invalid representative')
                item['symmetry'] = 'Symmetric' if section == 'Symmetric chains' else 'Asymmetric'
                item['graph'] = f"G{item['cycle-order']}-{item['signature']}"
                del item['levels']
                data['chains'].append(item)
        else:
            raise ValueError('Unrecognized section')
        i += 1
    def check(condition, message):
        if not condition:
            data['warnings'].append(message)
    check(path.stem == f'p{n}', 'Filename n differs from P(n) header')
    check(seen == set(sections), 'Missing sections')
    s = data['summary']
    check(s['bitstrings'] == 2**n, 'Summary word count != 2^n')
    check(len(data['graphs']) == s['graphs'], 'Graph row count mismatch')
    check(len({g['name'] for g in data['graphs']}) == len(data['graphs']), 'Duplicate graph names')
    check(len({c['sample'] for c in data['chains']}) == len(data['chains']), 'Duplicate representatives')
    for label, key in [('Symmetric', 'sym-chains'), ('Asymmetric', 'asym-chains')]:
        check(sum(c['symmetry'] == label for c in data['chains']) == s[key], key + ' row count mismatch')
    for key in ('bitstrings', 'bitloops', 'factors'):
        actual = sum(c[key] * (1 if c['symmetry'] == 'Symmetric' else 2) for c in data['chains'])
        check(actual == s[key], f'Weighted {key}: {actual} != summary {s[key]}')
    names = {g['name'] for g in data['graphs']}
    check(all(c['graph'] in names for c in data['chains']), 'Component references unknown graph')
    for g in data['graphs']:
        expected = sum(g['levels']) * g['cycle-order']
        check(g['bitloops'] == expected, g['name'] + ': topology node count mismatch')
        check(g['tree-depth'] == len(g['levels']) - 1, g['name'] + ': depth mismatch')
        check(g['name'] == f"G{g['cycle-order']}-{g['signature']}", 'Graph name mismatch')
        for label, key in [('Symmetric', 'sym-chains'), ('Asymmetric', 'asym-chains')]:
            check(sum(c['graph'] == g['name'] and c['symmetry'] == label for c in data['chains']) == g[key], g['name'] + ': ' + key + ' mismatch')
        for c in (c for c in data['chains'] if c['graph'] == g['name']):
            check(c['bitloops'] == g['bitloops'] and c['tree-depth'] == g['tree-depth'], g['name'] + ': component shape mismatch')
    return data


HTML = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Binary necklace output explorer</title>
<style>
:root{font-family:system-ui,sans-serif;color:#16253c;background:#f2f5fa}body{margin:0}main{max-width:1400px;margin:auto;padding:28px}h1{font-size:27px;margin:0}h2{font-size:19px;margin:0 0 16px}h3{font-size:15px}header{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;gap:20px}.muted{color:#64748b;font-size:13px}.card{background:white;border:1px solid #dce3ee;border-radius:12px;padding:20px;margin-bottom:20px}.controls{display:flex;gap:14px;align-items:end;flex-wrap:wrap;margin-bottom:16px}label{font-size:12px;color:#53647b;display:flex;flex-direction:column;gap:5px}select,input,button{font:inherit;padding:8px 10px;border:1px solid #cbd5e1;border-radius:6px;background:white;color:#16253c}button{cursor:pointer}button:disabled{opacity:.4;cursor:default}.metrics{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:20px}.metric{background:#f7f9fc;padding:14px;border-radius:8px}.metric strong{display:block;font-size:21px;margin-top:4px}.split{display:grid;grid-template-columns:1.2fr 1fr;gap:20px}.scroll{overflow:auto;max-height:420px}table{border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap}th,td{text-align:right;padding:9px 12px;border-bottom:1px solid #e8edf4}th{background:#f7f9fc;position:sticky;top:0}th:first-child,td:first-child{text-align:left}tr.selected{background:#eef4ff}td.mono{font-family:ui-monospace,monospace}svg{width:100%;display:block}svg text{font-family:system-ui,sans-serif;fill:#53647b;font-size:12px}.diagram{border:1px solid #e4eaf2;border-radius:8px;background:#fbfcfe;overflow:hidden}.badge{display:inline-block;background:#eef2ff;color:#384f8d;padding:5px 9px;border-radius:5px;font-size:12px;margin:4px 6px 8px 0}.pager{display:flex;align-items:center;gap:12px;margin-top:15px}.warn{color:#a15b00}details summary{cursor:pointer;font-weight:600}#chart{min-height:230px}@media(max-width:850px){.split{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}main{padding:14px}header{align-items:start;flex-direction:column}}
</style>
<main><header><div><h1>Binary necklace output explorer</h1><span class="muted">Power sets · components · graph types</span></div><label>Power set<select id="n"></select></label></header>
<section class="card"><h2>Across n</h2><div class="controls"><label>Metric<select id="metric"><option value="maxCycle">Maximum cycle length</option><option value="graphs">Graph types</option><option value="bitloops">Necklaces</option><option value="chains">Components, including reflected partners</option><option value="maxGraph">Largest graph, necklaces</option></select></label><label>Scale<select id="scale"><option value="log">Log₁₀ (1 + value)</option><option value="linear">Linear</option></select></label></div><div id="chart"></div><details><summary>Comparison table</summary><div class="scroll" id="comparison"></div></details></section>
<section class="card"><h2 id="heading"></h2><div class="metrics" id="summary"></div><div class="controls"><label>Graph type<select id="graph"></select></label><span class="muted">Arrows: necklace → adjacent-XOR image · Node labels: structural indices</span></div><div id="graphMetrics"></div><div class="split"><div><h3>Cycle and attached trees</h3><div id="mode" class="muted"></div><div class="diagram" id="topology"></div></div><div><h3>One cycle root and its incoming tree</h3><div id="treeMode" class="muted"></div><div class="diagram" id="tree"></div></div></div><details style="margin-top:16px"><summary>Depth counts and graph types</summary><div class="split"><div class="scroll" id="depths"></div><div class="scroll" id="types"></div></div></details></section>
<section class="card"><h2>Component representatives</h2><div class="controls"><label>Graph filter<select id="chainGraph"><option value="selected">Selected graph</option><option value="all">All graphs</option></select></label><label>Reflection class<select id="symmetry"><option value="all">All</option><option value="Symmetric">Reflection-invariant</option><option value="Asymmetric">Reflected pair</option></select></label><label>Binary sample contains<input id="search" type="search" placeholder="00101"></label><label>Rows per page<select id="pageSize"><option>25</option><option>50</option><option>100</option></select></label><label>Sort<select id="sort"><option value="sample">Sample ↑</option><option value="cycle-order">Cycle length ↓</option><option value="bitloops">Necklaces ↓</option><option value="bitstrings">Words ↓</option></select></label><button id="download">Export filtered CSV</button></div><div class="muted">Each reflected-pair row represents two components; coverage totals weight these rows ×2. Export retains the original column names and enum values.</div><div class="scroll" id="chains"></div><div class="pager"><button id="prev">Previous</button><span id="page"></span><button id="next">Next</button></div></section>
<section class="card"><details id="diagnosticDetails"><summary id="diagnosticTitle">Input diagnostics</summary><div class="scroll" id="diagnostics"></div></details></section><footer class="muted">Offline report · CSV inputs unchanged · Graph topology reconstructed from cycle length and branching sequence</footer></main>
<script id="data" type="application/json">__DATA__</script>
<script>
'use strict';
const DATA=JSON.parse(document.getElementById('data').textContent), $=id=>document.getElementById(id), fmt=x=>Number(x).toLocaleString('en-US'), NS='http://www.w3.org/2000/svg';
let current, graph, page=0, filtered=[];
const summaryLabel=k=>({'bitstrings':'Words','bitloops':'Necklaces','factors':'Primitive necklaces','sym-chains':'Reflection-invariant components','asym-chains':'Reflected component pairs','graphs':'Graph types'}[k]||k);
const reflectionLabel=value=>value==='Symmetric'?'Reflection-invariant':'Reflected pair';
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}
function table(target,headers,rows){const t=el('table'),head=el('thead'),tr=el('tr');headers.forEach(h=>tr.append(el('th',h)));head.append(tr);t.append(head);const b=el('tbody');rows.forEach(row=>{const r=el('tr');row.forEach((v,i)=>r.append(el('td',v,i===0?'mono':'')));b.append(r)});t.append(b);$(target).replaceChildren(t)}
function options(id,items){$(id).replaceChildren(...items.map(([v,t])=>{const o=el('option',t);o.value=v;return o}))}
function svg(w,h){const s=document.createElementNS(NS,'svg');s.setAttribute('viewBox',`0 0 ${w} ${h}`);s.setAttribute('role','img');return s}
function shape(s,tag,attrs,text){const e=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;s.append(e);return e}
let serial=0;
function arrows(s){const id='arrow'+serial++;const defs=shape(s,'defs',{}),m=shape(defs,'marker',{id,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:5,markerHeight:5,orient:'auto-start-reverse'});shape(m,'path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#8192ac'});return `url(#${id})`}
function edge(s,a,b,marker){const dx=b.x-a.x,dy=b.y-a.y,l=Math.hypot(dx,dy)||1;shape(s,'line',{x1:a.x+dx/l*5,y1:a.y+dy/l*5,x2:b.x-dx/l*7,y2:b.y-dy/l*7,stroke:'#93a4bd','stroke-width':1.2,'marker-end':marker})}
function node(s,p,cycle,label){const c=shape(s,'circle',{cx:p.x,cy:p.y,r:cycle?5:3.5,fill:cycle?'#2563eb':'#9b7cda'});shape(c,'title',{},label||'Tree necklace')}
function treeNodes(g){const nodes=[{depth:0,parent:-1}],byDepth=[[0]];for(let d=1;d<g.levels.length;d++){const ids=[];for(const p of byDepth[d-1]){const count=d===1?1:Number(g.signature[d-1]);for(let k=0;k<count;k++){ids.push(nodes.length);nodes.push({depth:d,parent:p})}}byDepth.push(ids)}return {nodes,byDepth}}
function drawTopology(g){const s=svg(640,460),marker=arrows(s),order=g['cycle-order'],total=g.bitloops,full=total<=600, count=full?order:Math.min(order,12),depth=g.levels.length-1;
 s.setAttribute('aria-label',full?`Complete directed graph with ${total} necklaces`:`Cycle schematic: ${order} roots, identical attached trees`);
 const roots=[];const cx=320,cy=230,R=order===1?0:full?105:140;
 for(let i=0;i<count;i++){const a=-Math.PI/2+2*Math.PI*i/count;roots.push({x:cx+R*Math.cos(a),y:cy+R*Math.sin(a),a})}
 if(order===1){shape(s,'path',{d:'M 318 226 C 270 179 370 179 324 226',fill:'none',stroke:'#2563eb','marker-end':marker})}
 else if(order===2){roots.forEach((r,i)=>{const b=roots[1-i],dx=i?65:-65;shape(s,'path',{d:`M ${r.x+dx/12} ${r.y} Q ${cx+dx} ${cy} ${b.x+dx/12} ${b.y}`,fill:'none',stroke:'#93a4bd','marker-end':marker})})}
 else for(let i=0;i<count;i++){edge(s,roots[i],roots[(i+1)%count],marker);if(order>count&&i===count-1)s.lastChild.setAttribute('stroke-dasharray','5 4')}
 if(full){const t=treeNodes(g);roots.forEach((r,ri)=>{const points=[r];for(let d=1;d<t.byDepth.length;d++){const ids=t.byDepth[d];ids.forEach((idx,k)=>{let p;if(order===1){p={x:70+(k+.5)*500/ids.length,y:cy+d*190/depth}}else{const a=r.a+((k+.5)/ids.length-.5)*2*Math.PI/order*.78,rad=R+d*100/depth;p={x:cx+rad*Math.cos(a),y:cy+rad*Math.sin(a)}}points[idx]=p;edge(s,p,points[t.nodes[idx].parent],marker);node(s,p,false,`Cycle ${ri}, depth ${d}`)})}})}
 roots.forEach((r,i)=>{node(s,r,true,`Cycle position ${i}`);if(count<=16)shape(s,'text',{x:r.x,y:r.y-12,'text-anchor':'middle'},'c'+i);if(!full){const p={x:r.x+Math.cos(r.a)*44,y:r.y+Math.sin(r.a)*44};edge(s,p,r,marker);shape(s,'rect',{x:p.x-16,y:p.y-10,width:32,height:20,rx:4,fill:'#eee8fa',stroke:'#b7a1da'});shape(s,'text',{x:p.x,y:p.y+4,'text-anchor':'middle'},'T')}});
 if(!full&&order>count)shape(s,'text',{x:cx,y:cy,'text-anchor':'middle'},`+ ${fmt(order-count)} cycle roots omitted`);
 $('mode').textContent=full?`Complete topology · ${fmt(total)} nodes`:`Schematic · ${fmt(order)} cycle roots · T = ${fmt(g.levels.reduce((a,b)=>a+b,0)-1)} incoming nodes per root${order>count?' · Dashed edge: omitted cycle segment':''}`;
 $('topology').replaceChildren(s)
}
function drawTree(g){const s=svg(520,460),marker=arrows(s),total=g.levels.reduce((a,b)=>a+b,0),exact=total<=200,depth=g.levels.length-1;
 s.setAttribute('aria-label',exact?'Exact incoming tree':'Incoming tree aggregated by depth');
 if(exact){const t=treeNodes(g),points=[];t.byDepth.forEach((ids,d)=>{ids.forEach((idx,k)=>{const p={x:25+(k+.5)*470/ids.length,y:35+d*385/depth};points[idx]=p;if(d)edge(s,p,points[t.nodes[idx].parent],marker);node(s,p,d===0,`Depth ${d}, node ${k}`)});shape(s,'text',{x:8,y:35+d*385/depth-10},'d'+d)})}
 else {g.levels.forEach((v,d)=>{const y=25+d*410/depth;if(d)edge(s,{x:230,y:y-9},{x:230,y:25+(d-1)*410/depth+9},marker);shape(s,'rect',{x:180,y:y-9,width:100,height:18,rx:4,fill:d?'#eee8fa':'#dbeafe'});shape(s,'text',{x:230,y:y+4,'text-anchor':'middle'},fmt(v)+' nodes');shape(s,'text',{x:300,y:y+4},'depth '+d)})}
 $('treeMode').textContent=exact?`Exact tree · ${fmt(total)} nodes including root`:`Aggregated by depth · ${fmt(total)} nodes including root`;
 $('tree').replaceChildren(s);
 table('depths',['Depth','Nodes / root','Nodes / component','Predecessors / node'],g.levels.map((v,d)=>[d,fmt(v),fmt(v*g['cycle-order']),d===0?'1 tree + 1 cycle':g.signature[d]]))
}
function chooseGraph(){graph=current.graphs[Number($('graph').value)];if(!graph)return;
 $('graphMetrics').replaceChildren(...[['Necklaces / component',graph.bitloops],['Cycle length',graph['cycle-order']],['Tree depth',graph['tree-depth']],['Reflection-invariant',graph['sym-chains']],['Reflected pairs',graph['asym-chains']],['Branching sequence',graph.signature]].map(([k,v])=>el('span',k+': '+(k==='Branching sequence'?v:fmt(v)),'badge')));
 drawTopology(graph);drawTree(graph);page=0;filterChains()
}
function chooseN(){current=DATA.runs[Number($('n').value)];$('heading').textContent=`P(${current.n}) · ${current.source}`;
 $('summary').replaceChildren(...Object.entries(current.summary).map(([k,v])=>{const e=el('div',summaryLabel(k),'metric');e.append(el('strong',fmt(v)));return e}));
 options('graph',current.graphs.map((g,i)=>[i,`${g.name} · ${fmt(g.bitloops)} necklaces / component`]));
 $('graph').value=current.graphs.reduce((best,g,i)=>g.bitloops>current.graphs[best].bitloops?i:best,0);
 table('types',['Graph','Reflection-invariant','Reflected pairs','Necklaces / component','Covered necklaces'],current.graphs.map(g=>[g.name,fmt(g['sym-chains']),fmt(g['asym-chains']),fmt(g.bitloops),fmt(g.bitloops*(g['sym-chains']+2*g['asym-chains']))]));chooseGraph();drawChart()
}
function filterChains(){const query=$('search').value.trim(),sym=$('symmetry').value,sort=$('sort').value;filtered=current.chains.filter(c=>($('chainGraph').value==='all'||c.graph===graph.name)&&(sym==='all'||c.symmetry===sym)&&c.sample.includes(query));filtered.sort((a,b)=>sort==='sample'?a.sample.localeCompare(b.sample):b[sort]-a[sort]||a.sample.localeCompare(b.sample));renderChains()}
function renderChains(){const size=Number($('pageSize').value),pages=Math.max(1,Math.ceil(filtered.length/size));page=Math.min(page,pages-1);const slice=filtered.slice(page*size,(page+1)*size);table('chains',['Sample word','Reflection class','Graph','Words','Necklaces','Primitive necklaces','Cycle length','Tree depth'],slice.map(c=>[c.sample,reflectionLabel(c.symmetry),c.graph,...['bitstrings','bitloops','factors','cycle-order','tree-depth'].map(k=>fmt(c[k]))]));$('page').textContent=`Page ${page+1} / ${pages} · ${fmt(filtered.length)} representatives`;$('prev').disabled=page===0;$('next').disabled=page+1>=pages}
function metric(r,k){if(k==='maxCycle')return Math.max(0,...r.graphs.map(g=>g['cycle-order']));if(k==='maxGraph')return Math.max(0,...r.graphs.map(g=>g.bitloops));if(k==='chains')return r.summary['sym-chains']+2*r.summary['asym-chains'];return r.summary[k]}
function drawChart(){const s=svg(1200,250),key=$('metric').value,log=$('scale').value==='log',transform=x=>log?Math.log10(1+x):x,vals=DATA.runs.map(r=>metric(r,key)),max=Math.max(1,...vals.map(transform)),width=1100/vals.length;
 for(let i=0;i<=4;i++){const y=205-i*45;shape(s,'line',{x1:75,y1:y,x2:1185,y2:y,stroke:'#e2e8f0'});shape(s,'text',{x:68,y:y+4,'text-anchor':'end'},(i*max/4).toLocaleString('en-US',{maximumFractionDigits:1}))}
 DATA.runs.forEach((r,i)=>{const h=transform(vals[i])/max*180,x=80+i*width;const bar=shape(s,'rect',{x,y:205-h,width:Math.max(2,width-6),height:Math.max(1,h),fill:r===current?'#2563eb':'#a5b9e1',rx:2,tabindex:0,role:'button','aria-label':`n=${r.n}: ${vals[i]}`});shape(bar,'title',{},`n=${r.n}: ${fmt(vals[i])}`);const pick=()=>{$('n').value=i;chooseN()};bar.onclick=pick;bar.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick()}};shape(s,'text',{x:x+(width-6)/2,y:225,'text-anchor':'middle'},r.n)});shape(s,'text',{x:20,y:15},log?'log₁₀(1 + value)':'value');shape(s,'text',{x:1190,y:242},'n');$('chart').replaceChildren(s)
}
$('download').onclick=()=>{const keys=['sample','symmetry','graph','bitstrings','bitloops','factors','cycle-order','tree-depth','signature'];const quote=x=>'"'+String(x).replaceAll('"','""')+'"';const csv=[keys,...filtered.map(c=>keys.map(k=>c[k]))].map(row=>row.map(quote).join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),a=el('a');a.href=url;a.download=`p${current.n}-representatives.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
$('n').onchange=chooseN;$('graph').onchange=chooseGraph;['metric','scale'].forEach(id=>$(id).onchange=drawChart);['chainGraph','symmetry','pageSize','sort'].forEach(id=>$(id).onchange=()=>{page=0;filterChains()});$('search').oninput=()=>{page=0;filterChains()};$('prev').onclick=()=>{page--;renderChains()};$('next').onclick=()=>{page++;renderChains()};
options('n',DATA.runs.map((r,i)=>[i,`n = ${r.n}`]));
table('comparison',['n','Words','Necklaces','Graph types','Reflection-invariant','Reflected pairs','Max cycle','Max depth'],DATA.runs.map(r=>[r.n,...['bitstrings','bitloops','graphs','sym-chains','asym-chains'].map(k=>fmt(r.summary[k])),fmt(metric(r,'maxCycle')),Math.max(...r.graphs.map(g=>g['tree-depth']))]));
table('diagnostics',['File','Status','Check'],DATA.diagnostics.map(d=>[d.source,d.status,d.message]));const issues=DATA.diagnostics.filter(d=>d.status!=='OK').length;$('diagnosticTitle').textContent=`Input diagnostics · ${issues} issues · ${DATA.runs.length} power sets`;$('diagnosticDetails').open=issues>0;
if(DATA.runs.length){$('n').value=DATA.runs.length-1;chooseN()}else{document.querySelectorAll('button,input,select').forEach(e=>e.disabled=true);$('heading').textContent='No usable power sets'}
</script></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--strict', action='store_true', help='Write report, then exit 2 if diagnostics contain issues')
    args = parser.parse_args(argv)
    runs, diagnostics = [], []
    paths = sorted(args.directory.glob('p*.csv'), key=lambda p: (len(p.name), p.name))
    paths = [p for p in paths if re.fullmatch(r'p\d+\.csv', p.name)]
    if not paths:
        diagnostics.append(dict(source=str(args.directory), status='ERROR', message='No p<n>.csv files found'))
    seen = set()
    for path in paths:
        try:
            run = parse_file(path)
            if not run['graphs']:
                raise ValueError('No graph rows')
            if run['n'] in seen:
                raise ValueError('Duplicate n')
            seen.add(run['n'])
            runs.append(run)
            for message in run['warnings']:
                diagnostics.append(dict(source=path.name, status='WARNING', message=message))
            if not run['warnings']:
                diagnostics.append(dict(source=path.name, status='OK', message='Counts and topology validated'))
        except (ValueError, IndexError, OSError, UnicodeError, csv.Error) as exc:
            diagnostics.append(dict(source=path.name, status='ERROR', message=str(exc)))
    runs.sort(key=lambda r:r['n'])
    data = json.dumps(dict(runs=runs, diagnostics=diagnostics), separators=(',', ':')).replace('<', '\\u003c')
    output = args.output or args.directory / 'output_analysis.html'
    if output.resolve() in [p.resolve() for p in paths] or output.resolve() == Path(__file__).resolve():
        parser.error('Output would overwrite an input or this script')
    output.write_text(HTML.replace('__DATA__', data), encoding='utf-8')
    issues = sum(d['status'] != 'OK' for d in diagnostics)
    print(f'{output}: {len(runs)} power sets, {sum(len(r["chains"]) for r in runs):,} representatives, {issues} diagnostic issues')
    for d in diagnostics:
        if d['status'] != 'OK':
            print(f'{d["source"]}: {d["status"]}: {d["message"]}', file=sys.stderr)
    return 2 if args.strict and issues else 0

if __name__ == '__main__':
    sys.exit(main())
