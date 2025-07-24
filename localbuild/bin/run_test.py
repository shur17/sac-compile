#!/usr/bin/python
# coding=utf-8
import getopt
import json
import os
import platform
import socket
import subprocess
import sys

import yaml

from common import LoggerUtil
from common import Utils, CommonDefine, CmdExecutor, PackageManager
from common.SSHConnection import SSHConnection

Utils.setup_yaml()
log = LoggerUtil.get_logger()
cmd_executor = CmdExecutor.CmdExecutor(False)

SAC_INFO_FILE = ""
TESTCASES = ""
IS_FORCE_UPDATE_TESTCASE = False
INSTALL_SHELL = False
IS_RUNBASE = False

TESTCASES_GIT_URL = "http://gitlab.sequoiadb.com/test/sac-auto-test.git"
BRANCH = "master"
TESTCASES_HOME = CommonDefine.TESTCASE_DIR

def display_and_exit():
    print("")
    print(" --help | -h                    : print help message")
    print(" --sac-info      <arg>          : sac information file path ")
    print(" --testcases     <arg>          : testcases")
    print(" --runbase                      : runbase")
    print(" --branch | -b   <arg>          : specify the branch of the test repository to pull")
    print(" --install-shell                : install database shell")
    print(" --force-update-testcase        : force update test project")
    sys.exit(0)


def parse_command():
    global SAC_INFO_FILE, TESTCASES, IS_RUNBASE, BRANCH, IS_FORCE_UPDATE_TESTCASE, INSTALL_SHELL
    try:
        options, args = getopt.getopt(sys.argv[1:], "h",
                                      ["help", "runbase", "force-update-testcase", "sac-info=", "testcases=", "branch=", "b=", "install-shell"])
    except getopt.GetoptError, e:
        log.error(e, exc_info=True)
        sys.exit(-1)

    for name, value in options:
        if name in ("-h", "--help"):
            display_and_exit()
        elif name in "--sac-info":
            SAC_INFO_FILE = value
        elif name in "--testcases":
            TESTCASES = value
        elif name in "--runbase":
            IS_RUNBASE = True
        if name in ("-b", "--branch"):
            BRANCH = value
        elif name in "--force-update-testcase":
            IS_FORCE_UPDATE_TESTCASE = True
        elif name in "--install-shell":
            INSTALL_SHELL = True

    if len(SAC_INFO_FILE.strip()) == 0 or not os.path.exists(SAC_INFO_FILE):
        raise Exception("Sac info file is not exist")

    if TESTCASES and IS_RUNBASE:
        raise Exception("--runbase can't be used with --testcases")

    if BRANCH is None or BRANCH.strip() == "":
        raise Exception("--branch | -b parameter value can't be empty")


def update_test_config(path, changes):
    # 读取文件内容
    with open(path, 'r') as file:
        lines = file.readlines()

    # 替换键值对
    new_lines = []
    for line in lines:
        for key, value in changes.items():
            # 找到键，并获取前导空格
            key_index = line.find(key + ":")
            if key_index != -1:
                leading_spaces = line[:key_index]
                # 根据值的类型确定是否需要引号
                formatted_value = "'{}'".format(value) if isinstance(value, basestring) else str(value)
                new_line = "{}{}: {},\n".format(leading_spaces, key, formatted_value)
                line = new_line
                break
        new_lines.append(line)

    # 写回文件
    with open(path, 'w') as file:
        file.writelines(new_lines)

def update_test_configs():
    TESTCASES_CONFIG = ""
    # 更新 ELF 配置文件
    testcase_elf_config = get_testcase_elf_config(sac_info)
    TESTCASES_CONFIG = os.path.join(TESTCASES_HOME, "src", "config", "logConfig.ts")
    update_test_config(TESTCASES_CONFIG, testcase_elf_config)

    # 更新 replset 配置文件
    testcase_repl_config = get_testcase_repl_config(sac_info)
    TESTCASES_CONFIG = os.path.join(TESTCASES_HOME, "src", "config", "replConfig.ts")
    update_test_config(TESTCASES_CONFIG, testcase_repl_config)

    # 更新 shard 配置文件
    testcase_shard_config = get_testcase_shard_config(sac_info)
    TESTCASES_CONFIG = os.path.join(TESTCASES_HOME, "src", "config", "shardConfig.ts")
    update_test_config(TESTCASES_CONFIG, testcase_shard_config)

    # 更新 sac 配置文件
    testcase_sac_config = get_testcase_sac_config(sac_info)
    TESTCASES_CONFIG = os.path.join(TESTCASES_HOME, "src", "config", "sacConfig.ts")
    update_test_config(TESTCASES_CONFIG, testcase_sac_config)

    # 更新 sdb 配置文件
    testcase_sdb_config = get_testcase_sdb_config(sac_info)
    TESTCASES_CONFIG = os.path.join(TESTCASES_HOME, "src", "config", "sdbConfig.ts")
    update_test_config(TESTCASES_CONFIG, testcase_sdb_config)

def get_sdb_info(sdb_section):
    host = sdb_section.get("coord")[0].get("hostname")
    coord_port = sdb_section.get("coord")[0].get("service")
    cata_port = sdb_section.get("cata")[0].get("service")
    user = sdb_section.get("user", "")
    password = sdb_section.get("password", "")
    return BusinessSDBInfo(host, coord_port, cata_port, user, password)


def get_dds_conn_info(dds_section):
    username = ""
    password = ""
    host = None
    port = None
    if 'replicaMode' in dds_section:
        replica_mode = dds_section['replicaMode']
        if 'auth' in replica_mode:
            username = replica_mode['auth']['username']
            password = replica_mode['auth']['password']
        rpl = replica_mode['replset'][0]
        member = rpl['members'][0]
        host = member['host']
        port = member['port']

    elif 'shardMode' in dds_section:
        shard_mode = dds_section['shardMode']
        if 'auth' in shard_mode:
            username = shard_mode['auth']['username']
            password = shard_mode['auth']['password']
        routers = shard_mode['routers']
        host = routers[0]['host']
        port = routers[0]['port']
    else:
        raise Exception("Invalid sac database section!")
    return DdsConnInfo(host, port, username, password)

def get_db_section(sac_info, section_key):
    db_section = Utils.get_section(sac_info, section_key)
    # 如果部署了多套集群，只获取第一套集群的信息
    if isinstance(db_section, list):
        db_section = db_section[0]
    return db_section


def get_instances_info(sac_info):
    business_section = sac_info['business_database']
    if 'instances' not in business_section:
        return None
    instances_info = InstancesInfo()
    if 'mysql' in business_section['instances']:
        mysql_section = business_section['instances']['mysql']
        if isinstance(mysql_section, list):
            mysql_section = mysql_section[0]
        instances_info.mysql_group = mysql_section['groupName']
        instances_info.user = mysql_section['user']
        instances_info.password = mysql_section['password']
        instance_url = mysql_section['nodes'][0]['hostname'] + ':' + str(mysql_section['nodes'][0]['port'])
        instances_info.instances.append(instance_url)
        instances_info.mysql_port = mysql_section['nodes'][0]['port']

    if 'mariadb' in business_section['instances']:
        mariadb_section = business_section['instances']['mariadb']
        if isinstance(mariadb_section, list):
            mariadb_section = mariadb_section[0]
        instances_info.mariadb_group = mariadb_section['groupName']
        instances_info.user = mariadb_section['user']
        instances_info.password = mariadb_section['password']
        instance_url = mariadb_section['nodes'][0]['hostname'] + ':' + str(mariadb_section['nodes'][0]['port'])
        instances_info.instances.append(instance_url)
        instances_info.mariadb_port = mariadb_section['nodes'][0]['port']
    return instances_info


def get_dds_info(dds_section):
    if dds_section is None or len(dds_section) == 0:
        return None
    dds_info = DDSInfo()
    repl_section = dds_section.get("replicaMode") if "replicaMode" in dds_section else None
    if repl_section is not None and len(repl_section) > 0:
        dds_info.repl_master = repl_section.get("primary", "")
        if 'auth' in repl_section and 'username' in repl_section['auth'] and 'password' in repl_section['auth']:
            dds_info.repl_user = repl_section['auth']['username']
            dds_info.repl_password = repl_section['auth']['password']
        if 'auth' in repl_section and 'rootUser' in repl_section['auth'] and 'rootPassword' in repl_section['auth']:
            dds_info.repl_root_user = repl_section['auth']['rootUser']
            dds_info.repl_root_password = repl_section['auth']['rootPassword']

    shard_section = dds_section.get("shardMode") if "shardMode" in dds_section else None
    if shard_section is not None and len(shard_section) > 0:
        node = shard_section.get('routers').get('members')[0].get('host') + ":" + str(shard_section.get('routers').get('members')[0].get('port'))
        dds_info.shard_node = node
        if 'auth' in shard_section and 'username' in shard_section['auth'] and 'password' in shard_section['auth']:
            dds_info.shard_user = shard_section['auth']['username']
            dds_info.shard_password = shard_section['auth']['password']
        if 'auth' in shard_section and 'rootUser' in shard_section['auth'] and 'rootPassword' in shard_section['auth']:
            dds_info.shard_root_user = shard_section['auth']['rootUser']
            dds_info.shard_root_password = shard_section['auth']['rootPassword']
        if 'replset' in shard_section and len(shard_section) > 0:
            for repl in shard_section['replset']:
                repl_name = repl['replName']
                is_config_server = repl.get('configSvr', False)
                if is_config_server:
                    dds_info.shard_config_service_name = repl_name
                elif dds_info.shard_data_service_name is None:
                    dds_info.shard_data_service_name = repl_name
    return dds_info


def get_mysql_single_instance_info(sac_info):
    instance_info = {
        'host': '',
        'port': '',
        'user': '',
        'password': ''
    }
    instances = sac_info['business_database']['instances']
    if 'mysql' in instances:
        mysql_section = instances['mysql']
        for mysql in mysql_section:
            if 'label' in mysql and mysql['label'] == 'singleMysqlInstance':
                instance_info['host'] = mysql['nodes'][0]['hostname']
                instance_info['port'] = mysql['nodes'][0]['port']
                instance_info['user'] = mysql['user']
                instance_info['password'] = mysql['password']
                return instance_info
    return None


def get_repl_service_name(sac_info):
    dds_info = Utils.get_section(sac_info, CommonDefine.SECTION_BUSINESS_DB_DDS)
    if dds_info is not None:
        repl_section = dds_info.get("replicaMode") if "replicaMode" in dds_info else None
        if repl_section is not None:
            return repl_section.get("replset")[0]['replName']
    return None

def get_testcase_sac_config(sac_info):
    changes = {}
    base_url = sac_info['sac']['url'] + '/api'
    sac_host = base_url.split('//')[1].split(':')[0]
    changes['baseURL'] = base_url
    changes['sacIp'] = sac_host
    changes['sacPath'] = sac_info['sac']['installPath']

    sac_db_info = get_dds_conn_info(get_db_section(sac_info, CommonDefine.SECTION_SAC_DB))
    changes['sacDBHost'] = sac_db_info.host
    changes['sacDBPort'] = sac_db_info.port
    changes['dbUsername'] = sac_db_info.user
    changes['dbPassword'] = sac_db_info.password

    if 'runtest' in sac_info:
        runtest_config = sac_info['runtest']
        if 'dds' in runtest_config:
            changes['dbPath'] = os.path.join(runtest_config['dds']['installPath'], 'bin', 'mongosh')
    return changes

def get_testcase_repl_config(sac_info):
    changes = {}
    dds_info = get_dds_info(Utils.get_section(sac_info, CommonDefine.SECTION_BUSINESS_DB_DDS))
    if dds_info is not None:
        if dds_info.repl_master is not None:
            changes['hostIp'] = dds_info.repl_master.split(':')[0]
            changes['port'] = int(dds_info.repl_master.split(':')[1])
        if dds_info.repl_user is not None:
            changes['dbUsername'] = dds_info.repl_user
        if dds_info.repl_password is not None:
            changes['dbPassword'] = dds_info.repl_password
        if dds_info.repl_root_user is not None:
            changes['dbRootUser'] = dds_info.repl_root_user
        if dds_info.repl_root_password is not None:
            changes['dbRootPassword'] = dds_info.repl_root_password

    if 'runtest' in sac_info:
        runtest_config = sac_info['runtest']
        if 'dds' in runtest_config:
            changes['dbPath'] = os.path.join(runtest_config['dds']['installPath'], 'bin', 'mongosh')

    repl_service_name = get_repl_service_name(sac_info)
    if repl_service_name is not None:
        changes['serviceName'] = repl_service_name
    return changes

def get_testcase_shard_config(sac_info):
    changes = {}
    dds_info = get_dds_info(Utils.get_section(sac_info, CommonDefine.SECTION_BUSINESS_DB_DDS))
    if dds_info is not None:
        if dds_info.shard_router_service_name is not None:
            changes['routerServiceName'] = dds_info.shard_router_service_name
        if dds_info.shard_config_service_name is not None:
            changes['configServiceName'] = dds_info.shard_config_service_name
        if dds_info.shard_data_service_name is not None:
            changes['dataServiceName'] = dds_info.shard_data_service_name
        if dds_info.shard_node is not None:
            changes['hostIp'] = dds_info.shard_node.split(':')[0]
            changes['port'] = int(dds_info.shard_node.split(':')[1])
        if dds_info.shard_user is not None:
            changes['dbUsername'] = dds_info.shard_user
        if dds_info.shard_password is not None:
            changes['dbPassword'] = dds_info.shard_password
        if dds_info.shard_root_user is not None:
            changes['dbRootUser'] = dds_info.shard_root_user
        if dds_info.shard_root_password is not None:
            changes['dbRootPassword'] = dds_info.shard_root_password

    if 'runtest' in sac_info:
        runtest_config = sac_info['runtest']
        if 'dds' in runtest_config:
            changes['dbPath'] = os.path.join(runtest_config['dds']['installPath'], 'bin', 'mongosh')
    return changes

def get_testcase_sdb_config(sac_info):
    changes = {}
    biz_sdb_info = get_sdb_info(get_db_section(sac_info, CommonDefine.SECTION_BUSINESS_DB_SDB))
    changes['hostIp'] = biz_sdb_info.host
    changes['coord'] = biz_sdb_info.coord
    changes['catalog'] = biz_sdb_info.cata
    changes['dbUsername'] = biz_sdb_info.user
    changes['dbPassword'] = biz_sdb_info.password

    instances_info = get_instances_info(sac_info)
    if instances_info is not None:
        if instances_info.mysql_group is not None:
            changes['mysqlInstanceGroup'] = instances_info.mysql_group
            changes['mysqlPort'] = instances_info.mysql_port
        if instances_info.mariadb_group is not None:
            changes['mariaInstanceGroup'] = instances_info.mariadb_group
            changes['mariadbPort'] = instances_info.mariadb_port
        changes['instanceUsername'] = instances_info.user
        changes['instancePassword'] = instances_info.password
        changes['instanceGroup'] = instances_info.instances
    if 'runtest' in sac_info:
        runtest_config = sac_info['runtest']
        if 'sequoiadb' in runtest_config:
            changes['dbPath'] = os.path.join(runtest_config['sequoiadb']['installPath'], 'bin', 'sdb')
        if 'mysql' in runtest_config:
            changes['mysqlPath'] = os.path.join(runtest_config['mysql']['installPath'], 'bin')
        if 'mariadb' in runtest_config:
            changes['mariadbPath'] = os.path.join(runtest_config['mariadb']['installPath'], 'bin')

    changes['testCaseIp'] = socket.gethostbyname(socket.gethostname())
    mysql_single_instance_info = get_mysql_single_instance_info(sac_info)
    if mysql_single_instance_info is not None:
        changes['singleSqlInstanceHost'] = mysql_single_instance_info['host']
        changes['singleSqlInstancePort'] = mysql_single_instance_info['port']
        changes['singleSqlInstanceUsername'] = mysql_single_instance_info['user']
        changes['singleSqlInstancePassword'] = mysql_single_instance_info['password']
    return changes

def get_testcase_elf_config(sac_info):
    changes = {}
    elf_section = Utils.get_section(sac_info, CommonDefine.SECTION_BUSINESS_DB_ELF)
    if elf_section is not None:
        changes["elfPath"] = elf_section.get("installPath")
        changes["elfHost"] = elf_section.get("host")
        changes["esPassword"] = elf_section.get("elasticsearch").get("password")
        changes["esPort"] = elf_section.get("elasticsearch").get("port")
        changes["logstashPort"] = elf_section.get("logstash").get("port")
    return changes

class BusinessSDBInfo:
    def __init__(self, host, coord, cata, user, password):
        self.host = host
        self.coord = coord
        self.cata = cata
        self.user = user
        self.password = password

class DdsConnInfo:
    def __init__(self, host, port, user, password):
        self.host = host
        self.port = port
        self.user = user
        self.password = password


class InstancesInfo:
    def __init__(self):
        self.mysql_group = None
        self.mysql_port = None
        self.mariadb_group = None
        self.mariadb_port = None
        # 任意一个实例的用户名和密码
        self.user = None
        self.password = None
        # mysql 和 mariadb 中的任意一个实例
        self.instances = []


class DDSInfo:
    def __init__(self):
        self.repl_master = None
        self.repl_user = None
        self.repl_password = None
        self.repl_root_user = None
        self.repl_root_password = None

        self.shard_node = None
        self.shard_user = None
        self.shard_password = None
        self.shard_root_user = None
        self.shard_root_password = None
        # dds 部署工具不支持配置 routers 服务名，默认值固定为 router service
        self.shard_router_service_name = 'router service'
        self.shard_config_service_name = None
        self.shard_data_service_name = None


def parse_string_to_dicts(s):
    last_brace_index = s.rfind('}')
    begin_index = s.find('{')
    s = s[begin_index:last_brace_index + 1]

    parts = s.strip().split('}\n{')

    cleaned_parts = []
    for part in parts:
        if not part.startswith('{'):
            part = '{' + part
        if not part.endswith('}'):
            part += '}'
        cleaned_parts.append(part)

    dicts = []
    for part in cleaned_parts:
        item = json.loads(part)
        if len(item) > 0:
            dicts.append(item)
    return dicts


def get_cluster_node_name(ssh, sac_db_info, cid):
    cmd = """ /opt/sequoiadb/bin/sdb "db=new Sdb('{}',{},'{}','{}');db.sequoiasac_sys.node.find({{cid:{}}}, {{node_name:''}}).limit(1)" """.format(
        sac_db_info.host, sac_db_info.coord, sac_db_info.user, sac_db_info.password, cid)
    result = ssh.cmd(cmd, True)['stdout'].strip()
    return parse_string_to_dicts(result)[0]['node_name']


def get_host_info_from_hosts(hosts, host_name):
    for host_info in hosts:
        if host_info['hostname'] == host_name:
            return host_info
    raise Exception("Host {} is not declared in hosts section of the sac.yml".format(host_name))


def get_dds_cluster_mode(node, hosts):
    host, port = node.split(':')
    host_info = get_host_info_from_hosts(hosts, host)
    ssh = None
    try:
        ssh = SSHConnection(host=host_info['hostname'], user=host_info['user'], pwd=host_info['password'])
        cmd = """ /opt/sequoiadds/bin/mongosh --port {} --eval "db.isMaster()" """.format(port)
        result = ssh.cmd(cmd, True)['stdout'].strip()
        if 'configsvr' in result:
            return "shard"
        return "replica"
    finally:
        if ssh is not None:
            ssh.close()


def exec_test():
    cmd = 'bash -c "' + os.path.join(TESTCASES_HOME, 'runtest.sh')
    cmd_suffix = '{}"'.format(TESTCASES) if TESTCASES else '"'
    cmd += ' base"' if IS_RUNBASE else cmd_suffix
    if platform.system() == 'Windows':
        log.warn("Current system is windows, failed to exec test: {}".format(cmd))
    else:
        subprocess.call(cmd, shell=True)


def need_install(current_install_info, install_config, pacakge_path):
    if not current_install_info['is_installed']:
        return True
    current_install_path = current_install_info['installed_path']
    install_path = install_config['installPath']
    if not Utils.path_equals(current_install_path, install_path):
        log.info("Install path is not equals, need install: current={}, config={}".format(current_install_path,
                                                                                          install_path))
        return True
    current_md5 = current_install_info['md5']
    md5 = Utils.get_file_md5(pacakge_path)
    if current_md5 != md5:
        log.info("Package md5 is not equals, need install: current={}, package={}".format(current_md5, md5))
        return True
    return False


def check_and_install_shells(runtest_config):
    if runtest_config is None:
        return
    sdb_install_info = Utils.get_install_info("/etc/default/sequoiadb")
    if 'sequoiadb' in runtest_config:
        if need_install(sdb_install_info, runtest_config['sequoiadb'], PackageManager.get_sdb_package()):
            log.info("Sdb shell is not exist, install it")
            install_path = runtest_config['sequoiadb']['installPath']
            cmd = "python {} --package {} --install-path {} --install-local --force".format(
                os.path.join(CommonDefine.BIN_DIR, 'install_sdb.py'),
                PackageManager.get_sdb_package(), install_path)
            cmd_executor.command(cmd)
            sdb_install_info = Utils.get_install_info("/etc/default/sequoiadb")
        else:
            log.info("Sdb shell is exist, skip install")

    mysql_install_info = Utils.get_install_info("/etc/default/sequoiasql-mysql")
    if 'mysql' in runtest_config:
        if need_install(mysql_install_info, runtest_config['mysql'],
                        PackageManager.get_mysql_package()):
            log.info("Mysql shell is not exist, install it")
            install_path = runtest_config['mysql']['installPath']
            cmd = "python {} --package {} --install-path {} --install-local --force".format(
                os.path.join(CommonDefine.BIN_DIR, 'install_mysql.py'),
                PackageManager.get_mysql_package(), install_path)
            cmd_executor.command(cmd)
            mysql_install_info = Utils.get_install_info("/etc/default/sequoiasql-mysql")
        else:
            log.info("Mysql shell is exist, skip install")

    mariadb_install_info = Utils.get_install_info("/etc/default/sequoiasql-mariadb")
    if 'mariadb' in runtest_config:
        if need_install(mariadb_install_info, runtest_config['mariadb'],
                        PackageManager.get_mariadb_package()):
            log.info("Mariadb shell is not exist, install it")
            install_path = runtest_config['mariadb']['installPath']
            cmd = "python {} --package {} --install-path {} --install-local --force".format(
                os.path.join(CommonDefine.BIN_DIR, 'install_mariadb.py'),
                PackageManager.get_mariadb_package(), install_path)
            cmd_executor.command(cmd)
            mariadb_install_info = Utils.get_install_info("/etc/default/sequoiasql-mariadb")
        else:
            log.info("Mariadb shell is exist, skip install")

    dds_install_info = Utils.get_install_info("/etc/default/sequoiadb-dds")
    if 'dds' in runtest_config:
        if need_install(dds_install_info, runtest_config['dds'],
                        PackageManager.get_dds_package()):
            log.info("DDS shell is not exist, install it")
            install_path = runtest_config['dds']['installPath']
            cmd = "python {} --package {} --install-path {} --install-local --force".format(
                os.path.join(CommonDefine.BIN_DIR, 'install_dds.py'),
                PackageManager.get_dds_package(), install_path)
            cmd_executor.command(cmd)
            dds_install_info = Utils.get_install_info("/etc/default/sequoiadb-dds")
        else:
            log.info("DDS shell is exist, skip install")

    install_info = {
        'sequoiadb': sdb_install_info,
        'mysql': mysql_install_info,
        'mariadb': mariadb_install_info,
        'dds': dds_install_info
    }
    return install_info


if __name__ == '__main__':
    try:
        parse_command()
        sac_info = yaml.load(open(SAC_INFO_FILE, 'r'), Loader=yaml.FullLoader)
        if INSTALL_SHELL and 'runtest' in sac_info:
            check_and_install_shells(sac_info['runtest'])
            sys.exit(0)

        testcases_clone_cmd = "git clone -b {} {} {}".format(BRANCH, TESTCASES_GIT_URL, CommonDefine.TESTCASE_DIR)

        if not os.path.exists(CommonDefine.TESTCASE_DIR):
            log.info("Testcases is not exist, pull from git")
            cmd_executor.command(testcases_clone_cmd)
        else:
            if IS_FORCE_UPDATE_TESTCASE:
                log.info("Force update testcases")
                cmd_executor.command("rm -rf {}".format(CommonDefine.TESTCASE_DIR))
                cmd_executor.command(testcases_clone_cmd)
            else:
                log.info("Testcases is exist, skip pull from git")

        log.info("Init testcase config")
        update_test_configs()

        log.info("Begin to run test")
        exec_test()
    except Exception as e:
        log.exception("Failed to exec run_test.py: {}".format(e))
        raise e
