def gunzipped(path: str) -> str:
    return path.removesuffix(".gz")


def gzipped(path: str) -> str:
    return "%s.gz" % path
