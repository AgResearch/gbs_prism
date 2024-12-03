import gzip as gzip_module
import os
import shutil


def gzip(path: str, remove=True):
    path_gz = "%s.gz" % path
    with open(path, "rb") as f_in:
        with gzip_module.open(path_gz, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    if remove:
        os.remove(path)
