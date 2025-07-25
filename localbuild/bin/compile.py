#!/usr/bin/python
# coding=utf-8
import getopt
import glob
import os
import sys
import shutil
import subprocess

from common.LoggerUtil import get_logger
from common import CommonDefine

log = get_logger()

BUILD_RUN_GIT_URL = "http://gitlab.sequoiadb.com/sequoiadb/build_run.git"
SAC_COMPILE_GIT_URL = "http://gitlab.sequoiadb.com/sequoiadb/sac-compile.git"
SAC_BUILD_SCRIPT_PATH = os.path.join(CommonDefine.SAC_PRO_DIR, "build.sh")
SAC_BUILD_OUTPUT_DIR = os.path.join(CommonDefine.SAC_PRO_DIR, "build")
BUILD_RUN_DIR = os.path.join(SAC_BUILD_OUTPUT_DIR, "build_run")
BUILD_RUN_RELEASE_DIR = os.path.join(BUILD_RUN_DIR, "release")
OUTPUT_DIR = ""


def display_and_exit():
    print("")
    print(" --help | -h                        : print help message")
    print(" --output | -o <output dir path>    : output directory of compile product")
    sys.exit(0)


def parse_command():
    global OUTPUT_DIR
    try:
        options, args = getopt.getopt(sys.argv[1:], "ho:",
                                      ["help", "output="])
    except getopt.GetoptError, e:
        log.error(e, exc_info=True)
        sys.exit(-1)

    for name, value in options:
        if name in ("-h", "--help"):
            display_and_exit()
        elif name in ("-o", "--output"):
            OUTPUT_DIR = value

    if len(OUTPUT_DIR.strip()) == 0 or not os.path.exists(OUTPUT_DIR):
        raise Exception("Missing output directory or directory not exist")


def exec_compile():
    # 1. 执行编译脚本
    cmd = 'bash -c "{} -p"'.format(SAC_BUILD_SCRIPT_PATH)
    subprocess.call(cmd, shell=True)

    # 2. 拉取 run 包编译工具
    if os.path.exists(BUILD_RUN_DIR):
        shutil.rmtree(BUILD_RUN_DIR)
    cmd = 'git clone {} {}'.format(BUILD_RUN_GIT_URL, BUILD_RUN_DIR)
    subprocess.call(cmd, shell=True)

    # 3. 执行 run 包编译
    sac_tar_file_path = glob.glob(os.path.join(SAC_BUILD_OUTPUT_DIR, "sac-*-release.tar.gz"))
    if len(sac_tar_file_path) == 0 or len(sac_tar_file_path) > 1:
        raise Exception("Missing sac release tar file or more than one")
    cmd = 'bash -c "cd {}; ./callbuildpackage.sh -t {} -u {}"'.format(BUILD_RUN_DIR, sac_tar_file_path[0], SAC_COMPILE_GIT_URL)
    subprocess.call(cmd, shell=True)

    # 4. 将编译产物拷贝到指定目录
    cmd = 'cp {}/*.run {}'.format(BUILD_RUN_RELEASE_DIR, OUTPUT_DIR)
    subprocess.call(cmd, shell=True)


if __name__ == '__main__':
    try:
        parse_command()
        exec_compile()
    except Exception as e:
        log.exception("Failed to exec compile.py: {}".format(e))
        raise e
