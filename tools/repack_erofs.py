#!/usr/bin/env python3
"""Repack a metadata-preserving local tree with 4.19-compatible EROFS features.

Never pass an NTFS/DrvFS extraction or a device block path. This tool only
writes new regular files and validates the completed filesystem.
"""
import argparse,hashlib,json,os,stat,struct,subprocess
from pathlib import Path

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def inventory(root):
    result=[]
    for path in [root,*sorted(root.rglob('*'))]:
        info=path.lstat()
        attrs={key:os.getxattr(path,key,follow_symlinks=False).hex()
               for key in sorted(os.listxattr(path,follow_symlinks=False))}
        if 'security.selinux' not in attrs:
            raise ValueError('Missing SELinux xattr: '+str(path.relative_to(root)))
        item={'path':str(path.relative_to(root)),'mode':info.st_mode,
              'uid':info.st_uid,'gid':info.st_gid,'xattrs':attrs}
        if stat.S_ISREG(info.st_mode):item['sha256']=digest(path)
        elif stat.S_ISLNK(info.st_mode):item['link']=os.readlink(path)
        elif not stat.S_ISDIR(info.st_mode):raise ValueError('Unexpected special inode: '+str(path))
        result.append(item)
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tree',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--limit',type=int,required=True)
    args=ap.parse_args();root=args.tree.resolve();out=args.output.resolve()
    if os.geteuid()!=0:raise SystemExit('Local host root is required to preserve xattrs/ownership')
    if not root.is_dir() or out.exists() or str(out).startswith('/dev/'):
        raise ValueError('Use an existing local tree and a new regular output file')
    fs=subprocess.check_output(['stat','-f','-c','%T',root],text=True).strip()
    if fs not in ('ext2/ext3','btrfs','xfs'):
        raise ValueError('Metadata-preserving local filesystem required, got '+fs)
    out.parent.mkdir(parents=True,exist_ok=True)
    manifest=inventory(root)
    manifest_file=out.with_suffix('.files.json')
    manifest_file.write_text(json.dumps(manifest,separators=(',',':'))+'\n')
    command=['mkfs.erofs','--quiet','-z','lz4hc,level=9','-C4096',
             '-E','^xattr-name-filter','--workers=4',str(out),str(root)]
    subprocess.run(command,check=True)
    if out.stat().st_size>args.limit:raise ValueError('Output exceeds real device partition capacity')
    with out.open('rb') as f:f.seek(1024);sb=f.read(128)
    magic,compat=struct.unpack_from('<I4xI',sb);incompat=struct.unpack_from('<I',sb,80)[0]
    if magic!=0xe0f5e1e2 or incompat & ~3:
        raise ValueError('EROFS incompatible features for selected 4.19: '+hex(incompat))
    check=subprocess.run(['fsck.erofs','--extract',str(out)],text=True,capture_output=True,check=True)
    # A read-only mount verifies content and every metadata tuple against the
    # input tree; it never mounts or touches a phone partition.
    verify=out.parent/(out.stem+'-readback')
    verify.mkdir(exist_ok=False)
    mounted=False
    try:
        subprocess.run(['mount','-t','erofs','-o','loop,ro',str(out),str(verify)],check=True)
        mounted=True
        actual=inventory(verify)
        if actual!=manifest:raise ValueError('Repacked EROFS content or metadata round-trip differs')
    finally:
        if mounted:subprocess.run(['umount',str(verify)],check=True)
        verify.rmdir()
    report={'schema':1,'image':out.name,'bytes':out.stat().st_size,'sha256':digest(out),
            'partition_capacity':args.limit,'erofs_compat':compat,'erofs_incompat':incompat,
            'all_files_metadata_and_hash_roundtrip':True,'file_count':len(manifest),
            'manifest_sha256':digest(manifest_file),'fsck_passed':True,
            'mkfs_command':command[:command.index(str(out))],
            'fsck_output':check.stdout+check.stderr,'runtime_verified':False}
    out.with_suffix('.report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
