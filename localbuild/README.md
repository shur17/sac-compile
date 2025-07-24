本工具用于一键安装部署 SAC 集群及相关数据源或组件（Sdb、DDS、MySql、Mariadb、ELF)，并执行前端界面自动化测试。

# 目录结构
```
localbuild.py    # 工具入口脚本，负责调度
localbuild
   ├── bin       # 存放各个安装子脚本
   ├── conf      # 配置 SSH 主机账号密码信息
   ├── logs      # 存放工具日志
   ├── package   # 存放安装过程所需的安装包，可使用 fetch_package.sh 一键从 ci 拉取最新的安装包
   ├── template  # 存放部署模板，不同机器数量对应不同的模板，模板里描述了各个组件的安装配置，可根据需要进行修改
   ├── tools     # 存放相关工具脚本，如 ssh 互信工具、ES 系统参数调整工具
   └── workdir   # 存放工具运行时的临时文件
```
    

# 环境准备

1. 下载 gitlab 仓库
    ```
    # cd /data/gitlab
    # git clone http://gitlab.sequoiadb.com/sequoiadb/sac.git
    # git clone http://gitlab.sequoiadb.com/test/sac-auto-test.git
    ```

2. 调整 ES 系统参数（在 ES 安装机器上执行，假设 ES 机器为 192.168.31.82）
    ```
    # cd /data/gitlab/sac/localbuild/tools/
    # scp ./update_es_sys_config.sh root@192.168.31.82:/tmp/
    # ssh root@192.168.31.82 '/tmp/update_es_sys_config.sh' 
    ```

3. 安装 localbuild 依赖库
    ```
    # pip install paramiko==1.13.0
    # pip install PyYAML==5.2
    ```
   
4. 安装 nodejs
    ```
    # cd /data/soft
    # cp /data/gitlab/sac-auto-test/testcases/tools/nodejs/node-v16.15.1-linux-x64.tar.gz ./
    # tar -zxvf ./node-v16.15.1-linux-x64.tar.gz
   
    // 加入环境变量中
    # cat ~/.bashrc 
    ...
    export NODEJS_HOME=/data/soft/node-v16.15.1-linux-x64/
    export PATH=$NODEJS_HOME/bin:$PATH
    ...
   
    # source ~/.bashrc
    ```

5. 安装 Cypress 及其依赖
    ```
    // 以 Ubuntu 操作系统为例
    # apt-get install libgtk2.0-0 libgtk-3-0 libgbm-dev libnotify-dev libgconf-2-4 libnss3 libxss1 libasound2 libxtst6 xauth xvfb

    // 中文字体
    # cd /data/gitlab/sac-auto-test/testcases/tools/install-font
    # ./install-font.sh
    
    # cd ~
    # mkdir -p .cache/Cypress
    # cd .cache/Cypress
    # cp /data/gitlab/sac-auto-test/testcases/story/Cypress/Cypress-Linux.zip ./
    # unzip ./Cypress-Linux.zip
    # chmod -R 777 ~/.cache/Cypress
    ```
   
6. 执行 Localbuild 执行主机的连通性检查，配置 SSH 互信、host 映射
    ```
    # cd /data/gitlab/sac/
    # vi localbuild/conf/ssh_info.yml
    # python localbuild.py --host 192.168.31.8,192.168.31.82 --host-check
    ```
    

# 安装包准备

将 SAC、Sdb、DDS、MySql、Mariadb、ELF 的安装包放置在 localbuild/package 目录下，也可以直接使用目录下的 fetch_packages.sh 脚本一键从 CI 拉取最新的安装包。

# 脚本使用

1. 一键安装部署并执行测试
    ```
    python localbuild.py --clean --install --runtest --host 192.168.31.10,192.168.31.11
    ```
   
    - 脚本会根据机器数量从 template 目录下找到对应的部署模板 localbuild_2host.yml，基于该模板声明的内容进行部署（也可以手动修改该模板文件，例如修改端口配置、移除部分组件的安装）

2. 一键编译安装部署基本 SAC 集群，并执行基本测试用例
    ```
    python localbuild.py --compile --clean --install base --runbase --host 192.168.31.10,192.168.31.11
    ```

3. 仅安装部署

    ```
    python localbuild.py --clean --install --host 192.168.31.10,192.168.31.11
    ```

4. 仅执行测试

    ```
    # 执行全部测试用例
    python localbuild.py --runtest 
   
    # 执行指定用例
    python localbuild.py --runtest "cypress/e2e/story/chartExample/chart_tip.cy.js"
    ```
   
    - 需要先完成安装部署才能执行测试命令，测试时会基于 workdir 下的 sac.yml （部署后产生此文件） 所描述的集群信息进行测试。
    - 测试时会自动从 ci 上拉取测试工程到 sac 工程的同级目录(sac-auto-testcase)，如果已经拉取过则默认不会再次拉取，可指定 --force-update-testcase 参数强制拉取。

5. 清理环境

    ```
    # 清理机器 192.168.31.10、192.168.31.11 的 SAC、Sdb、DDS、MySql、Mariadb、ELF
    python localbuild.py --clean --host 192.168.31.10,192.168.31.11
    ```
   
# 其它说明
内存要求
  * 1host：需要保证内存在 24G 以上
  * 2host: host1（默认安装 SAC 的机器）16G 以上，host2 8G 以上
  * 3host: host1（默认安装 SAC 的机器）16G 以上，host2、host3 8G 以上
  * 4host: host1（默认安装 SAC 的机器）16G 以上，host2、host3、host4 8G 以上
  * 5host: host2（默认安装 SAC 的机器）16G 以上，host1、host3、host4、host5 8G 以上


# FAQ
1. 脚本执行机报错： ncompatible ssh peer (no acceptable kex algorithm)
    ```
    vim /etc/ssh/sshd_config
    # 添加如下内容：
    KexAlgorithms curve25519-sha256@libssh.org,ecdh-sha2-nistp256,ecdh-sha2-nistp384,ecdh-sha2-nistp521,diffie-hellman-group-exchange-sha256,diffie-hellman-group14-sha1,diffie-hellman-group-exchange-sha1,diffie-hellman-group1-sha1
    # 重启 sshd 服务
    systemctl restart sshd
    ```
2. 如果不想安装部分组件：如 ELF、DDS，该如何操作？
   - 根据机器数量，在 template 目录下找到对应的部署模板，将对应组件的配置段注释即可。