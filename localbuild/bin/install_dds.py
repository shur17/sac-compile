#!/usr/bin/python
# coding=utf-8
import getopt
import glob
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time

import yaml

from common.SSHConnection import SSHConnection
from common.LoggerUtil import get_logger
from common import Utils
from common import CommonDefine
from common.CmdExecutor import CmdExecutor

Utils.setup_yaml()
log = get_logger()

cmd_executor = CmdExecutor(False)

TOOL_UNTAR_DIR = os.path.join(CommonDefine.WORK_DIR, "sdb-dds-cc")

PACKAGE_FILE = ""
CONFIG = ""
SECTION = ""
IS_FORCE = False
IS_CLEAN = False
OUTPUT_FILE = ""
IS_INSTALL_LOCAL = False
INSTALL_PATH = None
SKIP_INSTALL_HOST = []

DEFAULT_INSTALL_PATH = "/opt/sequoiadds"
REMOTE_WORK_DIR = CommonDefine.REMOTE_WORK_DIR


def display_and_exit():
    print("")
    print(" --help | -h                    : print help message")
    print(" --package       <arg>          : dds installation package path")
    print(" --config        <arg>          : config file path")
    print(" --section       <arg>          : dds config section name")
    print(" --output | -o   <arg>          : output dds information path")
    print(" --clean                        : clean dds")
    print(" --force                        : force to install dds")
    print(" --skip-install-host            : skip install sdb on host list")
    print(" --install-local                : install dds locally only")
    sys.exit(0)


def parse_command():
    global PACKAGE_FILE, CONFIG, SECTION, IS_FORCE, OUTPUT_FILE, IS_CLEAN, IS_INSTALL_LOCAL, INSTALL_PATH, SKIP_INSTALL_HOST
    try:
        options, args = getopt.getopt(sys.argv[1:], "h:o:",
                                      ["help", "package=", "output=", "config=", "section=", "force", "clean",
                                       "install-local", "install-path=", "skip-install-host="])
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
        elif name in "--install-path":
            INSTALL_PATH = value
        elif name in "--skip-install-host":
            SKIP_INSTALL_HOST = value.split(",")

    if IS_CLEAN:
        if len(CONFIG.strip()) == 0 or not os.path.exists(CONFIG):
            raise Exception("Missing config file or config file is not exists!")
    elif IS_INSTALL_LOCAL:
        if len(PACKAGE_FILE.strip()) == 0 or not os.path.exists(PACKAGE_FILE):
            raise Exception("Missing dds installation package or package file is not exists!")
    else:
        if len(PACKAGE_FILE.strip()) == 0 or not os.path.exists(PACKAGE_FILE):
            raise Exception("Missing dds installation package or package file is not exists!")
        if len(CONFIG.strip()) == 0 or not os.path.exists(CONFIG):
            raise Exception("Missing config file or config file is not exists!")
        if len(SECTION.strip()) == 0:
            raise Exception("Missing config section name!")
        if len(OUTPUT_FILE.strip()) == 0:
            raise Exception("Missing output file path!")


def load_config():
    with open(CONFIG) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def clean_dds(host):
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


def get_dds_info(config_info):
    dds_info = Utils.get_section(config_info, SECTION)
    if dds_info is None or len(dds_info) == 0:
        return None, None
    if INSTALL_PATH is None:
        install_path = dds_info.get("installPath", DEFAULT_INSTALL_PATH)
    else:
        install_path = INSTALL_PATH
    replica_dds = dds_info.get("replicaMode", None)
    shard_dds = dds_info.get("shardMode", None)
    return install_path, replica_dds, shard_dds


def get_install_hosts(hosts, replica_dds, shard_dds):
    install_hosts = []
    host_names = Utils.get_dds_install_hosts(replica_dds, shard_dds)

    for hostname in host_names:
        match = False
        for host in hosts:
            if host.get("hostname") == hostname:
                install_hosts.append(host)
                match = True
                break
        if not match:
            raise Exception("Can not find dds host {} in hosts section".format(hostname))
    return install_hosts


def get_install_info(ssh):
    install_info = {
        "is_installed": False,
        "installed_path": ""
    }
    if ssh.is_file_exist("/etc/default/sequoiadb-dds"):
        install_info['installed_path'] = \
            ssh.cmd("grep 'INSTALL_DIR' /etc/default/sequoiadb-dds | awk -F'=' '{print $2}'", True)['stdout']
        install_info['is_installed'] = True
    return install_info


def clean_and_install(old_install_path, remote_dds_run_file, install_path, ssh):
    do_clean(old_install_path, ssh)
    log.info("Installing dds")
    ssh.cmd("{} --mode unattended --prefix {}".format(remote_dds_run_file, install_path), True)


def do_clean(old_install_path, ssh):
    if not ssh.is_file_exist(old_install_path):
        log.info("dds is not found in {}, skip clean".format(old_install_path))
        return
    log.info("Cleaning dds")
    ssh.cmd("{}/bin/sdb_dds_ctl stop --all --force".format(old_install_path), True)
    ssh.cmd("{}/uninstall --mode unattended".format(old_install_path), True)
    ssh.cmd("rm -rf {}".format(old_install_path))
    Utils.kill_process(ssh, old_install_path, "sequoiadb-dds-guard")
    Utils.kill_process(ssh, old_install_path, "bin/mongod")
    Utils.kill_process(ssh, old_install_path, "bin/mongos")


def install_dds(host, install_path):
    ssh = None
    remote_dds_run_file = os.path.join(REMOTE_WORK_DIR, PACKAGE_FILE.split(os.sep)[-1])
    try:
        ssh = SSHConnection(host=host['hostname'], user=host['user'], pwd=host['password'])
        Utils.ssh_send_package(ssh, PACKAGE_FILE, remote_dds_run_file)
        install_info = get_install_info(ssh)

        if not install_info['is_installed']:
            log.info("Installing dds")
            ssh.cmd("{} --mode unattended --prefix {}".format(remote_dds_run_file, install_path), True)
        else:
            old_install_path = install_info['installed_path']
            if IS_FORCE:
                log.info("Forcing uninstall and reinstall, please wait")
                clean_and_install(old_install_path, remote_dds_run_file, install_path, ssh)
            else:
                log.info("dds is exists!")
                while True:
                    print("Do you want uninstall and reinstall it ?(y/n):\n")
                    res = raw_input("Please enter your choice:")
                    if res == "Y" or res == "y":
                        log.info("uninstalling and reinstalling, please wait")
                        clean_and_install(old_install_path, remote_dds_run_file, install_path, ssh)
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


def get_global_config(deploy_config):
    global_config = {}
    global_config['user'] = "sdbadmin"
    global_config['sshPort'] = 22
    if 'auth' in deploy_config:
        security = {}
        security['enabled'] = True
        security['keyfilePath'] = deploy_config.get("auth").get("keyFile")
        security['createKeyfile'] = True
        global_config['security'] = security
    return {'global': global_config}


def write_config_file(config, filename):
    file_path = os.path.join(TOOL_UNTAR_DIR, filename)
    with open(file_path, "w") as file:
        yaml.dump(config, file)


def do_deploy(config_file_name):
    cmd = 'su - sdbadmin -c' + '"' + os.path.join(TOOL_UNTAR_DIR, "sdb-dds-cc -c") + " " + os.path.join(TOOL_UNTAR_DIR,
                                                                                                        config_file_name) + '"'
    subprocess.check_call(cmd, shell=True)


def get_master_node(node, install_hosts, install_path):
    host = node.get('host')
    port = node.get('port')
    host_info = next((item for item in install_hosts if item.get("hostname") == host))
    ssh = None
    try:
        ssh = SSHConnection(host=host_info['hostname'], user=host_info['user'], pwd=host_info['password'])
        retry_count = 0
        while retry_count < 60:
            cmd = """
                {}/bin/mongosh --quiet --port {}  --eval 'rs.isMaster()'
                """.format(install_path, port)
            res = ssh.cmd(cmd, True)
            if res['status'] != 0:
                raise Exception("Failed to get replica master node!")
            result = res['stdout']
            match = re.search(r"primary:\s*'([^']+)'", result)
            primary_ip_port = match.group(1).replace("'", "") if match else None
            if primary_ip_port is None:
                retry_count += 1
                time.sleep(1)
                continue
            return {
                'host': primary_ip_port.split(":")[0],
                'port': int(primary_ip_port.split(":")[1])
            }
        raise Exception("Replica master node is not exists")
    finally:
        if ssh:
            ssh.close()


def deploy_replica_dds(replica_dds, hosts, install_path):
    install_hosts = get_install_hosts(hosts, replica_dds, None)
    deploy_dds(replica_dds, "replica", install_hosts, install_path)
    nodes = get_node_in_ever_replica(replica_dds)
    primary_node = get_master_node(nodes[0], install_hosts, install_path)
    primary = primary_node.get('host') + ":" + str(primary_node.get('port'))
    replica_dds['primary'] = str(primary)


def deploy_shard_dds(shard_dds, hosts, install_path):
    install_hosts = get_install_hosts(hosts, None, shard_dds)
    deploy_dds(shard_dds, "shard", install_hosts, install_path)


def get_any_dds_node(dds_deploy_config):
    if 'routers' in dds_deploy_config:
        node = dds_deploy_config.get('routers')[0]
        return node.get('host'), node.get('port')
    if 'replset' in dds_deploy_config:
        node = dds_deploy_config.get('replset')[0].get('members')[0]
        return node.get('host'), node.get('port')


def get_node_in_ever_replica(dds_deploy_config):
    res = []
    if 'routers' in dds_deploy_config:
        node = dds_deploy_config.get('routers').get('members')[0]
        res.append({
            'host': node.get('host'),
            'port': node.get('port'),
            'is_router': True
        })
    replset = dds_deploy_config.get('replset')
    for repl in replset:
        member = repl.get('members')[0]
        is_config_server = True if repl.get('configSvr', False) else False
        res.append({
            'host': member.get('host'),
            'port': member.get('port'),
            'is_config_server': is_config_server,
        })
    return res


def create_super_user(auth, node, install_hosts, install_path):
    host = node.get('host')
    port = node.get('port')
    root_user = auth.get("rootUser")
    root_pwd = auth.get("rootPassword")
    host_info = next((item for item in install_hosts if item.get("hostname") == host))
    ssh = None
    try:
        ssh = SSHConnection(host=host_info['hostname'], user=host_info['user'], pwd=host_info['password'])
        cmd = install_path + """/bin/mongosh --quiet  --port ${port} --eval '
                db.getSiblingDB("admin").createUser({
                    user: "${root_user}",
                    pwd: "${root_pwd}",
                    roles: ["userAdminAnyDatabase", "root"]
                })
            '
            """
        cmd = cmd.replace("${port}", str(port)).replace("${root_user}", root_user).replace("${root_pwd}", root_pwd)
        ssh.cmd(cmd, True)
    finally:
        if ssh:
            ssh.close()


def create_sac_role_and_user_for_node(auth, node, install_hosts, install_path):
    host = node.get('host')
    port = node.get('port')
    username = auth.get("username")
    password = auth.get("password")
    sac_maintainer_user = auth.get("sacMaintainerUser")
    sac_maintainer_password = auth.get("sacMaintainerPassword")
    sac_backup_user = auth.get("sacBackupUser")
    sac_backup_password = auth.get("sacBackupPassword")
    root_user = auth.get("rootUser")
    root_pwd = auth.get("rootPassword")
    host_info = next((item for item in install_hosts if item.get("hostname") == host))
    ssh = None
    try:
        ssh = SSHConnection(host=host_info['hostname'], user=host_info['user'], pwd=host_info['password'])
        cmd = install_path + """/bin/mongosh --quiet  --port ${port} --username ${root_user} --password ${root_pwd} --eval 'db.getSiblingDB("admin").createRole({
                role: "sac_monitor",
                privileges: [
                    {
                        resource: {cluster: true},
                        actions:["listDatabases","serverStatus", "getShardMap", "getParameter", "replSetGetStatus", "getCmdLineOpts", "getLog", "top"]
                    },
                    {
                        resource: {db: "", collection: "" },
                        actions:["listCollections", "dbStats", "collStats"]
                    },
                    {
                        resource: {db: "config", collection: ""  },
                        actions:["find", "listCollections", "dbStats", "collStats"]
                    },
                    {
                        resource: {db: "local", collection: "" },
                        actions:["listCollections", "dbStats", "collStats"]
                    },
                    {
                        resource: {db: "local", collection: "oplog.rs" },
                        actions:["find"]
                    },
                    {
                        resource: {db: "local", collection: "replset.election" },
                        actions:["collStats", "find"]
                    },
                    {
                        resource: {db: "local", collection: "replset.initialSyncId" },
                        actions:["collStats", "find"]
                    },
                    {
                        resource: {db: "local", collection: "replset.minvalid" },
                        actions:["collStats", "find"]
                    },
                    {
                        resource: {db: "local", collection: "replset.oplogTruncateAfterPoint" },
                        actions:["collStats", "find"]
                    },
                    {
                        resource: {db: "admin", collection: "" },
                        actions:["listCollections", "dbStats", "collStats"]
                    },
                    {
                        resource: { db: "", collection: "system.profile" },
                        actions:["find", "collStats"]
                    },
                    {
                        resource: { db: "", collection: "" },
                        actions: ["find"]
                    }
                ],
                roles:[]
            })'
            """
        cmd = cmd.replace("${port}", str(port)).replace("${root_user}", root_user).replace("${root_pwd}", root_pwd)
        ssh.cmd(cmd, True)
        cmd = install_path + """/bin/mongosh --quiet --port ${port} --username ${root_user} --password ${root_pwd} --eval '
                db.getSiblingDB("admin").createUser({
                    user: "${username}",
                    pwd: "${password}",
                    roles: ["sac_monitor"]
                })
            '
            """
        cmd = cmd.replace("${port}", str(port)).replace("${username}", username).replace("${password}",
                                                                                         password).replace(
            "${root_user}", root_user).replace("${root_pwd}", root_pwd)
        ssh.cmd(cmd, True)

        cmd = install_path + """/bin/mongosh --quiet  --port ${port} --username ${root_user} --password ${root_pwd} --eval 'db.getSiblingDB("admin").createRole({
               role: "sac_maintainer",
               privileges: [
                   {
                       resource: {cluster: true},
                       actions: [ "setParameter", "killop", "inprog", "replSetGetStatus", "replSetGetConfig", "replSetConfigure", "replSetStateChange" ]
                   },
                   {
                       resource: { db: "", collection: "" },
                       actions: [ "killCursors", "indexStats" ]
                   }
               ],
               roles:[{ "role": "userAdminAnyDatabase", "db": "admin" }]
            })'
            """
        cmd = cmd.replace("${port}", str(port)).replace("${root_user}", root_user).replace("${root_pwd}", root_pwd)
        ssh.cmd(cmd, True)
        cmd = install_path + """/bin/mongosh --quiet --port ${port} --username ${root_user} --password ${root_pwd} --eval '
                db.getSiblingDB("admin").createUser({
                    user: "${sac_maintainer_user}",
                    pwd: "${sac_maintainer_password}",
                    roles: ["sac_maintainer"]
                })
            '
            """
        cmd = cmd.replace("${port}", str(port)).replace("${sac_maintainer_user}", sac_maintainer_user).replace("${sac_maintainer_password}",
                  sac_maintainer_password).replace("${root_user}", root_user).replace("${root_pwd}", root_pwd)
        ssh.cmd(cmd, True)

        cmd = install_path + """/bin/mongosh --quiet  --port ${port} --username ${root_user} --password ${root_pwd} --eval  'db.getSiblingDB("admin").createRole({
               role: "sac_backup",
               privileges: [
                   {
                        resource: { anyResource: true },
                        actions: ["fsync"]
                   },
                   {
                       resource: { cluster: true },
                       actions: [
                           "getCmdLineOpts",
                           "getParameter",
                           "internal",
                           "getShardMap",
                           "replSetGetStatus",
                           "replSetGetConfig"
                       ]
                   },
                   {
                       resource: { db: "admin", collection: "system.version" },
                       actions: ["find"]
                   },
                   {
                       resource: { db: "config", collection: "shards" },
                       actions: ["find"]
                   },
                   {
                       resource: { db: "config", collection: "transactions" },
                       actions: ["find"]
                   },
                   {
                       resource: { db: "local", collection: "oplog.rs" },
                       actions: ["find"]
                   }
               ],
               roles: []
            })'
            """
        cmd = cmd.replace("${port}", str(port)).replace("${root_user}", root_user).replace("${root_pwd}", root_pwd)
        ssh.cmd(cmd, True)
        cmd = install_path + """/bin/mongosh --quiet --port ${port} --username ${root_user} --password ${root_pwd} --eval '
                db.getSiblingDB("admin").createUser({
                    user: "${sac_backup_user}",
                    pwd: "${sac_backup_password}",
                    roles: [ { "role": "sac_backup", "db":"admin" } ]
                })
            '
            """
        cmd = cmd.replace("${port}", str(port)).replace("${sac_backup_user}", sac_backup_user).replace("${sac_backup_password}",
                  sac_backup_password).replace("${root_user}", root_user).replace("${root_pwd}", root_pwd)
        ssh.cmd(cmd, True)
    finally:
        if ssh:
            ssh.close()

def wait_primary_writeable(node, install_hosts, install_path):
    host = node.get('host')
    port = node.get('port')
    host_info = next((item for item in install_hosts if item.get("hostname") == host))
    ssh = None
    try:
        ssh = SSHConnection(host=host_info['hostname'], user=host_info['user'], pwd=host_info['password'])
        while True:
            cmd = install_path + """/bin/mongosh --quiet --port ${port} --eval '
                    db.hello().isWritablePrimary
                 '
                """
            cmd = cmd.replace("${port}", str(port))
            res = ssh.cmd(cmd, True)['stdout']
            if 'true' in res:
                break
    finally:
        if ssh:
            ssh.close()


def create_role_and_user(auth, dds_deploy_config, install_hosts, dds_type, install_path):
    if 'username' not in auth or 'password' not in auth:
        return
    log.info("Creating user {} for dds".format(auth.get("username")))
    nodes = get_node_in_ever_replica(dds_deploy_config)
    if dds_type == 'replica':
        node = get_master_node(nodes[0], install_hosts, install_path)
        wait_primary_writeable(node, install_hosts, install_path)
        create_super_user(auth, node, install_hosts, install_path)
        create_sac_role_and_user_for_node(auth, node, install_hosts, install_path)
    else:
        for node in nodes:
            if node.get('is_config_server'):
                continue
            if not node.get('is_router'):
                node = get_master_node(node, install_hosts, install_path)
            wait_primary_writeable(node, install_hosts, install_path)
            create_super_user(auth, node, install_hosts, install_path)
            create_sac_role_and_user_for_node(auth, node, install_hosts, install_path)


def deploy_dds(dds_deploy_config, dds_type, install_hosts, install_path):
    # 生成配置文件
    config = {}
    config.update(get_global_config(dds_deploy_config))
    auth = dds_deploy_config.get("auth", None)
    if auth is not None:
        del dds_deploy_config['auth']
    config.update(dds_deploy_config)

    # 写入配置文件
    write_config_file(config, "{}.yml".format(dds_type))

    # 执行部署
    do_deploy("{}.yml".format(dds_type))

    # 创建用户
    if auth is not None:
        create_role_and_user(auth, dds_deploy_config, install_hosts, dds_type, install_path)
        dds_deploy_config['auth'] = auth


def prepare_dds_deploy_tool():
    # 解压部署工具
    if os.path.exists(TOOL_UNTAR_DIR):
        shutil.rmtree(TOOL_UNTAR_DIR)
    os.makedirs(TOOL_UNTAR_DIR)
    sdb_dds_cc_paths = glob.glob(os.path.join(CommonDefine.PACKAGE_DIR, "sdb-dds-cc_v*.tar.gz"))
    if len(sdb_dds_cc_paths) == 0:
        raise Exception("Can not find dds deploy tool in {}".format(CommonDefine.PACKAGE_DIR))
    with tarfile.open(sdb_dds_cc_paths[0], 'r:gz') as tar_ref:
        for member in tar_ref.getmembers():
            # Skip the top-level directory name
            if '/' in member.name:
                # Get the path without the top-level directory
                member_path = '/'.join(member.name.split('/')[1:])
                # Set the member's name to the new path
                member.name = member_path
                print(member)
                # Extract the member
                tar_ref.extract(member, TOOL_UNTAR_DIR)


def remove_fields(data, fields):
    if isinstance(data, dict):
        return {k: remove_fields(v, fields) for k, v in data.items() if k not in fields}
    elif isinstance(data, list):
        return [remove_fields(i, fields) for i in data]
    else:
        return data


def generate_deploy_result(replica_dds, shard_dds):
    log.info("Generate deploy result: {}".format(OUTPUT_FILE))
    parent_directory = os.path.dirname(OUTPUT_FILE)
    if parent_directory and not os.path.exists(parent_directory):
        os.makedirs(parent_directory)
    dds_info = {}
    if replica_dds is not None:
        dds_info["replicaMode"] = replica_dds
    if shard_dds is not None:
        dds_info["shardMode"] = shard_dds

    dds_info = remove_fields(dds_info, ['dbPath', 'systemLog'])
    yml_info = {"dds": dds_info}
    with open(OUTPUT_FILE, "w") as file:
        yaml.dump(yml_info, file)


def install_dds_local():
    if platform.system() == "Windows":
        raise Exception("Not support install dds on windows")
    dds_install_info = Utils.get_install_info("/etc/default/sequoiadb-dds")
    if dds_install_info['is_installed']:
        if IS_FORCE:
            log.info("DDS is installed, force to reinstall")
            cmd_executor.command("{}/bin/sdb_dds_ctl stop --all --force".format(dds_install_info['installed_path']))
            cmd_executor.command("{}/uninstall --mode unattended".format(dds_install_info['installed_path']))
            cmd_executor.command("rm -rf {}".format(dds_install_info['installed_path']))
        else:
            log.info("DDS is installed, skip install")
            return
    install_path = INSTALL_PATH if INSTALL_PATH is not None else DEFAULT_INSTALL_PATH
    cmd_executor.command("chmod +x {}".format(PACKAGE_FILE))
    cmd_executor.command("{} --mode unattended --prefix {}".format(PACKAGE_FILE, install_path))


if __name__ == '__main__':
    try:
        parse_command()
        if IS_INSTALL_LOCAL:
            install_dds_local()
            sys.exit(0)

        config_info = load_config()
        hosts = config_info.get("hosts")
        if IS_CLEAN:
            for host in hosts:
                log.info("Begin to clean dds on {}".format(host.get("hostname")))
                clean_dds(host)
            sys.exit(0)

        install_path, replica_dds, shard_dds = get_dds_info(config_info)
        install_hosts = get_install_hosts(hosts, replica_dds, shard_dds)
        if len(install_hosts) == 0:
            log.info("No dds host to install")
            sys.exit(0)

        # 安装 dds
        for host in install_hosts:
            if host.get("hostname") in SKIP_INSTALL_HOST:
                continue
            log.info("Begin to install dds on {}".format(host.get("hostname")))
            install_dds(host, install_path)

        # 准备 dds 部署工具
        prepare_dds_deploy_tool()

        # 部署 dds
        if replica_dds is not None:
            log.info("Begin to deploy replica dds")
            deploy_replica_dds(replica_dds, hosts, install_path)

        if shard_dds is not None:
            log.info("Begin to deploy shard dds")
            deploy_shard_dds(shard_dds, hosts, install_path)

        #  生成部署信息
        generate_deploy_result(replica_dds, shard_dds)

    except Exception as e:
        log.exception("Failed to exec install_dds.py: {}".format(e))
        raise e
