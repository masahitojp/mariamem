from pathlib import Path
import subprocess,os,json,re,collections
W=Path(__file__).resolve().parents[1];S=W/'worktree';T=W/'temp';E=W/'evidence';env=dict(os.environ,GOTOOLCHAIN='go1.26.10')
summary={}
for label in ['baseline','direct','shared']:
 out={}
 for fn in ['MemoryEA','Fn18056','Fn5423','Fn18187','Fn13460','Fn15594']:
  text=subprocess.check_output(['go','tool','objdump','-s',r'\.'+fn+'$',str(T/(label+'.test'))],env=env,text=True);(E/(label+'-'+fn+'-asm.txt')).write_text(text)
  out[fn]={'memory_ea_calls':text.count('CALL github.com/masahitojp/mariamem/internal/generatedgo/code/base.MemoryEA(SB)'),'panic_calls':text.count('CALL runtime.gopanic(SB)'),'instruction_lines':len(re.findall(r'^  .*0x[0-9a-f]+',text,re.M))}
 summary[label]=out
(E/'assembly-summary.json').write_text(json.dumps(summary,indent=2))
