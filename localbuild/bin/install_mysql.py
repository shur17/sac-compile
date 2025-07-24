#!/usr/bin/python
# coding=utf-8
import getopt
import os
import platform
import sys
import yaml

from common.SSHConnection import SSHConnection
from common.LoggerUtil import get_logger
from common import Utils, CmdExecutor, CommonDefine

Utils.setup_yaml()
log = get_logger()
cmd_executor = CmdExecutor.CmdExecutor(False)

PACKAGE_FILE = ""
CONFIG = ""
SECTION = ""
IS_FORCE = False
IS_CLEAN = False
IS_INSTALL_LOCAL = False
OUTPUT_FILE = ""
IS_ENABLE_SLOW_QUERY = False
INSTALL_PATH = None

DEFAULT_INSTALL_PATH = "/opt/sequoiasql/mysql"
REMOTE_WORK_DIR = CommonDefine.REMOTE_WORK_DIR


def display_and_exit():
    print("")
    print(" --help | -h                    : print help message")
    print(" --package       <arg>          : mysql installation package path ")
    print(" --config        <arg>          : config file path ")
    print(" --section       <arg>          : sdb config section name")
    print(" --output | -o   <arg>          : output mysql information path")
    print(" --clean                        : clean mysql")
    print(" --force                        : force to install mysql")
    print(" --install-local                : only install mysql on local host")
    print(" --enable-slow-query            : enable slow query")

    sys.exit(0)


def parse_command():
    global PACKAGE_FILE, CONFIG, SECTION, IS_FORCE, OUTPUT_FILE, IS_CLEAN, IS_INSTALL_LOCAL, IS_ENABLE_SLOW_QUERY, INSTALL_PATH
    try:
        options, args = getopt.getopt(sys.argv[1:], "ho:",
                                      ["help", "package=", "output=", "config=", "section=", "force", "clean",
                                       "install-local", "enable-slow-query", "install-path="])
    except getopt.GetoptError, e:
        log.error(e, exc_info=True)
        sys.exit(-1)

    for name, value in options:
        if name in ("-h", "--help"):
            display_and_exit()
        elif name in "--package-file":
            PACKAGE_FILE = value
        elif name in "--config":
            CONFIG = value
        elif name in ("-o", "--output"):
            OUTPUT_FILE = value
        elif name in "--section":
            SECTION = value
        elif name in "--force":
            IS_FORCE = True
        elif name in "--clean":
            IS_CLEAN = True
        elif name in "--install-local":
            IS_INSTALL_LOCAL = True
        elif name in "--enable-slow-query":
            IS_ENABLE_SLOW_QUERY = True
        elif name in "--install-path":
            INSTALL_PATH = value

    if IS_CLEAN:
        if len(CONFIG.strip()) == 0 or not os.path.exists(CONFIG):
            raise Exception("Missing config file or config file is not exists!")
    elif IS_INSTALL_LOCAL:
        if len(PACKAGE_FILE.strip()) == 0 or not os.path.exists(PACKAGE_FILE):
            raise Exception("Missing mysql installation package or package file is not exists!")
    else:
        if len(PACKAGE_FILE.strip()) == 0 or not os.path.exists(PACKAGE_FILE):
            raise Exception("Missing mysql installation package or package file is not exists!")
        if len(CONFIG.strip()) == 0 or not os.path.exists(CONFIG):
            raise Exception("Missing config file or config file is not exists!")
        if len(SECTION.strip()) == 0:
            raise Exception("Missing config section name!")
        if len(OUTPUT_FILE.strip()) == 0:
            raise Exception("Missing output file path!")


def load_config():
    with open(CONFIG) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def get_mysql_info(sdb_cluster):
    if 'instances' not in sdb_cluster or 'mysql' not in sdb_cluster['instances']:
        return None
    mysql_section = sdb_cluster.get("instances").get("mysql")
    if mysql_section is not None and len(mysql_section) > 0:
        coord = sdb_cluster.get("coord")[0].get("hostname") + ":" + str(sdb_cluster.get("coord")[0].get("service"))
        mysql_section["coord"] = coord
        if 'user' in sdb_cluster and 'password' in sdb_cluster \
                and len(sdb_cluster['user']) > 0 and len(sdb_cluster['password']) > 0:
            mysql_section['sdb_user'] = sdb_cluster['user']
            mysql_section['sdb_password'] = sdb_cluster['password']
        return mysql_section
    else:
        return None


def get_install_hosts(hosts, mysql_group):
    install_hosts = []
    host_names_set = set()

    nodes = mysql_group.get("nodes")
    for node in nodes:
        hostname = node.get("hostname")
        host_names_set.add(hostname)

    for hostname in host_names_set:
        match = False
        for host in hosts:
            if host.get("hostname") == hostname:
                install_hosts.append(host)
                match = True
                break
        if not match:
            raise Exception("Can not find mysql host {} in host section".format(hostname))
    if len(install_hosts) == 0:
        raise Exception("Mysql hosts is not declared in hosts section")
    return install_hosts


def get_install_info(ssh):
    check_res = {
        "is_installed": False,
        "installed_path": ""
    }
    if ssh.is_file_exist("/etc/default/sequoiasql-mysql"):
        check_res['installed_path'] = \
            ssh.cmd("grep 'INSTALL_DIR' /etc/default/sequoiasql-mysql | awk -F'=' '{print $2}'", True)['stdout']
        check_res['is_installed'] = True
    return check_res


def install_mysql(host, install_path):
    ssh = None
    remote_mysql_run_file = os.path.join(REMOTE_WORK_DIR, PACKAGE_FILE.split(os.sep)[-1])
    try:
        ssh = SSHConnection(host=host['hostname'], user=host['user'], pwd=host['password'])
        Utils.ssh_send_package(ssh, PACKAGE_FILE, remote_mysql_run_file)
        install_info = get_install_info(ssh)

        if not install_info['is_installed']:
            log.info("Installing mysql")
            ssh.cmd("{} --mode unattended --prefix {}".format(remote_mysql_run_file, install_path), True)
        else:
            old_install_path = install_info['installed_path']
            if IS_FORCE:
                log.info("Forcing uninstall and reinstall, please wait")
                clean_and_install(old_install_path, remote_mysql_run_file, install_path, ssh)
            else:
                log.info("mysql is exists!")
                while True:
                    print("Do you want uninstall and reinstall it ?(y/n):\n")
                    res = raw_input("Please enter your choice:")
                    if res == "Y" or res == "y":
                        log.info("uninstalling and reinstalling, please wait")
                        clean_and_install(old_install_path, remote_mysql_run_file, install_path, ssh)
                        break
                    elif res == "N" or res == "n":
                        print("know your choice, exiting!")
                        sys.exit(0)
                    else:
                        print("I don't know your choice,please enter again")
                        continue
    finally:
        if ssh:
            ssh.close()


def clean_and_install(old_install_path, remote_mysql_run_file, install_path, ssh):
    do_clean(old_install_path, ssh)
    log.info("Installing mysql")
    ssh.cmd("{} --mode unattended --prefix {}".format(remote_mysql_run_file, install_path), True)


def do_clean(install_path, ssh):
    if not ssh.is_file_exist(install_path):
        log.info("mysql is not found in {}, skip clean".format(install_path))
        return
    log.info("Cleaning mysql")
    ssh.cmd("{}/uninstall --mode unattended".format(install_path), True)
    ssh.cmd("rm -rf {}".format(install_path))
    Utils.kill_process(ssh, install_path, "mysql")


def get_mysql_groups(config_data):
    mysql_groups = []
    sdb_clusters = Utils.get_section(config_data, SECTION)
    for cluster in sdb_clusters:
        mysql_info = get_mysql_info(cluster)
        if not mysql_info:
            continue
        if INSTALL_PATH is not None:
            mysql_info['installPath'] = INSTALL_PATH
        mysql_groups.append(mysql_info)
    return mysql_groups


def deploy_mysql(install_hosts, mysql_group):
    hostname_to_host_info = {host_info.get("hostname"): host_info for host_info in install_hosts}
    nodes = mysql_group.get("nodes")
    install_path = mysql_group.get("installPath")
    for index, node in enumerate(nodes):
        ssh = None
        host_info = hostname_to_host_info.get(node.get("hostname"))
        try:
            ssh = SSHConnection(host=host_info['hostname'], user=host_info['user'], pwd=host_info['password'])
            if index == 0 and 'groupName' in mysql_group:
                # 创建实例组
                log.info("Creating mysql group: {}".format(mysql_group.get("groupName")))
                create_mysql_group_cmd = "{}/bin/ha_inst_group_init {} --host {}".format(install_path,
                                                                                         mysql_group.get("groupName"),
                                                                                         mysql_group.get("coord"))
                if 'sdb_user' in mysql_group and 'sdb_password' in mysql_group:
                    create_mysql_group_cmd = "echo " + mysql_group[
                        'sdb_password'] + "|" + create_mysql_group_cmd + " --user {} -p".format(
                        mysql_group['sdb_user'])
                ssh.cmd(create_mysql_group_cmd, True)

            # 创建实例并加入到组
            log.info("Creating mysql instance: {}".format(node.get("instanceName")))
            group_str = ""
            if 'groupName' in mysql_group:
                group_str = " -g {}".format(mysql_group.get("groupName"))
            add_mysql_inst_cmd = "{}/bin/sdb_mysql_ctl addinst {} -D {}/database/{} -P {} {} --sdb-conn-addr {}".format(
                install_path,
                node.get("instanceName"), install_path, node.get("port"), node.get("port"),
                group_str,
                mysql_group.get("coord"))
            if 'sdb_user' in mysql_group and 'sdb_password' in mysql_group:
                add_mysql_inst_cmd += " --sdb-user {} --sdb-passwd {}".format(mysql_group['sdb_user'],
                                                                              mysql_group['sdb_password'])
            ssh.cmd(add_mysql_inst_cmd, True)

            # 设置密码
            log.info("Setting mysql password")
            set_pwd_cmd = '''{}/bin/mysql -h 127.0.0.1 -P {} -u root -e "GRANT ALL PRIVILEGES ON *.* TO {}@'%' IDENTIFIED BY '{}' WITH GRANT OPTION;FLUSH PRIVILEGES;"''' \
                .format(install_path, node.get("port"), mysql_group.get("user"), mysql_group.get("password"))
            ssh.cmd(set_pwd_cmd, True)

            # 开启慢查询
            if IS_ENABLE_SLOW_QUERY:
                log.info("Enable slow query")
                cmd = " echo '\nperformance-schema-max-digest-length=1024\n" + \
                      "performance-schema-max-sql-text-length=1024\n" + \
                      "slow-query-log=on\n" + \
                      "long-query-time=0' >> {}/database/{}/auto.cnf".format(install_path, node.get("port"))
                ssh.cmd(cmd, True)
                # 重启实例
                log.info("Restart mysql instance: {}".format(node.get("instanceName")))
                restart_mysql_inst_cmd = "{}/bin/sdb_mysql_ctl restart {}".format(install_path,
                                                                                  node.get("instanceName"))
                ssh.cmd(restart_mysql_inst_cmd, True)

        finally:
            if ssh:
                ssh.close()


def generate_deploy_result(mysql_groups):
    log.info("Generate deploy result: {}".format(OUTPUT_FILE))
    parent_directory = os.path.dirname(OUTPUT_FILE)
    if parent_directory and not os.path.exists(parent_directory):
        os.makedirs(parent_directory)
    yml_info = {}

    yml_info["mysql"] = mysql_groups
    with open(OUTPUT_FILE, "w") as file:
        yaml.dump(yml_info, file)


def clean_mysql(host):
    ssh = None
    try:
        ssh = SSHConnection(host=host['hostname'], user=host['user'], pwd=host['password'])
        install_info = get_install_info(ssh)
        if install_info['is_installed']:
            install_path = install_info['installed_path']
            do_clean(install_path, ssh)
    finally:
        if ssh:
            ssh.close()


def install_mysql_local():
    if platform.system() == "Windows":
        raise Exception("Not support install mysql on windows")
    mysql_install_info = Utils.get_install_info("/etc/default/sequoiasql-mysql")
    if mysql_install_info['is_installed']:
        if IS_FORCE:
            log.info("MySQL is installed, force to reinstall")
            cmd_executor.command("{}/uninstall --mode unattended".format(mysql_install_info['installed_path']))
            cmd_executor.command("rm -rf {}".format(mysql_install_info['installed_path']))
        else:
            log.info("MySQL is installed, skip install")
            return
    install_path = INSTALL_PATH if INSTALL_PATH is not None else DEFAULT_INSTALL_PATH
    cmd_executor.command("chmod +x {}".format(PACKAGE_FILE))
    cmd_executor.command("{} --mode unattended --prefix {}".format(PACKAGE_FILE, install_path))


if __name__ == '__main__':
    try:
        parse_command()

        if IS_INSTALL_LOCAL:
            install_mysql_local()
            sys.exit(0)

        config_info = load_config()
        hosts = config_info.get("hosts")

        if IS_CLEAN:
            for host in hosts:
                log.info("Begin to clean mysql on {}".format(host.get("hostname")))
                clean_mysql(host)
            sys.exit(0)

        # 获取所有的 mysql 实例组
        mysql_groups = get_mysql_groups(config_info)
        if len(mysql_groups) == 0:
            log.info("No mysql instance to install")
            sys.exit(0)

        # 安装 mysql
        installed_hosts = set()
        for mysql_group in mysql_groups:
            install_hosts = get_install_hosts(hosts, mysql_group)
            install_path = mysql_group.get("installPath")
            for host in install_hosts:
                if host.get("hostname") in installed_hosts:
                    continue
                installed_hosts.add(host.get("hostname"))
                log.info("Begin to install mysql on {}".format(host.get("hostname")))
                install_mysql(host, install_path)

        # 创建 mysql 实例、实例组
        for mysql_group in mysql_groups:
            log.info("Begin to deploy mysql group: {}".format(mysql_group.get("groupName", "None")))
            install_hosts = get_install_hosts(hosts, mysql_group)
            deploy_mysql(install_hosts, mysql_group)

        #  生成部署信息
        generate_deploy_result(mysql_groups)

    except Exception as e:
        log.exception("Failed to exec install_mysql.py: {}".format(e))
        raise e
