from pathlib import Path
import os,signal,subprocess,time
root=Path.cwd();pid=int((root/'work/graphiti-data/service.pid').read_text())
command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
if str(root/'outputs/agent_engine/graphiti_service.py') not in command:raise SystemExit('Refusing to stop a process not belonging to this service')
os.kill(pid,signal.SIGTERM);time.sleep(.5)
subprocess.run(['work/profile-env/bin/python','outputs/agent_engine/graphiti-local/start.py'],check=True)
