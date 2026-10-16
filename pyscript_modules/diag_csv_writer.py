import os

def append_csv(p, h, ln, nf):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        if nf:
            f.write(h + "\n")
        f.write(ln + "\n")
