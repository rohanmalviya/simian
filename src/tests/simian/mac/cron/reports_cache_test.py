#!/usr/bin/env python
# 
# Copyright 2010 Google Inc. All Rights Reserved.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# #

"""reports_cache module tests."""



import datetime
import logging
logging.basicConfig(filename='/dev/null')
import random

from django.conf import settings
settings.configure()
from google.apputils import app
from google.apputils import basetest
import mox
import stubout
from simian.mac.cron import reports_cache


class ReportsCacheModuleTest(mox.MoxTestBase):

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.stubs = stubout.StubOutForTesting()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.stubs.UnsetAll()

  def testIsTimeDelta(self):
    """Test IsTimeDelta()."""
    dt1 = datetime.datetime(2009, 1, 1, 0, 0, 0)

    dt2 = dt1 + datetime.timedelta(seconds=10)
    self.assertTrue(
        reports_cache.IsTimeDelta(dt1, dt2, seconds=20) is not None)
    dt2 = dt1 + datetime.timedelta(seconds=30)
    self.assertFalse(
        reports_cache.IsTimeDelta(dt1, dt2, seconds=20) is not None)

    dt2 = dt1 + datetime.timedelta(minutes=10)
    self.assertTrue(
        reports_cache.IsTimeDelta(dt1, dt2, minutes=20) is not None)
    dt2 = dt1 + datetime.timedelta(minutes=30)
    self.assertFalse(
        reports_cache.IsTimeDelta(dt1, dt2, minutes=20) is not None)

    dt2 = dt1 + datetime.timedelta(hours=10)
    self.assertTrue(
        reports_cache.IsTimeDelta(dt1, dt2, hours=20) is not None)
    dt2 = dt1 + datetime.timedelta(hours=30)
    self.assertFalse(
        reports_cache.IsTimeDelta(dt1, dt2, hours=20) is not None)

    dt2 = dt1 + datetime.timedelta(days=10)
    self.assertTrue(
        reports_cache.IsTimeDelta(dt1, dt2, days=20) is not None)
    dt2 = dt1 + datetime.timedelta(days=30)
    self.assertFalse(
        reports_cache.IsTimeDelta(dt1, dt2, days=20) is not None)


class ReportsCacheCleanupTest(mox.MoxTestBase):

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.stubs = stubout.StubOutForTesting()

  def tearDown(self):
    self.mox.UnsetStubs()
    self.stubs.UnsetAll()

  def _GenDatetimes(self, *add_seconds):
    """Generate a random datetime and additional datetimes after it.

    Args:
      add_seconds: optional, integers supplied which will
        be added to the base random datetime.
    Returns:
      list of datetime objects, starting from a random datetime and
      including additional objects with offsets from add_seconds
    """
    d = datetime.datetime.fromtimestamp(random.randint(0, 2**31))
    output = [d]
    for add_second in add_seconds:
      output.append(d + datetime.timedelta(seconds=add_second))
    return output

  def _GenBaseSummaryOutput(self, rc):
    """Generate base summary info.

    Args:
      rc: ReportsCache instance
    Returns:
      dict, summary values initialized to 0
    """
    summary_output = {}
    for k in rc.USER_EVENTS:
      summary_output[k] = 0
    summary_output['total_events'] = 0
    summary_output['total_users'] = 0
    summary_output['total_uuids'] = 0
    return summary_output

  def _GenReportsAndSummary(self, summary_output, reports_raw):
    """Generate reports objects and calculate summary.

    Note that summary_output is modified.

    Args:
      summary_output: dict, to populate calculated summary data into
      reports_raw: list, of raw report data to feed
    Returns:
      list of objects, emulating the appearance of an Entity
      (with properties populated from reports_raw)
    """
    reports = []
    users = {}
    uuids = set()
    for report_raw in reports_raw:
      report = self.mox.CreateMockAnything()
      for k in report_raw.keys():
        setattr(report, k, report_raw[k])
      reports.append(report)

      summary_output[report_raw['event']] += 1
      summary_output['total_events'] += 1
      users.setdefault(report_raw['user'], 0)
      users[report_raw['user']] += 1
      uuids.add(report_raw['uuid'])
    summary_output['total_users'] = len(users.keys())
    summary_output['total_uuids'] = len(uuids)
    for user in users:
      summary_output.setdefault('total_users_%d_events' % users[user], 0)
      summary_output['total_users_%d_events' % users[user]] += 1
    return reports

  def testGenerateMsuUserSummaryWhenNoData(self):
    """Test _GenerateMsuUserSummary()."""
    rc = reports_cache.ReportsCache()

    reports = None
    cursor = None
    summary = None
    summary_output = self._GenBaseSummaryOutput(rc)

    lquery = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(reports_cache.models, 'ComputerMSULog')
    self.mox.StubOutWithMock(reports_cache.models, 'KeyValueCache')
    self.mox.StubOutWithMock(reports_cache.models, 'ReportsCache')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ObtainLock')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ReleaseLock')

    reports_cache.gae_util.ObtainLock('msu_user_summary_lock').AndReturn(True)
    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    reports_cache.models.KeyValueCache.MemcacheWrappedGet(
        'msu_user_summary_cursor', 'text_value').AndReturn(cursor)
    reports_cache.models.ReportsCache.GetMsuUserSummary(
        since=None, tmp=True).AndReturn((summary, None))
    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_output, since=None, tmp=True).AndReturn(None)

    lquery.fetch(rc.FETCH_LIMIT).AndReturn(reports)

    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_output, since=None).AndReturn(None)
    reports_cache.models.KeyValueCache.DeleteMemcacheWrap(
        'msu_user_summary_cursor', prop_name='text_value')
    reports_cache.models.ReportsCache.DeleteMsuUserSummary(
        since=None, tmp=True).AndReturn(None)
    reports_cache.gae_util.ReleaseLock('msu_user_summary_lock').AndReturn(True)

    self.mox.ReplayAll()
    rc._GenerateMsuUserSummary()
    self.mox.VerifyAll()

  def testGenerateMsuUserSummaryWhenData(self):
    """Test _GenerateMsuUserSummary()."""
    rc = reports_cache.ReportsCache()

    (dt_a1, dt_a2) = self._GenDatetimes(10)
    reports_raw = [
        {
            'uuid': 'u1', 'mtime': dt_a1,
            'event': 'launched', 'user': 'a'
        },
        {
            'uuid': 'u1', 'mtime': dt_a2,
            'event': 'exit_later_clicked', 'user': 'a'
        },
    ]

    reports = []
    cursor = None
    summary = None
    summary_output = self._GenBaseSummaryOutput(rc)
    summary_empty = summary_output.copy()
    reports = self._GenReportsAndSummary(summary_output, reports_raw)

    lquery = self.mox.CreateMockAnything()
    mock_summary = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(reports_cache.models, 'ComputerMSULog')
    self.mox.StubOutWithMock(reports_cache.models, 'KeyValueCache')
    self.mox.StubOutWithMock(reports_cache.models, 'ReportsCache')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ObtainLock')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ReleaseLock')

    reports_cache.gae_util.ObtainLock('msu_user_summary_lock').AndReturn(True)
    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    reports_cache.models.KeyValueCache.MemcacheWrappedGet(
        'msu_user_summary_cursor', 'text_value').AndReturn(cursor)
    reports_cache.models.ReportsCache.GetMsuUserSummary(
        since=None, tmp=True).AndReturn((summary, None))
    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_empty, since=None, tmp=True).AndReturn(None)

    lquery.fetch(rc.FETCH_LIMIT).AndReturn(reports)
    i = 0
    last_user = None
    for report in reports:
      if last_user != report.user:
        lquery.cursor().AndReturn('cursor%d' % i)
        i +=1
      last_user = report.user

    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    lquery.with_cursor('cursor%d' % (i-1)).AndReturn(None)
    lquery.fetch(rc.FETCH_LIMIT).AndReturn(None)

    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_output, since=None).AndReturn(None)
    reports_cache.models.KeyValueCache.DeleteMemcacheWrap(
        'msu_user_summary_cursor', prop_name='text_value')
    reports_cache.models.ReportsCache.DeleteMsuUserSummary(
        since=None, tmp=True).AndReturn(None)
    reports_cache.gae_util.ReleaseLock('msu_user_summary_lock').AndReturn(True)

    self.mox.ReplayAll()
    rc._GenerateMsuUserSummary()
    self.mox.VerifyAll()

  def testGenerateMsuUserSummaryWhenDataFetchBoundary(self):
    """Test _GenerateMsuUserSummary()."""
    rc = reports_cache.ReportsCache()

    (dt_a1, dt_a2) = self._GenDatetimes(10)
    reports_raw = [
        {
            'uuid': 'u1', 'mtime': dt_a1,
            'event': 'launched', 'user': 'a'
        },
        {
            'uuid': 'u1', 'mtime': dt_a2,
            'event': 'exit_later_clicked', 'user': 'a'
        },
        {
            'uuid': 'u2', 'mtime': dt_a1,
            'event': 'launched', 'user': 'b'
        },
        {
            'uuid': 'u2', 'mtime': dt_a2,
            'event': 'exit_later_clicked', 'user': 'b'
        },
    ]

    rc.FETCH_LIMIT = len(reports_raw)

    reports = []
    cursor = None
    summary = None
    summary_output = self._GenBaseSummaryOutput(rc)
    summary_empty = summary_output.copy()
    reports = self._GenReportsAndSummary(summary_output, reports_raw)

    # adjust for intentional buffer boundary dropping user 'b'
    for report_raw in reports_raw:
      if report_raw['user'] == 'b':
        summary_output[report_raw['event']] -= 1
        summary_output['total_events'] -= 1
    summary_output['total_users'] -= 1
    summary_output['total_uuids'] -= 1
    summary_output['total_users_2_events'] -= 1

    lquery = self.mox.CreateMockAnything()
    mock_summary = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(reports_cache.models, 'ComputerMSULog')
    self.mox.StubOutWithMock(reports_cache.models, 'KeyValueCache')
    self.mox.StubOutWithMock(reports_cache.models, 'ReportsCache')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ObtainLock')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ReleaseLock')

    reports_cache.gae_util.ObtainLock('msu_user_summary_lock').AndReturn(True)
    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    reports_cache.models.KeyValueCache.MemcacheWrappedGet(
        'msu_user_summary_cursor', 'text_value').AndReturn(cursor)
    reports_cache.models.ReportsCache.GetMsuUserSummary(
        since=None, tmp=True).AndReturn((summary, None))
    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_empty, since=None, tmp=True).AndReturn(None)

    lquery.fetch(rc.FETCH_LIMIT).AndReturn(reports)
    i = 0
    last_user = None
    for report in reports:
      if last_user != report.user:
        lquery.cursor().AndReturn('cursor%d' % i)
        i += 1
      last_user = report.user

    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    lquery.with_cursor('cursor%d' % (i-2)).AndReturn(None)  # prev cursor
    lquery.fetch(rc.FETCH_LIMIT).AndReturn(None)  # stop test

    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_output, since=None).AndReturn(None)
    reports_cache.models.KeyValueCache.DeleteMemcacheWrap(
        'msu_user_summary_cursor', prop_name='text_value')
    reports_cache.models.ReportsCache.DeleteMsuUserSummary(
        since=None, tmp=True).AndReturn(None)
    reports_cache.gae_util.ReleaseLock('msu_user_summary_lock').AndReturn(True)

    self.mox.ReplayAll()
    rc._GenerateMsuUserSummary()
    self.mox.VerifyAll()

  def testGenerateMsuUserSummaryWhenDataSinceOneDay(self):
    """Test _GenerateMsuUserSummary()."""
    rc = reports_cache.ReportsCache()
    since_days = 1

    (now, dt_a1, dt_a2) = self._GenDatetimes(10, 20)
    reports_raw = [
        {
            'uuid': 'u1', 'mtime': dt_a1,
            'event': 'launched', 'user': 'a'
        },
        {
            'uuid': 'u1', 'mtime': dt_a2,
            'event': 'exit_later_clicked', 'user': 'a'
        },
    ]

    reports = []
    cursor = None
    lock_name = 'msu_user_summary_lock_%dD' % since_days
    summary = None
    summary_output = self._GenBaseSummaryOutput(rc)
    summary_empty = summary_output.copy()
    reports = self._GenReportsAndSummary(summary_output, reports_raw)

    lquery = self.mox.CreateMockAnything()
    mock_summary = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(reports_cache.models, 'ComputerMSULog')
    self.mox.StubOutWithMock(reports_cache.models, 'KeyValueCache')
    self.mox.StubOutWithMock(reports_cache.models, 'ReportsCache')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ObtainLock')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ReleaseLock')

    reports_cache.gae_util.ObtainLock(lock_name).AndReturn(True)
    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    reports_cache.models.KeyValueCache.MemcacheWrappedGet(
        'msu_user_summary_cursor_%dD' % since_days, 'text_value').AndReturn(cursor)
    reports_cache.models.ReportsCache.GetMsuUserSummary(
        since='%dD' % since_days, tmp=True).AndReturn((summary, None))
    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_empty, since='%dD' % since_days, tmp=True).AndReturn(None)

    lquery.fetch(rc.FETCH_LIMIT).AndReturn(reports)
    i = 0
    last_user = None
    for report in reports:
      if last_user != report.user:
        lquery.cursor().AndReturn('cursor%d' % i)
        i +=1
      last_user = report.user

    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    lquery.with_cursor('cursor%d' % (i-1)).AndReturn(None)
    lquery.fetch(rc.FETCH_LIMIT).AndReturn(None)

    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_output, since='%dD' % since_days).AndReturn(None)
    reports_cache.models.KeyValueCache.DeleteMemcacheWrap(
        'msu_user_summary_cursor_%dD' % since_days, prop_name='text_value')
    reports_cache.models.ReportsCache.DeleteMsuUserSummary(
        since='%dD' % since_days, tmp=True).AndReturn(None)
    reports_cache.gae_util.ReleaseLock(lock_name).AndReturn(True)

    self.mox.ReplayAll()
    rc._GenerateMsuUserSummary(since_days=since_days, now=now)
    self.mox.VerifyAll()

  def testGenerateMsuUserSummaryWhenDataSinceOneDayTooOld(self):
    """Test _GenerateMsuUserSummary()."""
    rc = reports_cache.ReportsCache()
    since_days = 1

    (now, dt_a1, dt_a2) = self._GenDatetimes(86500, 86550)
    reports_raw = [
        {
            'uuid': 'u1', 'mtime': dt_a1,
            'event': 'launched', 'user': 'a'
        },
        {
            'uuid': 'u1', 'mtime': dt_a2,
            'event': 'exit_later_clicked', 'user': 'a'
        },
    ]

    reports = []
    cursor = None
    cursor_name = 'msu_user_summary_cursor_%dD' % since_days
    lock_name = 'msu_user_summary_lock_%dD' % since_days
    summary = None
    summary_output = self._GenBaseSummaryOutput(rc)
    summary_empty = summary_output.copy()
    reports = self._GenReportsAndSummary(summary_output, reports_raw)

    lquery = self.mox.CreateMockAnything()
    mock_summary = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(reports_cache.models, 'ComputerMSULog')
    self.mox.StubOutWithMock(reports_cache.models, 'KeyValueCache')
    self.mox.StubOutWithMock(reports_cache.models, 'ReportsCache')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ObtainLock')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ReleaseLock')

    reports_cache.gae_util.ObtainLock(lock_name).AndReturn(True)
    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    reports_cache.models.KeyValueCache.MemcacheWrappedGet(
        cursor_name, 'text_value').AndReturn(cursor)
    reports_cache.models.ReportsCache.GetMsuUserSummary(
        since='%dD' % since_days, tmp=True).AndReturn((summary, None))
    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_empty, since='%dD' % since_days, tmp=True).AndReturn(None)

    lquery.fetch(rc.FETCH_LIMIT).AndReturn(reports)
    i = 0
    last_user = None
    for report in reports:
      if last_user != report.user:
        lquery.cursor().AndReturn('cursor%d' % i)
        i +=1
      last_user = report.user

    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    lquery.with_cursor('cursor%d' % (i-1)).AndReturn(None)
    lquery.fetch(rc.FETCH_LIMIT).AndReturn(None)

    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_empty, since='%dD' % since_days).AndReturn(None)
    reports_cache.models.KeyValueCache.DeleteMemcacheWrap(
        cursor_name, prop_name='text_value')
    reports_cache.models.ReportsCache.DeleteMsuUserSummary(
        since='%dD' % since_days, tmp=True).AndReturn(None)
    reports_cache.gae_util.ReleaseLock(lock_name).AndReturn(True)

    self.mox.ReplayAll()
    rc._GenerateMsuUserSummary(since_days=since_days, now=now)
    self.mox.VerifyAll()

  def testGenerateMsuUserSummaryWhenLotsData(self):
    """Test _GenerateMsuUserSummary()."""
    rc = reports_cache.ReportsCache()

    reports_raw = []
    user_id = 0
    uuid_id = 0
    while len(reports_raw) < 501:
      uuid = 'uuid%d' % uuid_id
      user = 'user%d' % user_id
      (dt_a1, dt_a2) = self._GenDatetimes(10)
      reports_raw.extend([
          {
              'uuid': uuid, 'mtime': dt_a1,
              'event': 'launched', 'user': user
          },
          {
              'uuid': uuid, 'mtime': dt_a2,
              'event': 'exit_later_clicked', 'user': user
          },
      ])
      uuid_id += 1
      user_id += 1

    reports = []
    cursor = None
    summary = None
    summary_output = self._GenBaseSummaryOutput(rc)
    summary_empty = summary_output.copy()
    reports = self._GenReportsAndSummary(summary_output, reports_raw)

    lquery = self.mox.CreateMockAnything()
    mock_summary = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(reports_cache.models, 'ComputerMSULog')
    self.mox.StubOutWithMock(reports_cache.models, 'KeyValueCache')
    self.mox.StubOutWithMock(reports_cache.models, 'ReportsCache')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ObtainLock')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ReleaseLock')

    reports_cache.gae_util.ObtainLock('msu_user_summary_lock').AndReturn(True)
    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    reports_cache.models.KeyValueCache.MemcacheWrappedGet(
        'msu_user_summary_cursor', 'text_value').AndReturn(cursor)
    reports_cache.models.ReportsCache.GetMsuUserSummary(
        since=None, tmp=True).AndReturn((summary, None))
    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_empty, since=None, tmp=True).AndReturn(None)

    lquery.fetch(rc.FETCH_LIMIT).AndReturn(reports)
    i = 0
    last_user = None
    for report in reports:
      if last_user != report.user:
        lquery.cursor().AndReturn('cursor%d' % i)
        i +=1
      last_user = report.user

    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    lquery.with_cursor('cursor%d' % (i-1)).AndReturn(None)
    lquery.fetch(rc.FETCH_LIMIT).AndReturn(None)

    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_output, since=None).AndReturn(None)
    reports_cache.models.KeyValueCache.DeleteMemcacheWrap(
        'msu_user_summary_cursor', prop_name='text_value')
    reports_cache.models.ReportsCache.DeleteMsuUserSummary(
        since=None, tmp=True).AndReturn(None)
    reports_cache.gae_util.ReleaseLock('msu_user_summary_lock').AndReturn(True)

    self.mox.ReplayAll()
    rc._GenerateMsuUserSummary()
    self.mox.VerifyAll()

  def testGenerateMsuUserSummaryWhenLotsDataSlow(self):
    """Test _GenerateMsuUserSummary()."""
    rc = reports_cache.ReportsCache()

    reports_raw = []
    user_id = 0
    uuid_id = 0
    while len(reports_raw) < 501:
      uuid = 'uuid%d' % uuid_id
      user = 'user%d' % user_id
      (dt_a1, dt_a2) = self._GenDatetimes(10)
      reports_raw.extend([
          {
              'uuid': uuid, 'mtime': dt_a1,
              'event': 'launched', 'user': user
          },
          {
              'uuid': uuid, 'mtime': dt_a2,
              'event': 'exit_later_clicked', 'user': user
          },
      ])
      uuid_id += 1
      user_id += 1

    reports = []
    cursor = None
    summary = None
    summary_output = self._GenBaseSummaryOutput(rc)
    summary_empty = summary_output.copy()
    reports = self._GenReportsAndSummary(summary_output, reports_raw)

    lquery = self.mox.CreateMockAnything()
    mock_summary = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(reports_cache.models, 'ComputerMSULog')
    self.mox.StubOutWithMock(reports_cache.models, 'KeyValueCache')
    self.mox.StubOutWithMock(reports_cache.models, 'ReportsCache')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ObtainLock')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ReleaseLock')

    self.mox.StubOutWithMock(reports_cache.time, 'time')
    self.mox.StubOutWithMock(reports_cache, 'taskqueue')

    reports_cache.gae_util.ObtainLock('msu_user_summary_lock').AndReturn(True)
    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    reports_cache.models.KeyValueCache.MemcacheWrappedGet(
        'msu_user_summary_cursor', 'text_value').AndReturn(cursor)
    reports_cache.models.ReportsCache.GetMsuUserSummary(
        since=None, tmp=True).AndReturn((summary, None))
    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_empty, since=None, tmp=True).AndReturn(None)

    reports_cache.time.time().AndReturn(0)
    lquery.fetch(rc.FETCH_LIMIT).AndReturn(reports)
    i = 0
    last_user = None
    for report in reports:
      if last_user != report.user:
        lquery.cursor().AndReturn('cursor%d' % i)
        i +=1
      last_user = report.user

    last_user_cursor = 'cursor%d' % (i-1)
    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    lquery.with_cursor(last_user_cursor).AndReturn(None)

    reports_cache.time.time().AndReturn(reports_cache.RUNTIME_MAX_SECS + 1)
    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_output, since=None, tmp=True).AndReturn(None)
    reports_cache.models.KeyValueCache.MemcacheWrappedSet(
        'msu_user_summary_cursor',
        'text_value', last_user_cursor).AndReturn(None)
    reports_cache.taskqueue.add(
        url='/cron/reports_cache/msu_user_summary',
        method='GET',
        countdown=5).AndReturn(None)
    reports_cache.gae_util.ReleaseLock('msu_user_summary_lock').AndReturn(True)

    # second run
    reports_cache.gae_util.ObtainLock('msu_user_summary_lock').AndReturn(True)
    reports_cache.models.ComputerMSULog.all().AndReturn(lquery)
    reports_cache.models.KeyValueCache.MemcacheWrappedGet(
        'msu_user_summary_cursor', 'text_value').AndReturn(last_user_cursor)
    reports_cache.models.ReportsCache.GetMsuUserSummary(
        since=None, tmp=True).AndReturn([summary_output, 'mtime'])
    lquery.with_cursor(last_user_cursor)

    reports_cache.time.time().AndReturn(0)
    lquery.fetch(rc.FETCH_LIMIT).AndReturn(None)
    reports_cache.models.ReportsCache.SetMsuUserSummary(
        summary_output, since=None)
    reports_cache.models.KeyValueCache.DeleteMemcacheWrap(
        'msu_user_summary_cursor', prop_name='text_value')
    reports_cache.models.ReportsCache.DeleteMsuUserSummary(
        since=None, tmp=True).AndReturn(None)
    reports_cache.gae_util.ReleaseLock('msu_user_summary_lock').AndReturn(True)

    self.mox.ReplayAll()
    rc._GenerateMsuUserSummary()
    rc._GenerateMsuUserSummary()
    self.mox.VerifyAll()

  def testGenerateInstallCounts(self):
    """Test _GenerateInstallCounts()."""
    install_counts = {
        'foo': {
            'install_count': 2,
            'applesus': True,
            'duration_count': 1,
            'duration_total_seconds': 30,
            'duration_seconds_avg': 30},
        'bar': {'install_count': 2, 'install_fail_count': 1, 'applesus': False},
    }

    new_foo = self.mox.CreateMockAnything()
    new_foo.package = 'foo'
    new_foo.applesus = True
    new_foo.duration_seconds = 20
    new_bar = self.mox.CreateMockAnything()
    new_bar.package = 'bar'
    new_bar.applesus = False
    new_bar.duration_seconds = 10
    new_bar_success = self.mox.CreateMockAnything()
    new_bar_success.package = 'bar'
    new_bar_success.applesus = False
    new_bar_success.duration_seconds = 10
    new_bar_success2 = self.mox.CreateMockAnything()
    new_bar_success2.package = 'bar'
    new_bar_success2.applesus = False
    new_bar_success2.duration_seconds = 20
    new_zzz = self.mox.CreateMockAnything()
    new_zzz.package = 'zzz'
    new_zzz.applesus = False
    new_zzz.duration_seconds = None

    new_installs = [
        new_foo, new_bar, new_bar_success, new_zzz, new_bar_success2]

    new_install_counts = {
        'foo': {
            'install_count': 2,
            'install_fail_count': 1,
            'applesus': True,
            'duration_count': 1,
            'duration_total_seconds': 30,
            'duration_seconds_avg': 30,
         },
        'bar': {
            'install_count': 4,
            'install_fail_count': 2,
            'applesus': False,
            'duration_count': 2,
            'duration_total_seconds': 30,
            'duration_seconds_avg': 30 / 2,
         },
        'zzz': {
            'install_count': 1,
            'install_fail_count': 0,
            'applesus': False,
            'duration_count': 0,
            'duration_total_seconds': 0,
            'duration_seconds_avg': None,
        },
    }
    new_foo.IsSuccess().AndReturn(False)
    new_bar.IsSuccess().AndReturn(False)
    new_bar_success.IsSuccess().AndReturn(True)
    new_zzz.IsSuccess().AndReturn(True)
    new_bar_success2.IsSuccess().AndReturn(True)

    self.mox.StubOutWithMock(reports_cache.models, 'KeyValueCache')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ObtainLock')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'ReleaseLock')
    self.mox.StubOutWithMock(
        reports_cache.models.KeyValueCache, 'get_by_key_name')
    self.mox.StubOutWithMock(reports_cache.models.InstallLog, 'all')
    self.mox.StubOutWithMock(
        reports_cache.models.ReportsCache, 'GetInstallCounts')
    self.mox.StubOutWithMock(
        reports_cache.models.ReportsCache, 'SetInstallCounts')

    lock_name = 'pkgs_list_cron_lock'
    reports_cache.gae_util.ObtainLock(lock_name).AndReturn(True)

    reports_cache.models.ReportsCache.GetInstallCounts().AndReturn(
        (install_counts, None))
    mock_query = self.mox.CreateMockAnything()
    reports_cache.models.InstallLog.all().AndReturn(mock_query)
    mock_query.order('server_datetime').AndReturn(mock_query)
    mock_cursor_obj = self.mox.CreateMockAnything()
    mock_cursor_obj.text_value = 'foocursor'
    reports_cache.models.KeyValueCache.get_by_key_name(
        'pkgs_list_cursor').AndReturn(mock_cursor_obj)
    mock_query.with_cursor(mock_cursor_obj.text_value)
    mock_query.fetch(1000).AndReturn(new_installs)

    reports_cache.models.ReportsCache.SetInstallCounts(new_install_counts)
    mock_query.cursor().AndReturn(None)
    mock_cursor_obj.put().AndReturn(None)

    self.mox.StubOutWithMock(reports_cache.deferred, 'defer')
    reports_cache.deferred.defer(
        reports_cache._GenerateInstallCounts).AndReturn(None)
    reports_cache.gae_util.ReleaseLock(lock_name).AndReturn(True)

    self.mox.ReplayAll()
    reports_cache._GenerateInstallCounts()
    self.mox.VerifyAll()

  def testGenerateTrendingInstallsCache(self):
    """Tests _GenerateTrendingInstallsCache."""
    self.mox.StubOutWithMock(reports_cache.models.InstallLog, 'all')
    self.mox.StubOutWithMock(reports_cache.gae_util, 'QueryIterator')
    self.mox.StubOutWithMock(
        reports_cache.models.ReportsCache, 'SetTrendingInstalls')

    install_one = self.mox.CreateMockAnything()
    install_one.package = 'package_one'
    install_two = self.mox.CreateMockAnything()
    install_two.package = 'package_two'
    install_three = self.mox.CreateMockAnything()
    install_three.package = 'package_three'
    install_four = self.mox.CreateMockAnything()
    install_four.package = 'package_four'
    installs = [
        install_one, install_one, install_two, install_three, install_four]

    mock_query = self.mox.CreateMockAnything()
    reports_cache.models.InstallLog.all().AndReturn(mock_query)
    mock_query.filter(
        'mtime >', mox.IsA(reports_cache.datetime.datetime)).AndReturn(
            mock_query)
    reports_cache.gae_util.QueryIterator(mock_query).AndReturn(installs)

    install_one.IsSuccess().AndReturn(True)
    install_one.IsSuccess().AndReturn(True)
    install_two.IsSuccess().AndReturn(False)
    install_three.IsSuccess().AndReturn(False)
    install_four.IsSuccess().AndReturn(True)

    expected_trending = {
        'success': {
            'packages': [
                 (install_one.package, 2, 66.666666666666657),
                 (install_four.package, 1, 33.333333333333329),
             ],
             'total': 3,
        },
        'failure': {
            'packages': [
                 (install_two.package, 1, 50.0),
                 (install_three.package, 1, 50.0),
             ],
             'total': 2,
         },
    }
    reports_cache.models.ReportsCache.SetTrendingInstalls(
        1, mox.SameElementsAs(expected_trending))

    self.mox.ReplayAll()
    reports_cache._GenerateTrendingInstallsCache(1)
    self.mox.VerifyAll()


def main(unused_argv):
  basetest.main()


if __name__ == '__main__':
  app.run()