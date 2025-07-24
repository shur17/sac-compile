import hashlib
import os
import subprocess

from LoggerUtil import get_logger
from collections import OrderedDict

import yaml

import httplib
import json
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
import base64

log = get_logger()


def setup_yaml():
    def quoted_presenter(dumper, data):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')

    def dict_presenter(dumper, data):
        return dumper.represent_dict(data.items())

    yaml.add_representer(str, quoted_presenter)
    yaml.add_representer(OrderedDict, dict_presenter)


def write_jvm_options(ssh, jvm_options, remote_jvm_conf_file):
    if jvm_options is not None:
        if "-Xms" in jvm_options:
            ssh.cmd("sed -i '/^-Xms/d' {}".format(remote_jvm_conf_file))
        if "-Xmx" in jvm_options:
            ssh.cmd("sed -i '/^-Xmx/d' {}".format(remote_jvm_conf_file))
        custom_jvm_options = jvm_options.replace(" ", "\n")
        ssh.cmd("echo '\n{}' >> {}".format(custom_jvm_options, remote_jvm_conf_file))


def format_time(time_in_sec):
    hour = time_in_sec / 3600
    min = (time_in_sec % 3600) / 60
    sec = time_in_sec % 60
    costs = ""
    if hour > 0:
        costs = costs + str(hour) + " h "
    if min > 0:
        costs = costs + str(min) + " min "
    if sec >= 0:
        costs = costs + str(sec) + " s "
    return costs


def is_dir_empty(dir):
    if not os.path.exists(dir):
        return True
    return not os.listdir(dir)


def get_section(config, section):
    sections = section.split(".")
    target_section = config
    for section in sections:
        if section not in target_section:
            return None
        else:
            target_section = target_section[section]
    if target_section is None or len(target_section) == 0:
        return None
    return target_section


def kill_process(ssh, *keywords):
    cmd = "ps aux "
    for keyword in keywords:
        cmd += "| grep '{}' ".format(keyword)
    cmd += "| grep -v 'grep' | awk '{print $2}' | xargs kill -9"
    ssh.cmd(cmd)


def get_install_info_item(item, etc_default_path):
    cmd = ["grep", item, etc_default_path]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = process.communicate()

    if process.returncode == 0:
        return output.split('=')[1].strip()
    else:
        raise Exception("Failed exec {}".format(cmd))


def get_install_info(etc_default_path):
    install_info = {
        "is_installed": False,
        "installed_path": None,
        "md5": None
    }
    if os.path.exists(etc_default_path):
        try:
            install_info['is_installed'] = True
            install_info['md5'] = get_install_info_item("MD5", etc_default_path)
            install_info['installed_path'] = get_install_info_item("INSTALL_DIR", etc_default_path)
        except:
            raise Exception("Failed to get install info from {}".format(etc_default_path))

    return install_info


def path_equals(path1, path2):
    if path1.endswith("/"):
        path1 = path1[:-1]
    if path2.endswith("/"):
        path2 = path2[:-1]
    return path1 == path2


def get_file_md5(file_path):
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_remote_file_md5(ssh, file_path):
    cmd = "md5sum {}".format(file_path)
    output = ssh.cmd(cmd)['stdout']
    return output.split(" ")[0]


def is_file_md5_same(ssh, local_file_path, remote_file_path):
    local_md5 = get_file_md5(local_file_path)
    remote_md5 = get_remote_file_md5(ssh, remote_file_path)
    return local_md5 == remote_md5


def get_dds_install_hosts(replica_dds, shard_dds):
    host_names_set = set()

    if replica_dds is not None:
        replset = replica_dds.get("replset")
        for repl in replset:
            members = repl.get("members")
            for member in members:
                host_names_set.add(member.get("host"))

    if shard_dds is not None:
        routers = shard_dds.get("routers")
        for router in routers.get("members"):
            host_names_set.add(router.get("host"))
        replset = shard_dds.get("replset")
        for repl in replset:
            members = repl.get("members")
            for member in members:
                host_names_set.add(member.get("host"))

    return list(host_names_set)


def ssh_send_package(ssh, local_pacakge_path, remote_package_path, grant_execute_priv=True):
    if ssh.is_file_exist(remote_package_path) and is_file_md5_same(ssh, local_pacakge_path, remote_package_path):
        log.info("Package {} is exists on {}, skip upload".format(os.path.basename(local_pacakge_path), ssh.host))
    else:
        parent_dir = os.path.dirname(remote_package_path)
        ssh.cmd("mkdir -p {}".format(parent_dir))
        log.info("Uploading {} to {}:{}".format(local_pacakge_path, ssh.host, remote_package_path))
        ssh.upload(local_pacakge_path, remote_package_path)
        if grant_execute_priv:
            ssh.cmd("chmod +x {}".format(remote_package_path))

def encrypt_with_md5(plain_text):
    md5_hash = hashlib.md5()
    md5_hash.update(plain_text.encode())
    return md5_hash.hexdigest()

def encrypt_with_rsa(rsa_pub_key_str, plain_text):
    rsa_pub_key = RSA.importKey(rsa_pub_key_str)
    cipher = PKCS1_v1_5.new(rsa_pub_key)
    encrypted_message = cipher.encrypt(plain_text.encode('utf-8'))
    return base64.b64encode(encrypted_message).decode('utf-8')

def get_rsa_pub_key(base_url):
    conn = None
    try:
        conn = httplib.HTTPConnection(base_url)
        conn.request("GET", "/api/gateway/config/pub-key")
        response = conn.getresponse()
        data = json.loads(response.read())

        if data['code'] != 0:
            raise Exception("Failed to get rsa pub key, errorCode: {}, msg: {}, detail: {}"
                                .format(data['code'], data['msg'], data['detail']))

        return data['data']['value']
    finally:
        if conn is not None:
            conn.close()


def login(base_url, username, password):
    conn = None
    try:
        conn = httplib.HTTPConnection(base_url)
        payload = json.dumps({'username': username, 'password': password})
        headers = {'Content-Type': 'application/json'}
        conn.request("POST", "/api/user-center/login", payload, headers)
        response = conn.getresponse()
        data = json.loads(response.read())

        if data['code'] != 0:
            raise Exception("Failed to login, errorCode: {}, msg: {}, detail: {}"
                                .format(data['code'], data['msg'], data['detail']))

        return data['data']
    finally:
        if conn is not None:
            conn.close()

def scan_servers(base_url, token, params):
    conn = None
    try:
        conn = httplib.HTTPConnection(base_url)
        payload = json.dumps(params)
        headers = {'Content-Type': 'application/json', 'Sac-Access-Token': token}
        conn.request("POST", "/api/deploy/servers/scan", payload, headers)
        response = conn.getresponse()
        data = json.loads(response.read())

        if data['code'] != 0:
            raise Exception("Failed to scan servers, errorCode: {}, msg: {}, detail: {}"
                                .format(data['code'], data['msg'], data['detail']))

        return data['data']['value']
    finally:
        if conn is not None:
            conn.close()

def add_servers(base_url, token, params):
    conn = None
    try:
        conn = httplib.HTTPConnection(base_url)
        payload = json.dumps(params)
        headers = {'Content-Type': 'application/json', 'Sac-Access-Token': token}
        conn.request("POST", "/api/deploy/servers/add", payload, headers)
        response = conn.getresponse()
        data = json.loads(response.read())

        if data['code'] != 0:
            raise Exception("Failed to add servers, errorCode: {}, msg: {}, detail: {}"
                                .format(data['code'], data['msg'], data['detail']))

        return data['data']
    finally:
        if conn is not None:
            conn.close()

def get_task_progress(base_url, token, tid):
    conn = None
    try:
        conn = httplib.HTTPConnection(base_url)
        headers = {'Content-Type': 'application/json', 'Sac-Access-Token': token}
        conn.request("GET", "/api/deploy/task/" + str(tid), headers=headers)
        response = conn.getresponse()
        data = json.loads(response.read())

        if data['code'] != 0:
            raise Exception("Failed to get task progress, taskId: {}, errorCode: {}, msg: {}, detail: {}"
                                .format(tid, data['code'], data['msg'], data['detail']))

        return data['data']
    finally:
        if conn is not None:
            conn.close()