"""Experiment-only Python owner. Installs no changes into the shipped package."""
import contextvars
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tempfile
import threading

import mariamem
from mariamem.snapshot import Snapshot, _host_identity

B=16384
parent_context=contextvars.ContextVar('d2_parent',default=None)
temporary_context=contextvars.ContextVar('d2_temporary',default=False)

class D2Snapshot(Snapshot):
    def _initialize(self,manifest,layout,options,temporary=None):
        self._manifest=copy.deepcopy(manifest)
        self.layout=copy.deepcopy(layout)
        self._options=options.copy()
        self._temporary=temporary
        self._condition=threading.Condition()
        self._borrowers=0
        self._closed=False
        self._released=False
        self._close_error=None

    @classmethod
    def acquire(cls,root,options,temporary):
        obj=object.__new__(cls)
        obj._files=[]
        try:
            if {p.name for p in root.iterdir()}!={'segments','d2.json'}:
                raise ValueError('D2 candidate inventory')
            envelope=json.loads((root/'d2.json').read_text())
            m,l=envelope['manifest'],envelope['layout']
            _,build=_host_identity(options)
            if m['wasm_sha256']!=build or m['format']!='mariamem-cold-snapshot' or m['version']!=1 or m['source_storage']!='memory':
                raise ValueError('D2 identity mismatch')
            sizes=l['segments'];parents=l['parents'];parent=parent_context.get()
            if type(parents) is not int or not 0<=parents<=len(sizes):
                raise ValueError('D2 parent count')
            if parents:
                if parent is None or sizes[:parents]!=parent.layout['segments']:
                    raise ValueError('D2 missing parent owner')
                with parent._borrow() as files:
                    for name,fd,size in files:
                        obj._files.append((name,os.dup(fd),size))
            elif parent is not None and parent.layout['segments']:
                raise ValueError('D2 lost parent identity')
            directory=root/'segments'
            if {p.name for p in directory.iterdir()}!={str(i) for i in range(parents,len(sizes))}:
                raise ValueError('D2 segment inventory')
            for i in range(parents,len(sizes)):
                p=directory/str(i)
                fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                obj._files.append((str(i),fd,sizes[i]))
                p.unlink()
            shutil.rmtree(root)
            for i,(_,fd,size) in enumerate(obj._files):
                st=os.fstat(fd)
                if type(size) is not int or size<=0 or size>4<<20 or size%B or not stat.S_ISREG(st.st_mode) or st.st_size!=size or st.st_nlink or fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE!=os.O_RDONLY:
                    raise ValueError('D2 backing metadata')
            names=set()
            for name in l['dirs']:
                if name in names or m['entries'].get(name)!={'kind':'directory'}:
                    raise ValueError('D2 directory inventory')
                names.add(name)
            if '.' not in names:
                raise ValueError('D2 root')
            for name,f in l['files'].items():
                entry=m['entries'].get(name)
                if name in names or name in ('','.') or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts or str(PurePosixPath(name))!=name:
                    raise ValueError('D2 file name')
                names.add(name)
                if not entry or entry['kind']!='file' or entry['bytes']!=f['size'] or type(f['size']) is not int or f['size']<0 or len(f['refs'])!=(f['size']+B-1)//B:
                    raise ValueError('D2 file range')
                for r in f['refs']:
                    seg,off,valid=r['seg'],r['off'],r['valid']
                    if any(type(v) is not int for v in (seg,off,valid)):
                        raise ValueError('D2 reference type')
                    if seg==-1 and off==valid==0:
                        continue
                    if seg<0 or seg>=len(sizes) or off<0 or off%B or off>sizes[seg]-B or not 0<=valid<=B:
                        raise ValueError('D2 reference range')
            if names!=set(m['entries']):
                raise ValueError('D2 inventory mismatch')
            for name in names- {'.'}:
                if str(PurePosixPath(name).parent) not in l['dirs']:
                    raise ValueError('D2 missing directory')
            obj._initialize(m,l,options,temporary)
            obj.verify()
            return obj
        except BaseException:
            for _,fd,_ in obj._files:
                os.close(fd)
            temporary.cleanup()
            raise

    def verify(self):
        zero=bytes(B)
        for name,f in self.layout['files'].items():
            h=hashlib.sha256()
            for i,r in enumerate(f['refs']):
                n=min(B,f['size']-i*B)
                valid=min(n,r['valid']) if r['seg']>=0 else 0
                if valid:
                    b=os.pread(self._files[r['seg']][1],valid,r['off'])
                    if len(b)!=valid:raise ValueError('D2 short read')
                    h.update(b)
                h.update(zero[:n-valid])
            if h.hexdigest()!=self._manifest['entries'][name]['sha256']:
                raise ValueError('D2 content mismatch')

    def clone(self):
        obj=object.__new__(type(self));obj._files=[]
        try:
            with self._borrow() as files:
                for name,fd,size in files:obj._files.append((name,os.dup(fd),size))
                obj._initialize(self._manifest,self.layout,self._options)
            return obj
        except BaseException:
            for _,fd,_ in obj._files:os.close(fd)
            raise

    def _spawn(self,argv,**kwargs):
        with self._borrow() as files,tempfile.TemporaryFile() as description:
            data={'manifest':self._manifest,'d2':self.layout,'files':[{'name':name,'fd':fd} for name,fd,_ in files]}
            description.write(json.dumps(data).encode());description.flush();description.seek(0)
            return subprocess.Popen([*argv,'--prepared-fd',str(description.fileno())],pass_fds=(*[fd for _,fd,_ in files],description.fileno()),**kwargs)

    def fork(self,**options):
        hold=self.clone()
        try:
            db=mariamem.Database(**{**self._options,**options,'snapshot':hold})
            db._d2_parent=hold
            return db
        except BaseException:
            hold.close()
            raise

def install():
    if getattr(mariamem.Database,'_d2_installed',False):return
    original_created=Snapshot._created
    original_snapshot=mariamem.Database._snapshot
    original_request=mariamem.Database._request
    original_dispose=mariamem.Database._dispose
    def created(cls,root,options,temporary):
        if (root/'d2.json').exists():
            try:
                return D2Snapshot.acquire(root,options,temporary)
            except Exception as exc:
                raise mariamem.HostError(str(exc),code='snapshot_failed',closed=True) from exc
        return original_created(root,options,temporary)
    def snapshot(self,destination,**kwargs):
        hold=getattr(self,'_d2_parent',None)
        pin=hold.clone() if hold is not None else None
        token=parent_context.set(pin);temp=temporary_context.set(destination is None)
        try:
            return original_snapshot(self,destination,**kwargs)
        finally:
            temporary_context.reset(temp);parent_context.reset(token)
            if pin is not None:pin.close()
    def request(self,operation,*args,**kwargs):
        if operation=='snapshot' and temporary_context.get() and os.environ.get('MARIAMEM_D2')=='1':kwargs['d2']=True
        return original_request(self,operation,*args,**kwargs)
    def dispose(self):
        try:return original_dispose(self)
        finally:
            hold=getattr(self,'_d2_parent',None)
            if hold is not None:self._d2_parent=None;hold.close()
    Snapshot._created=classmethod(created)
    mariamem.Database._snapshot=snapshot
    mariamem.Database._request=request
    mariamem.Database._dispose=dispose
    mariamem.Database._d2_installed=True
