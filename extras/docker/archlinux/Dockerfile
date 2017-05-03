FROM imriss/archlinux

RUN echo 'Calvin on Arch Linux'

MAINTAINER Reza Farrahi <imriss@ieee.org>
LABEL description="Calvin / Arch Linux"

RUN  pacman -Syyu --noconfirm \
  && pacman -S findutils nano vi --needed --noconfirm \
  && pacman-db-upgrade \
  && export editor=nano \
&& pacman -S --needed --noconfirm systemd python python-yaml wget 


