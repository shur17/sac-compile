# coding=utf-8
import logging
import paramiko
import sys
import os
import LoggerUtil

log = LoggerUtil.get_logger()


class SSHConnection:

    def __init__(self, host='', port=22, user='', pwd=None):
        self.host = host
        self.port = port
        self.user = user
        self.pwd = pwd
        self.__transport = paramiko.Transport((self.host, self.port))
        logging.getLogger("paramiko").setLevel(logging.WARNING)
        if pwd is None:
            private_key_path = os.path.expanduser("~/.ssh/id_rsa")
            private_key = paramiko.RSAKey.from_private_key_file(private_key_path)
            self.__transport.connect(username=self.user, pkey=private_key)
        else:
            self.__transport.connect(username=self.user, password=self.pwd)
        self.sftp = paramiko.SFTPClient.from_transport(self.__transport)

    def close(self):
        self.sftp.close()
        self.__transport.close()

    def get_hostname(self):
        return self.cmd('hostname', True)['stdout'].strip()

    def get_host_ip(self):
        cmd = "echo '" \
              "import socket\n" \
              "local_hostname = socket.gethostname()\n" \
              "local_ip = socket.gethostbyname(local_hostname)\n" \
              "print(local_ip)" \
              "' | python"
        return self.cmd(cmd, True)['stdout'].strip()

    def upload(self, local_path, remote_path):
        log.debug("uploading file {} to {}:{}".format(local_path, self.host, remote_path))
        self.sftp.put(local_path, remote_path)

    def write_file(self, remote_path, content, is_append=False):
        log.debug("write data to {}:{}".format(self.host, remote_path))
        write_type = 'w'
        if is_append:
            write_type = 'a'
        self.sftp.open(remote_path, write_type).write(content)

    def download(self, remote_path, local_path):
        self.sftp.get(remote_path, local_path)

    def mkdir(self, target_path):
        self.sftp.mkdir(target_path)

    # 递归创建目录
    def makedirs(self, target_path):
        path_components = target_path.split('/')
        path = ''
        for component in path_components:
            if component == '':
                continue
            path += '/' + component
            try:
                self.sftp.stat(path)
            except IOError as e:
                # 目录不存在，需要创建
                if e.errno == 2:
                    self.mkdir(path)
                else:
                    raise e

    def rmdir(self, target_path):
        self.sftp.rmdir(target_path)

    def listdir(self, target_path):
        return self.sftp.listdir(target_path)

    def is_file_exist(self, target_path):
        return self.cmd('ls {}'.format(target_path))['status'] == 0

    def remove(self, target_path):
        self.sftp.remove(target_path)

    def cmd(self, command):
        return self.cmd(command, False)

    def cmd(self, command, strict_mode=False):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.load_system_host_keys()
        try:
            ssh._transport = self.__transport
        except Exception as e:
            print(e)
            sys.exit()
        log.debug("exec cmd [{}] on host {}".format(command, self.host))
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(command)
        channel = ssh_stdout.channel
        status = channel.recv_exit_status()

        result = ssh_stdout.read()
        msg = ssh_stderr.read()
        if len(result.strip()) != 0:
            log.debug("cmd stdout: " + result)
        elif len(msg.strip()) != 0:
            log.debug("cmd stderr: " + msg)
        if strict_mode and status != 0:
            err_msg = "exec cmd failed! cmd=" + command + ", status=" + str(
                status) + ", stdout=" + result + ", stderr=" + msg
            log.error(err_msg)
            raise Exception("exec cmd failed!")
        res = {
            "status": status,
            "stdout": result.strip(),
            "stderr": msg.strip()
        }
        return res
