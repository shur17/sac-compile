FROM maven:3.8-openjdk-8

WORKDIR /sac

SHELL ["/bin/bash", "-c"]

RUN set -eux; \
    apt-get update; \
    apt-get install -y python2 gcc python2-dev libffi-dev libssl-dev make; \
    ln -s /usr/bin/python2 /usr/bin/python; \
    wget https://bootstrap.pypa.io/pip/2.7/get-pip.py; \
    python2 get-pip.py; \
    rm -rf get-pip.py; \
    pip install pyyaml==5.2 paramiko==1.13.0 scp==0.15.0 pytest hypothesis; \
    curl -fsSL https://fnm.vercel.app/install | bash; \
    source ~/.bashrc; \
    fnm use --install-if-missing 20.15.1; \
    apt-get purge -y --auto-remove gcc python2-dev libffi-dev libssl-dev make; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*