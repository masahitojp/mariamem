from pathlib import Path
repo=Path('worktree')
p=repo/'benchmarks/spikes/issue65-native-control/patch.py';s=p.read_text();old='extern void mariamem_spike_dispatch_start(THD*);';new='extern bool mariamem_spike_dispatch_start(THD*, enum enum_server_command);';assert s.count(old)==1;s=s.replace(old,new);old='mariamem_spike_dispatch_start(thd);';assert s.count(old)==1;s=s.replace(old,'if (mariamem_spike_dispatch_start(thd,command)) return DISPATCH_COMMAND_CLOSE_CONNECTION;');p.write_text(s)
p=repo/'benchmarks/spikes/issue65-wasix-link/prepare.py';s=p.read_text();anchor="base=prior.read_text();mark=";assert s.count(anchor)==1
s=s.replace(anchor,"base=prior.read_text()\nbase=base.replace('extern void mariamem_spike_dispatch_start(THD*);','extern bool mariamem_spike_dispatch_start(THD*, enum enum_server_command);').replace('mariamem_spike_dispatch_start(thd);','if (mariamem_spike_dispatch_start(thd,command)) return DISPATCH_COMMAND_CLOSE_CONNECTION;')\nmark=")
p.write_text(s)
print('Aligned historical generators with current dispatch hook; no guest rewrite')
