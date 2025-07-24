#!/usr/bin/python
# coding=utf-8
import getopt
import os
import paramiko
import sys
import yaml

from common import CommonDefine, Utils
from common.SSHConnection import SSHConnection
from common.LoggerUtil import get_logger
from common.CmdExecutor import CmdExecutor

Utils.setup_yaml()
log = get_logger()

cmd_executor = CmdExecutor(False)

"""
Parameters
"""
HOST_LIST = []
SSH_INFO_FILE = ""

"""
Global Variables - SSH
"""
ROOT_USER = "root"
SDB_USER = "sdbadmin"
SDB_USER_GROUP = "sdbadmin_group"
SSH_KEY_FILENAME = "id_rsa"
SSH_PUB_KEY_FILENAME = "id_rsa.pub"


def display_and_exit():
    print("")
    print(" --help | -h                    : print help message")
    print(" --config        <arg>          : config file path")
    print(" --host          <arg>          : hostname, use ',' to split multiple hosts")
    sys.exit(0)


def parse_command():
    global HOST_LIST, SSH_INFO_FILE
    try:
        options, args = getopt.getopt(sys.argv[1:], "h:o:", ["help", "host=", "config="])
    except getopt.GetoptError, e:
        log.error(e, exc_info=True)
        sys.exit(-1)

    for name, value in options:
        if name in ("-h", "--help"):
            display_and_exit()
        elif name in "--host":
            HOST_LIST = value.split(',')
        elif name in "--config":
            SSH_INFO_FILE = value

    if len(HOST_LIST) == 0:
        raise Exception("Missing --host parameter")

    if len(SSH_INFO_FILE) == 0 or not os.path.exists(SSH_INFO_FILE):
        raise Exception("Missing --config parameter or file not exist")


def check_host_environment(host_list, ssh_info_map, ssh_client_map):
    # 1、检查用户配置的 ssh 主机密码是否正确
    check_and_create_user(host_list, ssh_info_map, ssh_client_map)
    # 2、配置主机之间的互信
    check_and_setup_ssh_trust(host_list, ssh_client_map)
    # 3、配置主机之间的 host 映射
    check_and_config_host_mapping(host_list, ssh_client_map)


def check_and_create_user(host_list, ssh_info_map, ssh_client_map):
    # 1. 校验 root 用户 ssh 密码是否正确
    for host in host_list:
        ssh_password = ssh_info_map[host][ROOT_USER]
        ssh = SSHConnection(host=host, user=ROOT_USER, pwd=ssh_password)
        ssh_client_map.setdefault(host, {})
        ssh_client_map[host][ROOT_USER] = ssh

    # 2. 检查 sdbadmin 用户是否存在，不存在则创建
    for host in host_list:
        ssh = ssh_client_map[host][ROOT_USER]
        is_sdb_user_exist = ssh.cmd('id -u {}'.format(SDB_USER))['status'] == 0
        is_sdb_user_group_exist = ssh.cmd('getent group {}'.format(SDB_USER_GROUP))['status'] == 0

        if not is_sdb_user_group_exist:
            log.info("Group {} not exists, create it".format(SDB_USER_GROUP))
            ssh.cmd('groupadd {}'.format(SDB_USER_GROUP), True)

        if not is_sdb_user_exist:
            log.info("User {} not exists on host {}, create it".format(SDB_USER, host))
            ssh.cmd('useradd -g {} {}'.format(SDB_USER_GROUP, SDB_USER), True)
            ssh.cmd('echo "{}:{}" | chpasswd'.format(SDB_USER, "Admin@1024"), True)

        ssh.cmd("chown -R {}:{} /home/{}/".format(SDB_USER, SDB_USER_GROUP, SDB_USER), True)

    # 3. 校验 sdbadmin 用户 ssh 密码是否正确
    for host in host_list:
        ssh_password = ssh_info_map[host][SDB_USER]
        ssh = SSHConnection(host=host, user=SDB_USER, pwd=ssh_password)
        ssh_client_map[host][SDB_USER] = ssh


def check_and_setup_ssh_trust(host_list, ssh_client_map):
    # 1. 配置脚本执行机与部署机的 root 用户免密登录
    local_ssh_key_dir = os.path.expanduser("~/.ssh")
    local_ssh_key_file = os.path.join(local_ssh_key_dir, SSH_KEY_FILENAME)
    local_ssh_pub_key_file = os.path.join(local_ssh_key_dir, SSH_PUB_KEY_FILENAME)
    if not os.path.exists(local_ssh_pub_key_file):
        cmd_executor.command("ssh-keygen -t rsa -P '' -f {} -y > {}".format(
            local_ssh_key_file, local_ssh_pub_key_file))

    for deploy_host in host_list:
        root_nopassword = cmd_executor.command(
            "ssh -o 'passwordauthentication=no' -o 'StrictHostKeyChecking=no' {}@{} echo 'SSH connection is OK.'".format(
                ROOT_USER, deploy_host), False) == 0
        if not root_nopassword:
            log.info("Secret-free login for {} failed, setup trust for host: {}".format(ROOT_USER, deploy_host))
            setup_trust(local_ssh_pub_key_file, ROOT_USER, deploy_host, ssh_client_map)

    # 2. 配置部署机之间的 sdbadmin 用户免密登录
    for deploy_host in host_list:
        ssh = ssh_client_map[deploy_host][SDB_USER]
        ssh_key_dir = os.path.join(get_remote_user_home_dir(SDB_USER, ssh), ".ssh")
        ssh_key_file = os.path.join(ssh_key_dir, SSH_KEY_FILENAME)
        ssh_pub_key_file = os.path.join(ssh_key_dir, SSH_PUB_KEY_FILENAME)
        if not ssh.is_file_exist(ssh_pub_key_file):
            ssh.cmd('ssh-keygen -t rsa -P "" -f {} -y > {}'.format(ssh_key_file, ssh_pub_key_file))

        for remote_host in host_list:
            check_trust_cmd = "ssh -o 'passwordauthentication=no' -o 'StrictHostKeyChecking=no' {}@{} echo 'SSH connection is OK.'".format(
                SDB_USER, remote_host)
            res = ssh.cmd(check_trust_cmd)

            if res['status'] == 0:
                continue

            if "Permission denied" in res['stderr'] or "Host key verification failed" in res['stderr']:
                log.info("Secret-free login for {} failed, setup trust host {} to {}".format(
                    SDB_USER, deploy_host, remote_host))
                setup_trust_remotely(ssh, ssh_pub_key_file, remote_host, SDB_USER, ssh_client_map)
                # 检查互信配置是否生效
                ssh.cmd(check_trust_cmd, True)
            else:
                raise Exception("SSH connection failed, host: {}, error: {}".format(remote_host, res['stderr']))


def setup_trust_remotely(ssh, ssh_pub_key_file, remote_host, remote_user, ssh_client_map):
    if not os.path.exists(CommonDefine.WORK_DIR):
        cmd_executor.command("mkdir -p {}".format(CommonDefine.WORK_DIR))
    tmp_pub_key_file = os.path.join(CommonDefine.WORK_DIR, SSH_PUB_KEY_FILENAME)
    ssh.download(ssh_pub_key_file, tmp_pub_key_file)
    setup_trust(tmp_pub_key_file, remote_user, remote_host, ssh_client_map)


def get_remote_user_home_dir(remote_user, ssh):
    get_user_detail_cmd = "getent passwd {}".format(remote_user)
    ssh_user_detail = ssh.cmd(get_user_detail_cmd, True)['stdout']
    ssh_user_home_dir = ssh_user_detail.split(":")[5]
    return ssh_user_home_dir


def setup_trust(ssh_pub_key_file, ssh_user, remote_host, ssh_client_map):
    with open(ssh_pub_key_file, 'r') as f:
        local_pub_Key = f.read()

    ssh = ssh_client_map[remote_host][ssh_user]
    remote_ssh_path = os.path.join(get_remote_user_home_dir(ssh_user, ssh), ".ssh")
    remote_ssh_auth_key_file = os.path.join(remote_ssh_path, "authorized_keys")

    ssh.makedirs(remote_ssh_path)
    ssh.write_file(remote_ssh_auth_key_file, local_pub_Key, True)
    ssh.cmd("chmod 700 {}".format(remote_ssh_path))
    ssh.cmd("chmod 600 {}".format(remote_ssh_auth_key_file))


def check_and_config_host_mapping(host_list, ssh_client_map):
    host_name_map = {}
    host_ip_map = {}
    for host in host_list:
        ssh = ssh_client_map[host][ROOT_USER]
        host_name_map[host] = ssh.get_hostname()
        host_ip_map[host] = ssh.get_host_ip()

    for host in host_list:
        ssh = ssh_client_map[host][ROOT_USER]
        for remote_host in host_list:
            remote_host_name = host_name_map[remote_host]
            remote_host_ping_success = ssh.cmd("ping -c 1 -W 1 {}".format(remote_host_name))['status'] == 0
            if not remote_host_ping_success:
                log.info('Failed to ping {} to {}, config host mapping'.format(host, remote_host))
                ssh.cmd('echo "{} {}" >> /etc/hosts'.format(host_ip_map[remote_host], remote_host_name), True)


def generate_ssh_info(host_list, ssh_info_file):
    ssh_info_map = {}
    """
    ssh_info_map: {
        "192.168.31.9": {
            "root": "sequoiadb",
            "sdbadmin": "Admin@1024"
        }
    }
    """
    default_root_password = "sequoiadb"
    default_sdb_password = "Admin@1024"

    # 1. 读取密码配置文件
    with open(ssh_info_file) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    # 2. 获取通用账号密码配置
    common_section = Utils.get_section(data, "common")
    if common_section:
        root_password = common_section.get(ROOT_USER, None)
        sdb_password = common_section.get(SDB_USER, None)
        if root_password:
            default_root_password = root_password
        if sdb_password:
            default_sdb_password = sdb_password

    # 3. 初始化每个主机的账号密码为通用账号密码
    for host in host_list:
        ssh_info_map.setdefault(host, {})
        ssh_info_map[host][ROOT_USER] = default_root_password
        ssh_info_map[host][SDB_USER] = default_sdb_password

    # 4. 获取 specific 特定主机指定的账号密码
    specific_section = Utils.get_section(data, "specific")
    if specific_section:
        for host in specific_section.keys():
            ssh_info_map.setdefault(host, {})
            for user in specific_section.get(host).keys():
                ssh_info_map[host][user] = specific_section.get(host).get(user)

    return ssh_info_map


if __name__ == '__main__':
    ssh_client_map = dict()
    try:
        parse_command()
        ssh_info_map = generate_ssh_info(HOST_LIST, SSH_INFO_FILE)
        check_host_environment(HOST_LIST, ssh_info_map, ssh_client_map)
    except Exception as e:
        log.exception("Failed to exec check_host.py: {}".format(e))
        raise e
    finally:
        for host, credentials in ssh_client_map.items():
            for _, ssh_client in credentials.items():
                ssh_client.close()
