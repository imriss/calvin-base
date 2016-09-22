# -*- coding: utf-8 -*-

# Copyright (c) 2015-2016 Ericsson AB
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

import unittest
import time
import pytest

from calvin.csparser import cscompile as compiler
from calvin.Tools import cscompiler as compile_tool
from calvin.Tools import deployer
from calvin.utilities import calvinlogger
from calvin.requests.request_handler import RequestHandler
from . import helpers

_log = calvinlogger.get_logger(__name__)


def absolute_filename(filename):
    import os.path
    return os.path.join(os.path.dirname(__file__), filename)

rt1 = None
rt2 = None
rt3 = None
test_type = None
request_handler = None

def expected_tokens(rt, actor_id, t_type='seq'):
    return helpers.expected_tokens(request_handler, rt, actor_id, t_type)

def wait_for_tokens(rt, actor_id, size=5, retries=20):
    return helpers.wait_for_tokens(request_handler, rt, actor_id, size, retries)
    
def actual_tokens(rt, actor_id, size=5, retries=20):
    return helpers.actual_tokens(request_handler, rt, actor_id, size, retries)
   
  
def setup_module(module):
    global rt1, rt2, rt3
    global peerlist
    global request_handler
    global test_type

    request_handler = RequestHandler()
    test_type, [rt1, rt2, rt3], peerlist = helpers.setup_test_type(request_handler)


def teardown_module(module):
    global rt1
    global rt2
    global rt3
    global test_type
    global request_handler

    helpers.teardown_test_type(request_handler, [rt1, rt2, rt3], test_type)


class CalvinTestBase(unittest.TestCase):

    def setUp(self):
        self.rt1 = rt1
        self.rt2 = rt2
        self.rt3 = rt3

    def assert_lists_equal(self, expected, actual, min_length=5):
        self.assertTrue(len(actual) >= min_length, "Received data too short (%d), need at least %d" % (len(actual), min_length))
        self._assert_lists_equal(expected, actual)

    def _assert_lists_equal(self, expected, actual):
        assert actual
        assert reduce(lambda a, b: a and b[0] == b[1], zip(expected, actual), True) 
        
    def compile_script(self, script, name):
        # Instead of rewriting tests after compiler.compile_script changed
        # from returning app_info, errors, warnings to app_info, issuetracker
        # use this stub in tests to keep old behaviour
        app_info, issuetracker = compiler.compile_script(script, name)
        return app_info, issuetracker.errors(), issuetracker.warnings()

    def wait_for_migration(self, runtime, actors, retries=20):
        retry = 0
        if not isinstance(actors, list):
            actors = [ actors ]
        while retry < retries:
            try:
                for actor in actors:
                    request_handler.get_actor(runtime, actor)
                break
            except Exception:
                _log.info("Migration not finished, retrying in %d" % (retry,))
                retry += 1
                time.sleep(retry)

    def migrate(self, source, dest, actor):
        request_handler.migrate(source, actor, dest.id)
        self.wait_for_migration(dest, [actor])

@pytest.mark.essential
class TestConnections(CalvinTestBase):

    @pytest.mark.slow
    def testLocalSourceSink(self):
        _log.analyze("TESTRUN", "+", {})
        src = request_handler.new_actor(self.rt1, 'std.CountTimer', 'src')
        snk = request_handler.new_actor_wargs(self.rt1, 'io.StandardOut', 'snk', store_tokens=1, quiet=1)

        request_handler.connect(self.rt1, snk, 'token', self.rt1.id, src, 'integer')

        actual = wait_for_tokens(self.rt1, snk)
        expected = expected_tokens(self.rt1, src, 'seq')
        
        self.assert_lists_equal(expected, actual)

        request_handler.delete_actor(self.rt1, src)
        request_handler.delete_actor(self.rt1, snk)

    def testMigrateSink(self):
        _log.analyze("TESTRUN", "+", {})
        src = request_handler.new_actor(self.rt1, 'std.CountTimer', 'src')
        snk = request_handler.new_actor_wargs(self.rt1, 'io.StandardOut', 'snk', store_tokens=1, quiet=1)

        request_handler.connect(self.rt1, snk, 'token', self.rt1.id, src, 'integer')

        pre_migrate = wait_for_tokens(self.rt1, snk)

        self.migrate(self.rt1, self.rt2, snk)
        
        actual = wait_for_tokens(self.rt2, snk, len(pre_migrate)+5)
        expected = expected_tokens(self.rt1, src)
        
        self.assert_lists_equal(expected, actual)

        request_handler.delete_actor(self.rt1, src)
        request_handler.delete_actor(self.rt2, snk)

    def testMigrateSource(self):
        _log.analyze("TESTRUN", "+", {})
        src = request_handler.new_actor(self.rt1, 'std.CountTimer', 'src')
        snk = request_handler.new_actor_wargs(self.rt1, 'io.StandardOut', 'snk', store_tokens=1, quiet=1)

        request_handler.connect(self.rt1, snk, 'token', self.rt1.id, src, 'integer')

        actual = wait_for_tokens(self.rt1, snk)

        self.migrate(self.rt1, self.rt2, src)

        actual = actual_tokens(self.rt1, snk, len(actual)+5 )
        expected = expected_tokens(self.rt2, src)

        self.assert_lists_equal(expected, actual)

        request_handler.delete_actor(self.rt2, src)
        request_handler.delete_actor(self.rt1, snk)

    def testTwoStepMigrateSinkSource(self):
        _log.analyze("TESTRUN", "+", {})
        src = request_handler.new_actor(self.rt1, 'std.CountTimer', 'src')
        snk = request_handler.new_actor_wargs(self.rt1, 'io.StandardOut', 'snk', store_tokens=1, quiet=1)

        request_handler.connect(self.rt1, snk, 'token', self.rt1.id, src, 'integer')

        pre_migrate = wait_for_tokens(self.rt1, snk)
        self.migrate(self.rt1, self.rt2, snk)
        mid_migrate = wait_for_tokens(self.rt2, snk, len(pre_migrate)+5)
        self.migrate(self.rt1, self.rt2, src)
        post_migrate = wait_for_tokens(self.rt2, snk, len(mid_migrate)+5)
        
        expected = expected_tokens(self.rt2, src)
        
        self.assert_lists_equal(expected, post_migrate, min_length=10)

        request_handler.delete_actor(self.rt2, src)
        request_handler.delete_actor(self.rt2, snk)

    def testTwoStepMigrateSourceSink(self):
        _log.analyze("TESTRUN", "+", {})
        src = request_handler.new_actor(self.rt1, 'std.CountTimer', 'src')
        snk = request_handler.new_actor_wargs(self.rt1, 'io.StandardOut', 'snk', store_tokens=1, quiet=1)

        request_handler.connect(self.rt1, snk, 'token', self.rt1.id, src, 'integer')

        pre_migrate = wait_for_tokens(self.rt1, snk)
        self.migrate(self.rt1, self.rt2, src)
        mid_migrate = wait_for_tokens(self.rt1, snk, len(pre_migrate)+5)
        self.migrate(self.rt1, self.rt2, snk)
        post_migrate = wait_for_tokens(self.rt2, snk, len(mid_migrate)+5)

        expected = expected_tokens(self.rt2, src)
        self.assert_lists_equal(expected, post_migrate, min_length=15)

        request_handler.delete_actor(self.rt2, src)
        request_handler.delete_actor(self.rt2, snk)


@pytest.mark.essential
class TestScripts(CalvinTestBase):

    @pytest.mark.slow
    def testInlineScript(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
          src : std.CountTimer()
          snk : io.StandardOut(store_tokens=1, quiet=1)
          src.integer > snk.token
          """
        app_info, errors, warnings = self.compile_script(script, "simple")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()
        snk = d.actor_map['simple:snk']
        src = d.actor_map['simple:src']

        actual = wait_for_tokens(self.rt1, snk)
        expected = expected_tokens(self.rt1, src)

        self.assert_lists_equal(expected, actual)

        helpers.destroy_app(d)

    @pytest.mark.slow
    def testFileScript(self):
        _log.analyze("TESTRUN", "+", {})
        scriptname = 'test1'
        scriptfile = absolute_filename("scripts/%s.calvin" % (scriptname, ))
        app_info, issuetracker = compile_tool.compile_file(scriptfile)
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        src = d.actor_map['%s:src' % scriptname]
        snk = d.actor_map['%s:snk' % scriptname]

        actual = wait_for_tokens(self.rt1, snk)        
        expected = expected_tokens(self.rt1, src)

        self.assert_lists_equal(expected, actual)

        helpers.destroy_app(d)


@pytest.mark.essential
class TestMetering(CalvinTestBase):

    @pytest.mark.slow
    def testMetering(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
          src : std.CountTimer()
          snk : io.StandardOut(store_tokens=1, quiet=1)
          src.integer > snk.token
          """

        r = request_handler.register_metering(self.rt1)
        user_id = r['user_id']
        app_info, errors, warnings = self.compile_script(script, "simple")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()
        
        snk = d.actor_map["simple:snk"]
        src = d.actor_map["simple:src"]
        tokens = len(wait_for_tokens(self.rt1, snk, 10))
        
        metainfo = request_handler.get_actorinfo_metering(self.rt1, user_id)
        data1 = request_handler.get_timed_metering(self.rt1, user_id)

        actual = wait_for_tokens(self.rt1, snk, tokens+10)
        data2 = request_handler.get_timed_metering(self.rt1, user_id)

        assert snk in metainfo
        assert data1[snk][0][1] in metainfo[snk]

        expected = expected_tokens(self.rt1, src)
        self.assert_lists_equal(expected, actual)
        
        # Verify only new data
        assert max([data[0] for data in data1[snk]]) < min([data[0] for data in data2[snk]])
        # Verify about same number of tokens (time diff makes exact match not possible)
        diff = len(data1[snk]) + len(data2[snk]) - len(actual)
        assert diff > -3 and diff < 3
        
        request_handler.unregister_metering(self.rt1, user_id)
        helpers.destroy_app(d)


    @pytest.mark.slow
    def testMigratingMetering(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
          src : std.CountTimer()
          snk : io.StandardOut(store_tokens=1, quiet=1)
          src.integer > snk.token
          """

        r1 = request_handler.register_metering(self.rt1)
        user_id = r1['user_id']
        # Register as same user to keep it simple
        r2 = request_handler.register_metering(self.rt2, user_id)
        # deploy app
        app_info, errors, warnings = self.compile_script(script, "simple")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['simple:snk']
        src = d.actor_map['simple:src']
        tokens = len(wait_for_tokens(self.rt1, snk))
        
        # migrate sink back and forth
        self.migrate(self.rt1, self.rt2, snk)
        tokens = len(wait_for_tokens(self.rt2, snk, tokens+5))
        self.migrate(self.rt2, self.rt1, snk)
        tokens = len(wait_for_tokens(self.rt1, snk, tokens+5))

        # Get metering
        metainfo1 = request_handler.get_actorinfo_metering(self.rt1, user_id)
        metainfo2 = request_handler.get_actorinfo_metering(self.rt2, user_id)
        data1 = request_handler.get_timed_metering(self.rt1, user_id)
        data2 = request_handler.get_timed_metering(self.rt2, user_id)

        # Check metainfo
        assert snk in metainfo1
        assert snk in metainfo2
        assert data1[snk][0][1] in metainfo1[snk]
        assert data2[snk][0][1] in metainfo2[snk]

        # Check that the sink produced something
        expected = expected_tokens(self.rt1, src)
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual)
        # Verify action times of data2 is in middle of data1

        limits = (min([data[0] for data in data2[snk]]), max([data[0] for data in data2[snk]]))
        v = [data[0] for data in data1[snk]]
        assert len(filter(lambda x: x > limits[0] and x < limits[1], v)) == 0
        assert len(filter(lambda x: x < limits[0], v)) > 0
        assert len(filter(lambda x: x > limits[1], v)) > 0
        # Verify about same number of tokens (time diff makes exact match not possible)
        diff = len(data1[snk]) + len(data2[snk]) - len(actual)
        assert diff > -3 and diff < 3
        request_handler.unregister_metering(self.rt1, user_id)
        request_handler.unregister_metering(self.rt2, user_id)
        helpers.destroy_app(d)


    @pytest.mark.slow
    def testAggregatedMigratingMetering(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
          src : std.CountTimer()
          snk : io.StandardOut(store_tokens=1, quiet=1)
          src.integer > snk.token
          """

        r1 = request_handler.register_metering(self.rt1)
        user_id = r1['user_id']
        # Register as same user to keep it simple
        r2 = request_handler.register_metering(self.rt2, user_id)
        # deploy app
        app_info, errors, warnings = self.compile_script(script, "simple")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()
        
        snk = d.actor_map['simple:snk']
        src = d.actor_map['simple:src']
        # migrate sink back and forth
        tokens = len(wait_for_tokens(self.rt1, snk))

        self.migrate(self.rt1, self.rt2, snk)
        tokens = len(wait_for_tokens(self.rt2, snk, tokens+5))
        self.migrate(self.rt2, self.rt1, snk)
        tokens = len(wait_for_tokens(self.rt1, snk, tokens+5))
        
        # Get metering
        metainfo1 = request_handler.get_actorinfo_metering(self.rt1, user_id)
        data1 = request_handler.get_timed_metering(self.rt1, user_id)
        agg2 = request_handler.get_aggregated_metering(self.rt2, user_id)
        data2 = request_handler.get_timed_metering(self.rt2, user_id)
        agg1 = request_handler.get_aggregated_metering(self.rt1, user_id)
        metainfo2 = request_handler.get_actorinfo_metering(self.rt2, user_id)
        
        # Check metainfo
        assert snk in metainfo1
        assert snk in metainfo2
        assert data1[snk][0][1] in metainfo1[snk]
        assert data2[snk][0][1] in metainfo2[snk]
        
        # Check that the sink produced something
        expected = expected_tokens(self.rt1, src)
        actual = actual_tokens(self.rt1, snk, len(expected))
        self.assert_lists_equal(expected, actual)
        
        # Verify about same number of tokens (time diff makes exact match not possible)
        total_timed = len(data1[snk]) + len(data2[snk])
        diff = total_timed - len(actual)
        assert diff > -3 and diff < 3
        total_agg = sum(agg1['activity'][snk].values()) + sum(agg2['activity'][snk].values())
        diff = total_agg - len(actual)
        assert diff > -3 and diff < 3
        assert sum(agg1['activity'][snk].values()) >= len(data1[snk])
        assert sum(agg2['activity'][snk].values()) <= len(data2[snk])
        request_handler.unregister_metering(self.rt1, user_id)
        request_handler.unregister_metering(self.rt2, user_id)
        helpers.destroy_app(d)


    @pytest.mark.slow
    def testLateAggregatedMigratingMetering(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
          src : std.CountTimer()
          snk : io.StandardOut(store_tokens=1, quiet=1)
          src.integer > snk.token
          """

        # deploy app
        app_info, errors, warnings = self.compile_script(script, "simple")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()
        
        src = d.actor_map['simple:src']
        snk = d.actor_map['simple:snk']
        
        # migrate sink back and forth
        tokens = len(wait_for_tokens(self.rt1, snk))
        self.migrate(self.rt1, self.rt2, snk)
        tokens = len(wait_for_tokens(self.rt2, snk, tokens+5))
        self.migrate(self.rt2, self.rt1, snk)
        tokens = len(wait_for_tokens(self.rt1, snk, tokens+5))

        # Metering
        r1 = request_handler.register_metering(self.rt1)
        user_id = r1['user_id']

        # Register as same user to keep it simple
        r2 = request_handler.register_metering(self.rt2, user_id)
        metainfo1 = request_handler.get_actorinfo_metering(self.rt1, user_id)
        agg2 = request_handler.get_aggregated_metering(self.rt2, user_id)
        agg1 = request_handler.get_aggregated_metering(self.rt1, user_id)
        metainfo2 = request_handler.get_actorinfo_metering(self.rt2, user_id)

        # Check metainfo
        assert snk in metainfo1
        assert snk in metainfo2

        # Check that the sink produced something
        expected = expected_tokens(self.rt1, src)
        actual = actual_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual)
        
        total_agg = sum(agg1['activity'][snk].values()) + sum(agg2['activity'][snk].values())
        diff = total_agg - len(actual)
        assert diff > -3 and diff < 3
        request_handler.unregister_metering(self.rt1, user_id)
        request_handler.unregister_metering(self.rt2, user_id)
        
        helpers.destroy_app(d)


class TestStateMigration(CalvinTestBase):

    def testSimpleState(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
          src : std.CountTimer()
          sum : std.Sum()
          snk : io.StandardOut(store_tokens=1, quiet=1)
          src.integer > sum.integer
          sum.integer > snk.token
          """
        app_info, errors, warnings = self.compile_script(script, "simple")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()
        
        src = d.actor_map['simple:src']
        csum = d.actor_map['simple:sum']
        snk = d.actor_map['simple:snk']

        tokens = len(wait_for_tokens(self.rt1, snk))
        self.migrate(self.rt1, self.rt2, csum)
    
        actual = request_handler.report(self.rt1, snk, tokens+5)
        expected = expected_tokens(self.rt1, src, 'sum')

        self.assert_lists_equal(expected, actual)
        helpers.destroy_app(d)


@pytest.mark.slow
@pytest.mark.essential
class TestAppLifeCycle(CalvinTestBase):

    def testAppDestructionOneRemote(self):
        from functools import partial
        
        _log.analyze("TESTRUN", "+", {})
        script = """
          src : std.CountTimer()
          sum : std.Sum()
          snk : io.StandardOut(store_tokens=1, quiet=1)
          src.integer > sum.integer
          sum.integer > snk.token
          """
        app_info, errors, warnings = self.compile_script(script, "simple")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        src = d.actor_map['simple:src']
        csum = d.actor_map['simple:sum']
        snk = d.actor_map['simple:snk']

        tokens = len(wait_for_tokens(self.rt1, snk))
        self.migrate(self.rt1, self.rt2, csum)
        
        actual = actual_tokens(self.rt1, snk, tokens+5)
        expected = expected_tokens(self.rt1, src, 'sum')

        self.assert_lists_equal(expected, actual)
        
        helpers.delete_app(request_handler, self.rt1, d.app_id)
        
        def check_actors(runtime):
            for actor in src, csum, snk:
                a = request_handler.get_actor(runtime, actor)
                if a is not None:
                    _log.info("Actor '%r' still present on runtime '%r" % (actor, runtime.id, ))
                    return False
            return True

        for rt in [ self.rt1, self.rt2, self.rt3 ]:
            check_rt = partial(check_actors, rt)
            all_gone = helpers.retry(20, check_rt, lambda x: x, "Not all actors gone on rt '%r'" % (rt.id, ))
            assert all_gone

        def check_application(runtime):
            try :
                app = request_handler.get_application(runtime, d.app_id)
            except Exception as e:
                msg = str(e.message)
                if msg.startswith(404):
                    return True
            return app is None
            
        for rt in [ self.rt1, self.rt2, self.rt3 ]:
            check_rt = partial(check_application, rt)
            all_gone = helpers.retry(20, check_rt, lambda x: x, "Application still present on rt '%r'" % (rt.id, ))
            assert all_gone
            
        self.assertTrue(request_handler.get_application(self.rt1, d.app_id) is None)
        self.assertTrue(request_handler.get_application(self.rt2, d.app_id) is None)
        self.assertTrue(request_handler.get_application(self.rt3, d.app_id) is None)

    def testAppDestructionAllRemote(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
          src : std.CountTimer()
          sum : std.Sum()
          snk : io.StandardOut(store_tokens=1, quiet=1)
          src.integer > sum.integer
          sum.integer > snk.token
          """
        #? import sys
        #? from twisted.python import log
        #? log.startLogging(sys.stdout)

        app_info, errors, warnings = self.compile_script(script, "simple")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        src = d.actor_map['simple:src']
        csum = d.actor_map['simple:sum']
        snk = d.actor_map['simple:snk']

        tokens = len(wait_for_tokens(self.rt1, snk))
        
        self.migrate(self.rt1, self.rt2, src)
        self.migrate(self.rt1, self.rt2, csum)
        self.migrate(self.rt1, self.rt2, snk)
        
        actual = actual_tokens(self.rt2, snk, tokens+5)
        expected = expected_tokens(self.rt2, src, 'sum')

        self.assert_lists_equal(expected, actual)
        
        helpers.delete_app(request_handler, self.rt1, d.app_id)

        def verify_gone(runtime, actor):
            import json
            a = request_handler.get_actor(runtime, actor)
            if a is not None:
                _log.info("Actor: %s" % (json.dumps(a, default=str, indent=2)))
            return a is None
            
        delay = 0.1
        for a in range(20):
            all_removed = None
            try:
                for rt in [ self.rt1, self.rt2, self.rt3 ]:
                    for actor in [ src, csum, snk ]:
                        self.assertTrue(verify_gone(rt, actor))
            except AssertionError as e:
                print a, e
                all_removed = e
            if all_removed is None:
                break
            _log.info("Not all actors gone, checking in %f" % (delay,))
            time.sleep(delay)
            delay *= 2

        if all_removed:
            raise all_removed

        self.assertTrue(request_handler.get_application(self.rt1, d.app_id) is None)
        self.assertTrue(request_handler.get_application(self.rt2, d.app_id) is None)
        self.assertTrue(request_handler.get_application(self.rt3, d.app_id) is None)


@pytest.mark.essential
class TestEnabledToEnabledBug(CalvinTestBase):

    def test10(self):
        _log.analyze("TESTRUN", "+", {})
        # Two actors, doesn't seem to trigger the bug
        src = request_handler.new_actor(self.rt1, 'std.Counter', 'src')
        snk = request_handler.new_actor_wargs(self.rt1, 'io.StandardOut', 'snk', store_tokens=1, quiet=1)

        request_handler.connect(self.rt1, snk, 'token', self.rt1.id, src, 'integer')

        actual = actual_tokens(self.rt1, snk, 10)

        self.assert_lists_equal(range(1, 10), actual)

        request_handler.delete_actor(self.rt1, src)
        request_handler.delete_actor(self.rt1, snk)

    def test11(self):
        _log.analyze("TESTRUN", "+", {})
        # Same as test10, but scripted
        script = """
            src : std.Counter()
            snk : io.StandardOut(store_tokens=1, quiet=1)

            src.integer > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "simple")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['simple:snk']

        actual = actual_tokens(self.rt1, snk, 10)
        self.assert_lists_equal(range(1, 10), actual)

        helpers.destroy_app(d)

    def test20(self):
        _log.analyze("TESTRUN", "+", {})
        src = request_handler.new_actor(self.rt1, 'std.Counter', 'src')
        ity = request_handler.new_actor(self.rt1, 'std.Identity', 'ity')
        snk = request_handler.new_actor_wargs(self.rt1, 'io.StandardOut', 'snk', store_tokens=1, quiet=1)

        request_handler.connect(self.rt1, snk, 'token', self.rt1.id, ity, 'token')
        request_handler.connect(self.rt1, ity, 'token', self.rt1.id, src, 'integer')

        actual = actual_tokens(self.rt1, snk, 10)

        self.assert_lists_equal(range(1, 10), actual)

        request_handler.delete_actor(self.rt1, src)
        request_handler.delete_actor(self.rt1, ity)
        request_handler.delete_actor(self.rt1, snk)

    def test21(self):
        _log.analyze("TESTRUN", "+", {})
        src = request_handler.new_actor(self.rt1, 'std.Counter', 'src')
        ity = request_handler.new_actor(self.rt2, 'std.Identity', 'ity')
        snk = request_handler.new_actor_wargs(self.rt3, 'io.StandardOut', 'snk', store_tokens=1, quiet=1)

        request_handler.connect(self.rt3, snk, 'token', self.rt2.id, ity, 'token')
        request_handler.connect(self.rt2, ity, 'token', self.rt1.id, src, 'integer')

        actual = actual_tokens(self.rt3, snk, 10)
        self.assert_lists_equal(range(1,10), actual)

        request_handler.delete_actor(self.rt1, src)
        request_handler.delete_actor(self.rt2, ity)
        request_handler.delete_actor(self.rt3, snk)

    def test22(self):
        _log.analyze("TESTRUN", "+", {})
        src = request_handler.new_actor(self.rt1, 'std.Counter', 'src')
        ity = request_handler.new_actor(self.rt2, 'std.Identity', 'ity')
        snk = request_handler.new_actor_wargs(self.rt3, 'io.StandardOut', 'snk', store_tokens=1, quiet=1)

        request_handler.connect(self.rt2, ity, 'token', self.rt1.id, src, 'integer')
        request_handler.connect(self.rt3, snk, 'token', self.rt2.id, ity, 'token')

        actual = actual_tokens(self.rt3, snk, 10)
        self.assert_lists_equal(range(1,10), actual)

        actual = actual_tokens(self.rt3, snk, len(actual)+1)
        self.assert_lists_equal(range(1,len(actual)), actual)

        request_handler.delete_actor(self.rt1, src)
        request_handler.delete_actor(self.rt2, ity)
        request_handler.delete_actor(self.rt3, snk)

    def test25(self):
        _log.analyze("TESTRUN", "+", {})
        src = request_handler.new_actor(self.rt1, 'std.Counter', 'src')
        ity = request_handler.new_actor(self.rt1, 'std.Identity', 'ity')
        snk = request_handler.new_actor_wargs(self.rt1, 'io.StandardOut', 'snk', store_tokens=1, quiet=1)

        request_handler.connect(self.rt1, ity, 'token', self.rt1.id, src, 'integer')
        request_handler.connect(self.rt1, snk, 'token', self.rt1.id, ity, 'token')

        actual = actual_tokens(self.rt1, snk, 10)

        self.assert_lists_equal(range(1, 10), actual)

        request_handler.delete_actor(self.rt1, src)
        request_handler.delete_actor(self.rt1, ity)
        request_handler.delete_actor(self.rt1, snk)

    def test26(self):
        _log.analyze("TESTRUN", "+", {})
        # Same as test20
        script = """
            src : std.Counter()
            ity : std.Identity()
            snk : io.StandardOut(store_tokens=1, quiet=1)

            src.integer > ity.token
            ity.token > snk.token
          """
        app_info, errors, warnings = self.compile_script(script, "simple")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()
        snk = d.actor_map['simple:snk']
        
        actual = actual_tokens(self.rt1, snk, 10)        
        self.assert_lists_equal(range(1,10), actual)

        helpers.destroy_app(d)


    def test30(self):
        _log.analyze("TESTRUN", "+", {})
        src = request_handler.new_actor(self.rt1, 'std.Counter', 'src')
        snk1 = request_handler.new_actor_wargs(self.rt1, 'io.StandardOut', 'snk1', store_tokens=1, quiet=1)
        snk2 = request_handler.new_actor_wargs(self.rt1, 'io.StandardOut', 'snk2', store_tokens=1, quiet=1)

        request_handler.set_port_property(self.rt1, src, 'out', 'integer',
                                            port_properties={'routing': 'fanout', 'nbr_peers': 2})

        request_handler.connect(self.rt1, snk1, 'token', self.rt1.id, src, 'integer')
        request_handler.connect(self.rt1, snk2, 'token', self.rt1.id, src, 'integer')

        actual1 = actual_tokens(self.rt1, snk1, 10)
        actual2 = actual_tokens(self.rt1, snk2, 10)

        self.assert_lists_equal(list(range(1, 10)), actual1)
        self.assert_lists_equal(list(range(1, 10)), actual2)

        request_handler.delete_actor(self.rt1, src)
        request_handler.delete_actor(self.rt1, snk1)
        request_handler.delete_actor(self.rt1, snk2)

    def test31(self):
        # Verify that fanout defined implicitly in scripts is handled correctly
        _log.analyze("TESTRUN", "+", {})
        script = """
            src : std.Counter()
            snk1 : io.StandardOut(store_tokens=1, quiet=1)
            snk2 : io.StandardOut(store_tokens=1, quiet=1)

            src.integer > snk1.token
            src.integer > snk2.token
        """
        app_info, errors, warnings = self.compile_script(script, "test31")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()
        
        snk1 = d.actor_map['test31:snk1']
        snk2 = d.actor_map['test31:snk2']
        actual1 = actual_tokens(self.rt1, snk1, 10)
        actual2 = actual_tokens(self.rt1, snk2, 10)
        expected = list(range(1, 10))

        self.assert_lists_equal(expected, actual1)
        self.assert_lists_equal(expected, actual2)

        d.destroy()

    def test32(self):
        # Verify that fanout from component inports is handled correctly
        _log.analyze("TESTRUN", "+", {})
        script = """
            component Foo() in -> a, b{
              a : std.Identity()
              b : std.Identity()
              .in >  a.token
              .in > b.token
              a.token > .a
              b.token > .b
            }

            snk2 : io.StandardOut(store_tokens=1, quiet=1)
            snk1 : io.StandardOut(store_tokens=1, quiet=1)
            foo : Foo()
            req : std.Counter()
            req.integer > foo.in
            foo.a > snk1.token
            foo.b > snk2.token
        """
        app_info, errors, warnings = self.compile_script(script, "test32")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk1 = d.actor_map['test32:snk1']
        snk2 = d.actor_map['test32:snk2']
        actual1 = actual_tokens(self.rt1, snk1, 10)
        actual2 = actual_tokens(self.rt1, snk2, 10)
        expected = list(range(1, 10))

        self.assert_lists_equal(expected, actual1)
        self.assert_lists_equal(expected, actual2)

        d.destroy()

    def test40(self):
        # Verify round robin port
        _log.analyze("TESTRUN", "+", {})
        src = request_handler.new_actor(self.rt1, 'std.Counter', 'src')
        snk1 = request_handler.new_actor_wargs(self.rt1, 'io.StandardOut', 'snk1', store_tokens=1, quiet=1)
        snk2 = request_handler.new_actor_wargs(self.rt1, 'io.StandardOut', 'snk2', store_tokens=1, quiet=1)

        request_handler.set_port_property(self.rt1, src, 'out', 'integer',
                                            port_properties={'routing': 'round-robin', 'nbr_peers': 2})

        request_handler.connect(self.rt1, snk1, 'token', self.rt1.id, src, 'integer')
        request_handler.connect(self.rt1, snk2, 'token', self.rt1.id, src, 'integer')

        snk1_meta = request_handler.get_actor(self.rt1, snk1)
        snk2_meta = request_handler.get_actor(self.rt1, snk2)
        snk1_token_id = snk1_meta['inports'][0]['id']
        snk2_token_id = snk2_meta['inports'][0]['id']

        actual1 = actual_tokens(self.rt1, snk1, 10)
        actual2 = actual_tokens(self.rt1, snk2, 10)

        # Round robin lowest peer id get first token
        start = 1 if snk1_token_id < snk2_token_id else 2
        self.assert_lists_equal(list(range(start, 20, 2)), actual1)
        start = 1 if snk1_token_id > snk2_token_id else 2
        self.assert_lists_equal(list(range(start, 20, 2)), actual2)

        request_handler.delete_actor(self.rt1, src)
        request_handler.delete_actor(self.rt1, snk1)
        request_handler.delete_actor(self.rt1, snk2)



@pytest.mark.essential
class TestNullPorts(CalvinTestBase):

    def testVoidActor(self):
        # Verify that the null port of a std.Void actor behaves as expected
        _log.analyze("TESTRUN", "+", {})
        script = """
            src1 : std.Counter()
            src2 : std.Void()
            join : std.Join()
            snk  : io.StandardOut(store_tokens=1, quiet=1)

            src1.integer > join.token_1
            src2.void > join.token_2
            join.token > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testVoidActor")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testVoidActor:snk']        
        actual = wait_for_tokens(self.rt1, snk, 10)
        expected = list(range(1, 10))
        self.assert_lists_equal(expected, actual)

        helpers.destroy_app(d)

    def testTerminatorActor(self):
        # Verify that the null port of a std.Terminator actor behaves as expected
        _log.analyze("TESTRUN", "+", {})
        script = """
            src  : std.Counter()
            term : std.Terminator()
            snk  : io.StandardOut(store_tokens=1, quiet=1)

            src.integer > term.void
            src.integer > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testTerminatorActor")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()
        
        snk = d.actor_map['testTerminatorActor:snk']
        actual = wait_for_tokens(self.rt1, snk)        
        expected = list(range(1, 10))

        self.assert_lists_equal(expected, actual)
        helpers.destroy_app(d)


@pytest.mark.essential
class TestCompare(CalvinTestBase):

    def testBadOp(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src   : std.Counter()
            const : std.Constant(data=5, n=-1)
            pred  : std.Compare(op="<>")
            snk   : io.StandardOut(store_tokens=1, quiet=1)

            src.integer > pred.a
            const.token > pred.b
            pred.result > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testBadOp")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testBadOp:snk']
        actual = wait_for_tokens(self.rt1, snk, 10)
        expected = [0] * 10

        self.assert_lists_equal(expected, actual)
        helpers.destroy_app(d)

    def testEqual(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src   : std.Counter()
            const : std.Constant(data=5, n=-1)
            pred  : std.Compare(op="=")
            snk   : io.StandardOut(store_tokens=1, quiet=1)

            src.integer > pred.a
            const.token > pred.b
            pred.result > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testEqual")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testEqual:snk']

        expected = [x == 5 for x in range(1, 10)]
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual)
        helpers.destroy_app(d)


    def testGreaterThanOrEqual(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src   : std.Counter()
            const : std.Constant(data=5, n=-1)
            pred  : std.Compare(op=">=")
            snk   : io.StandardOut(store_tokens=1, quiet=1)

            src.integer > pred.a
            const.token > pred.b
            pred.result > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testGreaterThanOrEqual")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testGreaterThanOrEqual:snk']
        expected = [x >= 5 for x in range(1, 10)]
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual)
        helpers.destroy_app(d)



@pytest.mark.essential
class TestSelect(CalvinTestBase):

    def testTrue(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src   : std.Counter()
            const : std.Constant(data=true, n=-1)
            route : std.Select()
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            term  : std.Terminator()

            src.integer > route.data
            const.token > route.select
            route.case_true  > snk.token
            route.case_false > term.void
        """
        app_info, errors, warnings = self.compile_script(script, "testTrue")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testTrue:snk']
        actual = wait_for_tokens(self.rt1, snk, 10)
        expected = list(range(1, 10))

        self.assert_lists_equal(expected, actual)
        helpers.destroy_app(d)

    def testFalse(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src   : std.Counter()
            const : std.Constant(data=0, n=-1)
            route : std.Select()
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            term  : std.Terminator()

            src.integer > route.data
            const.token > route.select
            route.case_true  > term.void
            route.case_false > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testFalse")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testFalse:snk']
      
        actual = wait_for_tokens(self.rt1, snk, 10)
        expected = list(range(1, 10))

        self.assert_lists_equal(expected, actual)
        helpers.destroy_app(d)


    def testBadSelect(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src   : std.Counter()
            const : std.Constant(data=2, n=-1)
            route : std.Select()
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            term  : std.Terminator()

            src.integer > route.data
            const.token > route.select
            route.case_true  > term.void
            route.case_false > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testBadSelect")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testBadSelect:snk']
        actual = wait_for_tokens(self.rt1, snk, 10)
        expected = list(range(1, 10))

        self.assert_lists_equal(expected, actual)
        
        helpers.destroy_app(d)


@pytest.mark.essential
class TestDeselect(CalvinTestBase):

    def testDeselectTrue(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src     : std.Counter()
            const_5 : std.Constantify(constant=5)
            const_0 : std.Constant(data=0, n=-1)
            const_1 : std.Constant(data=1, n=-1)
            comp    : std.Compare(op="<=")
            ds      : std.Deselect()
            snk     : io.StandardOut(store_tokens=1, quiet=1)

            const_0.token > ds.case_false
            const_1.token > ds.case_true
            src.integer > comp.a
            src.integer > const_5.in
            const_5.out > comp.b
            comp.result > ds.select
            ds.data > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testDeselectTrue")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testDeselectTrue:snk']

        expected = [1] * 5 + [0] * 5
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=10)
        helpers.destroy_app(d)

    def testDeselectFalse(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src     : std.Counter()
            const_5 : std.Constantify(constant=5)
            const_0 : std.Constant(data=0, n=-1)
            const_1 : std.Constant(data=1, n=-1)
            comp    : std.Compare(op="<=")
            ds      : std.Deselect()
            snk     : io.StandardOut(store_tokens=1, quiet=1)

            const_0.token > ds.case_true
            const_1.token > ds.case_false
            src.integer > comp.a
            src.integer > const_5.in
            const_5.out > comp.b
            comp.result > ds.select
            ds.data > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testDeselectFalse")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testDeselectFalse:snk']

        expected = [0] * 5 + [1] * 5
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=10)
        
        helpers.destroy_app(d)


    def testDeselectBadSelect(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src     : std.Counter()
            const_5 : std.Constantify(constant=5)
            const_0 : std.Constant(data=0, n=11)
            ds      : std.Deselect()
            snk     : io.StandardOut(store_tokens=1, quiet=1)

            const_0.token > ds.case_false
            src.integer > ds.case_true
            const_0.token > const_5.in
            const_5.out > ds.select
            ds.data > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testDeselectBadSelect")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testDeselectBadSelect:snk']

        expected = [0] * 10
        actual = wait_for_tokens(self.rt1, snk, len(expected))
        
        self.assert_lists_equal(expected, actual, min_length=10)

        helpers.destroy_app(d)


@pytest.mark.essential
class TestLineJoin(CalvinTestBase):

    def testBasicJoin(self):
        _log.analyze("TESTRUN", "+", {})
        datafile = absolute_filename('data.txt')
        script = """
            fname : std.Constant(data="%s")
            src   : io.FileReader()
            join  : text.LineJoin()
            snk   : io.StandardOut(store_tokens=1, quiet=1)

            fname.token > src.filename
            src.out   > join.line
            join.text > snk.token
        """ % (datafile, )
        
        app_info, errors, warnings = self.compile_script(script, "testBasicJoin")
        print errors
       
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        with open(datafile, "r") as fp:
            expected = ["\n".join([l.rstrip() for l in fp.readlines()])]

        snk = d.actor_map['testBasicJoin:snk']

        actual = wait_for_tokens(self.rt1, snk, 1)

        self.assert_lists_equal(expected, actual, min_length=1)

        helpers.destroy_app(d)


@pytest.mark.essential
class TestRegex(CalvinTestBase):

    def testRegexMatch(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src   : std.Constant(data="24.1632", n=1)
            regex : text.RegexMatch(regex=!"\d+\.\d+")
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            term  : std.Terminator()

            src.token      > regex.text
            regex.match    > snk.token
            regex.no_match > term.void
        """
        app_info, errors, warnings = self.compile_script(script, "testRegexMatch")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testRegexMatch:snk']

        expected = ["24.1632"]
        actual = wait_for_tokens(self.rt1, snk, 1)

        self.assert_lists_equal(expected, actual, min_length=1)

        helpers.destroy_app(d)



    def testRegexNoMatch(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src   : std.Constant(data="x24.1632", n=1)
            regex : text.RegexMatch(regex=!"\d+\.\d+")
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            term  : std.Terminator()

            src.token      > regex.text
            regex.no_match > snk.token
            regex.match    > term.void
        """
        app_info, errors, warnings = self.compile_script(script, "testRegexNoMatch")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testRegexNoMatch:snk']
        expected = ["x24.1632"]
        actual = wait_for_tokens(self.rt1, snk, 1)
        
        self.assert_lists_equal(expected, actual, min_length=1)

        helpers.destroy_app(d)


    def testRegexCapture(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src   : std.Constant(data="24.1632", n=1)
            regex : text.RegexMatch(regex=!"(\d+)\.\d+")
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            term  : std.Terminator()

            src.token      > regex.text
            regex.match    > snk.token
            regex.no_match > term.void
        """
        app_info, errors, warnings = self.compile_script(script, "testRegexCapture")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testRegexCapture:snk']

        expected = ["24"]
        actual = wait_for_tokens(self.rt1, snk, 1)

        self.assert_lists_equal(expected, actual, min_length=1)

        helpers.destroy_app(d)


    def testRegexMultiCapture(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src   : std.Constant(data="24.1632", n=1)
            regex : text.RegexMatch(regex=!"(\d+)\.(\d+)")
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            term  : std.Terminator()

            src.token      > regex.text
            regex.match    > snk.token
            regex.no_match > term.void
        """
        app_info, errors, warnings = self.compile_script(script, "testRegexMultiCapture")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testRegexMultiCapture:snk']

        expected = ["24"]
        actual = wait_for_tokens(self.rt1, snk, 1)

        self.assert_lists_equal(expected, actual, min_length=1)

        helpers.destroy_app(d)


    def testRegexCaptureNoMatch(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src   : std.Constant(data="x24.1632", n=1)
            regex : text.RegexMatch(regex=!"(\d+)\.\d+")
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            term  : std.Terminator()

            src.token      > regex.text
            regex.no_match > snk.token
            regex.match    > term.void
        """
        app_info, errors, warnings = self.compile_script(script, "testRegexCaptureNoMatch")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testRegexCaptureNoMatch:snk']
        expected = ["x24.1632"]
        actual = wait_for_tokens(self.rt1, snk, 1)

        self.assert_lists_equal(expected, actual, min_length=1)

        helpers.destroy_app(d)


@pytest.mark.essential
class TestConstantAsArguments(CalvinTestBase):

    def testConstant(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            define FOO = 42
            src   : std.Constant(data=FOO, n=10)
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            src.token > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testConstant")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testConstant:snk']

        expected = [42]*10
        actual = wait_for_tokens(self.rt1, snk, len(expected))
        
        self.assert_lists_equal(expected, actual, min_length=10)

        helpers.destroy_app(d)

    def testConstantRecursive(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            define FOO = BAR
            define BAR = 42
            src   : std.Constant(data=FOO, n=10)
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            src.token > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testConstantRecursive")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testConstantRecursive:snk']

        expected = [42]*10
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=10)

        helpers.destroy_app(d)


@pytest.mark.essential
class TestConstantOnPort(CalvinTestBase):

    def testLiteralOnPort(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            42 > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testLiteralOnPort")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()
        time.sleep(.1)

        snk = d.actor_map['testLiteralOnPort:snk']

        expected = [42]*10
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=10)

        helpers.destroy_app(d)

    def testConstantOnPort(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            define FOO = "Hello"
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            FOO > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testConstantOnPort")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testConstantOnPort:snk']

        expected = ["Hello"]*10
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=10)

        helpers.destroy_app(d)

    def testConstantRecursiveOnPort(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            define FOO = BAR
            define BAR = "yay"
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            FOO > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testConstantRecursiveOnPort")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testConstantRecursiveOnPort:snk']

        expected = ["yay"]*10
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=10)

        helpers.destroy_app(d)


@pytest.mark.essential
class TestConstantAndComponents(CalvinTestBase):

    def testLiteralOnCompPort(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            component Foo() -> out {
                i:std.Stringify()
                42 > i.in
                i.out > .out
            }
            src   : Foo()
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            src.out > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testLiteralOnCompPort")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testLiteralOnCompPort:snk']

        expected = ["42"]*10
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=10)

        helpers.destroy_app(d)

    def testConstantOnCompPort(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            define MEANING = 42
            component Foo() -> out {
                i:std.Stringify()
                MEANING > i.in
                i.out > .out
            }
            src   : Foo()
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            src.out > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testConstantOnCompPort")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testConstantOnCompPort:snk']

        expected = ["42"]*10
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=10)

        helpers.destroy_app(d)

    def testStringConstantOnCompPort(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            define MEANING = "42"
            component Foo() -> out {
                i:std.Identity()
                MEANING > i.token
                i.token > .out
            }
            src   : Foo()
            snk   : io.StandardOut(store_tokens=1, quiet=1)
            src.out > snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testStringConstantOnCompPort")
        print errors
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testStringConstantOnCompPort:snk']

        expected = ["42"]*10
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=10)

        helpers.destroy_app(d)


@pytest.mark.essential
class TestConstantAndComponentsArguments(CalvinTestBase):

    def testComponentArgument(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
        component Count(len) -> seq {
            src : std.Constant(data="hup", n=len)
            src.token > .seq
        }
        src : Count(len=5)
        snk : io.StandardOut(store_tokens=1, quiet=1)
        src.seq > snk.token
        """

        app_info, errors, warnings = self.compile_script(script, "testComponentArgument")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testComponentArgument:snk']

        expected = ["hup"]*5
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=5)

        helpers.destroy_app(d)

    def testComponentConstantArgument(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
        define FOO = 5
        component Count(len) -> seq {
            src : std.Constant(data="hup", n=len)
            src.token > .seq
        }
        src : Count(len=FOO)
        snk : io.StandardOut(store_tokens=1, quiet=1)
        src.seq > snk.token
        """

        app_info, errors, warnings = self.compile_script(script, "testComponentConstantArgument")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testComponentConstantArgument:snk']

        expected = ["hup"]*5
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=5)
        
        helpers.destroy_app(d)


    def testComponentConstantArgumentDirect(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
        define FOO = 10
        component Count() -> seq {
         src : std.Constant(data="hup", n=FOO)
         src.token > .seq
        }
        src : Count()
        snk : io.StandardOut(store_tokens=1, quiet=1)
        src.seq > snk.token
        """

        app_info, errors, warnings = self.compile_script(script, "testComponentConstantArgumentDirect")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testComponentConstantArgumentDirect:snk']

        expected = ["hup"]*10
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=10)

        helpers.destroy_app(d)

    def testComponentArgumentAsImplicitActor(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
        component Count(data) -> seq {
            i : std.Identity()
            data > i.token
            i.token > .seq
        }
        src : Count(data="hup")
        snk : io.StandardOut(store_tokens=1, quiet=1)
        src.seq > snk.token
        """

        app_info, errors, warnings = self.compile_script(script, "testComponentArgumentAsImplicitActor")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testComponentArgumentAsImplicitActor:snk']

        expected = ["hup"]*10
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=10)

        helpers.destroy_app(d)

    def testComponentConstantArgumentAsImplicitActor(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
        define FOO = "hup"
        component Count(data) -> seq {
            i : std.Identity()
            data > i.token
            i.token > .seq
        }
        src : Count(data=FOO)
        snk : io.StandardOut(store_tokens=1, quiet=1)
        src.seq > snk.token
        """

        app_info, errors, warnings = self.compile_script(script, "testComponentConstantArgumentAsImplicitActor")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk = d.actor_map['testComponentConstantArgumentAsImplicitActor:snk']

        expected = ["hup"]*10
        actual = wait_for_tokens(self.rt1, snk, len(expected))

        self.assert_lists_equal(expected, actual, min_length=10)
        d.destroy()

@pytest.mark.essential
class TestConstantifyOnPort(CalvinTestBase):

    def testLiteralOnPort(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src : std.Counter()
            snk : io.StandardOut(store_tokens=1, quiet=1)
            src.integer > /"X"/ snk.token
        """
        app_info, errors, warnings = self.compile_script(script, "testLiteralOnPort")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()
        
        snk = d.actor_map['testLiteralOnPort:snk']

        actual = wait_for_tokens(self.rt1, snk, 10)
        expected = ['X']*len(actual)

        self.assert_lists_equal(expected, actual, min_length=10)

        d.destroy()

    def testLiteralOnPortlist(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src : std.Counter()
            snk1 : io.StandardOut(store_tokens=1, quiet=1)
            snk2 : io.StandardOut(store_tokens=1, quiet=1)
            src.integer > /"X"/ snk1.token, snk2.token
        """
        app_info, errors, warnings = self.compile_script(script, "testLiteralOnPortlist")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk1 = d.actor_map['testLiteralOnPortlist:snk1']
        snk2 = d.actor_map['testLiteralOnPortlist:snk2']
        
        actual1 = wait_for_tokens(self.rt1, snk1, 10)
        actual2 = wait_for_tokens(self.rt1, snk2, 10)
        
        expected1 = ['X']*len(actual1)
        expected2 = range(1, len(actual2))

        self.assert_lists_equal(expected1, actual1, min_length=10)
        self.assert_lists_equal(expected2, actual2, min_length=10)

        d.destroy()

    def testLiteralsOnPortlist(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            src : std.Counter()
            snk1 : io.StandardOut(store_tokens=1, quiet=1)
            snk2 : io.StandardOut(store_tokens=1, quiet=1)
            src.integer > /"X"/ snk1.token, /"Y"/ snk2.token
        """
        app_info, errors, warnings = self.compile_script(script, "testLiteralsOnPortlist")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk1 = d.actor_map['testLiteralsOnPortlist:snk1']
        snk2 = d.actor_map['testLiteralsOnPortlist:snk2']
        actual1 = wait_for_tokens(self.rt1, snk1, 10)
        actual2 = wait_for_tokens(self.rt1, snk2, 10)
        
        expected1 = ['X']*len(actual1)
        expected2 = ['Y']*len(actual2)

        self.assert_lists_equal(expected1, actual1, min_length=10)
        self.assert_lists_equal(expected2, actual2, min_length=10)

        d.destroy()

    def testConstantsOnPortlist(self):
        _log.analyze("TESTRUN", "+", {})
        script = """
            define FOO = "X"
            define BAR = "Y"
            src : std.Counter()
            snk1 : io.StandardOut(store_tokens=1, quiet=1)
            snk2 : io.StandardOut(store_tokens=1, quiet=1)
            src.integer > /FOO/ snk1.token, /BAR/ snk2.token
        """
        app_info, errors, warnings = self.compile_script(script, "testConstantsOnPortlist")
        d = deployer.Deployer(self.rt1, app_info)
        d.deploy()

        snk1 = d.actor_map['testConstantsOnPortlist:snk1']
        snk2 = d.actor_map['testConstantsOnPortlist:snk2']

        actual1 = wait_for_tokens(self.rt1, snk1, 10)
        actual2 = wait_for_tokens(self.rt1, snk2, 10)
        expected1 = ['X']*len(actual1)
        expected2 = ['Y']*len(actual2)

        self.assert_lists_equal(expected1, actual1, min_length=10)
        self.assert_lists_equal(expected2, actual2, min_length=10)

        d.destroy()
