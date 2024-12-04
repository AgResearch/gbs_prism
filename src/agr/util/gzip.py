import gzip as gzip_module
import os
import shutil


def gzip(path: str, remove=True) -> str:
    path_gz = "%s.gz" % path
    with open(path, "rb") as f_in:
        with gzip_module.open(path_gz, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    if remove:
        os.remove(path)
    return path_gz


def gunzip(path_gz: str) -> str:
    path = path_gz.removesuffix(".gz")
    with gzip_module.open(path_gz, "rb") as f_in:
        with open(path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    return path
