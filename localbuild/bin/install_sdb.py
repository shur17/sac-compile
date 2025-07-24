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
OUTPUT_FILE = ""
IS_ENABLE_SLOW_QUERY = False
IS_INSTALL_LOCAL = False
IS_DISABLE_RECYCLE_BIN = False
INSTALL_PATH = None
SKIP_INSTALL_HOST = []

DEFAULT_INSTALL_PATH = "/opt/sequoiadb"
REMOTE_WORK_DIR = CommonDefine.REMOTE_WORK_DIR


def display_and_exit():
    print("")
    print(" --help | -h                    : print help message")
    print(" --package       <arg>          : sdb installation package path")
    print(" --config        <arg>          : config file path")
    print(" --section       <arg>          : sdb config section name")
    print(" --output | -o   <arg>          : output sdb information path")
    print(" --clean                        : clean sdb")
    print(" --force                        : force to install sdb cluster")
    print(" --install-local                : install sdb locally only")
    print(" --enable-slow-query            : enable slow query")
    print(" --skip-install-host            : skip install sdb on host list")
    print(" --disable-recycle-bin          : disable recycle bin")
    sys.exit(0)


def parse_command():
    global PACKAGE_FILE, CONFIG, SECTION, IS_FORCE, OUTPUT_FILE, IS_CLEAN, IS_ENABLE_SLOW_QUERY, \
        IS_INSTALL_LOCAL, SKIP_INSTALL_HOST, IS_DISABLE_RECYCLE_BIN, INSTALL_PATH
    try:
        options, args = getopt.getopt(sys.argv[1:], "ho:",
                                      ["help", "package=", "output=", "config=", "section=", "force", "clean",
                                       "enable-slow-query", "install-local", "skip-install-host=",
                                       "disable-recycle-bin", "install-path="])
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
        elif name in "--clean":
            IS_CLEAN = True
        elif name in "--force":
            IS_FORCE = True
        elif name in "--enable-slow-query":
            IS_ENABLE_SLOW_QUERY = True
        elif name in "--install-local":
            IS_INSTALL_LOCAL = True
        elif name in "--skip-install-host":
            SKIP_INSTALL_HOST = value.split(",")
        elif name in "--disable-recycle-bin":
            IS_DISABLE_RECYCLE_BIN = True
        elif name in "--install-path":
            INSTALL_PATH = value

    if IS_CLEAN:
        if len(CONFIG.strip()) == 0 or not os.path.exists(CONFIG):
            raise Exception("Missing config file or config file is not exists!")
    elif IS_INSTALL_LOCAL:
        if len(PACKAGE_FILE.strip()) == 0 or not os.path.exists(PACKAGE_FILE):
            raise Exception("Missing sdb installation package or package file is not exists!")
    else:
        if len(PACKAGE_FILE.strip()) == 0 or not os.path.exists(PACKAGE_FILE):
            raise Exception("Missing sdb installation package or package file is not exists!")
        if len(CONFIG.strip()) == 0 or not os.path.exists(CONFIG):
            raise Exception("Missing config file or config file is not exists!")
        if len(SECTION.strip()) == 0:
            raise Exception("Missing config section name!")
        if len(OUTPUT_FILE.strip()) == 0:
            raise Exception("Missing output file path!")


def load_config():
    with open(CONFIG) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def get_install_info(ssh):
    install_info = {
        "is_installed": False,
        "installed_path": ""
    }
    if ssh.is_file_exist("/etc/default/sequoiadb"):
        install_info['installed_path'] = \
            ssh.cmd("grep 'INSTALL_DIR' /etc/default/sequoiadb | awk -F'=' '{print $2}'", True)['stdout']
        install_info['is_installed'] = True
    return install_info


def install_sdb(host, install_path):
    ssh = None
    remote_sdb_run_file = os.path.join(REMOTE_WORK_DIR, PACKAGE_FILE.split(os.sep)[-1])
    try:
        ssh = SSHConnection(host=host['hostname'], user=host['user'], pwd=host['password'])
        Utils.ssh_send_package(ssh, PACKAGE_FILE, remote_sdb_run_file)
        install_info = get_install_info(ssh)

        if not install_info['is_installed']:
            log.info("Installing sdb")
            ssh.cmd("{} --mode unattended --prefix {}".format(remote_sdb_run_file, install_path), True)
        else:
            old_install_path = install_info['installed_path']
            if IS_FORCE:
                print("Forcing uninstall and reinstall, please wait")
                clean_and_install(old_install_path, remote_sdb_run_file, install_path, ssh)
            else:
                print("SDB cluster is exists !")
                while True:
                    print("Do you want uninstall and reinstall it ?(y/n):\n")
                    res = raw_input("Please enter your choice:")
                    if res == "Y" or res == "y":
                        print("uninstalling and reinstalling, please wait")
                        clean_and_install(old_install_path, remote_sdb_run_file, install_path, ssh)
                        break
                    elif res == "N" or res == "n":
                        print("know your choice, exiting!")
                        sys.exit(0)
                    else:
                        print("I don't know your choice, lease enter again")
                        continue
    finally:
        if ssh:
            ssh.close()


def clean_and_install(old_install_path, remote_sdb_run_file, install_path, ssh):
    do_clean(old_install_path, ssh)
    log.info("Installing sdb")
    ssh.cmd("{} --mode unattended --prefix {}".format(remote_sdb_run_file, install_path), True)


def do_clean(install_path, ssh):
    if not ssh.is_file_exist(install_path):
        log.info("sdb is not found in {}, skip clean".format(install_path))
        return
    log.info("Cleaning sdb")
    res = ssh.cmd("su - sdbadmin -c 'sdbstop -a'")
    if res['status'] != 0:
        raise Exception("Failed to stop SDB cluster!")
    ssh.cmd("{}/uninstall --mode unattended".format(install_path), True)
    ssh.cmd("rm -rf {}".format(install_path))
    Utils.kill_process(ssh, "sdbcmd")
    Utils.kill_process(ssh, "sdbcm(")
    Utils.kill_process(ssh, "sequoiadb(")


def get_cluster_info(config_data):
    cluster_info = []
    section_data = Utils.get_section(config_data, SECTION)
    if isinstance(section_data, list):
        cluster_info.extend(section_data)
    else:
        cluster_info.append(section_data)
    for cluster in cluster_info:
        if INSTALL_PATH is not None:
            cluster['installPath'] = INSTALL_PATH
    return cluster_info


def get_hosts_in_cluster(hosts, cluster):
    hosts_in_cluster = []
    hostnames_in_cluster = set()
    hostname_to_host_info = {host_info.get("hostname"): host_info for host_info in hosts}

    hostnames = []
    for key in ["cata", "coord", "groups"]:
        items = cluster.get(key, [])
        for item in items:
            hostname = item.get("hostname")
            hostnames.append(hostname)
    for hostname in hostnames:
        if hostname not in hostnames_in_cluster:
            host_info = hostname_to_host_info.get(hostname)
            if host_info:
                hosts_in_cluster.append(host_info)
                hostnames_in_cluster.add(hostname)

    return hosts_in_cluster


def generate_deploy_conf(cluster):
    """
    sequoiadb.conf:
    role,groupName,hostName,serviceName,dbPath
    catalog,SYSCatalogGroup,192.168.31.71,11800,[installPath]/database/catalog/11800
    coord,SYSCoord,192.168.31.71,11810,[installPath]/database/coord/11810
    data,group1,192.168.31.71,11820,[installPath]/database/data/11820
    """
    deploy_conf = "role,groupName,hostName,serviceName,dbPath"
    cata_info = cluster.get("cata")
    for cata in cata_info:
        deploy_conf += "\ncatalog,SYSCatalogGroup,{},{},[installPath]/database/catalog/{}" \
            .format(cata.get("hostname"),
                    cata.get("service"),
                    cata.get("service"))

    coord_info = cluster.get("coord")
    for coord in coord_info:
        deploy_conf += "\ncoord,SYSCoord,{},{},[installPath]/database/coord/{}" \
            .format(coord.get("hostname"),
                    coord.get("service"),
                    coord.get("service"))

    groups = cluster.get("groups")
    for group in groups:
        deploy_conf += "\ndata,{},{},{},[installPath]/database/data/{}" \
            .format(group.get("name"),
                    group.get("hostname"),
                    group.get("service"),
                    group.get("service"))
    return deploy_conf


def deploy_sdb(hosts_in_cluster, cluster):
    # 连接集群中的任意一台机器
    host_info = next(
        (item for item in hosts_in_cluster if item.get("hostname") == cluster.get("coord")[0].get("hostname")))
    install_path = cluster.get("installPath")
    ssh = None
    try:
        ssh = SSHConnection(host=host_info['hostname'], user=host_info['user'], pwd=host_info['password'])
        deploy_conf = generate_deploy_conf(cluster)
        ssh.cmd("echo '" + deploy_conf + "' >{}/tools/deploy/sequoiadb.conf".format(install_path), True)
        deployRes = ssh.cmd("su - sdbadmin -c 'bash {}/tools/deploy/quickDeploy.sh --sdb'".format(install_path))
        if deployRes['status'] != 0:
            raise Exception("Failed to deploy sdb cluster: {}".format(deployRes['stderr']))

        coord_host = cluster.get("coord")[0].get("hostname")
        coord_port = cluster.get("coord")[0].get("service")

        # 开启慢查询
        if IS_ENABLE_SLOW_QUERY:
            log.info("Enable slow query")
            res = ssh.cmd(""" 
                {}/bin/sdb  '
                db = new Sdb("{}",{});
                db.updateConf( {{ mongroupmask: "slowQuery:detail" }} );
                db.updateConf( {{ monslowquerythreshold: 300 }} );'
                """.format(install_path, coord_host, coord_port))
            if res['status'] != 0:
                raise Exception("Failed to enable slow query: {}".format(res['stderr']))

        # 禁用回收站
        if IS_DISABLE_RECYCLE_BIN:
            log.info("Disable recycle bin")
            ssh.cmd(""" 
                {}/bin/sdb  '
                db = new Sdb("{}",{});
                db.getRecycleBin().disable();
                '
                """.format(install_path, coord_host, coord_port), True)

        # 创建用户
        if 'user' in cluster and len(cluster['user']) > 0:
            log.info("Create user: {}:{}".format(cluster['user'], cluster['password']))
            res = ssh.cmd(""" 
                {}/bin/sdb  '
                db = new Sdb("{}",{});
                db.createUsr("{}", "{}");'
                """.format(install_path, coord_host, coord_port, cluster['user'], cluster['password']))
            if res['status'] != 0:
                raise Exception("Failed to create user: {}".format(res['stderr']))

    finally:
        if ssh:
            ssh.close()


def generate_deploy_result(clusters):
    log.info("Generate deploy result: {}".format(OUTPUT_FILE))
    parent_directory = os.path.dirname(OUTPUT_FILE)
    if parent_directory and not os.path.exists(parent_directory):
        os.makedirs(parent_directory)
    for cluster in clusters:
        if 'instances' in cluster:
            del cluster['instances']
    yml_info = {}
    if len(clusters) == 1:
        yml_info["sequoiadb"] = clusters[0]
    else:
        yml_info["sequoiadb"] = clusters
    with open(OUTPUT_FILE, "w") as file:
        yaml.dump(yml_info, file)


def clean_sdb(host):
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


def install_sdb_local():
    if platform.system() == "Windows":
        raise Exception("Not support install sdb on windows")
    sdb_install_info = Utils.get_install_info("/etc/default/sequoiadb")
    if sdb_install_info['is_installed']:
        if IS_FORCE:
            log.info("Sdb is installed, force to reinstall")
            cmd_executor.command("su - sdbadmin -c 'sdbstop -a'")
            cmd_executor.command("{}/uninstall --mode unattended".format(sdb_install_info['installed_path']))
            cmd_executor.command("rm -rf {}".format(sdb_install_info['installed_path']))
        else:
            log.info("Sdb is installed, skip install")
            return
    install_path = INSTALL_PATH if INSTALL_PATH else DEFAULT_INSTALL_PATH
    cmd_executor.command("chmod +x {}".format(PACKAGE_FILE))
    cmd_executor.command("{} --mode unattended --prefix {}".format(PACKAGE_FILE, install_path))


if __name__ == '__main__':
    try:
        parse_command()
        if IS_INSTALL_LOCAL:
            install_sdb_local()
            sys.exit(0)

        config_data = load_config()
        hosts = config_data.get("hosts")
        if IS_CLEAN:
            for host in hosts:
                log.info("Begin to clean sdb on {}".format(host.get("hostname")))
                clean_sdb(host)
            sys.exit(0)

        # 安装 sdb
        installed_hosts = set()
        clusters = get_cluster_info(config_data)
        for cluster in clusters:
            hosts_in_cluster = get_hosts_in_cluster(hosts, cluster)
            for host in hosts_in_cluster:
                if host.get("hostname") in SKIP_INSTALL_HOST:
                    continue
                if host.get("hostname") in installed_hosts:
                    continue
                installed_hosts.add(host.get("hostname"))
                log.info("Begin to install sdb on {}".format(host.get("hostname")))
                install_sdb(host, cluster['installPath'])

        # 部署 sdb
        for cluster in clusters:
            log.info("Begin to deploy sdb cluster.")
            hosts_in_cluster = get_hosts_in_cluster(hosts, cluster)
            deploy_sdb(hosts_in_cluster, cluster)

        # 生成部署信息
        generate_deploy_result(clusters)

    except Exception as e:
        log.exception("Failed to exec install_sdb.py: {}".format(e))
        raise e
