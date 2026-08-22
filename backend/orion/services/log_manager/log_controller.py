import logging


class log:
    __instance = None

    @staticmethod
    def g():
        if log.__instance is None:
            log()
        return log.__instance

    def __init__(self):
        if log.__instance is not None:
            raise Exception("This class is a singleton!")
        log.__instance = self
        self.__logger = logging.getLogger("orion_mail")
        if not self.__logger.hasHandlers():
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            self.__logger.addHandler(handler)
        self.__logger.setLevel(logging.INFO)
        self.__logger.propagate = False

    def i(self, message: str) -> None:
        self.__logger.info(message)

    def e(self, message: str) -> None:
        self.__logger.error(message)
