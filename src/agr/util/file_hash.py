import hashlib


def file_legible_hash(path: str) -> str:
    """Return hash of file, not for security related use."""
    m = hashlib.md5(usedforsecurity=False)
    with open(path, "rb") as f:
        m.update(f.read())
    return m.hexdigest()


def write_file_legible_hash(in_path: str, out_path: str):
    h = file_legible_hash(in_path)
    with open(out_path, "w") as out_f:
        _ = out_f.write("%s\n" % h)
