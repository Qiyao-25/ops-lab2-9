from pathlib import Path
from datetime import datetime, timedelta, timezone
from statistics import mean
import csv, json, re, hashlib

BASE = Path(__file__).resolve().parent
if not (BASE/'timing.json').exists():
    BASE = BASE/'ops-lab2-9-sync/runs/task0-fsync-retest-20261103T122130+0800'
TZ=timezone(timedelta(hours=8))
events=json.loads((BASE/'timing.json').read_text(encoding='utf-8'))
runs=[x for x in events if 'group' in x]
def dt(s):return datetime.fromisoformat(s)
def phase(t):
    left=t-timedelta(seconds=1)
    if left>=dt(events[0]['time']) and t<=dt(runs[0]['start']):return 'idle'
    for r in runs:
        if left>=dt(r['start']) and t<=dt(r['end']):return f"group{r['group']}-run{r['repeat']}"
    return None
rows=[]
for r in runs:
    text=(BASE/r['file']).read_text(encoding='utf-8')
    m=re.search(r'mean ([\d.]+)\s+p50 ([\d.]+)\s+p90 ([\d.]+)\s+p99 ([\d.]+)\s+max ([\d.]+)',text)
    assert m and r['returncode']==0
    row={k:r[k] for k in ['group','repeat','start','end','file']}
    row.update(dict(zip(['mean_ms','p50_ms','p90_ms','p99_ms','max_ms'],map(float,m.groups()))))
    row['serial_fsync_per_s']=1000/row['mean_ms'];rows.append(row)
def writecsv(name,items):
    with (BASE/name).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(items[0]),lineterminator='\n');w.writeheader();w.writerows(items)
writecsv('bench-summary.csv',rows)
selected=[];vm=[];io=[]
headers=None;data_index=0
for lineno,line in enumerate((BASE/'vmstat.log').read_text(encoding='utf-8').splitlines(),1):
    a=line.split()
    if a and a[0]=='r':headers=a[:18]
    if len(a)<20 or not a[0].isdigit():continue
    data_index+=1
    if data_index==1:continue
    t=dt(a[-2]+'T'+a[-1]).replace(tzinfo=TZ);p=phase(t)
    if not p:continue
    row=dict(zip(headers,map(float,a[:18])));row.update(phase=p,time=t.isoformat(),line=lineno);vm.append(row)
    selected.append({'tool':'vmstat','file':'vmstat.log','line':lineno,'interval_end':t.isoformat(),'phase':p})
t=None;headers=None;data_index=0
for lineno,line in enumerate((BASE/'iostat.log').read_text(encoding='utf-8').splitlines(),1):
    a=line.split()
    if len(a)==1 and re.match(r'\d{4}-\d\d-\d\dT',a[0]):t=dt(a[0])
    elif a and a[0]=='Device':headers=a[1:]
    elif a and a[0]=='vda':
        data_index+=1
        if data_index==1:continue
        p=phase(t)
        if not p:continue
        row=dict(zip(headers,map(float,a[1:])));row.update(phase=p,time=t.isoformat(),line=lineno);io.append(row)
        selected.append({'tool':'iostat','file':'iostat.log','line':lineno,'interval_end':t.isoformat(),'phase':p})
writecsv('selected-samples.csv',selected)
def ranges(items,keys):
    return {k:{'min':min(x[k] for x in items),'max':max(x[k] for x in items),'mean':mean(x[k] for x in items)} for k in keys}
resources={}
for state in ['idle','active']:
    a=[x for x in vm if (x['phase']=='idle')==(state=='idle')]
    b=[x for x in io if (x['phase']=='idle')==(state=='idle')]
    for x in a:x['us_plus_sy']=x['us']+x['sy']
    resources[state]={'vmstat_samples':len(a),'iostat_samples':len(b),
        'vmstat':ranges(a,['r','b','us_plus_sy','id','wa','st','si','so']),
        'iostat':ranges(b,['w/s','wkB/s','w_await','f/s','f_await','aqu-sz','%util'])}
selected_times={x['time'][11:19] for x in vm if x['phase']!='idle'}
background={}
meta=json.loads((BASE/'environment.json').read_text(encoding='utf-8'))
collector_pid=next(x['command'][-1] for x in meta['environment'] if x['command'][:2]==['taskset','-pc'])
for lineno,line in enumerate((BASE/'pidstat-io.log').read_text(encoding='utf-8').splitlines(),1):
    a=line.split()
    if len(a)!=8 or a[0] not in selected_times or not a[1].isdigit():continue
    # /proc/PID/io includes waited-for children: do not count collector's
    # post-wait child I/O again as unrelated background writes.
    if a[-1]=='enrolld' or a[2]==collector_pid:continue
    value=float(a[4])
    if value:
        name=a[-1];v=background.setdefault(name,{'max_kB_wr_per_s':0,'nonzero_samples':0})
        v['max_kB_wr_per_s']=max(v['max_kB_wr_per_s'],value);v['nonzero_samples']+=1
old=mean([1.274,1.300,1.265]);new=mean(x['mean_ms'] for x in rows)
summary={'note':'Means are calculated from rounded per-run mean outputs, N=2000 each. Percentiles are per run and are not pooled or averaged.',
         'original_mean_ms':old,'new_six_run_mean_ms':new,'new_serial_fsync_per_s':1000/new,
         'mean_increase_percent':(new/old-1)*100,'serial_limit_decrease_percent':(1-old/new)*100,
         'groups':{str(g):{'mean_ms':mean(x['mean_ms'] for x in rows if x['group']==g)} for g in [1,2]},
         'pidstat_note':'Collector PID '+collector_pid+' excluded: /proc/PID/io includes waited-for children. Other process activity is not proof of unrelated I/O contention; jbd2 may serve the benchmark itself.',
         'resources':resources,'background_write_activity_during_selected_active_samples':background}
(BASE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
