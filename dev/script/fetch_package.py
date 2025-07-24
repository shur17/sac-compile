# -*- coding: UTF-8 -*-

import getopt
import re
import os
import paramiko
import sys
import subprocess
from scp import SCPClient

hostname = '192.168.20.253'
username = 'sequoiadb'
password = 'sequoiadb'

search_base_dir = None
package_version = None
package_name = ''
download_dir = ''
remote_file_path = ''
remote_file_name = ''

reload(sys)
sys.setdefaultencoding('utf-8')

def display_and_exit():
    print("")
    print(" --help | -h          : print help message")
    print(" --search-base-dir    : base dir to search package")
    print(" --version            : package version")
    print(" --name               : package name")
    print(" --download-dir       : package download path")
    sys.exit(0)

def parse_command():
    global search_base_dir, package_version, package_name, download_dir
    try:
        options, args = getopt.getopt(sys.argv[1:], "h", ["help", "search-base-dir=", "version=", "name=", "download-dir="])
    except getopt.GetoptError, e:
        print("Failed to parse command, errMsg: " + str(e))
        sys.exit(1)

    for name, value in options:
        if name in ("-h", "--help"):
            display_and_exit()
        elif name in "--search-base-dir":
            search_base_dir = value
        elif name in "--version":
            package_version = value
        elif name in "--name":
            package_name = value
        elif name in "--download-dir":
            download_dir = value

if __name__ == "__main__":
    ssh = None
    try:
        parse_command()

        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, username=username, password=password)

        search_dir = ""
        # 先根据版本号找到安装包所在目录
        if package_version is not None and search_base_dir is not None:
            search_dir_cmd = "find " + search_base_dir + " -type d -name " + package_version + " | head -n 1"
            print("execute cmd: " + search_dir_cmd)
            stdin, stdout, stderr = ssh.exec_command(search_dir_cmd)

            output = stdout.read().decode("utf-8").strip()
            error = stderr.read().decode("utf-8").strip()

            if output:
                search_dir = output
            else:
                print("Failed to find package dir on remote server: " + hostname + ", package_version: "+ package_version +", name: " + package_name)
                sys.exit(1)

        else:
            search_dir = "/data/share_new/7.版本归档_NEW"
        cmd = "find " + search_dir + " -name " + package_name + " | head -n 1"
        print("execute cmd: " + cmd)
        stdin, stdout, stderr = ssh.exec_command(cmd)

        output = stdout.read().decode("utf-8").strip()
        error = stderr.read().decode("utf-8").strip()

        if output:
            remote_file_path = output
            remote_file_name = os.path.basename(remote_file_path)
        else:
            print("Failed to find package on remote server: " + hostname + ", name: " + package_name)
            sys.exit(1)

        if error:
            print("Failed to execute command: " + cmd + ", errMsg: " + error)
            sys.exit(1)

        local_file_path = os.path.join(download_dir, remote_file_name)
        print("download file: " + remote_file_name + " from remote server: " + hostname)
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        # 拉取远程主机的安装包到本地环境
        with SCPClient(ssh.get_transport()) as scp:
            scp.get(remote_file_path, download_dir)
        print("file " + remote_file_path.encode("utf-8") + " is succeed to transfer to " + local_file_path)

    except Exception as e:
        print("Failed to exec fetch_package.py: " + str(e))
        raise e

    finally:
        if ssh is not None:
            ssh.close()
