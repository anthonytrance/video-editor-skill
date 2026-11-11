"""Clean up a project folder so finished work doesn't fill the disk. Dry run unless --confirm.

  cleanup.py PROJECT                         old renders: everything in out/ except the newest
  cleanup.py PROJECT --keep v2.mp4           ... except the named render(s) instead
  cleanup.py PROJECT --close                 pack the keepers, list what has to be stored first
  cleanup.py PROJECT --close --stored listing.json --confirm
                                             delete everything proven to be stored, remove the folder
  cleanup.py --list ROOT                     every project under ROOT with its size and age
  cleanup.py --hash FILE                     the content hash of one file

A project is closed when its video is published or abandoned. Closing keeps nothing on this computer:

  small keepers (plans, brief, notes, footage logs, reviews, the delivery report) are packed into
  NAME-project.zip, which you upload to the project's permanent storage;
  big files (src/, audio/, brand/, the kept render) are deleted only when a listing of that storage contains
  a file with the same content hash, so a byte-identical copy is proven to exist;
  proxy/, review pictures and superseded renders can be made again and are deleted without a copy.

A listing is any JSON that contains objects with a "content_hash" (the Dropbox content hash: SHA-256 of the
SHA-256 of each 4 MB block). Pass --stored once per listing. A file whose hash is in no listing stays on disk
and is named in the output; nothing is ever deleted on a name or a size alone.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

BLOCK = 4 * 1024 * 1024
BIG = ('src', 'audio', 'brand', 'out')       # needs a proven copy before it goes
REMAKE = ('proxy',)                          # can be made again
PICTURES = {'.jpg', '.jpeg', '.png', '.webp'}
VIDEO = {'.mp4', '.mov', '.mkv', '.webm'}
KNOWN = set(BIG + REMAKE + ('log', 'review'))
MARKERS = ('edit.json', 'brief.txt')


_hashes = {}


def content_hash(path):
    st = os.stat(path)
    key = (str(path), st.st_size, st.st_mtime_ns)
    if key not in _hashes:
        whole = hashlib.sha256()
        with open(path, 'rb') as f:
            while block := f.read(BLOCK):
                whole.update(hashlib.sha256(block).digest())
        _hashes[key] = whole.hexdigest()
    return _hashes[key]


def hashes_in(node, found):
    if isinstance(node, dict):
        if isinstance(node.get('content_hash'), str):
            found.add(node['content_hash'].lower())
        for v in node.values():
            hashes_in(v, found)
    elif isinstance(node, list):
        for v in node:
            hashes_in(v, found)
    return found


def files(folder):
    """Every file under folder. Links and junctions are not followed, so nothing outside the project is touched."""
    out = []
    for root, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not is_link(Path(root) / d))
        out += [Path(root) / n for n in sorted(names)]
    return out


def is_link(p):
    if p.is_symlink():
        return True
    try:  # Windows junctions and other reparse points
        return bool(getattr(os.lstat(p), 'st_file_attributes', 0) & 0x400)
    except OSError:
        return False


def mb(n):
    return f'{n / 1e6:.1f} MB'


def size(paths):
    return sum(p.stat().st_size for p in paths)


def check_project(project):
    if not project.is_dir():
        sys.exit(f'Not a folder: {project}')
    if not any((project / m).exists() for m in MARKERS) and not any((project / d).is_dir() for d in ('src', 'out')):
        sys.exit(f'{project} does not look like a video project (no edit.json, brief.txt, src/ or out/). Nothing done.')


def renders(project):
    out = project / 'out'
    if not out.is_dir():
        return []
    return sorted((p for p in out.iterdir() if p.is_file() and p.suffix.lower() in VIDEO),
                  key=lambda p: (p.stat().st_mtime, p.name))


def split_renders(project, keep):
    """(kept, superseded). Kept: the named renders, or the newest one."""
    all_ = renders(project)
    if keep:
        missing = [k for k in keep if not any(p.name == k for p in all_)]
        if missing:
            sys.exit(f"--keep names a render that is not in out/: {', '.join(missing)}")
        kept = [p for p in all_ if p.name in keep]
    else:
        kept = all_[-1:]
    return kept, [p for p in all_ if p not in kept]


def write_report(project, kept):
    """The delivery report belongs with the keepers; make it if it is missing and can still be made."""
    target = project / 'report.txt'
    plan = project / 'edit.json'
    if target.exists() or not plan.exists() or len(kept) != 1:
        return
    try:
        import report
        from common import load
        target.write_text(report.build(load(str(plan)), str(kept[0])) + '\n', encoding='utf-8')
    except (Exception, SystemExit) as e:   # a report is a nicety here; never block a cleanup on it
        print(f'Note: no delivery report could be written ({str(e)[:120]}).')


def pack(project, big):
    """Small keepers in one zip with fixed dates and order, so the same content always gives the same hash."""
    target = project / f'{project.name}-project.zip'
    keepers = []
    for p in files(project):
        rel = p.relative_to(project)
        top = rel.parts[0]
        if p == target or p in big or top in REMAKE or top in BIG:
            continue
        if top == 'review' and p.suffix.lower() in PICTURES:
            continue
        keepers.append(p)
    lines = [f'{content_hash(p)}  {p.stat().st_size:>12}  {p.relative_to(project).as_posix()}' for p in big]
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in keepers:
            info = zipfile.ZipInfo(p.relative_to(project).as_posix(), date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, p.read_bytes())
        info = zipfile.ZipInfo('big-files.txt', date_time=(2020, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, 'Big files this project used: content hash, bytes, path. They are not in this zip.\n'
                   + '\n'.join(lines) + '\n')
    return target, keepers


def remove(paths, project):
    freed = 0
    for p in paths:
        if project not in p.parents:
            sys.exit(f'Refusing to delete outside the project: {p}')
        n = p.stat().st_size
        os.remove(p)
        freed += n
    return freed


def prune(project):
    """Remove folders that are now empty, the project folder included."""
    for root, dirs, names in os.walk(project, topdown=False):
        r = Path(root)
        if not is_link(r) and not any(r.iterdir()):
            r.rmdir()


def tidy(project, keep, confirm):
    kept, old = split_renders(project, keep)
    if not old:
        print(f"Nothing to tidy: out/ holds {len(kept)} render(s) and none is superseded.")
        return 0
    print(f"{'Deleting' if confirm else 'Would delete'} {len(old)} superseded render(s), {mb(size(old))}:")
    for p in old:
        print(f'  {p.name}  {mb(p.stat().st_size)}')
    print('Keeping: ' + (', '.join(p.name for p in kept) or 'nothing'))
    if confirm:
        print(f'Freed {mb(remove(old, project))}.')
    else:
        print('Dry run. Add --confirm to delete.')
    return 0


def close(project, keep, stored_files, confirm):
    kept, old = split_renders(project, keep)
    write_report(project, kept)
    everything = files(project)
    big = [p for p in everything
           if p.relative_to(project).parts[0] in BIG and p not in old]
    zip_path, keepers = pack(project, big)
    stored = set()
    for f in stored_files:
        try:
            hashes_in(json.loads(Path(f).read_text(encoding='utf-8-sig')), stored)
        except (OSError, ValueError) as e:
            sys.exit(f'Cannot read listing {f}: {e}')
    need = big + [zip_path]
    proven = [p for p in need if content_hash(p) in stored]
    missing = [p for p in need if p not in proven]
    again = [p for p in files(project) if p not in need and p not in keepers and p not in old]
    # the keepers themselves only go once the zip that holds them is proven
    zip_ok = zip_path in proven
    doomed = proven + old + again + (keepers if zip_ok else [])

    print(f'Project {project.name}: {len(files(project))} files, {mb(size(files(project)))}.')
    print(f'Keepers packed into {zip_path.name} ({len(keepers)} small files, {mb(zip_path.stat().st_size)}).')
    print(f'Proven stored, safe to delete: {len(proven)} file(s), {mb(size(proven))}.')
    for p in proven:
        print(f'  {p.relative_to(project).as_posix()}')
    print(f'Can be made again, deleted without a copy: {len(old)} superseded render(s) and {len(again)} proxy or '
          f'review file(s), {mb(size(old + again))}.')
    if missing:
        print(f'NOT proven stored, these stay on disk ({mb(size(missing))}). Upload them, or find where they already '
              'live, and pass a listing of that place with --stored:')
        for p in missing:
            print(f'  {p.relative_to(project).as_posix()}  {mb(p.stat().st_size)}  {content_hash(p)}')
    if not confirm:
        print('Dry run. Nothing was deleted. Add --confirm to delete what is listed as safe.')
        return 1 if missing else 0
    freed = remove(doomed, project)
    prune(project)
    left = files(project) if project.exists() else []
    print(f'Freed {mb(freed)}.')
    if left:
        print(f'{len(left)} file(s) remain in {project}, {mb(size(left))}. The project is not closed yet.')
        return 1
    print(f'Project folder removed: {project}')
    return 0


def list_projects(root):
    root = Path(root)
    if not root.is_dir():
        sys.exit(f'Not a folder: {root}')
    rows = []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and not is_link(p)):
        if not any((d / m).exists() for m in MARKERS) and not (d / 'out').is_dir():
            continue
        fs = files(d)
        newest = max((p.stat().st_mtime for p in fs), default=d.stat().st_mtime)
        rows.append((d.name, size(fs), (time.time() - newest) / 86400, len(renders(d))))
    if not rows:
        print(f'No video projects under {root}.')
    for name, n, days, r in rows:
        print(f'{name}: {mb(n)}, {r} render(s), last touched {days:.0f} day(s) ago.')
    if rows:
        print(f'Total {mb(sum(r[1] for r in rows))} in {len(rows)} project(s). Close the ones that are published.')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('project', nargs='?')
    ap.add_argument('--keep', action='append', default=[], metavar='RENDER',
                    help='render in out/ to keep (default: the newest); repeatable')
    ap.add_argument('--close', action='store_true', help='the project is finished: keep nothing here')
    ap.add_argument('--stored', action='append', default=[], metavar='LISTING.json',
                    help='listing of permanent storage with content hashes; repeatable')
    ap.add_argument('--confirm', action='store_true', help='really delete')
    ap.add_argument('--list', metavar='ROOT', help='list the projects under ROOT')
    ap.add_argument('--hash', metavar='FILE', help='print the content hash of FILE')
    a = ap.parse_args()
    if a.hash:
        print(content_hash(a.hash))
        return 0
    if a.list:
        list_projects(a.list)
        return 0
    if not a.project:
        ap.error('name a project folder, or use --list ROOT')
    project = Path(a.project).resolve()
    check_project(project)
    return close(project, a.keep, a.stored, a.confirm) if a.close else tidy(project, a.keep, a.confirm)


if __name__ == '__main__':
    sys.exit(main())
