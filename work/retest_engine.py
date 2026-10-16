from pathlib import Path
import subprocess,sys,json,time
base=Path('outputs/agent_engine'); result=[]
for name in ['context','fidelity','situation','lifetime','development','temperament','world_growth','interaction','extended','complete']:
 start=time.monotonic()
 run=subprocess.run([sys.executable,str(base/f'check_{name}.py')],capture_output=True,text=True)
 result.append({'suite':name,'exit_code':run.returncode,'seconds':round(time.monotonic()-start,3),'stdout':run.stdout,'stderr':run.stderr})
 print(name,run.returncode,flush=True)
 if run.returncode: print(run.stdout,run.stderr,flush=True)
Path('work/fresh-regression-results.json').write_text(json.dumps(result,indent=2)+'\n')
raise SystemExit(int(any(r['exit_code'] for r in result)))
