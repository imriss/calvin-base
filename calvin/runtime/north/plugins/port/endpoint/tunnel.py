# -*- coding: utf-8 -*-

# Copyright (c) 2016 Ericsson AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from calvin.runtime.north.calvin_token import Token
from calvin.runtime.north.plugins.port.endpoint.common import Endpoint
from calvin.runtime.north.plugins.port.queue.common import COMMIT_RESPONSE, QueueEmpty, QueueFull
import time
from calvin.utilities.calvinlogger import get_logger

_log = get_logger(__name__)

#
# Remote tunnel endpoints
#


class TunnelInEndpoint(Endpoint):

    """docstring for TunnelInEndpoint"""

    def __init__(self, port, tunnel, peer_node_id, peer_port_id, trigger_loop):
        super(TunnelInEndpoint, self).__init__(port)
        self.tunnel = tunnel
        self.peer_port_id = peer_port_id
        self.peer_node_id = peer_node_id
        self.trigger_loop = trigger_loop

    def __str__(self):
        str = super(TunnelInEndpoint, self).__str__()
        return str

    def is_connected(self):
        return True

    def attached(self):
        self.port.queue.add_reader(self.port.id)

    def recv_token(self, payload):
        try:
            r = self.port.queue.com_write(Token.decode(payload['token']), payload['sequencenbr'])
            if r == COMMIT_RESPONSE.handled:
                # New token, trigger loop
                self.trigger_loop()
            if r == COMMIT_RESPONSE.invalid:
                ok = False
            else:
                # Either old or new token, ack it
                ok = True
            _log.debug("recv_token %s %s: %d %s => %s %d" % (self.port.id, self.port.name, payload['sequencenbr'], payload['token'], "True" if ok else "False", r))
        except QueueFull:
            # Queue full just send NACK
            ok = False
        reply = {
            'cmd': 'TOKEN_REPLY',
            'port_id': payload['port_id'],
            'peer_port_id': payload['peer_port_id'],
            'sequencenbr': payload['sequencenbr'],
            'value': 'ACK' if ok else 'NACK'
        }
        self.tunnel.send(reply)

    def set_peer_port_id(self, id):
        self.peer_port_id = id

    def get_peer(self):
        return (self.peer_node_id, self.peer_port_id)


class TunnelOutEndpoint(Endpoint):

    """docstring for TunnelOutEndpoint"""

    def __init__(self, port, tunnel, peer_node_id, peer_port_id, trigger_loop):
        super(TunnelOutEndpoint, self).__init__(port)
        self.tunnel = tunnel
        self.peer_id = peer_port_id
        self.peer_node_id = peer_node_id
        self.trigger_loop = trigger_loop
        # Keep track of acked tokens, only contains something post call if acks comes out of order
        self.sequencenbrs_acked = []
        self.backoff = 0.0
        self.time_cont = 0.0
        self.bulk = True

    def __str__(self):
        str = super(TunnelOutEndpoint, self).__str__()
        return str

    def is_connected(self):
        return True

    def attached(self):
        self.port.queue.add_reader(self.peer_id)

    def detached(self):
        # cancel any tentative reads to acked reads
        # Tunneled transport tokens after last continuous acked token will be resent later,
        # receiver will just ack them again if rereceived
        self.port.queue.cancel(self.peer_id)

    def reply(self, sequencenbr, status):
        _log.debug("Reply on port %s/%s/%s [%i] %s" % (self.port.owner.name, self.peer_id, self.port.name, sequencenbr, status))
        if status == 'ACK':
            self._reply_ack(sequencenbr, status)
        elif status == 'NACK':
            self._reply_nack(sequencenbr, status)
        else:
            # FIXME implement ABORT
            pass

    def _reply_ack(self, sequencenbr, status):
        # Back to full send speed directly
        self.bulk = True
        self.backoff = 0.0
        # Maybe someone can fill the queue again
        self.trigger_loop()
        r = self.port.queue.com_commit(self.peer_id, sequencenbr)
        if r == COMMIT_RESPONSE.handled or r == COMMIT_RESPONSE.invalid:
            return
        self.sequencenbrs_acked.append(sequencenbr)
        self.sequencenbrs_acked.sort()
        for n in self.sequencenbrs_acked[:]:
            r = self.port.queue.com_commit(self.peer_id, n)
            if r == COMMIT_RESPONSE.handled or r == COMMIT_RESPONSE.invalid:
                self.sequencenbrs_acked.remove(n)

    def _reply_nack(self, sequencenbr, status):
        # Make send only send one token at a time and have increasing time between them
        curr_time = time.time()
        if self.bulk:
            self.time_cont = curr_time
        if self.time_cont <= curr_time:
            # Need to trigger again due to either too late NACK or switched from series of ACK
            self.trigger_loop()
        self.bulk = False
        self.backoff = min(1.0, 0.1 if self.backoff < 0.1 else self.backoff * 2.0)

        r = self.port.queue.com_cancel(self.peer_id, sequencenbr)
        if r == COMMIT_RESPONSE.handled:
            # Filter out ACK for later seq nbrs, should not happen but precaution
            self.sequencenbrs_acked = [n for n in self.sequencenbrs_acked if n < sequencenbr]

    def _send_one_token(self):
        sequencenbr_sent, token = self.port.queue.com_peek(self.peer_id)
        _log.debug("Send on port  %s/%s/%s [%i] %s" % (self.port.owner.name,
                                                       self.peer_id,
                                                       self.port.name,
                                                       sequencenbr_sent,
                                                       "" if self.bulk else "@%f/%f" % (self.time_cont, self.backoff)))
        self.tunnel.send({
            'cmd': 'TOKEN',
            'token': token.encode(),
            'peer_port_id': self.peer_id,
            'sequencenbr': sequencenbr_sent,
            'port_id': self.port.id
        })

    def use_monitor(self):
        return True

    def communicate(self, *args, **kwargs):
        # FIXME uses internal queue attributes
        sent = False
        if self.bulk:
            # Send all we have, since other side seems to keep up
            while self.port.queue.tokens_available(1, self.peer_id):
                sent = True
                self._send_one_token()
        elif (self.port.queue.tokens_available(1, self.peer_id) and
              self.port.queue.com_is_committed(self.peer_id) and
              time.time() >= self.time_cont):
            # Send only one since other side sent NACK likely due to their FIFO is full
            # Something to read and last (N)ACK recived
            self._send_one_token()
            sent = True
            self.time_cont = time.time() + self.backoff
            # Make sure that resend will be tried in backoff seconds
            self.trigger_loop(self.backoff)
        return sent

    def get_peer(self):
        return (self.peer_node_id, self.peer_id)
