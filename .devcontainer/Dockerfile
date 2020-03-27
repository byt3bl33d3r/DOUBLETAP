FROM debian:latest

ENV USERNAME byt3bl33d3r
ENV PYTHON_VERSION 3.8.1
ENV LANG C.UTF-8

ENV PYENV_VIRTUALENVWRAPPER_PREFER_PYVENV "true"
ENV PATH $HOME/.local/bin:/usr/local/bin:$PATH

RUN set -ex \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        man \
        sudo \
        mosh \
        curl \
        wget \
        make \
        vim \
        zsh \
        build-essential \
        libssl-dev \
        zlib1g-dev \
        libbz2-dev \
        libreadline-dev \
        libsqlite3-dev \
        llvm \
        libncurses5-dev \
        libncursesw5-dev \
        xz-utils \
        tk-dev \
        libffi-dev \
        liblzma-dev \
        python-openssl \
        git \
        ca-certificates

RUN set -ex \
    && shell=$(which zsh) \
    && sed -i "s~DSHELL=.*~DSHELL=$shell~" /etc/adduser.conf \
    && sed -i "s~SHELL=.*~SHELL=$shell~" /etc/default/useradd

WORKDIR /tmp

RUN set -ex \
    && curl -Lo ohmyzsh_installer.sh https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh \
    && sh /tmp/ohmyzsh_installer.sh --unattended \
    && rm /tmp/ohmyzsh_installer.sh

RUN set -ex \
    && curl -Lo pyenv_installer.sh https://github.com/pyenv/pyenv-installer/raw/master/bin/pyenv-installer \
    && bash /tmp/pyenv_installer.sh \
    && rm /tmp/pyenv_installer.sh

RUN set -ex \
    && git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ~/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting
 
RUN set -ex \
    && sed -i 's~export ZSH=.*~export ZSH="$HOME/.oh-my-zsh"~' ~/.zshrc \
    && sed -i 's/ZSH_THEME=.*/ZSH_THEME="lambda"/' ~/.zshrc \
    && sed -i 's/plugins=.*/plugins=(git pyenv extract zsh_reload history-substring-search zsh-syntax-highlighting)/' ~/.zshrc \
    && echo 'alias sudo="sudo -E "' >> ~/.zshrc \
    && cat ~/.zshrc | grep -v '#' | grep -v -e '^$'

RUN set -ex \
    && echo 'export LANG=C.UTF-8' > ~/.zshenv \
    && echo 'export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"' >> ~/.zshenv \
    && echo 'export PYENV_VIRTUALENVWRAPPER_PREFER_PYVENV="true"' >> ~/.zshenv \
    && cat ~/.zshenv

RUN set -ex \
    && chsh -s $(which zsh)

RUN set -ex \
    && cp -r ~/.pyenv /etc/skel \
    && cp -r ~/.oh-my-zsh /etc/skel \
    && cp ~/.zshrc /etc/skel \
    && sed -i 's/ZSH_THEME=.*/ZSH_THEME="norm"/' /etc/skel/.zshrc \
    && cp ~/.zshenv /etc/skel

RUN set -ex && adduser $USERNAME && usermod -aG sudo $USERNAME
RUN set -ex && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" | EDITOR='tee -a' visudo

USER $USERNAME

SHELL ["/usr/bin/zsh", "-c"]

RUN source ~/.zshrc \
    && pyenv install ${PYTHON_VERSION} \
    && pyenv global ${PYTHON_VERSION}

RUN source ~/.zshrc \
    && pip3 install -U pip \
    && pip3 install --user -U pipenv

WORKDIR "/home/$USERNAME"
