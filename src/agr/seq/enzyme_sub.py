import re

_enzyme_sub_re = re.compile(r"HpaIII?")  # matches HpaII or HpaIII
_enzyme_sub = "MspI"


def enzyme_sub_for_uneak(enzyme: str) -> str:
    """
    map enzymes such as HpaIII and HpaII (methylation sensitive) to equivalent
    (same recognition-site) enzymes that uneak knows about
    """
    return _enzyme_sub_re.sub(_enzyme_sub, enzyme)
