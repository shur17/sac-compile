#!/usr/bin/python
# coding=utf-8
import getopt
import os
import platform
import shutil
import sys
from datetime import datetime

import yaml

from localbuild.bin.common import CommonDefine, Utils, PackageManager
from localbuild.bin.common.CmdExecutor import CmdExecutor
from localbuild.bin.common.LoggerUtil import get_logger

log = get_logger()
cmd_executor = CmdExecutor(False)

HOST_LIST = []
IS_CHECK_HOST = False
IS_COMPILE = False
IS_INSTALL = False
IS_INSTALL_BASE = False
IS_RUNTEST = False
TESTCASES = None
IS_RUNBASE = False
IS_SPECIFY_BRANCH = False
BRANCH = None
IS_CLEAN = False
IS_FORCE = False
IS_FORCE_UPDATE_TESTCASE = False


def display_and_exit():
    print("")
    print(" --help | -h                    : print help message")
    print(" --host          <arg>          : hostname, use ',' to split multiple hosts")
    print(" --host-check                   : check host environment")
    print(" --compile                      : compile sac")
    print(" --install      [base]          : install sac and requirements")
    print(" --runtest      [tests]         : execute test cases")
    print(" --runbase                      : execute base test cases, can't be used with --runtest")
    print(" --branch | -b                  : specify the branch of the test repository to pull")
    print(" --clean                        : clean sac and requirements")
    print(" --force                        : force to install sac and requirements")
    print(" --force-update-testcase        : force to update testcase project")
    sys.exit(0)


def parse_command():
    global HOST_LIST, IS_CHECK_HOST, IS_COMPILE, IS_RUNTEST, IS_RUNBASE, TESTCASES, IS_SPECIFY_BRANCH, BRANCH, IS_INSTALL, IS_INSTALL_BASE,\
        IS_CLEAN, IS_FORCE, IS_FORCE_UPDATE_TESTCASE
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg == '--runtest':
            if i + 1 >= len(argv) or argv[i + 1].startswith('-'):
                argv.insert(i + 1, 'all')
        if arg == '--install':
            if i + 1 >= len(argv) or argv[i + 1].startswith('-'):
                argv.insert(i + 1, 'full')
    try:
        options, args = getopt.getopt(argv, "h",
                                      ["help", "host=", "host-check", "compile", "install=", "runtest=", "runbase", "branch=", "b=", "clean", "force",
                                       "force-update-testcase"])
    except getopt.GetoptError, e:
        log.error(e, exc_info=True)
        sys.exit(-1)

    for name, value in options:
        if name in ("-h", "--help"):
            display_and_exit()
        elif name in "--host":
            HOST_LIST = value.split(',')
        elif name in "--host-check":
            IS_CHECK_HOST = True
        elif name in "--compile":
            IS_COMPILE = True
        elif name in "--install":
            IS_INSTALL = True
            IS_INSTALL_BASE = value == "base"
        elif name in "--runtest":
            IS_RUNTEST = True
            TESTCASES = value
        elif name in "--runbase":
            IS_RUNBASE = True
        elif name in ("-b", "--branch"):
            IS_SPECIFY_BRANCH = True
            BRANCH = value
        elif name in "--clean":
            IS_CLEAN = True
        elif name in "--force":
            IS_FORCE = True
        elif name in "--force-update-testcase":
            IS_FORCE_UPDATE_TESTCASE = True

    if len(HOST_LIST) == 0 and (IS_CHECK_HOST or IS_INSTALL or IS_CLEAN):
        raise Exception("Missing host list!")

    required_commands = {
        '--host-check': IS_CHECK_HOST,
        '--compile': IS_COMPILE,
        '--install': IS_INSTALL,
        '--runtest': IS_RUNTEST,
        '--runbase': IS_RUNBASE,
        '--clean': IS_CLEAN
    }
    if not any(required_commands.values()):
        raise Exception("Missing command, please use one of: {}".format(', '.join(required_commands.keys())))

    if IS_RUNBASE and IS_RUNTEST:
        raise Exception("--runbase can't be used with --runtest!")

    if IS_SPECIFY_BRANCH and (BRANCH is None or BRANCH.strip() == ""):
        raise Exception("--branch | -b parameter value can't be empty")


class ExecItem():
    def __init__(self, desc, script, cost=0):
        self.desc = desc
        self.script = script
        self.cost = cost


def get_config_file(check=True):
    host_num = len(HOST_LIST)
    template_dir_path = os.path.join(CommonDefine.WORK_DIR, "conf", "base" if IS_INSTALL_BASE else "")
    file_path = os.path.join(template_dir_path, "localbuild_{}host.yml".format(host_num))
    if check and not os.path.exists(file_path):
        raise Exception("Missing config file: {}".format(file_path))
    return file_path


def exec_check_host():
    log.info("Begin to check and configurate host environment...")
    start_time = datetime.now()
    cmd = "python {} --config {} --host {}".format(
        os.path.join(CommonDefine.BIN_DIR, "check_host.py"),
        os.path.join(CommonDefine.CONF_DIR, "ssh_info.yml"),
        ",".join(HOST_LIST))
    cmd_executor.command(cmd)
    log.info("Check host environment successfully!")
    cost_time = datetime.now() - start_time
    return ExecItem("Check host", "", cost_time.seconds)


def exec_compile():
    log.info("Begin to compile...")
    start_time = datetime.now()
    # 清理掉旧版本/旧 SAC 的 run 包
    cmd_executor.command("rm -f {}/{}".format(CommonDefine.PACKAGE_DIR, "sequoiasac-[0-9].*-enterprise-installer.run"))
    # 执行编译子脚本
    cmd_executor.command(
        "python {} --output {}".format(os.path.join(CommonDefine.BIN_DIR, "compile.py"), CommonDefine.PACKAGE_DIR))
    log.info("Compile successfully!")
    cost_time = datetime.now() - start_time
    return ExecItem("Compile", "", cost_time.seconds)


def exec_clean():
    log.info("Begin to clean...")
    config_file = get_config_file()
    start_time = datetime.now()
    for script in (
            "install_sac.py", "install_mysql.py", "install_mariadb.py", "install_sdb.py", "install_dds.py",
            "install_elf.py"):
        cmd_executor.command(
            "python {} --clean --config {}".format(os.path.join(CommonDefine.BIN_DIR, script), config_file))
    log.info("Clean successfully!")
    cost_time = datetime.now() - start_time
    return ExecItem("Clean", "", cost_time.seconds)


def exec_install():
    log.info("Begin to install...")
    items = get_install_items()
    for item in items:
        log.info("Exec: {}".format(item.script))
        start_time = datetime.now()
        cmd_executor.command(item.script)
        cost_time = datetime.now() - start_time
        item.cost = cost_time.seconds
    log.info("Install successfully!")
    return items


def load_config():
    with open(get_config_file()) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def exist_section(config_data, section):
    section_info = get_section(config_data, section)
    if len(section_info) == 0:
        return False
    return True


def get_section(config_data, section):
    section_info = config_data
    sections = section.split(".")
    for section in sections:
        section_info = section_info.get(section, {})
    return section_info


def exist_sub_section(config_data, parent_section, sub_section):
    parent = get_section(config_data, parent_section)
    if len(parent) == 0:
        return False
    sub_sections = sub_section.split(".")
    for item in parent:
        current = item
        if len(current) == 0:
            continue
        for name in sub_sections:
            current = current.get(name, None) if current is not None else {}
        if len(current) > 0:
            return True
    return False


def get_skip_install_dds_host():
    # 业务数据库和 sac 数据库可能都会安装 dds，如果某台机器上已经安装了 sac 数据的 dds，业务数据库就不需要安装了，直接部署即可
    sac_db_section = Utils.get_section(load_config(), CommonDefine.SECTION_SAC_DB)
    replica_dds = sac_db_section.get("replicaMode", None)
    shard_dds = sac_db_section.get("shardMode", None)
    hosts = Utils.get_dds_install_hosts(replica_dds, shard_dds)
    return ",".join(hosts)


def get_install_items():
    items = []
    config_file = get_config_file()
    config_data = load_config()

    bin_dir = CommonDefine.BIN_DIR
    force_str = "--force" if IS_FORCE else ""
    # 1.安装 sac 数据库 dds
    cmd = "python {} --package {} --config {} --section {} -o {} {}".format(
        os.path.join(bin_dir, "install_dds.py"),
        PackageManager.get_dds_package(), config_file,
        CommonDefine.SECTION_SAC_DB,
        CommonDefine.DSINFO_SAC_DB, force_str)
    items.append(ExecItem("Install sac database(dds)", cmd))

    # 2.安装业务数据库 sdb
    if exist_section(config_data, CommonDefine.SECTION_BUSINESS_DB_SDB):
        cmd = "python {} --package {} --config {} --section {} -o {} {} --enable-slow-query " \
              "--disable-recycle-bin".format(
            os.path.join(bin_dir, "install_sdb.py"),
            PackageManager.get_sdb_package(), config_file,
            CommonDefine.SECTION_BUSINESS_DB_SDB,
            CommonDefine.DSINFO_BUSINESS_DB_SDB,
            force_str)
        items.append(ExecItem("Install business database-sdb", cmd))

    # 3.安装业务数据库 mysql
    if exist_sub_section(config_data, CommonDefine.SECTION_BUSINESS_DB_SDB, CommonDefine.SUB_SECTION_MYSQL):
        cmd = "python {} --package {} --config {} --section {} -o {} {}  --enable-slow-query".format(
            os.path.join(bin_dir, "install_mysql.py"), PackageManager.get_mysql_package(),
            config_file,
            CommonDefine.SECTION_BUSINESS_DB_SDB,
            CommonDefine.DSINFO_BUSINESS_DB_MYSQL,
            force_str)
        items.append(ExecItem("Install business database-mysql", cmd))

    # 4.安装业务数据库 mariadb
    if exist_sub_section(config_data, CommonDefine.SECTION_BUSINESS_DB_SDB, CommonDefine.SUB_SECTION_MARIADB):
        cmd = "python {} --package {} --config {} --section {} -o {} {} --enable-slow-query".format(
            os.path.join(bin_dir, "install_mariadb.py"),
            PackageManager.get_mariadb_package(), config_file,
            CommonDefine.SECTION_BUSINESS_DB_SDB,
            CommonDefine.DSINFO_BUSINESS_DB_MARIADB,
            force_str)
        items.append(ExecItem("Install business database-mariadb", cmd))

    # 5.安装业务数据库 dds
    if exist_section(config_data, CommonDefine.SECTION_BUSINESS_DB_DDS):
        cmd = "python {} --package {} --config {} --section {} -o {} {} --skip-install-host {}".format(
            os.path.join(bin_dir, "install_dds.py"), PackageManager.get_dds_package(),
            config_file, CommonDefine.SECTION_BUSINESS_DB_DDS,
            CommonDefine.DSINFO_BUSINESS_DB_DDS,
            force_str, get_skip_install_dds_host())
        if platform.system() == "Windows":
            log.warn("Current platform is windows, skip install dds")
        else:
            items.append(ExecItem("Install business database-dds", cmd))

    # 6.安装 elf
    if exist_section(config_data, CommonDefine.SECTION_BUSINESS_DB_ELF):
        cmd = "python {} --package {} --config {} --business-section {} --elf-section {} -o {} {}".format(
            os.path.join(bin_dir, "install_elf.py"), PackageManager.get_elf_package(),
            config_file, CommonDefine.SECTION_BUSINESS_DB,
            CommonDefine.SECTION_BUSINESS_DB_ELF,
            CommonDefine.DSINFO_BUSINESS_DB_ELF,
            force_str)
        items.append(ExecItem("Install business database-elf", cmd))

    # 7.安装 sac
    cmd = "python {} --package {} --config {} --section {} --dsinfo {} -o {} {}".format(
        os.path.join(bin_dir, "install_sac.py"), PackageManager.get_sac_package(), config_file,
        CommonDefine.SECTION_BUSINESS_SAC,
        CommonDefine.DISINFO_DIR,
        CommonDefine.SAC_INFO,
        force_str)
    items.append(ExecItem("Install sac", cmd))

    # 8. 本地安装数据库的 shell
    cmd = "python {} --sac-info {} --install-shell".format(os.path.join(CommonDefine.BIN_DIR, "run_test.py"),
                                                           CommonDefine.SAC_INFO)
    items.append(ExecItem("Install database shell", cmd))

    return items


def exec_runtest():
    force_str = "--force-update-testcase" if IS_FORCE_UPDATE_TESTCASE else ""
    cmd = "python {} --sac-info {} {}".format(os.path.join(CommonDefine.BIN_DIR, "run_test.py"), CommonDefine.SAC_INFO,
                                              force_str)
    if TESTCASES is not None and TESTCASES != "all":
        cmd += " --testcases {}".format(TESTCASES)
    if IS_RUNBASE:
        cmd += " --runbase"
    if IS_SPECIFY_BRANCH:
        cmd += " --branch {}".format(BRANCH)
    log.info("Exec: {}".format(cmd))
    log.info("Begin to run test...")
    start_time = datetime.now()
    cmd_executor.command(cmd)
    cost_time = datetime.now() - start_time
    log.info("Run test end!")
    return ExecItem("Run test", cmd, cost_time.seconds)


def clean_workdir():
    if not Utils.is_dir_empty(CommonDefine.WORK_DIR):
        shutil.rmtree(CommonDefine.WORK_DIR)


def get_template_file():
    host_num = len(HOST_LIST)
    template_dir_path = os.path.join(CommonDefine.TEMPLATE_DIR, "base" if IS_INSTALL_BASE else "")
    file_path = os.path.join(template_dir_path, "localbuild_{}host.yml".format(host_num))
    if not os.path.exists(file_path):
        raise Exception("Missing template file: {}".format(file_path))
    return file_path


def resolve_config_file():
    template_file = get_template_file()

    with open(template_file) as f:
        content = f.read()

    for i, hostname in enumerate(HOST_LIST):
        content = content.replace("${hostname" + str(i + 1) + "}", hostname)

    config_file = get_config_file(False)
    os.makedirs(os.path.dirname(config_file))
    with open(config_file, 'w') as f:
        f.write(content)


def print_cost(exec_items):
    print "==============================COST SUMMARY:======================================"
    for item in exec_items:
        print "{}: {} ".format(item.desc, Utils.format_time(item.cost))
    print "Total cost: {} ".format(Utils.format_time(sum([item.cost for item in exec_items])))
    print "================================================================================"


if __name__ == '__main__':
    try:
        parse_command()

        exec_items = []
        if IS_CHECK_HOST:
            res = exec_check_host()
            exec_items.append(res)

        if IS_COMPILE:
            res = exec_compile()
            exec_items.append(res)

        if IS_CLEAN or IS_INSTALL:
            clean_workdir()
            resolve_config_file()

            if IS_CLEAN:
                res = exec_clean()
                exec_items.append(res)
            if IS_INSTALL:
                res = exec_install()
                exec_items.extend(res)

        if IS_RUNTEST or IS_RUNBASE:
            res = exec_runtest()
            exec_items.append(res)

        print_cost(exec_items)

    except Exception as e:
        log.exception("Failed to exec localbuild: {}".format(e))
        sys.exit(1)
