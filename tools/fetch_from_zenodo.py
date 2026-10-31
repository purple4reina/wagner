"""Extract selected members of the remote Wagner Ring Dataset zip via HTTP range requests.

Only the requested members are downloaded (zipfile checks each member's CRC), so the
10.6 GB archive never has to sit on disk next to its extracted contents.

usage: fetch_from_zenodo.py [--dest DIR] [--skip PREFIX]... [--only SUBSTRING]...

  --dest DIR        dataset root to extract into (default: ../data, next to this script)
  --skip PREFIX     leave out members whose path starts with PREFIX
  --only SUBSTRING  keep only members whose path contains SUBSTRING
"""
import io, pathlib, sys, urllib.request, zipfile

URL = "https://zenodo.org/api/records/7672157/files/WagnerRing_Public_zenodo_v0-1.zip/content"
BLOCK = 8 << 20

dest = pathlib.Path(__file__).resolve().parent.parent / "data"
rest = sys.argv[1:]
skip, only = [], []
while rest:
    flag, val, *rest = rest
    if flag == "--dest": dest = pathlib.Path(val)
    else: (skip if flag == "--skip" else only).append(val)

size = int(urllib.request.urlopen(urllib.request.Request(URL, method="HEAD")).headers["Content-Length"])


class RangeFile(io.RawIOBase):
    def __init__(self):
        self.pos, self.buf, self.buf_start = 0, b"", 0

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: size + off}[whence]
        return self.pos

    def read(self, n=-1):
        if n < 0 or self.pos + n > size: n = size - self.pos
        if n <= 0: return b""
        end = self.pos + n
        if not (self.buf_start <= self.pos and end <= self.buf_start + len(self.buf)):
            stop = min(size, max(end, self.pos + BLOCK))
            resp = urllib.request.urlopen(urllib.request.Request(URL, headers={"Range": f"bytes={self.pos}-{stop-1}"}))
            assert resp.status == 206, f"no range support: {resp.status}"
            self.buf, self.buf_start = resp.read(), self.pos
        off = self.pos - self.buf_start
        self.pos = end
        return self.buf[off:off + n]


zf = zipfile.ZipFile(RangeFile())
todo = [i for i in zf.infolist() if not i.is_dir()
        and not any(i.filename.startswith(p) for p in skip)
        and (not only or any(s in i.filename for s in only))]
total = sum(i.file_size for i in todo)
print(f"extracting {len(todo)} files, {total/1e6:.0f} MB -> {dest}", flush=True)
for n, i in enumerate(todo, 1):
    zf.extract(i, dest)
    print(f"  {n}/{len(todo)} {i.filename}", flush=True)
print("done")
