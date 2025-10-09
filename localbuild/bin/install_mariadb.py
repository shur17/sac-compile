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

DEFAULT_INSTALL_PATH = "/opt/sequoiasql/mariadb"
REMOTE_WORK_DIR = CommonDefine.REMOTE_WORK_DIR


def display_and_exit():
    print("")
    print(" --help | -h                    : print help message")
    print(" --package       <arg>          : mariadb installation package path ")
    print(" --config        <arg>          : config file path ")
    print(" --section       <arg>          : sdb config section name")
    print(" --output | -o   <arg>          : output mariadb information path")
    print(" --clean                        : clean mariadb")
    print(" --force                        : force to install mariadb")
    print(" --install-local                : install mariadb locally only")
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
        elif name in "--package":
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
            raise Exception("Missing mariadb installation package or package file is not exists!")
    else:
        if len(PACKAGE_FILE.strip()) == 0 or not os.path.exists(PACKAGE_FILE):
            raise Exception("Missing mariadb installation package or package file is not exists!")
        if len(CONFIG.strip()) == 0 or not os.path.exists(CONFIG):
            raise Exception("Missing config file or config file is not exists!")
        if len(SECTION.strip()) == 0:
            raise Exception("Missing config section name!")
        if len(OUTPUT_FILE.strip()) == 0:
            raise Exception("Missing output file path!")


def load_config():
    with open(CONFIG) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def get_mariadb_info(sdb_cluster):
    if 'instances' not in sdb_cluster or 'mariadb' not in sdb_cluster.get("instances"):
        return None
    mariadb_section = sdb_cluster.get("instances").get("mariadb")
    if mariadb_section is not None and len(mariadb_section) > 0:
        coord = sdb_cluster.get("coord")[0].get("hostname") + ":" + str(sdb_cluster.get("coord")[0].get("service"))
        mariadb_section["coord"] = coord
        if 'user' in sdb_cluster and 'password' in sdb_cluster \
                and len(sdb_cluster['user']) > 0 and len(sdb_cluster['password']) > 0:
            mariadb_section['sdb_user'] = sdb_cluster['user']
            mariadb_section['sdb_password'] = sdb_cluster['password']
        return mariadb_section
    else:
        return None


def get_install_hosts(hosts, mariadb_group):
    hosts_in_mariadb_groups = []
    host_names_set = set()
    nodes = mariadb_group.get("nodes")
    for node in nodes:
        hostname = node.get("hostname")
        host_names_set.add(hostname)
    for hostname in host_names_set:
        match = False
        for host in hosts:
            if host.get("hostname") == hostname:
                hosts_in_mariadb_groups.append(host)
                match = True
                break
        if not match:
            raise Exception("Can not find mariadb host {} in hosts section".format(hostname))
    return hosts_in_mariadb_groups


def get_install_info(ssh):
    check_res = {
        "is_installed": False,
        "installed_path": ""
    }
    if ssh.is_file_exist("/etc/default/sequoiasql-mariadb"):
        check_res['installed_path'] = \
            ssh.cmd("grep 'INSTALL_DIR' /etc/default/sequoiasql-mariadb | awk -F'=' '{print $2}'", True)['stdout']
        check_res['is_installed'] = True
    return check_res


def install_mariadb(host, install_path):
    ssh = None
    remote_mariadb_run_file = os.path.join(REMOTE_WORK_DIR, PACKAGE_FILE.split(os.sep)[-1])
    try:
        ssh = SSHConnection(host=host['hostname'], user=host['user'], pwd=host['password'])
        Utils.ssh_send_package(ssh, PACKAGE_FILE, remote_mariadb_run_file)
        install_info = get_install_info(ssh)

        if not install_info['is_installed']:
            log.info("Installing mariadb")
            ssh.cmd("{} --mode unattended --prefix {}".format(remote_mariadb_run_file, install_path), True)
        else:
            old_install_path = install_info['installed_path']
            if IS_FORCE:
                log.info("Forcing uninstall and reinstall, please wait")
                clean_and_install(old_install_path, remote_mariadb_run_file, install_path, ssh)
            else:
                log.info("mariadb is exists!")
                while True:
                    print("Do you want uninstall and reinstall it ?(y/n):\n")
                    res = raw_input("Please enter your choice:")
                    if res == "Y" or res == "y":
                        log.info("uninstalling and reinstalling, please wait")
                        clean_and_install(old_install_path, remote_mariadb_run_file, install_path, ssh)
                        break
                    elif res == "N" or res == "n":
                        print("know your choice, exiting!")
                        sys.exit(0)
                    else:
                        print("I don't know your choice, please enter again")
                        continue
    finally:
        if ssh:
            ssh.close()


def clean_and_install(old_install_path, remote_mariadb_run_file, install_path, ssh):
    do_clean(old_install_path, ssh)
    log.info("Installing mariadb")
    ssh.cmd("{} --mode unattended --prefix {}".format(remote_mariadb_run_file, install_path), True)


def do_clean(install_path, ssh):
    if not ssh.is_file_exist(install_path):
        log.info("mariaDB is not found in {}, skip clean".format(install_path))
        return
    log.info("Cleaning mariadb")
    ssh.cmd("{}/uninstall --mode unattended".format(install_path), True)
    ssh.cmd("rm -rf {}".format(install_path))
    Utils.kill_process(ssh, install_path, "mariadb")


def get_mariadb_groups(config_data):
    mariadb_groups = []
    sdb_clusters = Utils.get_section(config_data, SECTION)
    for cluster in sdb_clusters:
        mariadb_info = get_mariadb_info(cluster)
        if not mariadb_info:
            continue
        if INSTALL_PATH is not None:
            mariadb_info['installPath'] = INSTALL_PATH
        mariadb_groups.append(mariadb_info)
    return mariadb_groups


def deploy_mariadb(install_hosts, mariadb_group):
    hostname_to_host_info = {host_info.get("hostname"): host_info for host_info in install_hosts}
    nodes = mariadb_group.get("nodes")
    install_path = mariadb_group.get("installPath")
    for index, node in enumerate(nodes):
        ssh = None
        host_info = hostname_to_host_info.get(node.get("hostname"))
        try:
            ssh = SSHConnection(host=host_info['hostname'], user=host_info['user'], pwd=host_info['password'])
            if index == 0:
                # 创建实例组
                log.info("Creating mariadb group {}".format(mariadb_group.get("groupName")))
                create_mariadb_group_cmd = "{}/bin/ha_inst_group_init {} --host {}".format(install_path,
                                                                                           mariadb_group.get(
                                                                                               "groupName"),
                                                                                           mariadb_group.get("coord"))
                if 'sdb_user' in mariadb_group and 'sdb_password' in mariadb_group:
                    create_mariadb_group_cmd = "echo " + mariadb_group[
                        'sdb_password'] + "|" + create_mariadb_group_cmd + " --user {} -p".format(
                        mariadb_group['sdb_user'])
                ssh.cmd(create_mariadb_group_cmd, True)

            # 创建实例并加入到组
            log.info("Creating mariadb instance {}".format(node.get("instanceName")))
            add_mariadb_inst_cmd = "{}/bin/sdb_maria_ctl addinst {} -D {}/database/{} -P {} -g {} --sdb-conn-addr {}".format(
                install_path,
                node.get("instanceName"), install_path, node.get("port"), node.get("port"),
                mariadb_group.get("groupName"),
                mariadb_group.get("coord"))
            if 'sdb_user' in mariadb_group and 'sdb_password' in mariadb_group:
                add_mariadb_inst_cmd += " --sdb-user {} --sdb-passwd {}".format(mariadb_group['sdb_user'],
                                                                                mariadb_group['sdb_password'])
            ssh.cmd(add_mariadb_inst_cmd, True)

            # 创建用户
            admin_user = "sdbadmin"
            admin_pwd = "sdbadmin"
            if index == 0:
                log.info("Creating mariadb user")
                if mariadb_group.get("user") != admin_user:
                    # 如果不是 sdbadmin 用户，需要先初始化 sdbadmin 用户，再用 sdbadmin 用户管理其他用户
                    init_admin_user_cmd = ''' su - sdbadmin -c "{}/bin/mysql -S {}/database/{}/mysqld.sock -u {} -e \\"ALTER USER {}@localhost IDENTIFIED BY '{}';\\"" '''. \
                        format(install_path, install_path, node.get("port"), admin_user, admin_user, admin_pwd)
                    ssh.cmd(init_admin_user_cmd, True)
                    create_user_cmd = ''' su - sdbadmin -c "{}/bin/mysql -S {}/database/{}/mysqld.sock -u {} -p{} -e \\"CREATE USER {}@localhost IDENTIFIED BY '{}';\\"" '''. \
                        format(install_path, install_path, node.get("port"), admin_user, admin_pwd,
                               mariadb_group.get("user"),
                               mariadb_group.get("password"))
                    ssh.cmd(create_user_cmd, True)
                else:
                    # 如果是 sdbadmin 用户，直接设置密码即可
                    admin_pwd = mariadb_group.get("password")
                    cmd = ''' su - sdbadmin -c "{}/bin/mysql -S {}/database/{}/mysqld.sock -u {}  -e \\"ALTER USER {}@localhost IDENTIFIED BY '{}';\\"" '''. \
                        format(install_path, install_path, node.get("port"), admin_user, admin_user, admin_pwd)
                    ssh.cmd(cmd, True)

            # 开启远程登录
            log.info("Enabling remote login")
            cmd = '''{}/bin/mysql -h 127.0.0.1 -P {} -u {} -p{} -e "GRANT ALL PRIVILEGES ON *.* TO {}@'%' IDENTIFIED BY '{}' WITH GRANT OPTION;FLUSH PRIVILEGES;"''' \
                .format(install_path, node.get("port"), admin_user, admin_pwd,
                        mariadb_group.get("user"), mariadb_group.get("password"))
            ssh.cmd(cmd, True)

            # 开启慢查询
            if IS_ENABLE_SLOW_QUERY:
                log.info("Enabling slow query")
                cmd = " echo '\nperformance-schema=ON\n" + \
                      "performance-schema-consumer-events-stages-current=ON\n" + \
                      "performance-schema-consumer-events-stages-history-long=ON\n" + \
                      "slow-query-log=off\n" + \
                      "long-query-time=0' >> {}/database/{}/auto.cnf".format(install_path, node.get("port"))
                ssh.cmd(cmd, True)
                # 重启实例
                log.info("Restarting mariadb instance {}".format(node.get("instanceName")))
                restart_inst_cmd = "{}/bin/sdb_maria_ctl restart {}".format(install_path,
                                                                            node.get("instanceName"))
                ssh.cmd(restart_inst_cmd, True)
        except Exception as e:
            raise e
        finally:
            if ssh:
                ssh.close()


def generate_deploy_result(mariadb_groups):
    log.info("Generate deploy result: {}".format(OUTPUT_FILE))
    parent_directory = os.path.dirname(OUTPUT_FILE)
    if parent_directory and not os.path.exists(parent_directory):
        os.makedirs(parent_directory)
    yml_info = {}
    yml_info["mariadb"] = mariadb_groups
    with open(OUTPUT_FILE, "w") as file:
        yaml.dump(yml_info, file)


def clean_mariadb(host):
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


def install_mariadb_local():
    if platform.system() == "Windows":
        raise Exception("Not support install mariadb on windows")
    mariadb_install_info = Utils.get_install_info("/etc/default/sequoiasql-mariadb")
    if mariadb_install_info['is_installed']:
        if IS_FORCE:
            log.info("Mariadb is installed, force to reinstall")
            cmd_executor.command("{}/uninstall --mode unattended".format(mariadb_install_info['installed_path']))
            cmd_executor.command("rm -rf {}".format(mariadb_install_info['installed_path']))
        else:
            log.info("Mariadb is installed, skip install")
            return
    cmd_executor.command("chmod +x {}".format(PACKAGE_FILE))
    install_path = INSTALL_PATH if INSTALL_PATH is not None else DEFAULT_INSTALL_PATH
    cmd_executor.command("{} --mode unattended --prefix {}".format(PACKAGE_FILE, install_path))


if __name__ == '__main__':
    try:
        parse_command()
        if IS_INSTALL_LOCAL:
            install_mariadb_local()
            sys.exit(0)

        config_info = load_config()
        hosts = config_info.get("hosts")
        if IS_CLEAN:
            for host in hosts:
                log.info("Begin to clean mariadb on {}".format(host.get("hostname")))
                clean_mariadb(host)
            sys.exit(0)

        mariadb_groups = get_mariadb_groups(config_info)
        if len(mariadb_groups) == 0:
            log.info("No mariadb instance to install")
            sys.exit(0)

        # 安装 mariadb
        installed_hosts = set()
        for mariadb_group in mariadb_groups:
            install_hosts = get_install_hosts(hosts, mariadb_group)
            install_path = mariadb_group.get("installPath")
            if len(install_hosts) == 0:
                raise Exception("Can not find any available host in mariadb group")
            for host in install_hosts:
                if host.get("hostname") in installed_hosts:
                    continue
                installed_hosts.add(host.get("hostname"))
                log.info("Begin to install mariadb on {}".format(host.get("hostname")))
                install_mariadb(host, install_path)

        # 创建 mariadb 实例、实例组
        for mariadb_group in mariadb_groups:
            log.info("Begin to deploy mariadb group: {}".format(mariadb_group.get("groupName")))
            install_hosts = get_install_hosts(hosts, mariadb_group)
            deploy_mariadb(install_hosts, mariadb_group)

        #  生成部署信息
        generate_deploy_result(mariadb_groups)

    except Exception as e:
        log.exception("Failed to exec install_mariadb.py: {}".format(e))
        raise e
