# -*- coding: utf-8 -*-
"""Extract the PDF outline (bookmarks) -> heading titles and page numbers."""
import re
import sys


def load(path):
    return open(path, "rb").read()


def split_objects(data):
    objs = {}
    marks = [(m.start(), int(m.group(1))) for m in re.finditer(rb"(?m)^(\d+)\s+0\s+obj", data)]
    for i, (pos, num) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(data)
        objs[num] = data[pos:end]
    return objs


def get_int(body, key):
    m = re.search(key.encode() + rb"\s+(\d+)\s+0\s+R", body)
    if m:
        return int(m.group(1))
    m = re.search(key.encode() + rb"\s+(\d+)", body)
    return int(m.group(1)) if m else None


def get_refs(body, key):
    m = re.search(key.encode() + rb"\s*\[(.*?)\]", body, re.S)
    if not m:
        return []
    return [int(x) for x in re.findall(rb"(\d+)\s+0\s+R", m.group(1))]


def decode_title(raw):
    raw = raw.strip()
    if raw.startswith(b"<"):
        hexs = re.sub(rb"[^0-9A-Fa-f]", b"", raw[1:-1])
        try:
            b = bytes.fromhex(hexs.decode())
        except ValueError:
            return raw[:40].decode("latin-1", "replace")
        if b[:2] == b"\xfe\xff":
            return b[2:].decode("utf-16-be", "replace")
        return b.decode("latin-1", "replace")
    if raw.startswith(b"("):
        s = raw[1:-1]
        s = re.sub(rb"\\([nrtbf()\\])", lambda m: {b"n": b"\n", b"r": b"\r", b"t": b"\t"}.get(m.group(1), m.group(1)), s)
        try:
            return s.decode("utf-8")
        except UnicodeDecodeError:
            return s.decode("latin-1", "replace")
    return raw.decode("latin-1", "replace")


def title_of(body):
    m = re.search(rb"/Title\s*(<[0-9A-Fa-f\s]*>|\((?:[^()\\]|\\.)*\))", body, re.S)
    return decode_title(m.group(1)) if m else None


def page_list(objs):
    # 找到 /Type /Pages 且 /Count 最大者作为根
    best, best_count = None, -1
    for num, body in objs.items():
        if re.search(rb"/Type\s*/Pages", body):
            c = get_int(body, "/Count") or 0
            if c > best_count:
                best, best_count = num, c
    if best is None:
        return []
    order = []

    def walk(num, depth=0):
        body = objs.get(num, b"")
        kids = get_refs(body, "/Kids")
        if kids:
            for k in kids:
                walk(k, depth + 1)
        else:
            order.append(num)

    root = objs[best]
    kids = get_refs(root, "/Kids")
    for k in kids:
        walk(k)
    return order


def main(path):
    data = load(path)
    objs = split_objects(data)
    pages = page_list(objs)
    index = {p: i + 1 for i, p in enumerate(pages)}  # 对象号 -> 页码（从 1 开始）
    print("pages:", len(pages), file=sys.stderr)

    # 找 outline 根（通过 Catalog 的 /Outlines 引用）
    roots = [int(m.group(1)) for m in re.finditer(rb"/Outlines\s+(\d+)\s+0\s+R", data)]
    if not roots:
        roots = [n for n, b in objs.items() if re.search(rb"/Type\s*/Outlines", b)]
    items = []
    if roots:
        root_num = roots[0]
        first = get_int(objs[root_num], "/First")

        def walk_item(num, depth):
            while num:
                body = objs.get(num, b"")
                t = title_of(body)
                dest = None
                m = re.search(rb"/Dest\s*\[?\s*(\d+)\s+0\s+R", body)
                if m:
                    dest = int(m.group(1))
                else:
                    m = re.search(rb"/D\s*\[?\s*(\d+)\s+0\s+R", body)
                    if m:
                        dest = int(m.group(1))
                items.append((depth, t, index.get(dest)))
                child = get_int(body, "/First")
                if child:
                    walk_item(child, depth + 1)
                num = get_int(body, "/Next")

        walk_item(first, 1)

    for depth, t, pg in items:
        print(("%s" % ("  " * (depth - 1))) + "%s\t%s" % (pg, t))


if __name__ == "__main__":
    main(sys.argv[1])
