import os
import LoggerUtil

log = LoggerUtil.get_logger()


class CmdExecutor:
    def __init__(self, isDryRun):
        self.__isDryRun = isDryRun

    def command(self, cmd):
        self.command(cmd, True)

    def command(self, cmd, strictMode=True):
        log.debug("exec cmd: " + cmd)
        if self.__isDryRun:
            return
        ret = os.system(cmd)
        if ret != 0 and strictMode:
            raise Exception("Failed to exec cmd:" + cmd)
        else:
            return ret
