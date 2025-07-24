#!/usr/bin/python
# coding=utf-8
import getopt
import os
import sys

import yaml

from common.SSHConnection import SSHConnection
from common.LoggerUtil import get_logger
from common import Utils
from common import CommonDefine

Utils.setup_yaml()
log = get_logger()

PACKAGE_FILE = ""
CONFIG = ""
ELF_SECTION = ""
BUSINESS_SECTION = ""
IS_FORCE = False
IS_CLEAN = False
OUTPUT_FILE = ""
REMOTE_WORK_DIR = CommonDefine.REMOTE_WORK_DIR


def display_and_exit():
    print("")
    print(" --help | -h                        : print help message")
    print(" --package           <arg>          : elf installation package path")
    print(" --config            <arg>          : localbuild config file path")
    print(" --elf-section       <arg>          : elf config section name")
    print(" --business-section  <arg>          : business database config section name")
    print(" --output | -o       <arg>          : output elf information path")
    print(" --clean                            : clean elf")
    print(" --force                            : force to install elf")

    sys.exit(0)


def parse_command():
    global PACKAGE_FILE, CONFIG, ELF_SECTION, BUSINESS_SECTION, IS_FORCE, OUTPUT_FILE, IS_CLEAN
    try:
        options, args = getopt.getopt(sys.argv[1:], "ho:",
                                      ["help", "package=", "output=", "config=", "elf-section=", "business-section=",
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
        elif name in "--elf-section":
            ELF_SECTION = value
        elif name in "--business-section":
            BUSINESS_SECTION = value
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
        if len(ELF_SECTION.strip()) == 0:
            raise Exception("Missing elf section name!")
        if len(BUSINESS_SECTION.strip()) == 0:
            raise Exception("Missing business database section name!")
        if len(OUTPUT_FILE.strip()) == 0:
            raise Exception("Missing output file path!")


def load_config():
    with open(CONFIG) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def deploy_elf(host_info, elf_config):
    ssh = None
    remote_elf_package_file = os.path.join(REMOTE_WORK_DIR, PACKAGE_FILE.split(os.sep)[-1])
    try:
        ssh = SSHConnection(host=host_info['hostname'], user=host_info['user'], pwd=host_info['password'])
        Utils.ssh_send_package(ssh, PACKAGE_FILE, remote_elf_package_file, False)
        old_install_path = get_install_path(ssh)
        if old_install_path is None:
            do_deploy_elf(elf_config, remote_elf_package_file, ssh)
        else:
            def clean_and_deploy():
                do_clean_elf(ssh, old_install_path)
                do_deploy_elf(elf_config, remote_elf_package_file, ssh)

            if IS_FORCE:
                log.info("Forcing uninstall and reinstall, please wait")
                clean_and_deploy()

            else:
                log.info("dds is exists!")
                while True:
                    print("Do you want uninstall and reinstall it ?(y/n):\n")
                    res = raw_input("Please enter your choice:")
                    if res == "Y" or res == "y":
                        log.info("uninstalling and reinstalling ,please wait")
                        clean_and_deploy()
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


def do_deploy_elf(elf_config, remote_elf_package_file, ssh):
    install_path = elf_config.get("installPath")
    # 解压安装包
    log.info("Unpacking elf package to {}".format(install_path))
    ssh.cmd("rm -rf {}".format(install_path))
    ssh.cmd("mkdir -p {}".format(install_path))
    ssh.cmd("tar -zxf {} -C {}".format(remote_elf_package_file, install_path), True)
    ssh.cmd("mv {}/sequoiasac-elf/* {}".format(install_path, install_path))
    ssh.cmd("rm -rf {}/sequoiasac-elf".format(install_path))
    ssh.cmd("chown sdbadmin:sdbadmin_group -R {}".format(install_path), True)

    # 修改 elf 部署配置
    log.info("Writing elf deploy config")
    el_conf_file = "{}/config/el-deploy.yml".format(install_path)
    write_el_deploy_config(ssh, elf_config, el_conf_file)

    # 修改 es jvm 配置
    log.info("Writing elasticsearch jvm config")
    es_jvm_options = elf_config['elasticsearch'].get('jvmOptions', None)
    es_jvm_file = "{}/elasticsearch/config/jvm.options.d/jvm.options".format(install_path)
    Utils.write_jvm_options(ssh, es_jvm_options, es_jvm_file)

    # 修改 logstash jvm 配置
    log.info("Writing logstash jvm config")
    logstash_jvm_options = elf_config['logstash'].get('jvmOptions', None)
    logstash_jvm_file = "{}/logstash/config/jvm.options".format(install_path)
    Utils.write_jvm_options(ssh, logstash_jvm_options, logstash_jvm_file)

    # 部署集群
    log.info("Deploying elf")
    ssh.cmd("{}/bin/elf_admin deployel".format(install_path), True)


def write_filebeat_deploy_conf(ssh, sdb_cluster_info, filebeat_deploy_conf_file):
    conf = generate_filebeat_deploy_conf(sdb_cluster_info)
    ssh.write_file(filebeat_deploy_conf_file, conf, False)


def deploy_filebeat(host_info, sdb_cluster_info, el_install_path):
    ssh = None
    try:
        ssh = SSHConnection(host=host_info['hostname'], user=host_info['user'], pwd=host_info['password'])
        filebeat_deploy_conf_file = "{}/config/cluster-info.yml".format(el_install_path)
        write_filebeat_deploy_conf(ssh, sdb_cluster_info, filebeat_deploy_conf_file)
        deploy_cmd = "{}/bin/elf_admin deployfilebeat -c {}".format(el_install_path, filebeat_deploy_conf_file)
        ssh.cmd(deploy_cmd, True)
    finally:
        if ssh:
            ssh.close()


def do_clean_elf(ssh, install_path):
    if not ssh.is_file_exist(install_path):
        log.info("elf is not found in {}, skip clean".format(install_path))
        return
    log.info("Cleaning elf")
    # 清理集群
    ssh.cmd("{}/bin/elf_admin dropel".format(install_path), True)
    # 删除安装目录
    ssh.cmd("rm -rf {}".format(install_path))
    Utils.kill_process(ssh, install_path, "el_daemon")
    Utils.kill_process(ssh, install_path, "elasticsearch")
    Utils.kill_process(ssh, install_path, "logstash")


def clean_elf(host):
    ssh = None
    try:
        ssh = SSHConnection(host=host['hostname'], user=host['user'], pwd=host['password'])
        install_path = get_install_path(ssh)
        if install_path is not None:
            do_clean_elf(ssh, install_path)
    finally:
        if ssh:
            ssh.close()


def get_install_host(elf_config, hosts):
    host_info = None
    for host in hosts:
        if host.get("hostname") == elf_config.get("hostname"):
            host_info = host
    if host_info is None:
        raise Exception("Elf host is not declared in hosts section!")
    return host_info


def get_business_database(config_info):
    business_info = Utils.get_section(config_info, BUSINESS_SECTION)
    if business_info is None:
        raise Exception("Missing business database config!")
    return business_info


def get_install_path(ssh):
    cmd = """output=$(ps -ef | grep sequoiasac-elf | grep -v grep | grep -v bash); if [[ -z "$output" ]]; then echo ""; else echo $output | head -n 1 | awk '{print $8}' | xargs dirname | sed 's/\/sequoiasac-elf.*//'; fi """
    res = ssh.cmd(cmd, True)['stdout'].strip()
    if len(res) == 0 or res == '.':
        return None
    return res + "/sequoiasac-elf"


def write_el_deploy_config(ssh, elf_config, el_conf_file):
    conf_template_str = ssh.cmd("cat {}".format(el_conf_file))['stdout']
    conf_template = yaml.load(conf_template_str, Loader=yaml.FullLoader)
    conf_template['elasticsearch']['port'] = elf_config['elasticsearch']['port']
    conf_template['elasticsearch']['password'] = elf_config['elasticsearch']['password']
    conf_template['logstash']['port'] = elf_config['logstash']['port']
    ssh.cmd("echo '{}' > {}".format(yaml.dump(conf_template), el_conf_file), True)


class SdbClusterInfo:
    def __init__(self, coord, user, password):
        self.coord = coord
        self.user = user
        self.password = password
        self.sql_instances_group = []

    def set_coord(self, coord):
        self.coord = coord

    def set_user(self, user):
        self.user = user

    def set_password(self, password):
        self.password = password

    def add_sql_instances_group(self, sql_instances_group):
        self.sql_instances_group.append(sql_instances_group)


class SqlInstanceGroup:
    def __init__(self, group_name, user, password):
        self.group_name = group_name
        self.user = user
        self.password = password
        self.address = []

    def add_address(self, address):
        self.address.append(address)


def get_sql_instance_group(sdb, name):
    group_info = sdb.get("instances", {}).get(name, None)
    if group_info is not None:
        group = group_info.get("groupName")
        user = group_info.get("user")
        password = group_info.get("password")
        sql_instance_group = SqlInstanceGroup(group, user, password)
        nodes = group_info.get("nodes")
        for node in nodes:
            sql_instance_group.add_address(node.get("hostname") + ":" + str(node.get("port")))
        return sql_instance_group
    return None


def get_sdb_cluster_infos(sdb_section):
    sdb_clusters = []
    for sdb in sdb_section:
        coord = sdb.get("coord")[0].get("hostname") + ":" + str(sdb.get("coord")[0].get("service"))
        user = sdb.get("user", '')
        password = sdb.get("password", '')
        sdb_cluster_info = SdbClusterInfo(coord, user, password)
        mariadb = get_sql_instance_group(sdb, 'mariadb')
        if mariadb is not None:
            sdb_cluster_info.add_sql_instances_group(mariadb)
        mysql = get_sql_instance_group(sdb, 'mysql')
        if mysql is not None:
            sdb_cluster_info.add_sql_instances_group(mysql)
        sdb_clusters.append(sdb_cluster_info)
    return sdb_clusters


def generate_filebeat_deploy_conf(sdb_cluster):
    conf = {}
    conf['filebeat'] = {
        "sshPort": 22,
        "deployPath": "~/sequoiasac/filebeat",
        "maxProcess": 1
    }
    conf['sequoiadb'] = {}
    conf['sequoiadb']['storageEngine'] = {
        "coord": sdb_cluster.coord,
        "user": sdb_cluster.user,
        "password": sdb_cluster.password
    }
    conf['sequoiadb']['sqlInstanceGroups'] = []
    for sql_group in sdb_cluster.sql_instances_group:
        sql_group_conf = {
            "user": sql_group.user,
            "password": sql_group.password,
            "sqlGroupName": sql_group.group_name,
            "sqlInstances": [{"address": sql_group.address[0]}]
        }
        conf['sequoiadb']['sqlInstanceGroups'].append(sql_group_conf)
    return yaml.dump(conf)


def get_hosts_in_sdb_section(hosts, sdb_section):
    hosts_set = set()
    host_infos = []
    for sdb in sdb_section:
        for key in ["cata", "coord", "groups"]:
            for item in sdb.get(key):
                hosts_set.add(item.get("hostname"))
        if 'instances' not in sdb:
            continue
        instances = sdb.get("instances")
        for key in ["mariadb", "mysql"]:
            if key not in instances:
                continue
            group = instances.get(key, None)
            if group is None:
                continue
            for node in group.get("nodes"):
                hosts_set.add(node.get("hostname"))
    for host in hosts_set:
        match = False
        for host_info in hosts:
            if host == host_info.get("hostname"):
                match = True
                host_infos.append(host_info)
                break
        if not match:
            raise Exception("Host {} is not declared in hosts section!".format(host))
    return host_infos


def get_filebeat_install_path(ssh):
    cmd = """output=$(ps -ef | grep sequoiasac/filebeat/bin/filebeat | grep -v grep | grep -v bash); if [[ -z "$output" ]]; then echo ""; else echo $output | head -n 1 | awk '{print $8}' | sed 's|/bin/.*||'; fi"""
    res = ssh.cmd(cmd, True)['stdout'].strip()
    if len(res) == 0:
        return None
    return res


def clean_filebeat(host):
    ssh = None
    try:
        ssh = SSHConnection(host=host['hostname'], user=host['user'], pwd=host['password'])
        install_path = get_filebeat_install_path(ssh)
        if install_path is not None:
            ssh.cmd("{}/bin/filebeat_ctl stop".format(install_path), True)
            ssh.cmd("{}/tools/daemon/filebeat_daemon_ctl stop".format(install_path), True)
            ssh.cmd("rm -rf {}".format(install_path), True)
            Utils.kill_process(ssh, install_path, "filebeat")
        else:
            ssh.cmd("su - sdbadmin -c 'rm -rf ~/sequoiasac/filebeat'")
    finally:
        if ssh:
            ssh.close()


def generate_deploy_result(elf_config):
    log.info("Generate deploy result: {}".format(OUTPUT_FILE))
    parent_directory = os.path.dirname(OUTPUT_FILE)
    if parent_directory and not os.path.exists(parent_directory):
        os.makedirs(parent_directory)

    result = {}
    result['installPath'] = elf_config.get("installPath")
    result['host'] = elf_config.get("hostname")
    result['elasticsearch'] = {
        "port": elf_config.get("elasticsearch").get("port"),
        "password": elf_config.get("elasticsearch").get("password")
    }
    result['logstash'] = {
        "port": elf_config.get("logstash").get("port")
    }

    with open(OUTPUT_FILE, "w") as file:
        yaml.dump({'elf': result}, file)


def update_limits_conf(host_info):
    ssh = None
    try:
        local_file = os.path.join(CommonDefine.TOOLS_DIR, "update_limits_conf.sh")
        target_file = os.path.join(REMOTE_WORK_DIR, "update_limits_conf.sh")
        ssh = SSHConnection(host=host_info['hostname'], user=host_info['user'], pwd=host_info['password'])
        ssh.upload(local_file, target_file)
        ssh.cmd("bash {}".format(target_file))
    finally:
        if ssh:
            ssh.close()


if __name__ == '__main__':
    try:
        parse_command()
        config_info = load_config()
        hosts = config_info.get("hosts")

        if IS_CLEAN:
            for host in hosts:
                log.info("Begin to clean elf on {}".format(host.get("hostname")))
                clean_elf(host)
                clean_filebeat(host)
            sys.exit(0)

        sdb_section = get_business_database(config_info).get("sequoiadb")  # 目前仅支持采集 sdb 日志
        sdb_cluster_infos = get_sdb_cluster_infos(sdb_section)
        hosts_in_sdb = get_hosts_in_sdb_section(hosts, sdb_section)
        elf_config = Utils.get_section(config_info, ELF_SECTION)
        if elf_config is None:
            log.error("Missing elf config, skip to install elf!")
            sys.exit(0)

        # 部署 elf
        host_info = get_install_host(elf_config, hosts)
        log.info("Begin to deploy elf on {}".format(host_info.get("hostname")))
        # 更新 limits 配置，dds 部署时可能会修改 limits 配置
        update_limits_conf(host_info)
        deploy_elf(host_info, elf_config)

        # 部署 filebeat
        for host in hosts_in_sdb:
            clean_filebeat(host)
        for sdb_cluster_info in sdb_cluster_infos:
            deploy_filebeat(host_info, sdb_cluster_info, elf_config.get("installPath"))

        # 生成部署信息
        generate_deploy_result(elf_config)
    except Exception as e:
        log.exception("Failed to exec install_elf.py: {}".format(e))
        raise e
