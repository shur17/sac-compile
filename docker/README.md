# sac-server 镜像构建

sac 相关镜像分为三个:
- sequoiadb/sac-server-builder: sac 编译时基础镜像
- sequoiadb/sac-server-runtime: sac 运行时基础镜像
- sequoiadb/sac-server: sac 镜像

构建基础镜像时需要外网环境，因此可以提前构建好基础镜像后续 sac 镜像构建只需要拉取已构建的基础镜像即可。

## ./docker 下 sac 镜像相关文件

- docker-entrypoint.sh: sac 镜像入口脚本
- Dockerfile.builder: sac 编译时环境基础镜像
- Dockerfile.runtime: sac 运行时环境基础镜像
- Dockerfile: sac 镜像

## 镜像构建

1. 进入 sac 项目工程：

```bash
# 假设 sac 项目工程在 /xxx/sac
# 进入 sac 工程，执行后续操作
cd /xxx/sac
```

2. 构建 sac 编译时环境基础镜像（需要外网环境）

```bash
docker build -f docker/Dockerfile.builder -t sequoiadb/sac-server-builder .
```

3. 构建 sac 运行时环境基础镜像（需要外网环境）

```bash
docker build -f docker/Dockerfile.runtime -t sequoiadb/sac-server-runtime .
```

4. 构建 sac 镜像（依赖前两个镜像）

> sac 编译时和运行时环境镜像基本固定不变不需要每次都构建，可直接从内网镜像仓库拉取到本地即可：
> ```bash
> docker pull <仓库地址>/sequoiadb/sac-server-builder
> docker tag <仓库地址>/sequoiadb/sac-server-builder sequoiadb/sac-server-builder
> docker pull <仓库地址>/sequoiadb/sac-server-runtime
> docker tag <仓库地址>/sequoiadb/sac-server-runtime sequoiadb/sac-server-runtime
> ```

```bash
docker build -f docker/Dockerfile -t sequoiadb/sac-server:latest .
```

## 运行 sac 镜像

sac 镜像支持的环境变量：
- SAC_INIT_DDS_URIS: sac 数据库地址，"," 分隔多个地址，例如："192.168.1.1:27017,192.168.1.2:27017"
- SAC_INIT_DDS_USERNAME: 创建 sac 数据库用户的用户名
- SAC_INIT_DDS_PASSWORD: 创建 sac 数据库用户的密码
- SAC_INIT_DATABASE: 创建的 sac 数据库名，默认值："sequoiasac"

### 通过 docker run

```bash
docker run -d --name sac-server --restart always \
  -p "28000:28000" \                              # 对外开放 28000 端口
  -e "SAC_INIT_DDS_URIS=192.168.1.1:27017" \
  -e "SAC_INIT_DDS_USERNAME=sdbadmin" \
  -e "SAC_INIT_DDS_PASSWORD=sdbadmin" \
  -e "SAC_INIT_DATABASE=sequoiasac" \
  --add-host "u22:192.168.1.1" \                  # 添加 host 映射到 sac 容器
  -v "/xxx/sac-data:/data/sac" \                  # 配置 sac 数据持久化到宿主机 /xxx/sac-data
  -v "/home/xxx/.ssh:/home/sdbadmin/.ssh" \       # 配置 sac 容器使用宿主机 xxx 用户的 ssh 信息
  sequoiadb/sac-server:latest
```

### 通过 docker compose

在任意目录下创建 `compose.yaml` 文件，写入：

```yaml
# 创建一个命名卷保存持久化的 sac 数据
volumes:
  sac-data:
    driver: local

services:
  sac-server:
    image: sequoiadb/sac-server:latest
    ports:
      - "28000:28000"
    restart: always
    extra_hosts:
      - "u22:192.168.1.1"
    environment:
      - "SAC_INIT_DDS_URIS=192.168.1.1:27017"
      - "SAC_INIT_DDS_USERNAME=sdbadmin"
      - "SAC_INIT_DDS_PASSWORD=sdbadmin"
      - "SAC_INIT_DATABASE=sequoiasac"
    volumes:
      - "sac-data:/data/sac"
      - "/home/xxx/.ssh:/home/sdbadmin/.ssh"
```

进入 `compose.yaml` 文件所在目录执行

```bash
docker compose up -d
```

### sac 镜像中的时区

sac 镜像默认使用 `Asia/Shanghai` 时区，可通过如下方式调整容器的时区：

- 通过挂载 `/etc/timezone` 和 `/etc/localtime` 的方式保持与宿主机时区一致

```bash
docker run -d --name sac-server --restart always \
  ...
  -v "/etc/timezone:/etc/timezone:ro" \           # 配置 sac 容器使用宿主机时区
  -v "/etc/localtime:/etc/localtime:ro" \         # 配置 sac 容器使用宿主机时区
  ...
  sequoiadb/sac-server:latest
```

- 通过设置 `TZ` 环境变量的方式设置时区：

```bash
docker run -d --name sac-server --restart always \
  ...
  -e "TZ=Asia/Shanghai" \           # 配置 sac 容器使用 Asia/Shanghai 时区
  ...
  sequoiadb/sac-server:latest
```