#
# Copyright (C) 2018  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Authors: Jiri Konecny <jkonecny@redhat.com>
#


import unittest
import pytest
import enum

from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.payload.source import SourceFactory, PayloadSourceTypeUnrecognized
from pyanaconda.payload.source.sources import *  # pylint: disable=wildcard-import
from tests.unit_tests.pyanaconda_tests import patch_dbus_get_proxy_with_cache


class TestValues(enum.Enum):

    def __new__(cls, value, source):
        member = object.__new__(cls)
        member._value_ = value
        member.source = source
        return member

    http = "http://server.example.com/test", HTTPSource
    https = "https://server.example.com/test", HTTPSSource
    ftp = "ftp://server.example.com/test", FTPSource
    nfs_ks = "nfs://server.nfs.com:/path/on/server", NFSSource
    nfs_main_repo = "nfs:soft,async:server.example.com:/path/to/install_tree", NFSSource
    nfs_main_repo2 = "nfs:server.example.com:/path/to/install_tree", NFSSource
    file = "file:///root/extremely_secret_file.txt", FileSource

    cdrom = "cdrom", CDRomSource
    cdrom_test = "cdrom:/dev/cdrom", CDRomSource
    harddrive = "hd:/dev/sda2:/path/to/iso.iso", HDDSource
    harddrive_label = "hd:LABEL=TEST:/path/to/iso.iso", HDDSource
    harddrive_uuid = "hd:UUID=8176c7bf-04ff-403a-a832-9557f94e61db:/path/to/iso.iso", HDDSource
    hmc = "hmc", HMCSource

    broken_http = "htttp://broken.server.com/test", None
    broken_https = "htttps://broken.server.com/test", None
    broken_ftp = "ftp2://broken.server.com/test", None


class TestSourceFactoryTests(unittest.TestCase):

    def test_parse_repo_cmdline(self):
        for val in TestValues:
            klass = val.source

            if klass is None:
                with pytest.raises(PayloadSourceTypeUnrecognized):
                    SourceFactory.parse_repo_cmdline_string(val.value)
                continue

            source = SourceFactory.parse_repo_cmdline_string(val.value)
            assert isinstance(source, klass), \
                "Instance of source {} expected - get {}".format(klass, source)

    def _check_is_methods(self, check_method, valid_array, type_str):
        for val in TestValues:

            ret = check_method(val.value)
            if val in valid_array:
                assert ret, "Value {} is not marked as {}".format(val.value, type_str)
            else:
                assert not ret, "Value {} should non be marked as {}".format(val.value, type_str)

    def test_is_cdrom(self):
        self._check_is_methods(SourceFactory.is_cdrom,
                               [TestValues.cdrom, TestValues.cdrom_test],
                               "cdrom")

    def test_is_harddrive(self):
        self._check_is_methods(SourceFactory.is_harddrive,
                               [TestValues.harddrive, TestValues.harddrive_uuid,
                                TestValues.harddrive_label],
                               "harddrive")

    def test_is_nfs(self):
        self._check_is_methods(SourceFactory.is_nfs,
                               [TestValues.nfs_ks, TestValues.nfs_main_repo,
                                TestValues.nfs_main_repo2],
                               "nfs")

    def test_is_http(self):
        self._check_is_methods(SourceFactory.is_http,
                               [TestValues.http],
                               "http")

    def test_is_https(self):
        self._check_is_methods(SourceFactory.is_https,
                               [TestValues.https],
                               "https")

    def test_is_ftp(self):
        self._check_is_methods(SourceFactory.is_ftp,
                               [TestValues.ftp],
                               "ftp")

    def test_is_file(self):
        self._check_is_methods(SourceFactory.is_file,
                               [TestValues.file],
                               "file")

    def test_is_hmc(self):
        self._check_is_methods(SourceFactory.is_hmc,
                               [TestValues.hmc],
                               "hmc")

    def _check_create_proxy(self, source_type, test_value):
        payloads_proxy = PAYLOADS.get_proxy()
        payloads_proxy.CreateSource.return_value = "my/source/1"

        source = SourceFactory.parse_repo_cmdline_string(test_value)
        source_proxy = source.create_proxy()

        payloads_proxy.CreateSource.assert_called_once_with(source_type)
        assert source_proxy == PAYLOADS.get_proxy("my/source/1")

        return source_proxy

    @patch_dbus_get_proxy_with_cache
    def test_create_proxy_cdrom(self, proxy_getter):
        self._check_create_proxy(SOURCE_TYPE_CDROM, "cdrom")

    @patch_dbus_get_proxy_with_cache
    def test_create_proxy_harddrive(self, proxy_getter):
        proxy = self._check_create_proxy(SOURCE_TYPE_HDD, "hd:/dev/sda2:/path/to/iso.iso")
        assert proxy.Partition == "/dev/sda2"
        assert proxy.Directory == "/path/to/iso.iso"

    @patch_dbus_get_proxy_with_cache
    def test_create_proxy_nfs(self, proxy_getter):
        proxy = self._check_create_proxy(SOURCE_TYPE_NFS, "nfs:server.com:/path/to/install_tree")
        assert proxy.URL == "nfs:server.com:/path/to/install_tree"

    @patch_dbus_get_proxy_with_cache
    def test_create_proxy_url(self, proxy_getter):
        proxy = self._check_create_proxy(SOURCE_TYPE_URL, "http://server.example.com/test")

        repo_configuration = RepoConfigurationData()
        repo_configuration.type = URL_TYPE_BASEURL
        repo_configuration.url = "http://server.example.com/test"

        assert proxy.RepoConfiguration ==  \
            RepoConfigurationData.to_structure(repo_configuration)

    @patch_dbus_get_proxy_with_cache
    def test_create_proxy_file(self, proxy_getter):
        proxy = self._check_create_proxy(SOURCE_TYPE_URL, "file:///root/extremely_secret_file.txt")

        repo_configuration = RepoConfigurationData()
        repo_configuration.type = URL_TYPE_BASEURL
        repo_configuration.url = "file:///root/extremely_secret_file.txt"

        assert proxy.RepoConfiguration == \
            RepoConfigurationData.to_structure(repo_configuration)

    @patch_dbus_get_proxy_with_cache
    def test_create_proxy_hmc(self, proxy_getter):
        self._check_create_proxy(SOURCE_TYPE_HMC, "hmc")
