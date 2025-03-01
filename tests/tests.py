#!/usr/bin/env python

import ipaddress
import os
import select
import socket
import sys
import unittest

import pycares
from functools import partial
from tornado.tcpclient import Resolver

FIXTURES_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), 'fixtures'))


class DNSTest(unittest.TestCase):

    def setUp(self):
        self.channel = pycares.Channel(timeout=5.0, tries=1)

    def tearDown(self):
        self.channel = None

    def wait(self):
        while True:
            read_fds, write_fds = self.channel.getsock()
            if not read_fds and not write_fds:
                break
            timeout = self.channel.timeout()
            if timeout == 0.0:
                self.channel.process_fd(pycares.ARES_SOCKET_BAD, pycares.ARES_SOCKET_BAD)
                continue
            rlist, wlist, xlist = select.select(read_fds, write_fds, [], timeout)
            for fd in rlist:
                self.channel.process_fd(fd, pycares.ARES_SOCKET_BAD)
            for fd in wlist:
                self.channel.process_fd(pycares.ARES_SOCKET_BAD, fd)

    def assertNoError(self, errorno):
        if errorno == pycares.errno.ARES_ETIMEOUT and (os.environ.get('APPVEYOR') or os.environ.get('TRAVIS')):
            raise unittest.SkipTest('timeout')
        self.assertEqual(errorno, None)

    @unittest.skipIf(sys.platform == 'win32', 'skipped on Windows')
    def test_gethostbyaddr(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.gethostbyaddr('127.0.0.1', cb)
        self.wait()
        self.assertNoError(self.errorno)
        self.assertEqual(type(self.result), pycares.ares_host_result)

    @unittest.skipIf(sys.platform == 'win32', 'skipped on Windows')
    @unittest.skipIf(os.environ.get('TRAVIS') is not None, 'skipped on Travis')
    def test_gethostbyaddr6(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.gethostbyaddr('::1', cb)
        self.wait()
        self.assertNoError(self.errorno)
        self.assertEqual(type(self.result), pycares.ares_host_result)

    @unittest.skipIf(sys.platform == 'win32', 'skipped on Windows')
    def test_gethostbyname(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.gethostbyname('localhost', socket.AF_INET, cb)
        self.wait()
        self.assertNoError(self.errorno)
        self.assertEqual(type(self.result), pycares.ares_host_result)

    @unittest.skipIf(sys.platform == 'win32', 'skipped on Windows')
    def test_gethostbyname_small_timeout(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel = pycares.Channel(timeout=0.5, tries=1)
        self.channel.gethostbyname('localhost', socket.AF_INET, cb)
        self.wait()
        self.assertNoError(self.errorno)
        self.assertEqual(type(self.result), pycares.ares_host_result)

    @unittest.skipIf(sys.platform == 'win32', 'skipped on Windows')
    def test_getnameinfo(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.getnameinfo(('127.0.0.1', 80), pycares.ARES_NI_LOOKUPHOST|pycares.ARES_NI_LOOKUPSERVICE, cb)
        self.wait()
        self.assertNoError(self.errorno)
        self.assertEqual(type(self.result), pycares.ares_nameinfo_result)
        self.assertIn(self.result.node, ('localhost.localdomain', 'localhost'))
        self.assertEqual(self.result.service, 'http')

    def test_query_a(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('google.com', pycares.QUERY_TYPE_A, cb)
        self.wait()
        self.assertNoError(self.errorno)
        for r in self.result:
            self.assertEqual(type(r), pycares.ares_query_a_result)
            self.assertNotEqual(r.host, None)
            self.assertTrue(r.ttl >= 0)

    def test_query_a_bad(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('hgf8g2od29hdohid.com', pycares.QUERY_TYPE_A, cb)
        self.wait()
        self.assertEqual(self.result, None)
        self.assertEqual(self.errorno, pycares.errno.ARES_ENOTFOUND)

    def test_query_a_rotate(self):
        self.result, self.errorno = None, None
        self.errorno_count, self.count = 0, 0
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
            if errorno:
                self.errorno_count += 1
            self.count += 1
        self.channel = pycares.Channel(timeout=1.0, tries=1, rotate=True)
        self.channel.query('google.com', pycares.QUERY_TYPE_A, cb)
        self.channel.query('google.com', pycares.QUERY_TYPE_A, cb)
        self.channel.query('google.com', pycares.QUERY_TYPE_A, cb)
        self.wait()
        self.assertEqual(self.count, 3)
        self.assertEqual(self.errorno_count, 0)

    def test_query_aaaa(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('ipv6.google.com', pycares.QUERY_TYPE_AAAA, cb)
        self.wait()
        self.assertNoError(self.errorno)
        for r in self.result:
            self.assertEqual(type(r), pycares.ares_query_aaaa_result)
            self.assertNotEqual(r.host, None)
            self.assertTrue(r.ttl >= 0)

    def test_query_cname(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('www.amazon.com', pycares.QUERY_TYPE_CNAME, cb)
        self.wait()
        self.assertNoError(self.errorno)
        self.assertEqual(type(self.result), pycares.ares_query_cname_result)

    def test_query_mx(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('google.com', pycares.QUERY_TYPE_MX, cb)
        self.wait()
        self.assertNoError(self.errorno)
        for r in self.result:
            self.assertEqual(type(r), pycares.ares_query_mx_result)
            self.assertTrue(r.ttl >= 0)

    def test_query_ns(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('google.com', pycares.QUERY_TYPE_NS, cb)
        self.wait()
        self.assertNoError(self.errorno)
        for r in self.result:
            self.assertEqual(type(r), pycares.ares_query_ns_result)

    def test_query_txt(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('google.com', pycares.QUERY_TYPE_TXT, cb)
        self.wait()
        self.assertNoError(self.errorno)
        for r in self.result:
            self.assertEqual(type(r), pycares.ares_query_txt_result)
            self.assertTrue(r.ttl >= 0)

    def test_query_txt_chunked(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('jobscoutdaily.com', pycares.QUERY_TYPE_TXT, cb)
        self.wait()
        self.assertNoError(self.errorno)
        # If the chunks are aggregated, only one TXT record should be visible. Three would show if they are not properly merged.
        # jobscoutdaily.com.    21600   IN  TXT "v=spf1 " "include:emailcampaigns.net include:spf.dynect.net  include:ccsend.com include:_spf.elasticemail.com ip4:67.200.116.86 ip4:67.200.116.90 ip4:67.200.116.97 ip4:67.200.116.111 ip4:74.199.198.2 " " ~all"
        self.assertEqual(len(self.result), 1)
        self.assertEqual(self.result[0].text, 'v=spf1 include:emailcampaigns.net include:spf.dynect.net  include:ccsend.com include:_spf.elasticemail.com ip4:67.200.116.86 ip4:67.200.116.90 ip4:67.200.116.97 ip4:67.200.116.111 ip4:74.199.198.2  ~all')

    def test_query_txt_multiple_chunked(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('s-pulse.co.jp', pycares.QUERY_TYPE_TXT, cb)
        self.wait()
        self.assertNoError(self.errorno)
        # s-pulse.co.jp.      3600    IN  TXT "MS=ms18955624"
        # s-pulse.co.jp.      3600    IN  TXT "v=spf1 " "include:spf-bma.mpme.jp ip4:202.248.11.9 ip4:202.248.11.10 " "ip4:218.223.68.132 ip4:218.223.68.77 ip4:210.254.139.121 " "ip4:211.128.73.121 ip4:210.254.139.122 ip4:211.128.73.122 " "ip4:210.254.139.123 ip4:211.128.73.123 ip4:210.254.139.124 " "ip4:211.128.73.124 ip4:210.254.139.13 ip4:211.128.73.13 " "ip4:52.68.199.198 include:spf.betrend.com " "include:spf.protection.outlook.com " "~all"
        self.assertEqual(len(self.result), 2)

    def test_query_txt_bytes1(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('google.com', pycares.QUERY_TYPE_TXT, cb)
        self.wait()
        self.assertNoError(self.errorno)
        for r in self.result:
            self.assertEqual(type(r), pycares.ares_query_txt_result)
            self.assertIsInstance(r.text, str)  # it's ASCII
            self.assertTrue(r.ttl >= 0)

    def test_query_txt_bytes2(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('wide.com.es', pycares.QUERY_TYPE_TXT, cb)
        self.wait()
        self.assertNoError(self.errorno)
        for r in self.result:
            self.assertEqual(type(r), pycares.ares_query_txt_result)
            self.assertIsInstance(r.text, bytes)
            self.assertTrue(r.ttl >= 0)

    def test_query_txt_multiple_chunked_with_non_ascii_content(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('txt-non-ascii.dns-test.hmnid.ru', pycares.QUERY_TYPE_TXT, cb)
        self.wait()
        self.assertNoError(self.errorno)
        # txt-non-ascii.dns-test.hmnid.ru.        IN      TXT     "ascii string" "some\208misc\208stuff"

        self.assertEqual(len(self.result), 1)
        r = self.result[0]
        self.assertEqual(type(r), pycares.ares_query_txt_result)
        self.assertIsInstance(r.text, bytes)
        self.assertTrue(r.ttl >= 0)

    def test_query_soa(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('google.com', pycares.QUERY_TYPE_SOA, cb)
        self.wait()
        self.assertNoError(self.errorno)
        self.assertEqual(type(self.result), pycares.ares_query_soa_result)
        self.assertTrue(self.result.ttl >= 0)

    def test_query_srv(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('_xmpp-server._tcp.google.com', pycares.QUERY_TYPE_SRV, cb)
        self.wait()
        self.assertNoError(self.errorno)
        for r in self.result:
            self.assertEqual(type(r), pycares.ares_query_srv_result)
            self.assertTrue(r.ttl >= 0)

    def test_query_naptr(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('sip2sip.info', pycares.QUERY_TYPE_NAPTR, cb)
        self.wait()
        self.assertNoError(self.errorno)
        for r in self.result:
            self.assertEqual(type(r), pycares.ares_query_naptr_result)
            self.assertTrue(r.ttl >= 0)

    def test_query_ptr(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        ip = '8.8.8.8'
        self.channel.query(ipaddress.ip_address(ip).reverse_pointer, pycares.QUERY_TYPE_PTR, cb)
        self.wait()
        self.assertNoError(self.errorno)
        self.assertEqual(type(self.result), pycares.ares_query_ptr_result)
        self.assertIsInstance(self.result.ttl, int)
        self.assertGreaterEqual(self.result.ttl, 0)
        self.assertLessEqual(self.result.ttl, 2**31-1)
        self.assertEqual(type(self.result.aliases), list)

    def test_query_ptr_ipv6(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        ip = '2001:4860:4860::8888'
        self.channel.query(ipaddress.ip_address(ip).reverse_pointer, pycares.QUERY_TYPE_PTR, cb)
        self.wait()
        self.assertNoError(self.errorno)
        self.assertEqual(type(self.result), pycares.ares_query_ptr_result)
        self.assertIsInstance(self.result.ttl, int)
        self.assertGreaterEqual(self.result.ttl, 0)
        self.assertLessEqual(self.result.ttl, 2**31-1)
        self.assertEqual(type(self.result.aliases), list)

    def test_query_any(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('google.com', pycares.QUERY_TYPE_ANY, cb)
        self.wait()
        self.assertNoError(self.errorno)
        self.assertTrue(len(self.result) > 1)

    def test_query_cancelled(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('google.com', pycares.QUERY_TYPE_NS, cb)
        self.channel.cancel()
        self.wait()
        self.assertEqual(self.result, None)
        self.assertEqual(self.errorno, pycares.errno.ARES_ECANCELLED)

    def test_query_bad_type(self):
        self.assertRaises(ValueError, self.channel.query, 'google.com', 667, lambda *x: None)
        self.wait()

    def test_query_timeout(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.servers = ['1.2.3.4']
        self.channel.query('google.com', pycares.QUERY_TYPE_A, cb)
        self.wait()
        self.assertEqual(self.result, None)
        self.assertEqual(self.errorno, pycares.errno.ARES_ETIMEOUT)

    def test_channel_nameservers(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel = pycares.Channel(timeout=5.0, tries=1, servers=['8.8.8.8'])
        self.channel.query('google.com', pycares.QUERY_TYPE_A, cb)
        self.wait()
        self.assertNoError(self.errorno)

    def test_channel_nameservers2(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.servers = ['8.8.8.8']
        self.channel.query('google.com', pycares.QUERY_TYPE_A, cb)
        self.wait()
        self.assertNoError(self.errorno)

    def test_channel_nameservers3(self):
        servers = ['8.8.8.8', '8.8.4.4']
        self.channel.servers = servers
        servers2 = self.channel.servers
        self.assertEqual(servers, servers2)

    def test_channel_local_ip(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel = pycares.Channel(timeout=5.0, tries=1, servers=['8.8.8.8'], local_ip='127.0.0.1')
        self.channel.query('google.com', pycares.QUERY_TYPE_A, cb)
        self.wait()
        self.assertEqual(self.result, None)
        self.assertEqual(self.errorno, pycares.errno.ARES_ECONNREFUSED)

    def test_channel_local_ip2(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.servers = ['8.8.8.8']
        self.channel.set_local_ip('127.0.0.1')
        self.channel.query('google.com', pycares.QUERY_TYPE_A, cb)
        self.wait()
        self.assertEqual(self.result, None)
        self.assertEqual(self.errorno, pycares.errno.ARES_ECONNREFUSED)
        self.assertRaises(ValueError, self.channel.set_local_ip, 'an invalid ip')

    def test_channel_local_dev(self):
        '''
        Comments in c-ares say this only works for root, and ares ignores
        errors. So we won't test it.
        '''
        pass

    def test_channel_timeout(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel = pycares.Channel(timeout=0.5, tries=1)
        self.channel.gethostbyname('google.com', socket.AF_INET, cb)
        timeout = self.channel.timeout()
        self.assertTrue(timeout > 0.0)
        self.channel.cancel()
        self.wait()
        self.assertEqual(self.result, None)
        self.assertEqual(self.errorno, pycares.errno.ARES_ECANCELLED)

    def test_import_errno(self):
        from pycares.errno import ARES_SUCCESS
        self.assertTrue(True)

    def test_result_not_ascii(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('xn--cardeosapeluqueros-r0b.com', pycares.QUERY_TYPE_MX, cb)
        self.wait()
        self.assertNoError(self.errorno)
        for r in self.result:
            self.assertEqual(type(r), pycares.ares_query_mx_result)
            self.assertIsInstance(r.host, bytes)  # it's not ASCII
            self.assertTrue(r.ttl >= 0)

    def test_result_not_ascii2(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.query('ayesas.com', pycares.QUERY_TYPE_SOA, cb)
        self.wait()
        self.assertNoError(self.errorno)
        self.assertEqual(type(self.result), pycares.ares_query_soa_result)
        self.assertIsInstance(self.result.hostmaster, bytes)  # it's not ASCII
        self.assertTrue(self.result.ttl >= 0)

    def test_idna_encoding(self):
        host = 'españa.icom.museum'
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        # try encoding it as utf-8
        self.channel.gethostbyname(host.encode(), socket.AF_INET, cb)
        self.wait()
        self.assertEqual(self.errorno, pycares.errno.ARES_ENOTFOUND)
        self.assertEqual(self.result, None)
        # use it as is (it's IDNA encoded internally)
        self.channel.gethostbyname(host, socket.AF_INET, cb)
        self.wait()
        self.assertNoError(self.errorno)
        self.assertEqual(type(self.result), pycares.ares_host_result)

    def test_idna_encoding_query_a(self):
        host = 'españa.icom.museum'
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        # try encoding it as utf-8
        self.channel.query(host.encode(), pycares.QUERY_TYPE_A, cb)
        self.wait()
        self.assertEqual(self.errorno, pycares.errno.ARES_ENOTFOUND)
        self.assertEqual(self.result, None)
        # use it as is (it's IDNA encoded internally)
        self.channel.query(host, pycares.QUERY_TYPE_A, cb)
        self.wait()
        self.assertNoError(self.errorno)
        for r in self.result:
            self.assertEqual(type(r), pycares.ares_query_a_result)
            self.assertNotEqual(r.host, None)

    def test_idna2008_encoding(self):
        try:
            import idna
        except ImportError:
            raise unittest.SkipTest('idna module not installed')
        host = 'straße.de'
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel.gethostbyname(host, socket.AF_INET, cb)
        self.wait()
        self.assertNoError(self.errorno)
        self.assertEqual(type(self.result), pycares.ares_host_result)
        self.assertTrue('81.169.145.78' in self.result.addresses)

    @unittest.skipIf(sys.platform == 'win32', 'skipped on Windows')
    def test_custom_resolvconf(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel = pycares.Channel(tries=1, timeout=2.0, resolvconf_path=os.path.join(FIXTURES_PATH, 'badresolv.conf'))
        self.channel.query('google.com', pycares.QUERY_TYPE_A, cb)
        self.wait()
        self.assertEqual(self.result, None)
        self.assertEqual(self.errorno, pycares.errno.ARES_ETIMEOUT)

    def test_errorcode_dict(self):
        for err in ('ARES_SUCCESS', 'ARES_ENODATA', 'ARES_ECANCELLED'):
            val = getattr(pycares.errno, err)
            self.assertEqual(pycares.errno.errorcode[val], err)

    def test_search(self):
        self.result, self.errorno = None, None
        def cb(result, errorno):
            self.result, self.errorno = result, errorno
        self.channel = pycares.Channel(timeout=5.0, tries=1, domains=['google.com'])
        self.channel.search('cloud', pycares.QUERY_TYPE_A, cb)
        self.wait()
        self.assertNoError(self.errorno)
        for r in self.result:
            self.assertEqual(type(r), pycares.ares_query_a_result)
            self.assertNotEqual(r.host, None)

    def test_lookup(self):
        Resolver.configure("tornado.platform.caresresolver.CaresResolver")
        resolver = Resolver()
        resolver.channel = pycares.Channel(
            lookups="b",
            sock_state_cb=resolver._sock_state_cb,
            timeout=5,
            tries=1,
            socket_receive_buffer_size=4096,
            servers=["8.8.8.8", "8.8.4.4"],
            tcp_port=53,
            udp_port=53,
            rotate=True,
        )
        loop = resolver.io_loop
        sys.stdout.write("\n")
        for domain in [
            "google.com",
            "microsoft.com",
            "apple.com",
            "amazon.com",
            "baidu.com",
            "alipay.com",
            "tencent.com",
        ]:
            loop.run_sync(partial(resolver.resolve, domain, None))
            r = loop.run_sync(partial(resolver.resolve, domain, None))
            assert isinstance(r, list) and len(r) > 0, "Error Resolving: %s" % domain
            sys.stdout.write(
                "Resolving: %s:%s\n" % (domain, [i[1][0] for i in r if i[1]])
            )
            sys.stdout.flush()

if __name__ == '__main__':
    unittest.main(verbosity=2)

