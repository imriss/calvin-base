FROM alpine:3.2
RUN apk --update add python
RUN apk add git
RUN wget https://bootstrap.pypa.io/ez_setup.py -O - | python
RUN easy_install pip
RUN apk add gcc
RUN apk add python-dev
RUN apk add musl-dev
RUN git clone -b Release-0.1.0 https://github.com/EricssonResearch/calvin-base calvin01
RUN cd calvin01 && python setup.py install
RUN git clone https://github.com/EricssonResearch/calvin-base calvin
RUN cd calvin && python setup.py install
RUN csruntime --host localhost calvin01/calvin/tests/scripts/test1.calvin
RUN apk del gcc
RUN apk del python-dev
RUN apk del musl-dev
RUN rm -rf /var/cache/apk/*
ENTRYPOINT ["python"]
