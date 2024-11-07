class GbsPrismException(Exception):
    def __init__(self, args=None):
        super().__init__(args)


class GbsPrismUsageException(GbsPrismException):
    def __init__(self, args=None):
        super().__init__(args)


class GbsPrismDataException(GbsPrismException):
    def __init__(self, args=None):
        super().__init__(args)
