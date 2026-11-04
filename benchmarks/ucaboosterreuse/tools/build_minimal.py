import sys
from pathlib import Path
import subprocess,json,time
w=Path(sys.argv[1]).resolve();t=w/'temp';u=next((t/'upstream').iterdir());cfg=t/'config';cfg.mkdir(exist_ok=True)
flags=['HAVE_STRTOK_R','HAVE_MEMCPY','HAVE_MEMMOVE','HAVE_MEMSET','HAVE_STDLIB_H','HAVE_UNISTD_H','HAVE_STRING_H','HAVE_STRINGS_H','HAVE_STDINT_H','HAVE_INTTYPES_H','HAVE_SYS_TYPES_H','HAVE_SYS_SOCKET_H','HAVE_FCNTL_H','HAVE_LIMITS_H','HAVE_SYS_STAT_H','HAVE_FLOAT_H','HAVE_ALLOCA_H','HAVE_ALLOCA','HAVE_VA_COPY','HAVE_STRTOLL','HAVE_STRTOULL','HAVE_LONG_LONG','HAVE_DLOPEN','HAVE_POSIX_MEMALIGN']
config='#define SOCKET_SIZE_TYPE socklen_t\n#define STACK_DIRECTION -1\n'+'\n'.join('#define '+f+' 1' for f in flags)+'\n#define SIZEOF_CHARP 8\n#define SIZEOF_LONG 8\n#define SIZEOF_LONG_LONG 8\n#define SIZEOF_INT 4\n#define SIZEOF_SIZE_T 8\n#define SIZEOF_OFF_T 8\n#define SIZEOF_TIME_T 8\n#define SIZEOF_VOIDP 8\n#define SIZEOF_SHORT 2\n#define MACHINE_TYPE "arm64"\n#define SYSTEM_TYPE "Darwin"\n'
(cfg/'my_config.h').write_text(config)
(cfg/'mysql_version.h').write_text('#define MYSQL_VERSION_ID 120303\n#define MYSQL_SERVER_VERSION "12.3.3-MariaDB"\n#define PROTOCOL_VERSION 10\n')
cmd=['cc','-O2','-DNDEBUG','-DDISABLE_MYSQL_THREAD_H','-I'+str(cfg),'-I'+str(u/'include'),'-I'+str(u/'strings'),str(u/'strings/uca-dump.c'),'-o',str(t/'uca-dump')]
p=subprocess.run(cmd,text=True,capture_output=True);(w/'evidence/uca-dump-build.log').write_text(p.stdout+p.stderr);(w/'evidence/uca-dump-command.json').write_text(json.dumps(cmd,indent=2)+'\n');print(p.stderr[-7000:]);raise SystemExit(p.returncode)
