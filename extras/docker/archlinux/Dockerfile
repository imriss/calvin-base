FROM imriss/archlinux

RUN echo 'Calvin on Arch Linux'

MAINTAINER Reza Farrahi <imriss@ieee.org>
LABEL description="Calvin / Arch Linux"

RUN  pacman -Syyu --noconfirm \
  && pacman -S findutils nano vi --needed --noconfirm \
  && pacman-db-upgrade \
  && export editor=nano \
  && pacman -S --needed --noconfirm systemd python python-yaml wget python-pip 

# DDADD https://raw.githubusercontent.com/imriss/scylla/master/aur.sh /usr/sbin/aur.sh
# DDADD https://raw.githubusercontent.com/imriss/scylla/master/add-aur.sh /usr/sbin/add-aur
ADD ./aur.sh /usr/sbin/aur.sh
ADD ./add-aur.sh /usr/sbin/add-aur
RUN chmod u+x /usr/sbin/aur.sh
RUN chmod u+x /usr/sbin/add-aur
RUN add-aur docker

RUN su docker -c 'pacaur -S --needed --noprogressbar --noedit --noconfirm curl'

RUN cd / \
  && git clone --depth=50 --branch=master https://github.com/EricssonResearch/calvin-base calvin-base \
  && cd /calvin-base \
  && pip install --upgrade -r requirements.txt -r test-requirements.txt -e . 

RUN pacman -Scc --noconfirm \
  &&  rm /var/cache/pacman/pkg/* \
  && paccache -rf \
  && rm -rd /home/docker/sandground \
  && echo `du /usr/lib -hd 1`

WORKDIR /calvin-base/
EXPOSE 5000 5001
