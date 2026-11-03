from pathlib import Path
from datetime import datetime, timezone, timedelta
import subprocess, time, json, hashlib, os, re

ROOT = Path('/root/lab2')
os.chdir(ROOT)
TZ = timezone(timedelta(hours=8))
def stamp(): return datetime.now(TZ).isoformat()
def run(args):
    p = subprocess.run(args, capture_output=True, text=True)
    return {'command': args, 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert run(['pgrep', '-x', 'enrolld'])['returncode'] == 1, 'An enrolld is running; do not overlap'
assert run(['pgrep', '-x', 'loadgen'])['returncode'] == 1, 'A load generator is running; do not overlap'
name = 'task0-fsync-retest-' + datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')
out = ROOT/'runs'/name
out.mkdir(exist_ok=False)
binary_before = sha('bin/enrolld')
meta = {'started_at':stamp(), 'directory':str(out.relative_to(ROOT)), 'binary_sha256':binary_before,
        'method':'Two groups of three unpinned runs, N=2000 each; 20 s between groups; 10 s idle before, 5 s after. Existing background services kept running. No cache dropping or reboot.',
        'environment': [run(a) for a in [
            ['git','rev-parse','HEAD'], ['git','status','--short'], ['go','version','-m','bin/enrolld'],
            ['uname','-r'], ['findmnt','-T','data'], ['df','-h','data'], ['free','-m'],
            ['uptime'], ['taskset','-pc',str(os.getpid())],
            ['ps','-eo','pid,comm,pcpu,pmem','--sort=-pcpu'],
            ['git','diff','65e328a','HEAD','--','cmd/enrolld/commit.go','cmd/enrolld/main.go']]]}
(out/'environment.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
old = ROOT/'runs/recheck-fsync-20261102-122635-3923864.txt'
if old.exists():
    (out/'prior-retest-20261102.txt').write_bytes(old.read_bytes())
    meta['prior_retest_copy']={'source':str(old.relative_to(ROOT)),'sha256':sha(old),'date_source':'Source filename; exact start/end not recorded in that file.'}
env = dict(os.environ, LC_ALL='C', S_TIME_FORMAT='ISO')
monitors=[]
for filename,args in [
    ('vmstat.log',['vmstat','-w','-t','1']),
    ('iostat.log',['iostat','-dx','-t','1','vda']),
    ('pidstat-io.log',['pidstat','-d','-p','ALL','1'])]:
    f=(out/filename).open('w')
    monitors.append((subprocess.Popen(args,stdout=f,stderr=subprocess.STDOUT,env=env),f))
events=[]
try:
    print('RUN_DIRECTORY='+str(out),flush=True)
    events.append({'event':'idle_start','time':stamp()}); time.sleep(10)
    for group in [1,2]:
        for repeat in [1,2,3]:
            assert run(['pgrep','-x','enrolld'])['returncode']==1, 'Another enrolld appeared'
            assert run(['pgrep','-x','loadgen'])['returncode']==1, 'A load generator appeared'
            item={'group':group,'repeat':repeat,'start':stamp(),'command':['bin/enrolld','-bench-fsync','2000']}
            p=subprocess.run(item['command'],capture_output=True,text=True)
            item.update(end=stamp(),returncode=p.returncode)
            filename=f'group{group}-run{repeat}.txt'
            (out/filename).write_text(p.stdout)
            (out/(filename+'.stderr')).write_text(p.stderr)
            item['file']=filename; events.append(item)
            (out/'timing.json').write_text(json.dumps(events,ensure_ascii=False,indent=2)+'\n')
            assert p.returncode==0,p.stderr
            print(json.dumps(item,ensure_ascii=False)+'\n'+p.stdout,flush=True)
        if group==1:
            events.append({'event':'between_groups_idle_start','time':stamp()}); time.sleep(20)
    events.append({'event':'tail_idle_start','time':stamp()}); time.sleep(5)
finally:
    for p,f in monitors:
        p.terminate()
        try:p.wait(timeout=3)
        except subprocess.TimeoutExpired:p.kill();p.wait()
        f.close()
    meta.update(finished_at=stamp(),binary_sha256_after=sha('bin/enrolld'),environment_after=[run(['df','-h','data']),run(['uptime'])])
    (out/'environment.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    (out/'timing.json').write_text(json.dumps(events,ensure_ascii=False,indent=2)+'\n')
assert binary_before==meta['binary_sha256_after'], 'Binary changed during measurement'
print('COMPLETE='+name,flush=True)
