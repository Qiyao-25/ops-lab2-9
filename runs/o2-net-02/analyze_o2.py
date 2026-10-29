from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv,json,re,statistics,math,hashlib

BASE=Path(__file__).resolve().parent
RAW=BASE/'raw' if (BASE/'raw').is_dir() else BASE
TZ=timezone(timedelta(hours=8))
rows=list(csv.DictReader((RAW/'steps.csv').open(encoding='utf-8',newline='')))
steps=[r for r in rows if r['step']!='all']
assert len(steps)==9
for row in steps:
    assert int(row['end_unix'])-int(row['start_unix'])==30
    assert sum(int(row[k]) for k in ['ok','http_err','timeout','net_err'])==int(row['sent'])
combined=next(row for row in rows if row['step']=='all')
for key in ['sent','ok','http_err','timeout','net_err','dropped']:
    assert int(combined[key])==sum(int(row[key]) for row in steps)
DAY=datetime.fromtimestamp(int(steps[0]['start_unix']),TZ).date().isoformat()

def epoch(s):return int(datetime.fromisoformat(DAY+'T'+s).replace(tzinfo=TZ).timestamp())
def write_csv(name,data):
    with (BASE/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]),lineterminator='\n');w.writeheader();w.writerows(data)

def parse_sar(name):
    result=[];header=None
    for lineno,line in enumerate((RAW/name).read_text().splitlines(),1):
        tokens=line.split()
        if not tokens or not re.fullmatch(r'\d\d:\d\d:\d\d',tokens[0]):continue
        if len(tokens)>1 and tokens[1] in ['IFACE','atmptf/s']:
            header=tokens[1:];continue
        if header is None or len(tokens)!=len(header)+1:continue
        d=dict(zip(header,tokens[1:]));kind='DEV' if 'IFACE' in d else 'ETCP'
        try:
            for k in d:
                if k!='IFACE':d[k]=float(d[k])
        except ValueError:continue
        result.append({'source_file':name,'source_line':lineno,'epoch':epoch(tokens[0]),'kind':kind,**d})
    return result

def parse_cpu(name):
    result=[];header=None
    for lineno,line in enumerate((RAW/name).read_text().splitlines(),1):
        tokens=line.split()
        if not tokens or not re.fullmatch(r'\d\d:\d\d:\d\d',tokens[0]):continue
        if len(tokens)>1 and tokens[1]=='CPU':header=tokens[1:];continue
        if header is None or len(tokens)!=len(header)+1:continue
        d=dict(zip(header,tokens[1:]))
        try:
            for k in d:
                if k!='CPU':d[k]=float(d[k])
        except ValueError:continue
        d['busy']=sum(d.get(k,0) for k in ['%usr','%nice','%sys','%irq','%soft'])
        result.append({'source_file':name,'source_line':lineno,'epoch':epoch(tokens[0]),**d})
    return result

sar={h:parse_sar('sar-net-'+h+'.log') for h in ['A','B']}
cpu={h:parse_cpu('mpstat-'+h+'.log') for h in ['A','B']}
ss=[];snapshot=None;current=None
def flush_snapshot():
    if snapshot is not None:ss.append(snapshot.copy())
for lineno,line in enumerate((RAW/'ss-A.log').read_text().splitlines(),1):
    if re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d',line):
        flush_snapshot();snapshot={'epoch':int(datetime.fromisoformat(line).timestamp()),'source_line':lineno,'connections':0,'sendq_bytes':0,'max_socket_sendq_bytes':0,'sockets_with_retrans_field':0,'visible_socket_total_retrans_sum':0,'visible_socket_bytes_retrans_sum':0,'max_rtt_ms':0};current=None
        continue
    if snapshot is None:continue
    tokens=line.split()
    if len(tokens)>=4 and tokens[0].isdigit() and tokens[1].isdigit() and ':8080' in tokens[2]:
        current='192.168.0.77' in tokens[3]
        if current:
            snapshot['connections']+=1;sendq=int(tokens[1]);snapshot['sendq_bytes']+=sendq;snapshot['max_socket_sendq_bytes']=max(snapshot['max_socket_sendq_bytes'],sendq)
        continue
    if current and line[:1].isspace():
        m=re.search(r'\bretrans:(\d+)/(\d+)',line)
        if m:snapshot['sockets_with_retrans_field']+=1;snapshot['visible_socket_total_retrans_sum']+=int(m[2])
        m=re.search(r'\bbytes_retrans:(\d+)',line)
        if m:snapshot['visible_socket_bytes_retrans_sum']+=int(m[1])
        m=re.search(r'\brtt:([\d.]+)/',line)
        if m:snapshot['max_rtt_ms']=max(snapshot['max_rtt_ms'],float(m[1]))
        current=None
flush_snapshot()
write_csv('ss-snapshots.csv',ss)

summary=[];samples=[]
def avg(rs,k):return statistics.mean(x[k] for x in rs)
for r in steps:
    start,end=int(r['start_unix']),int(r['end_unix']);lo,hi=start+5,end-5
    out={'step':int(r['step']),'target_rps':int(r['target_rps']),'start_local':datetime.fromtimestamp(start,TZ).isoformat(),'window_start_local':datetime.fromtimestamp(lo,TZ).isoformat(),'window_end_local':datetime.fromtimestamp(hi,TZ).isoformat(),'ok_rps':int(r['ok'])/(end-start),'error_pct':100*(int(r['http_err'])+int(r['timeout'])+int(r['net_err']))/int(r['sent']) if int(r['sent']) else None,'timeouts':int(r['timeout']),'p99_ms':float(r['p99_ms']) if r['p99_ms'] else None,'lag_p99_ms':float(r['lag_p99_ms']) if r['lag_p99_ms'] else None,'gen_cpu_pct':float(r['gen_cpu_pct']),'client_body_goodput_mbps':int(r['ok'])/(end-start)*262144*8/1e6}
    for host in ['A','B']:
        dev=[x for x in sar[host] if x['kind']=='DEV' and x.get('IFACE')=='eth0' and lo<x['epoch']<=hi]
        assert len(dev)==20,(host,r['step'],len(dev))
        for key in ['txkB/s','rxkB/s']:
            out[host+'_'+key.replace('/','_')+'_mean']=avg(dev,key)
        out[host+'_tx_mbps']=avg(dev,'txkB/s')*1024*8/1e6
        out[host+'_rx_mbps']=avg(dev,'rxkB/s')*1024*8/1e6
        allcpu=[x for x in cpu[host] if x['CPU']=='all' and lo<x['epoch']<=hi]
        assert len(allcpu)==20
        out[host+'_cpu_busy_mean_pct']=avg(allcpu,'busy')
        out[host+'_cpu_steal_mean_pct']=avg(allcpu,'%steal')
        out[host+'_cpu_max_core_mean_pct']=max(avg([x for x in cpu[host] if x['CPU']==core and lo<x['epoch']<=hi],'busy') for core in ['0','1'])
        out[host+'_cpu_peak_one_second_pct']=max(x['busy'] for x in cpu[host] if x['CPU']!='all' and lo<x['epoch']<=hi)
        for x in dev:
            samples.append({'step':r['step'],'host':host,'kind':'DEV','source_file':x['source_file'],'source_line':x['source_line'],'epoch':x['epoch'],'key':'txkB/s;rxkB/s','value':str(x['txkB/s'])+';'+str(x['rxkB/s'])})
        for x in allcpu:
            samples.append({'step':r['step'],'host':host,'kind':'CPU','source_file':x['source_file'],'source_line':x['source_line'],'epoch':x['epoch'],'key':'busy_pct;steal_pct','value':str(x['busy'])+';'+str(x['%steal'])})
    etcp=[x for x in sar['A'] if x['kind']=='ETCP' and lo<x['epoch']<=hi]
    assert len(etcp)==20
    out['A_retrans_per_s_mean']=avg(etcp,'retrans/s')
    out['A_resets_per_s_mean']=avg(etcp,'orsts/s')
    for x in etcp:
        samples.append({'step':r['step'],'host':'A','kind':'ETCP','source_file':x['source_file'],'source_line':x['source_line'],'epoch':x['epoch'],'key':'retrans/s','value':str(x['retrans/s'])})
    ssrows=[x for x in ss if lo<=x['epoch']<hi]
    assert len(ssrows)>=8
    out['ss_samples']=len(ssrows)
    out['ss_connections_max']=max(x['connections'] for x in ssrows)
    out['ss_sendq_mean_mib']=avg(ssrows,'sendq_bytes')/(1024*1024)
    out['ss_sendq_max_mib']=max(x['sendq_bytes'] for x in ssrows)/(1024*1024)
    out['ss_max_rtt_ms']=max(x['max_rtt_ms'] for x in ssrows)
    out['ss_visible_total_retrans_max']=max(x['visible_socket_total_retrans_sum'] for x in ssrows)
    summary.append(out)
write_csv('network-summary.csv',summary)
write_csv('sample-index.csv',samples)
(BASE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('rate ok_rps err% p99 A_tx_Mbps B_rx_Mbps A_CPU A_core B_CPU B_core retrans/s SendQ_MiB(max)')
for x in summary:
    print(x['target_rps'],round(x['ok_rps'],2),None if x['error_pct'] is None else round(x['error_pct'],2),x['p99_ms'],round(x['A_tx_mbps'],2),round(x['B_rx_mbps'],2),round(x['A_cpu_busy_mean_pct'],2),round(x['A_cpu_max_core_mean_pct'],2),round(x['B_cpu_busy_mean_pct'],2),round(x['B_cpu_max_core_mean_pct'],2),round(x['A_retrans_per_s_mean'],2),round(x['ss_sendq_max_mib'],2))
