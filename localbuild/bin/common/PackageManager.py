# coding=utf-8
import glob
import os
import re

import CommonDefine


def get_sdb_package():
    return get_package("sdb", "sequoiadb-\d+(\.\d+)*-linux_.*-installer\.run", True)


def get_dds_package():
    return get_package("dds", "sequoiadb-dds-*-linux*-installer.run")


def get_mysql_package():
    return get_package("mysql", "sequoiasql-mysql-*-linux*-installer.run")


def get_mariadb_package():
    return get_package("mariadb", "sequoiasql-mariadb-*-linux*-installer.run")


def get_elf_package():
    return get_package("elf", "sequoiasac-elf-*-linux*-enterprise.tar.gz")


def get_sac_package():
    return get_package("sac", "sequoiasac-*-linux*-installer.run")


def get_package(name, pattern, use_regex=False):
    search_path = os.path.join(CommonDefine.PACKAGE_DIR, pattern)
    if use_regex:
        res = glob.glob(os.path.join(CommonDefine.PACKAGE_DIR, "*"))
        res = [filename for filename in res if re.match(".*" + pattern, filename)]
    else:
        res = glob.glob(search_path)
    if len(res) == 0:
        raise Exception("Missing {} package".format(name))
    if len(res) > 1:
        raise Exception("Multiple {} packages found:".format(name, res))
    return res[0]
