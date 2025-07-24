#!/usr/bin/python
# coding=utf-8
import getopt
import os
import sys
from collections import OrderedDict

import yaml
import time
import textwrap

from common.SSHConnection import SSHConnection
from common.LoggerUtil import get_logger
from common import Utils
from common import CommonDefine

reload(sys)
sys.setdefaultencoding('utf-8')

Utils.setup_yaml()
log = get_logger()

PACKAGE_FILE = ""
CONFIG = ""
SECTION = ""
DS_INFO_DIR = ""
IS_FORCE = False
IS_CLEAN = False
OUTPUT_FILE = ""
REMOTE_WORK_DIR = CommonDefine.REMOTE_WORK_DIR

SERVICES = [
    {"name": "gateway", "jvm_config_file": "sac-gateway/sac-gateway.vmoptions"},
    {"name": "registration", "jvm_config_file": "sac-registration-center/sac-registration-center.vmoptions"},
    {"name": "config", "jvm_config_file": "sac-config/sac-config.vmoptions"},
    {"name": "user", "jvm_config_file": "sac-user-center/sac-user-center.vmoptions"},
    {"name": "collector", "jvm_config_file": "sac-collector/sac-collector.vmoptions"},
    {"name": "monitor", "jvm_config_file": "sac-monitor/sac-monitor.vmoptions"},
    {"name": "deployment", "jvm_config_file": "sac-deployment/sac-deployment.vmoptions"},
    {"name": "alert", "jvm_config_file": "sac-alert/sac-alert.vmoptions"}
]


def display_and_exit():
    print("")
    print(" --help | -h                        : print help message")
    print(" --package           <arg>          : elf installation package path")
    print(" --config            <arg>          : localbuild config file path")
    print(" --section           <arg>          : sac config section name")
    print(" --dsinfo            <arg>          : dsinfo dir path")
    print(" --output | -o       <arg>          : output sac information path")
    print(" --clean                            : clean sac")
    print(" --force                            : force to install sac")

    sys.exit(0)


def parse_command():
    global PACKAGE_FILE, CONFIG, SECTION, DS_INFO_DIR, IS_FORCE, OUTPUT_FILE, IS_CLEAN
    try:
        options, args = getopt.getopt(sys.argv[1:], "ho:",
                                      ["help", "package=", "output=", "config=", "section=", "dsinfo=",
                                       "force", "clean"])
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
        elif name in "--dsinfo":
            DS_INFO_DIR = value
        elif name in "--force":
            IS_FORCE = True
        elif name in "--clean":
            IS_CLEAN = True

    if IS_CLEAN:
        if len(CONFIG.strip()) == 0 or not os.path.exists(CONFIG):
            raise Exception("Missing config file or config file is not exists!")
    else:
        if len(PACKAGE_FILE.strip()) == 0 or not os.path.exists(PACKAGE_FILE):
            raise Exception("Missing elf installation package or package file is not exists!")
        if len(CONFIG.strip()) == 0 or not os.path.exists(CONFIG):
            raise Exception("Missing config file or config file is not exists!")
        if len(SECTION.strip()) == 0:
            raise Exception("Missing sac section name!")
        if len(DS_INFO_DIR.strip()) == 0 or not os.path.exists(DS_INFO_DIR):
            raise Exception("Missing dsinfo dir or dsinfo dir is not exists!")
        if len(OUTPUT_FILE.strip()) == 0:
            raise Exception("Missing output file path!")


def load_config():
    with open(CONFIG) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def get_sac_section(config_info):
    section_info = Utils.get_section(config_info, SECTION)
    if section_info is None:
        raise Exception("Missing sac section!")
    return section_info


def get_sac_install_host_info(sac_section, hosts):
    hostname = sac_section.get("hostname")
    for host in hosts:
        if hostname == host.get("hostname"):
            return host
    raise Exception("Sac host is not declared in hosts section!")


def get_install_info(ssh):
    install_info = {
        "is_installed": False,
        "installed_path": ""
    }
    if ssh.is_file_exist("/etc/default/sequoiasac"):
        install_info['installed_path'] = \
            ssh.cmd("grep 'INSTALL_DIR' /etc/default/sequoiasac | awk -F'=' '{print $2}'", True)['stdout']
        install_info['is_installed'] = True
    return install_info


class SacDatabaseInfo:
    def __init__(self, username, password, urls):
        self.user = username
        self.password = password
        self.urls = urls


def install_sac(host, install_path):
    ssh = None
    remote_sac_run_file = os.path.join(REMOTE_WORK_DIR, PACKAGE_FILE.split(os.sep)[-1])
    try:
        ssh = SSHConnection(host=host['hostname'], user=host['user'], pwd=host['password'])
        Utils.ssh_send_package(ssh, PACKAGE_FILE, remote_sac_run_file)

        install_info = get_install_info(ssh)
        if not install_info['is_installed']:
            log.info("Installing sac")
            ssh.cmd("{} --mode unattended --prefix {}".format(remote_sac_run_file, install_path), True)
        else:
            old_install_path = install_info['installed_path']
            if IS_FORCE:
                log.info("Forcing uninstall and reinstall, please wait")
                clean_and_install(old_install_path, remote_sac_run_file, install_path, ssh)
            else:
                log.info("dds is exists!")
                while True:
                    print("Do you want uninstall and reinstall it ?(y/n):\n")
                    res = raw_input("Please enter your choice:")
                    if res == "Y" or res == "y":
                        log.info("uninstalling and reinstalling, please wait")
                        clean_and_install(old_install_path, remote_sac_run_file, install_path, ssh)
                        break
                    elif res == "N" or res == "n":
                        print("know your choice, exiting!")
                        sys.exit(0)
                    else:
                        print("I don't know your choice, please enter again")
                        continue
    finally:
        if ssh is not None:
            ssh.close()


def clean_and_install(old_install_path, remote_sac_run_file, install_path, ssh):
    # 清理 sac 集群
    do_clean_sac(old_install_path, ssh)

    # 安装 sac
    log.info("Installing sac")
    ssh.cmd("{} --mode unattended --prefix {}".format(remote_sac_run_file, install_path), True)


def do_clean_sac(install_path, ssh):
    if not ssh.is_file_exist(install_path):
        log.info("sac is not found in {}, skip clean".format(install_path))
        return
    log.info("Cleaning sac")
    ssh.cmd("{}/uninstall --mode unattended".format(install_path), True)
    ssh.cmd("rm -rf {}".format(install_path))
    Utils.kill_process(ssh, "sac.dir=" + install_path)


def prepare_jvm_config(install_path, config_template, sac_section, ssh):
    jvm_conf_dir = "{}/conf/samples/".format(install_path)
    for service in SERVICES:
        name = service['name']
        config_template['sacServer'][name]['port'] = sac_section['sacServer'][name]['port']
        if service['jvm_config_file'] is not None:
            jvm_config_file = jvm_conf_dir + service['jvm_config_file']
            custom_jvm_options = sac_section['sacServer'][name].get('jvmOptions', None)
            Utils.write_jvm_options(ssh, custom_jvm_options, jvm_config_file)


def prepare_deploy_config(install_path, sac_db_info, ssh):
    deploy_config_path = "{}/conf/deploy.yml".format(install_path)
    config_template = yaml.load(ssh.cmd("cat {}".format(deploy_config_path), True)['stdout'],
                                Loader=yaml.FullLoader)
    config_template['sacDatabase']['urls'] = sac_db_info.urls
    ssh.write_file(deploy_config_path, yaml.dump(config_template))
    return config_template


def get_sac_db_info():
    sac_db_section = yaml.load(open(CommonDefine.DSINFO_SAC_DB), Loader=yaml.FullLoader).get(
        'dds')
    username = None
    password = None
    urls = []
    if 'replicaMode' in sac_db_section:
        replica_mode = sac_db_section['replicaMode']
        if 'auth' in replica_mode:
            username = replica_mode['auth']['username']
            password = replica_mode['auth']['password']
        rpl = replica_mode['replset'][0]
        members = rpl['members']
        for member in members:
            urls.append(member['host'] + ":" + str(member['port']))
    elif 'shardMode' in sac_db_section:
        shard_mode = sac_db_section['shardMode']
        if 'auth' in shard_mode:
            username = shard_mode['auth']['username']
            password = shard_mode['auth']['password']
        routers = shard_mode['routers']
        for router in routers:
            urls.append(router['host'] + ":" + str(router['port']))
    else:
        raise Exception("Invalid sac database section!")

    return SacDatabaseInfo(username, password, urls)


def prepare_collect_policy(install_path, ssh):
    sdb_strategy_config_path = "{}/conf/default-collect-strategy.yml".format(install_path)
    local_sdb_strategy_config_path = CommonDefine.SDB_COLLECT_STRATEGY_PATH
    ssh.upload(local_sdb_strategy_config_path, sdb_strategy_config_path)

    dds_strategy_config_path = "{}/conf/default-dds-collect-strategy.yml".format(install_path)
    local_dds_strategy_config_path = CommonDefine.DDS_COLLECT_STRATEGY_PATH
    ssh.upload(local_dds_strategy_config_path, dds_strategy_config_path)


def deploy_sac(host, sac_section, sac_db_info):
    ssh = None
    try:
        ssh = SSHConnection(host=host['hostname'], user=host['user'], pwd=host['password'])
        install_path = sac_section['installPath']
        # 修改 sac 部署配置文件
        config_template = prepare_deploy_config(install_path, sac_db_info, ssh)
        # 修改采集策略
        prepare_collect_policy(install_path, ssh)
        # 修改 sac jvm 配置文件
        prepare_jvm_config(install_path, config_template, sac_section, ssh)
        # 部署 sac
        deploy_cmd = "{}/bin/sac_admin deploysac".format(install_path)
        if sac_db_info.user is not None and len(sac_db_info.user) > 0:
            deploy_cmd += " -u {} -p {}".format(sac_db_info.user,
                                                sac_db_info.password)
        res = ssh.cmd(deploy_cmd)
        if res['status'] != 0:
            raise Exception("Failed to deploy sac: {}".format(res['stderr']))
    finally:
        if ssh is not None:
            ssh.close()


def clean_sac(host):
    ssh = None
    try:
        ssh = SSHConnection(host=host['hostname'], user=host['user'], pwd=host['password'])
        install_info = get_install_info(ssh)
        if install_info['is_installed']:
            install_path = install_info['installed_path']
            do_clean_sac(install_path, ssh)
    finally:
        if ssh is not None:
            ssh.close()


def get_agent_install_path(ssh):
    cmd = "ps -ef | grep sequoiasac/sac-agent | grep -v grep | awk '{for(i=1;i<=NF;i++) if ($i ~ /^-Duser.dir=/) print substr($i,12)}'"
    res = ssh.cmd(cmd, True)['stdout'].strip()
    if len(res) == 0:
        return None
    return res


def clean_agent(host):
    ssh = None
    try:
        ssh = SSHConnection(host=host['hostname'], user=host['user'], pwd=host['password'])
        agent_install_path = get_agent_install_path(ssh)
        if agent_install_path is not None:
            ssh.cmd("{}/bin/sac_agent_ctl stop".format(agent_install_path), True)
            ssh.cmd("rm -rf {}".format(agent_install_path))
            ssh.cmd("su - sdbadmin -c 'rm -f ~/.sac/agent'")
            Utils.kill_process(ssh, agent_install_path, "sac-agent")
        else:
            ssh.cmd("rm -rf ~/sequoiasac")
    finally:
        if ssh is not None:
            ssh.close()


def get_dds_backup_agent_install_path(ssh):
    cmd = "su - sdbadmin -c \"cat ~/.sac/dds-backup-agent | grep ^INSTALL_DIR= | cut -d '=' -f 2\""
    res = ssh.cmd(cmd, True)['stdout'].strip()
    if len(res) == 0:
        return None
    return res


def clean_dds_backup_agent(host):
    ssh = None
    try:
        ssh = SSHConnection(host=host['hostname'], user=host['user'], pwd=host['password'])
        backup_agent_install_path = get_dds_backup_agent_install_path(ssh)
        if backup_agent_install_path is not None:
            ssh.cmd("su - sdbadmin -c '{}/bin/backup-agent-ctl stop --all'".format(backup_agent_install_path))
            ssh.cmd("su - sdbadmin -c 'bash {}/uninstall.sh'".format(backup_agent_install_path))
            ssh.cmd("su - sdbadmin -c 'rm -rf {}'".format(backup_agent_install_path))
            ssh.cmd("su - sdbadmin -c 'rm -f ~/.sac/dds-backup-agent'")
            Utils.kill_process(ssh, backup_agent_install_path, "dds-backup-agent")
    finally:
        if ssh is not None:
            ssh.close()

def add_server(host, sac_section, business_hosts):
    sac_host = host['hostname']
    gatewayPort = sac_section['sacServer']['gateway']['port']
    base_url = sac_host + ":" + str(gatewayPort)

    # 登录 SAC, 获取 token
    username = "admin"
    default_pwd_encrypt_with_md5 = Utils.encrypt_with_md5("Admin@1024")
    token = Utils.login(base_url, username, default_pwd_encrypt_with_md5)

    # 获取服务器信息
    rsa_pub_key = Utils.get_rsa_pub_key(base_url)
    # 转换成 PEM 格式
    pem_pub_key = "-----BEGIN PUBLIC KEY-----\n"
    pem_pub_key += '\n'.join(textwrap.wrap(rsa_pub_key, 64))
    pem_pub_key += "\n-----END PUBLIC KEY-----\n"
    default_pwd_encrypt_with_rsa = Utils.encrypt_with_rsa(pem_pub_key, "Admin@1024")
    host_info_list = [
        {
            "host": host["hostname"],
            'ssh_port': 22,
            "server_sac_username": "sdbadmin",
            "server_sac_user_group": "sdbadmin_group",
            "server_sac_password": default_pwd_encrypt_with_rsa,
            "server_sudo_username": host["user"],
            "server_sudo_password": Utils.encrypt_with_rsa(pem_pub_key, host['password']),
            "database_runtime_username": "sdbadmin",
            "database_runtime_user_group": "sdbadmin_group",
            "database_runtime_password": default_pwd_encrypt_with_rsa
        }
        for host in business_hosts
    ]
    params = {
        'create_database_runtime_user': True,
        'create_sac_runtime_user': True,
        'force_deploy_sac_agent': True,
        'host_info_list': host_info_list,
        'run_os_init': True,
        'sac_agent_port': 28081,
        'type': "server"
    }
    server_info_list = Utils.scan_servers(base_url, token, params)

    # 得到扫描失败的服务器信息并报错
    failed_hosts = [
        server_info['data'] for server_info in server_info_list if server_info['data']['errno'] != 0
    ]
    if failed_hosts:
        error_messages = []
        for host_info in failed_hosts:
            error_messages.append(
                '{ host: "%s", errno: %d, detail: "%s" }' % (
                    host_info['host'], host_info['errno'], host_info['detail']
                )
            )
        raise Exception("these hosts failed to scan: " + ", ".join(error_messages))

    for server_info in server_info_list:
        # 如果挂载路径为空，选根路径
        if not server_info['data']['mounts']:
            server_info['data']['mounts'].append("/")
        # 如果服务器类型为空，选物理服务器
        if server_info['data']['type'] is None:
            server_info['data']['type'] = 0

    # 添加服务器，获取任务ID
    for item1 in host_info_list:
        host1 = item1['host'].lower()
        for item2 in server_info_list:
            item2_data = item2['data']
            hostname2 = item2_data['hostname'].lower()
            if host1 == hostname2 or host1 in map(str, item2_data['ip']):
                item1['arch'] = item2_data['arch']
                item1['cpu_total_quota'] = item2_data['cpu_total_quota']
                item1['data_plane_address'] = item2_data['data_plane_address']
                item1['fenceid'] = item2_data['fenceid']
                item1['hostname'] = item2_data['hostname']
                item1['ip'] = item2_data['ip']
                item1['maintenance_plane_address'] = item2_data['maintenance_plane_address']
                item1['memory_total_quota'] = item2_data['memory_total_quota']
                item1['mounts'] = item2_data['mounts']
                item1['sac_agent_connect_address'] = item2_data['sac_agent_connect_address']
                item1['sac_agent_connect_port'] = item2_data['sac_agent_connect_port']
                item1['ssh_port'] = item2_data['ssh_port']
                item1['tags'] = item2_data['tags']
                item1['type'] = item2_data['type']
                item1['zone'] = item2_data['zone']
                break
        item1.pop('host', None)
        item1.pop('server_sac_username', None)
        item1.pop('server_sac_user_group', None)
        item1.pop('server_sac_password', None)

    params = {
        'create_database_runtime_user': True,
        'force_deploy_sac_agent': True,
        'host_info_list': host_info_list,
        'run_os_init': True,
        'sac_agent_port': 28081
    }
    tid = Utils.add_servers(base_url, token, params)

    # 每5秒查询一次任务进度，直至任务执行完成
    progress = {}
    while True:
        progress = Utils.get_task_progress(base_url, token, tid)
        status = progress['status']
        if status == "SUCCESS" or status == "FAILED":
            break
        time.sleep(5)

    log.debug("add servers log: {}".format(progress['log']))

    if progress['status'] != "SUCCESS":
        raise Exception("Failed to add server into sac")

def discover_cluster(host, sac_section):
    ssh = None
    try:
        ssh = SSHConnection(host=host['hostname'], user=host['user'], pwd=host['password'])
        sac_install_path = sac_section['installPath']
        # 1. 发现 sdb 集群
        if os.path.exists(CommonDefine.DSINFO_BUSINESS_DB_SDB):
            sdb_info = load_yml(CommonDefine.DSINFO_BUSINESS_DB_SDB)['sequoiadb']
            # 处理多个 sdb 集群的场景，只发现第一个
            if isinstance(sdb_info, list):
                sdb_info = sdb_info[0]
            discover_sdb_yml = generate_discover_yml(sac_section, sdb_info)
            discover_sdb_yml_remote_path = "{}/conf/discover.yml".format(sac_install_path)
            ssh.write_file(discover_sdb_yml_remote_path, yaml.dump(discover_sdb_yml))
            exec_discover_cmd(ssh, "sdb", sac_install_path, discover_sdb_yml_remote_path)
        # 2. 发现 dds 集群
        if os.path.exists(CommonDefine.DSINFO_BUSINESS_DB_DDS):
            dds_info = load_yml(CommonDefine.DSINFO_BUSINESS_DB_DDS)['dds']
            if 'replicaMode' in dds_info:
                discover_dds_yml = generate_discover_dds_yml(sac_section, dds_info['replicaMode'], "replicaMode")
                discover_dds_yml_remote_path = "{}/conf/discover-dds-repl.yml".format(sac_install_path)
                ssh.write_file(discover_dds_yml_remote_path, yaml.dump(discover_dds_yml))
                exec_discover_cmd(ssh, "dds", sac_install_path, discover_dds_yml_remote_path)
            if 'shardMode' in dds_info:
                discover_dds_yml = generate_discover_dds_yml(sac_section, dds_info['shardMode'], "shardMode")
                discover_dds_yml_remote_path = "{}/conf/discover-dds-shard.yml".format(sac_install_path)
                ssh.write_file(discover_dds_yml_remote_path, yaml.dump(discover_dds_yml))
                exec_discover_cmd(ssh, "dds", sac_install_path, discover_dds_yml_remote_path)
    finally:
        if ssh is not None:
            ssh.close()


def exec_discover_cmd(ssh, type, sac_install_path, config_file):
    cmd = "su - sdbadmin -c '{}/bin/sac_admin {} -c {} --sac-user admin --sac-passwd Admin@1024'".format(
        sac_install_path, "discover" if type == "sdb" else "discoverdds", config_file)
    ssh.cmd(cmd, True)


def generate_discover_yml(sac_section, sdb_info):
    discover_yml = {
        "clusterName": "sdb_cluster",
        "sac": {
            "gatewayUrl": "{}:{}".format(sac_section['hostname'], sac_section['sacServer']['gateway']['port']),
            "sslEnabled": False,
            "skipSqlBelongCheck": False,
        },
        "sequoiadb": {
            "storageEngine": {
                "coord": "{}:{}".format(sdb_info['coord'][0].get('hostname'), sdb_info['coord'][0].get('service')),
                "user": sdb_info['user'],
                "passwd": sdb_info['password']
            },
            "sqlInstanceGroups": []
        }
    }
    if os.path.exists(CommonDefine.DSINFO_BUSINESS_DB_MYSQL):
        mysql_info = load_yml(CommonDefine.DSINFO_BUSINESS_DB_MYSQL)['mysql'][0]
        mysql_node = mysql_info['nodes'][0]
        discover_yml['sequoiadb']['sqlInstanceGroups'].append({
            "user": mysql_info['user'],
            "passwd": mysql_info['password'],
            "sqlInstances": [{
                "address": "{}:{}".format(mysql_node['hostname'], mysql_node['port']),
            }]
        })
    if os.path.exists(CommonDefine.DSINFO_BUSINESS_DB_MARIADB):
        mariadb_info = load_yml(CommonDefine.DSINFO_BUSINESS_DB_MARIADB)['mariadb'][0]
        mariadb_node = mariadb_info['nodes'][0]
        discover_yml['sequoiadb']['sqlInstanceGroups'].append({
            "user": mariadb_info['user'],
            "passwd": mariadb_info['password'],
            "sqlInstances": [{
                "address": "{}:{}".format(mariadb_node['hostname'], mariadb_node['port']),
            }]
        })
    return discover_yml


def generate_discover_dds_yml(sac_section, dds_info, deploy_mode):
    if deploy_mode == "replicaMode":
        address = dds_info['primary']
    else:
        router = dds_info['routers']['members'][0]
        address = "{}:{}".format(router['host'], router['port'])

    return {
        "clusterName": "{}_cluster".format(deploy_mode),
        "sac": {
            "gatewayUrl": "{}:{}".format(sac_section['hostname'], sac_section['sacServer']['gateway']['port']),
            "sslEnabled": False,
        },
        "dds": {
            "address": address,
            "user": dds_info['auth']['username'],
            "passwd": dds_info['auth']['password']
        }
    }


def load_yml(file_path):
    with open(file_path) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def generate_sac_info(hosts, sac_section, config_info):
    log.info("Generate sac info: {}".format(OUTPUT_FILE))
    parent_directory = os.path.dirname(OUTPUT_FILE)
    if parent_directory and not os.path.exists(parent_directory):
        os.makedirs(parent_directory)
    sac_info = OrderedDict()
    sac_info['hosts'] = hosts
    sac_info['sac_database'] = OrderedDict()
    sac_info['sac_database'].update(load_yml(CommonDefine.DSINFO_SAC_DB))

    if os.path.exists(CommonDefine.DSINFO_BUSINESS_DB_ELF):
        sac_info.update(load_yml(CommonDefine.DSINFO_BUSINESS_DB_ELF))

    sac_info['business_database'] = OrderedDict()
    if os.path.exists(CommonDefine.DSINFO_BUSINESS_DB_SDB):
        sac_info['business_database'].update(load_yml(CommonDefine.DSINFO_BUSINESS_DB_SDB))

    if os.path.exists(CommonDefine.DSINFO_BUSINESS_DB_DDS):
        sac_info['business_database'].update(load_yml(CommonDefine.DSINFO_BUSINESS_DB_DDS))

    if os.path.exists(CommonDefine.DSINFO_BUSINESS_DB_MYSQL) or os.path.exists(CommonDefine.DSINFO_BUSINESS_DB_MARIADB):
        sac_info['business_database']['instances'] = OrderedDict()
        if os.path.exists(CommonDefine.DSINFO_BUSINESS_DB_MYSQL):
            sac_info['business_database']['instances'].update(load_yml(CommonDefine.DSINFO_BUSINESS_DB_MYSQL))
        if os.path.exists(CommonDefine.DSINFO_BUSINESS_DB_MARIADB):
            sac_info['business_database']['instances'].update(load_yml(CommonDefine.DSINFO_BUSINESS_DB_MARIADB))

    sac_info['sac'] = {
        "url": "http://{}:{}".format(sac_section['hostname'], sac_section['sacServer']['gateway']['port']),
        "installPath": sac_section['installPath']
    }
    sac_info['runtest'] = config_info.get("runtest")

    with open(OUTPUT_FILE, 'w') as f:
        f.write(yaml.dump(sac_info))


if __name__ == '__main__':
    try:
        parse_command()
        config_info = load_config()
        hosts = config_info.get("hosts")

        if IS_CLEAN:
            # 清理 sac 集群
            for host in hosts:
                log.info("Begin to clean sac agent on host {}".format(host['hostname']))
                clean_agent(host)

                log.info("Begin to clean dds backup agent on host {}".format(host['hostname']))
                clean_dds_backup_agent(host)

                log.info("Begin to clean sac on host {}".format(host['hostname']))
                clean_sac(host)

            sys.exit(0)

        sac_section = get_sac_section(config_info)
        sac_database_info = get_sac_db_info()
        install_host_info = get_sac_install_host_info(sac_section, hosts)

        # 安装 sac
        log.info("Begin to install sac on host {}".format(install_host_info['hostname']))
        install_sac(install_host_info, sac_section.get("installPath"))

        # 清理 agent
        for host in hosts:
            log.info("Begin to clean sac agent on host {}".format(host['hostname']))
            clean_agent(host)

        # 清理 dds_backup_agent
        for host in hosts:
            log.info("Begin to clean dds backup agent on host {}".format(host['hostname']))
            clean_dds_backup_agent(host)

        # 部署 sac
        log.info("Begin to deploy sac on host {}".format(install_host_info['hostname']))
        deploy_sac(install_host_info, sac_section, sac_database_info)

        # 添加服务器
        host_list = [
            host['hostname']
            for host in hosts
        ]
        log.info("Begin to add server into sac for hosts {}".format(host_list))
        add_server(install_host_info, sac_section, hosts)

        # 发现集群
        log.info("Begin to discover cluster")
        discover_cluster(install_host_info, sac_section)

        generate_sac_info(hosts, sac_section, config_info)



    except Exception as e:
        log.exception("Failed to exec install_sac.py:{}".format(e))
        raise e
